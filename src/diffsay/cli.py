#!/usr/bin/env python3
"""diffsay: explain what changed between two UI screenshots, in words an agent can act on.

Vision models miss most single-property UI changes (DiffSpot, 2026: best frontier model
recall 40.7%, line-height 4%). diffsay doesn't look; it measures. It localises changed
regions, then tests specific hypotheses against the pixels: a rigid move, items spreading
apart, a colour swap, an opacity blend, a gradient flip, rounded corners, and text-line
metrics (glyph height, line pitch, line width, ink weight). Every claim it prints comes
with the measurement behind it.

    diffsay.py before.png after.png            # human/agent readable report
    diffsay.py before.png after.png --json     # structured output
    diffsay.py before.png after.png --crops out/login   # + zoomed before/after strip per change
    diffsay.py scan app/build --crops out/     # every failed Paparazzi/Roborazzi screenshot test
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field

import numpy as np
from PIL import Image
from scipy import ndimage

NOISE = 12          # per-channel delta treated as rendering noise
INK = 40            # distance from background that counts as foreground ink
GROUP_GAP = 40      # changed pixels closer than this belong to one region


@dataclass
class Change:
    kind: str
    bbox: tuple[int, int, int, int]  # x, y, w, h
    summary: str
    evidence: dict = field(default_factory=dict)
    direction: str = ""


def load(path: str) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)


def hex_color(rgb) -> str:
    r, g, b = (int(round(v)) for v in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


# --------------------------------------------------------------------------- regions


def change_mask(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.abs(a - b).max(axis=2) > NOISE


def regions(mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Bounding boxes (x0, y0, x1, y1) of changed areas, nearby specks merged."""
    if not mask.any():
        return []
    grown = ndimage.binary_dilation(mask, iterations=GROUP_GAP // 2)
    labels, _ = ndimage.label(grown)
    boxes = []
    for sl in ndimage.find_objects(labels):
        ys, xs = sl
        sub = mask[sl]
        if sub.sum() < 3:
            continue
        rows = np.where(sub.any(axis=1))[0]
        cols = np.where(sub.any(axis=0))[0]
        boxes.append((xs.start + cols[0], ys.start + rows[0], xs.start + cols[-1] + 1, ys.start + rows[-1] + 1))
    return sorted(boxes, key=lambda bx: -(bx[2] - bx[0]) * (bx[3] - bx[1]))


def background(crop: np.ndarray) -> np.ndarray:
    """Most common colour on the crop's border ring."""
    ring = np.concatenate([crop[0], crop[-1], crop[:, 0], crop[:, -1]])
    quant = (ring // 4).astype(np.int32)
    keys = quant[:, 0] * 65536 + quant[:, 1] * 256 + quant[:, 2]
    values, counts = np.unique(keys, return_counts=True)
    best = values[counts.argmax()]
    return ring[keys == best].mean(axis=0)


def ink(crop: np.ndarray, bg: np.ndarray) -> np.ndarray:
    return np.abs(crop - bg).max(axis=2) > INK


# --------------------------------------------------------------------------- hypotheses


def best_shift(a: np.ndarray, b: np.ndarray, limit: int) -> tuple[int, int, float]:
    """Integer shift (dx, dy) that best maps a onto b, and the residual it leaves (0 = perfect)."""
    ga = a.mean(axis=2)
    gb = b.mean(axis=2)
    base = np.abs(ga - gb).mean() + 1e-9
    fa = np.fft.fft2(ga - ga.mean())
    fb = np.fft.fft2(gb - gb.mean())
    r = fb * np.conj(fa)
    corr = np.fft.ifft2(r / (np.abs(r) + 1e-9)).real
    h, w = ga.shape
    candidates = np.argsort(corr.ravel())[::-1][:8]
    best = (0, 0, 1.0)
    for c in candidates:
        dy, dx = divmod(int(c), w)
        dy = dy - h if dy > h // 2 else dy
        dx = dx - w if dx > w // 2 else dx
        if (dx, dy) == (0, 0) or abs(dx) > limit or abs(dy) > limit:
            continue
        residual = shifted_residual(ga, gb, dx, dy) / base
        if residual < best[2]:
            best = (dx, dy, residual)
    return best


def shifted_residual(ga: np.ndarray, gb: np.ndarray, dx: int, dy: int) -> float:
    h, w = ga.shape
    ya, yb = (0, dy) if dy >= 0 else (-dy, 0)
    xa, xb = (0, dx) if dx >= 0 else (-dx, 0)
    hh, ww = h - abs(dy), w - abs(dx)
    if hh <= 0 or ww <= 0:
        return float("inf")
    return float(np.abs(ga[ya:ya + hh, xa:xa + ww] - gb[yb:yb + hh, xb:xb + ww]).mean())


@dataclass
class TextMetrics:
    lines: list[tuple[int, int]]   # (top, bottom) per text line
    widths: list[int]
    ink: int
    left: int
    right: int

    @property
    def glyph_height(self) -> float:
        return float(np.median([b - t for t, b in self.lines])) if self.lines else 0.0

    @property
    def pitch(self) -> float:
        tops = [t for t, _ in self.lines]
        return float(np.median(np.diff(tops))) if len(tops) > 1 else 0.0


def text_metrics(mask: np.ndarray) -> TextMetrics:
    rows = mask.any(axis=1)
    lines, start = [], None
    for y, on in enumerate(list(rows) + [False]):
        if on and start is None:
            start = y
        elif not on and start is not None:
            if y - start >= 3:
                lines.append((start, y))
            start = None
    widths = []
    for t, b in lines:
        cols = np.where(mask[t:b].any(axis=0))[0]
        widths.append(int(cols[-1] - cols[0] + 1) if cols.size else 0)
    cols = np.where(mask.any(axis=0))[0]
    return TextMetrics(lines, widths, int(mask.sum()), int(cols[0]) if cols.size else 0, int(cols[-1]) if cols.size else 0)


def items(mask: np.ndarray, gap: int = 10) -> list[tuple[int, int, int, int]]:
    """Ink grouped into items (words, icons, boxes) as (x0, y0, x1, y1)."""
    grown = ndimage.binary_dilation(mask, structure=np.ones((3, gap)))
    labels, _ = ndimage.label(grown)
    out = []
    for ys, xs in ndimage.find_objects(labels):
        sub = mask[ys, xs]
        if sub.sum() < 4:
            continue
        r = np.where(sub.any(axis=1))[0]
        c = np.where(sub.any(axis=0))[0]
        out.append((xs.start + c[0], ys.start + r[0], xs.start + c[-1] + 1, ys.start + r[-1] + 1))
    return out


# --------------------------------------------------------------------------- explain one region


def explain(a: np.ndarray, b: np.ndarray, box: tuple[int, int, int, int]) -> Change:
    h, w = a.shape[:2]
    x0, y0, x1, y1 = box
    m = 32
    cx0, cy0, cx1, cy1 = max(0, x0 - m), max(0, y0 - m), min(w, x1 + m), min(h, y1 + m)
    ca, cb = a[cy0:cy1, cx0:cx1], b[cy0:cy1, cx0:cx1]
    changed = change_mask(ca, cb)
    bbox = (int(x0), int(y0), int(x1 - x0), int(y1 - y0))
    bg = background(ca)

    def change(kind, summary, direction="", **evidence):
        return Change(kind, bbox, summary, evidence, direction)

    opacity = _opacity(ca, cb, changed, bg)
    if opacity:
        return change("opacity", *opacity)

    gradient = _gradient(ca, cb, changed)
    if gradient:
        return change("gradient", gradient[0], gradient[1], **gradient[2])

    if recolor_score(ca, cb, changed) < 0.25 and _static_geometry(ca, cb, changed, bg):
        return _colour_change(ca, cb, changed, bg, change)

    shift = explained_shift(ca, cb, changed, bg)
    if shift:
        dx, dy, explained = shift
        if dy == 0 and abs(dx) > 26:
            return change("alignment", f"content shifted {abs(dx)}px {'right' if dx > 0 else 'left'} (alignment change)",
                          "right" if dx > 0 else "left", dx=dx, dy=dy, explained=explained)
        parts = ([f"{abs(dx)}px {'right' if dx > 0 else 'left'}"] if dx else []) + ([f"{abs(dy)}px {'down' if dy > 0 else 'up'}"] if dy else [])
        return change("moved", "element moved " + " and ".join(parts), " ".join(parts), dx=dx, dy=dy, explained=explained)

    corner = _corner_change(ca, cb, changed, bg)
    if corner:
        return change("rounded", f"corners became {corner}", corner)

    ia, ib = ink(ca, bg), ink(cb, bg)
    flow = item_flow(ca, cb, ia, ib)
    if flow:
        verdict = _layout(flow, change)
        if verdict:
            return verdict
    return _text_change(ia, ib, changed, change, flow)


def explained_shift(ca, cb, changed, bg, limit: int = 48):
    """A single (dx, dy) under which almost every changed pixel is the same content, moved."""
    ga, gb = ca.mean(axis=2), cb.mean(axis=2)
    fa = np.fft.fft2(ga - ga.mean())
    fb = np.fft.fft2(gb - gb.mean())
    r = fb * np.conj(fa)
    corr = np.fft.ifft2(r / (np.abs(r) + 1e-9)).real
    h, w = ga.shape
    ys, xs = np.where(changed)
    best = None
    for c in np.argsort(corr.ravel())[::-1][:16]:
        dy, dx = divmod(int(c), w)
        dy = dy - h if dy > h // 2 else dy
        dx = dx - w if dx > w // 2 else dx
        if (dx, dy) == (0, 0) or abs(dx) > limit or abs(dy) > limit:
            continue
        frac = _explained(ca, cb, ys, xs, dx, dy)
        if frac > 0.9 and (best is None or frac > best[2]) and _ink_follows(ca, cb, changed, bg, dx, dy) \
                and _whole_objects(ca, changed, bg) and not _inline_edit(ca, changed, bg, dx, dy):
            best = (dx, dy, round(frac, 3))
    return best


def _inline_edit(ca, changed, bg, dx, dy) -> bool:
    """Part of a text line nudged sideways with untouched text right beside it: a character edit, not a move."""
    if dy or abs(dx) > 12:
        return False
    ia = ink(ca, bg)
    ys, xs = np.where(changed)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    left = ia[y0:y1, max(0, x0 - 8):x0] & ~changed[y0:y1, max(0, x0 - 8):x0]
    right = ia[y0:y1, x1:x1 + 8] & ~changed[y0:y1, x1:x1 + 8]
    return bool(left.any() or right.any())


def _whole_objects(ca, changed, bg) -> bool:
    """Most ink of every object touching the change changed too (a glyph swap leaves its word intact)."""
    ia = ink(ca, bg)
    if not ia.any():
        return True
    labels, _ = ndimage.label(ndimage.binary_dilation(ia, structure=np.ones((3, 9))))
    touched = np.unique(labels[changed & ia])
    touched = touched[touched > 0]
    ys, xs = np.where(changed)
    change_area = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
    for t in touched:
        obj = ia & (labels == t)
        oy, ox = np.where(obj)
        if (oy.max() - oy.min() + 1) * (ox.max() - ox.min() + 1) > 4 * change_area:
            continue  # a container the change sits inside, not the thing that changed
        if (obj & changed).sum() < 0.5 * obj.sum():
            return False
    return True


def _static_geometry(ca, cb, changed, bg) -> bool:
    """Ink occupies the same pixels before and after: only colours changed."""
    near = ndimage.binary_dilation(changed, iterations=2)
    ia = (np.abs(ca - bg).max(axis=2) > NOISE) & near
    ib = (np.abs(cb - bg).max(axis=2) > NOISE) & near
    return _iou(ia, ib) > 0.9


def _ink_follows(ca, cb, changed, bg, dx, dy) -> bool:
    """The changed ink in before, moved by (dx, dy), lands on the changed ink in after."""
    near = ndimage.binary_dilation(changed, iterations=2)
    ia, ib = ink(ca, bg) & near, ink(cb, bg) & near
    if ia.sum() < 6 or ib.sum() < 6:
        return False
    moved = np.zeros_like(ia)
    h, w = ia.shape
    ys, xs = np.where(ia)
    ys, xs = ys + dy, xs + dx
    keep = (ys >= 0) & (ys < h) & (xs >= 0) & (xs < w)
    moved[ys[keep], xs[keep]] = True
    return _iou(moved, ib) > 0.85


def _iou(p: np.ndarray, q: np.ndarray) -> float:
    pd, qd = ndimage.binary_dilation(p), ndimage.binary_dilation(q)
    inter = (p & qd).sum() + (q & pd).sum()
    total = p.sum() + q.sum()
    return float(inter / total) if total else 1.0


def _explained(ca, cb, ys, xs, dx, dy) -> float:
    h, w = ca.shape[:2]
    ok = np.zeros(len(ys), dtype=bool)
    # Pixel shows the moved content: after(p) == before(p - shift).
    sy, sx = ys - dy, xs - dx
    inside = (sy >= 0) & (sy < h) & (sx >= 0) & (sx < w)
    ok[inside] |= np.abs(cb[ys[inside], xs[inside]] - ca[sy[inside], sx[inside]]).max(axis=1) <= NOISE * 2
    # Pixel was vacated: before(p) reappears at p + shift.
    ty, tx = ys + dy, xs + dx
    inside = (ty >= 0) & (ty < h) & (tx >= 0) & (tx < w)
    ok[inside] |= np.abs(ca[ys[inside], xs[inside]] - cb[ty[inside], tx[inside]]).max(axis=1) <= NOISE * 2
    return float(ok.mean())


def _gradient(ca, cb, changed):
    """A large smooth multi-colour fill whose colour ramp changed direction."""
    ys, xs = np.where(changed)
    if len(ys) < 400:
        return None
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    if changed[y0:y1, x0:x1].mean() < 0.5 or min(y1 - y0, x1 - x0) < 12:
        return None
    sa = ca[y0:y1, x0:x1].astype(float).mean(axis=2)
    sb = cb[y0:y1, x0:x1].astype(float).mean(axis=2)
    def smooth(g):
        local = (np.abs(np.diff(g, axis=0)).mean() + np.abs(np.diff(g, axis=1)).mean()) / 2
        levels, counts = np.unique(np.round(g / 3), return_counts=True)
        flat = counts.max() / g.size > 0.4  # one dominant colour: a solid fill, not a ramp
        return g.std() > 6 and local < 0.15 * g.std() and len(levels) >= 12 and not flat
    if not (smooth(sa) and smooth(sb)):
        return None
    return (f"gradient direction changed: {_ramp(sa)} -> {_ramp(sb)}", "", {"before": _ramp(sa), "after": _ramp(sb)})


def _ramp(g: np.ndarray) -> str:
    """Direction the fill gets darker toward, from a least-squares plane fit."""
    yy, xx = np.mgrid[0:g.shape[0], 0:g.shape[1]]
    A = np.c_[xx.ravel() / g.shape[1], yy.ravel() / g.shape[0], np.ones(g.size)]
    (gx, gy, _), *_ = np.linalg.lstsq(A, g.ravel(), rcond=None)
    angle = (np.degrees(np.arctan2(-gy, -gx)) + 360) % 360  # direction of decreasing brightness
    names = ["right", "bottom-right", "bottom", "bottom-left", "left", "top-left", "top", "top-right"]
    return "darker toward " + names[int(((angle + 22.5) % 360) // 45)]


def recolor_score(ca: np.ndarray, cb: np.ndarray, changed: np.ndarray) -> float:
    """~0 when every before-colour maps to one after-colour (a recolour); ~1 when geometry moved."""
    pa = ca[changed].astype(np.int32)
    pb = cb[changed].astype(float)
    if len(pa) < 4:
        return 1.0
    keys = (pa[:, 0] // 12) * 4096 + (pa[:, 1] // 12) * 64 + pa[:, 2] // 12
    order = np.argsort(keys)
    keys, pb = keys[order], pb[order]
    _, starts, counts = np.unique(keys, return_index=True, return_counts=True)
    spread = 0.0
    for s0, n in zip(starts, counts):
        spread += pb[s0:s0 + n].std(axis=0).mean() * n
    total = pb.std(axis=0).mean() * len(pb) + 1e-9
    # Bins with one pixel say nothing; penalise colour sets made mostly of singletons.
    singletons = (counts == 1).sum() / len(counts)
    return float(spread / total + 0.5 * singletons)


@dataclass
class Flow:
    moves: list[tuple[tuple[int, int, int, int], tuple[int, int]]]  # (before box, (dx, dy)) for matched items
    lost: list[tuple[int, int, int, int]]                            # before items with no same-shape match
    gained: list[tuple[int, int, int, int]]                          # after items never matched


def item_flow(ca, cb, ia, ib) -> Flow | None:
    before, after = items(ia), items(ib)
    if not before or not after:
        return None
    ga, gb = ca.mean(axis=2), cb.mean(axis=2)
    used = set()
    moves, lost = [], []
    for p in sorted(before, key=lambda r: (r[1], r[0])):
        pw, ph = p[2] - p[0], p[3] - p[1]
        best, best_cost = None, None
        for j, q in enumerate(after):
            if j in used or abs((q[2] - q[0]) - pw) > 1 or abs((q[3] - q[1]) - ph) > 1:
                continue
            dx, dy = q[0] - p[0], q[1] - p[1]
            if abs(dx) > 400 or abs(dy) > 200:
                continue
            hh, ww = min(ph, q[3] - q[1]), min(pw, q[2] - q[0])
            cost = np.abs(ga[p[1]:p[1] + hh, p[0]:p[0] + ww] - gb[q[1]:q[1] + hh, q[0]:q[0] + ww]).mean() + 0.01 * (abs(dx) + abs(dy))
            if best_cost is None or cost < best_cost:
                best, best_cost = j, cost
        if best is not None and best_cost < 12:
            used.add(best)
            q = after[best]
            moves.append((p, (q[0] - p[0], q[1] - p[1])))
        else:
            lost.append(p)
    gained = [q for j, q in enumerate(after) if j not in used]
    return Flow(moves, lost, gained)


def _layout(flow: Flow, change) -> Change | None:
    moved = [(p, d) for p, d in flow.moves if d != (0, 0)]
    if not moved or flow.lost or flow.gained:
        return None
    shifts = {d for _, d in moved}
    if len(shifts) == 1:
        dx, dy = next(iter(shifts))
        if dy == 0 and abs(dx) > 26:
            return change("alignment", f"content shifted {abs(dx)}px {'right' if dx > 0 else 'left'} (alignment change)",
                          "right" if dx > 0 else "left", dx=dx, items=len(moved))
        parts = ([f"{abs(dx)}px {'right' if dx > 0 else 'left'}"] if dx else []) + ([f"{abs(dy)}px {'down' if dy > 0 else 'up'}"] if dy else [])
        return change("moved", "element moved " + " and ".join(parts), " ".join(parts), dx=dx, dy=dy, items=len(moved))
    everything = sorted(flow.moves, key=lambda m: (m[0][1], m[0][0]))
    rows = _rows([p for p, _ in everything])
    dys = [d[1] for _, d in everything]
    dxs = [d[0] for _, d in everything]
    if len(set(dxs)) == 1 and len(rows) >= 2:
        # Each successive text line moved further: the line pitch changed.
        row_dy = [np.median([d[1] for p, d in everything if r0 <= p[1] < r1]) for r0, r1 in rows]
        steps = np.diff(row_dy)
        if len(steps) and (np.all(steps > 0) or np.all(steps < 0)) and len(rows) >= 3 or (len(rows) == 2 and steps.size and steps[0] != 0 and abs(steps[0]) <= 12):
            d = "looser" if steps.mean() > 0 else "tighter"
            return change("line-height", f"line spacing {d}: each line moved {steps.mean():+.1f}px relative to the one above",
                          d, step=float(round(steps.mean(), 1)), lines=len(rows))
    span = lambda key: max(p[2] + d[0] for p, d in everything) - min(p[0] + d[0] for p, d in everything) if key == "x" else \
        max(p[3] + d[1] for p, d in everything) - min(p[1] + d[1] for p, d in everything)
    before_w = max(p[2] for p, _ in everything) - min(p[0] for p, _ in everything)
    before_h = max(p[3] for p, _ in everything) - min(p[1] for p, _ in everything)
    grow = (span("x") - before_w) + (span("y") - before_h)
    if grow == 0 and len(set(dys)) == 1:
        return change("alignment", f"items redistributed horizontally (moves {sorted({int(v) for v in dxs})} px)", "",
                      moves=sorted({int(v) for v in dxs}))
    if grow == 0:
        return None
    d = "increased" if grow > 0 else "decreased"
    return change("spacing", f"spacing {d}: items spread by {int(grow):+d}px", d, grow=int(grow),
                  moves=sorted((int(a_), int(b_)) for a_, b_ in shifts))


def _rows(boxes):
    """Groups boxes into horizontal rows; returns (top, bottom) per row."""
    rows = []
    for x0, y0, x1, y1 in sorted(boxes, key=lambda r: r[1]):
        if rows and y0 < rows[-1][1] - 2:
            rows[-1][1] = max(rows[-1][1], y1)
        else:
            rows.append([y0, y1])
    return [(r0, r1) for r0, r1 in rows]


def _text_change(ia, ib, changed, change, flow: Flow | None) -> Change:
    # Measure only the items whose shape changed, when we know them.
    if flow and (flow.lost or flow.gained):
        ma = np.zeros_like(ia)
        mb = np.zeros_like(ib)
        for x0, y0, x1, y1 in flow.lost:
            ma[y0:y1, x0:x1] = ia[y0:y1, x0:x1]
        for x0, y0, x1, y1 in flow.gained:
            mb[y0:y1, x0:x1] = ib[y0:y1, x0:x1]
        if ma.any() and mb.any():
            ia, ib = ma, mb
    ta, tb = text_metrics(ia), text_metrics(ib)
    if not (ta.lines and tb.lines):
        if ib.sum() > ia.sum():
            return change("appeared", "new content appeared", "", ink=[int(ia.sum()), int(ib.sum())])
        if ib.sum() < ia.sum():
            return change("disappeared", "content disappeared", "", ink=[int(ia.sum()), int(ib.sum())])
        return change("changed", "pixels changed (unclassified)", "", changed_px=int(changed.sum()))
    gh_a, gh_b = ta.glyph_height, tb.glyph_height
    width_a, width_b = sum(ta.widths), sum(tb.widths)
    ink_ratio = tb.ink / max(1, ta.ink)
    width_ratio = width_b / max(1, width_a)
    if abs(gh_b - gh_a) >= 2 or (gh_a and abs(gh_b - gh_a) / gh_a > 0.12):
        d = "larger" if gh_b > gh_a else "smaller"
        return change("font-size", f"text became {d}: glyph height {gh_a:.0f}px -> {gh_b:.0f}px", d, glyph_height=[gh_a, gh_b])
    if len(ta.lines) == len(tb.lines) > 1 and abs(tb.pitch - ta.pitch) >= 1:
        d = "looser" if tb.pitch > ta.pitch else "tighter"
        return change("line-height", f"line spacing {d}: pitch {ta.pitch:.0f}px -> {tb.pitch:.0f}px", d, pitch=[ta.pitch, tb.pitch])
    if abs(ink_ratio - 1) > 0.06 and abs(ink_ratio - 1) > 1.4 * abs(width_ratio - 1):
        d = "bolder" if ink_ratio > 1 else "lighter"
        return change("font-weight", f"text became {d}: ink {ink_ratio:.0%} of before, width {width_ratio:.0%}", d,
                      ink_ratio=round(ink_ratio, 3), width_ratio=round(width_ratio, 3))
    if abs(width_ratio - 1) > 0.03:
        d = "wider" if width_ratio > 1 else "tighter"
        return change("letter-spacing", f"letter spacing {d}: line width {width_a}px -> {width_b}px, ink {ink_ratio:.0%}", d,
                      width=[width_a, width_b], ink_ratio=round(ink_ratio, 3))
    return change("text", "text content changed (line metrics unchanged)", "", changed_px=int(changed.sum()))


def _opacity(ca, cb, changed, bg):
    """Several distinct colours, all blended toward the background by one alpha."""
    pa, pb = ca[changed].astype(float), cb[changed].astype(float)
    if len(pa) < 20:
        return None
    da, db = pa - bg, pb - bg
    denom = (da * da).sum()
    if not denom:
        return None
    alpha = float((da * db).sum() / denom)
    fit = np.abs(alpha * da - db).mean() / (np.abs(da - db).mean() + 1e-9)
    sv = np.linalg.svd(da - da.mean(axis=0), compute_uv=False)
    several = len(_clusters(pa)) >= 2 and sv[1] / (sv[0] + 1e-9) > 0.12
    exact = fit < 0.02 and not _is_outline(changed)  # an exact blend; shade swaps miss by more, outlines are borders
    if (several and fit < 0.3 or exact) and (0.15 < alpha < 0.97 or alpha > 1.03):
        d = "more transparent" if alpha < 1 else "more opaque"
        return (f"element became {d}: every colour blended toward the background (alpha ~{alpha:.2f})", d)
    return None


def _colour_change(ca, cb, changed, bg, change):
    pa, pb = ca[changed].astype(float), cb[changed].astype(float)
    ys, xs = np.where(changed)
    sa = ca[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(float)
    sb = cb[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(float)
    area = changed[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    # Opacity: several distinct colours all blended toward the background by one alpha.
    clusters = _clusters(pa)
    da, db = pa - bg, pb - bg
    denom = (da * da).sum()
    alpha = float((da * db).sum() / denom) if denom else 1.0
    fit = np.abs(alpha * da - db).mean() / (np.abs(da - db).mean() + 1e-9)
    sv = np.linalg.svd(da - da.mean(axis=0), compute_uv=False) if len(da) > 2 else np.array([1.0, 0.0])
    several_colours = len(clusters) >= 2 and sv[1] / (sv[0] + 1e-9) > 0.12
    if several_colours and fit < 0.3 and (0.15 < alpha < 0.97 or alpha > 1.03):
        d = "more transparent" if alpha < 1 else "more opaque"
        return change("opacity", f"element became {d} (all colours blended toward background, alpha ~{alpha:.2f})", d, alpha=round(alpha, 2))
    old, new = _dominant(pa), _dominant(pb)
    note = f" (consistent with opacity ~{alpha:.0%})" if fit < 0.3 and 0.15 < alpha < 0.97 else ""
    if _is_outline(changed):
        return change("border-color", f"border colour {hex_color(old)} -> {hex_color(new)}", "", old=hex_color(old), new=hex_color(new))
    thick = ndimage.binary_erosion(changed, iterations=2).sum() / max(1, changed.sum())
    if thick > 0.3:
        return change("fill-color", f"fill colour {hex_color(old)} -> {hex_color(new)}{note}", "", old=hex_color(old), new=hex_color(new))
    return change("text-color", f"text colour {hex_color(old)} -> {hex_color(new)}{note}", "", old=hex_color(old), new=hex_color(new))


def _clusters(pixels: np.ndarray, share: float = 0.08) -> list:
    quant = (pixels // 24).astype(np.int32)
    keys = quant[:, 0] * 4096 + quant[:, 1] * 64 + quant[:, 2]
    values, counts = np.unique(keys, return_counts=True)
    return [v for v, c in zip(values, counts) if c >= share * len(pixels)]


def _dominant(pixels: np.ndarray):
    quant = (pixels // 8).astype(np.int32)
    keys = quant[:, 0] * 65536 + quant[:, 1] * 256 + quant[:, 2]
    values, counts = np.unique(keys, return_counts=True)
    return pixels[keys == values[counts.argmax()]].mean(axis=0)


def _is_outline(changed: np.ndarray) -> bool:
    """Changed pixels are thin straight runs: lines or a rectangle outline."""
    labels, n = ndimage.label(changed, structure=np.ones((3, 3)))
    if n == 0:
        return False
    line_px = 0
    for sl in ndimage.find_objects(labels):
        hh, ww = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        comp = changed[sl]
        thin = min(hh, ww) <= 3 and max(hh, ww) >= 12
        frame = hh > 6 and ww > 6 and comp.sum() <= 2 * (hh + ww) * 3 and comp[hh // 3:2 * hh // 3, ww // 3:2 * ww // 3].sum() == 0
        if thin or frame:
            line_px += comp.sum()
    return line_px / changed.sum() > 0.8


def _corner_change(ca, cb, changed, bg) -> str:
    """Changed pixels sit only in the corners of a filled box: its radius changed."""
    labels, n = ndimage.label(ndimage.binary_dilation(changed), structure=np.ones((3, 3)))
    if not 2 <= n <= 8:
        return ""
    comps = ndimage.find_objects(labels)
    if any((sl[0].stop - sl[0].start) > 40 or (sl[1].stop - sl[1].start) > 40 for sl in comps):
        return ""
    xs = sorted({sl[1].start // 6 for sl in comps} | {sl[1].stop // 6 for sl in comps})
    ys_ = [((sl[0].start + sl[0].stop) // 2) for sl in comps]
    if len(set(y // 8 for y in ys_)) > 2 * 2:
        return ""
    # More rounded = corner pixels turn into background in the after image.
    ia = ink(ca, bg) & changed
    ib = ink(cb, bg) & changed
    if ia.sum() == ib.sum():
        return ""
    return "more rounded" if ib.sum() < ia.sum() else "less rounded"


# --------------------------------------------------------------------------- top level


def compare(a: np.ndarray, b: np.ndarray, max_changes: int = 5) -> list[Change]:
    if a.shape != b.shape:
        h, w = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
        a, b = a[:h, :w], b[:h, :w]
    boxes = regions(change_mask(a, b))
    changes = []
    for band in _bands(boxes):
        if len(band) > 1:
            union = (min(b_[0] for b_ in band), min(b_[1] for b_ in band), max(b_[2] for b_ in band), max(b_[3] for b_ in band))
            row = _row_layout(a, b, union)
            if row:
                changes.append(row)
                continue
        changes += [explain(a, b, box) for box in band]
    changes.sort(key=lambda c: -c.bbox[2] * c.bbox[3])
    return _combine_moves(changes[:max_changes], a.shape[1])


def _bands(boxes):
    """Groups boxes whose vertical extents overlap (one row of a layout)."""
    bands = []
    for box in sorted(boxes, key=lambda b_: b_[1]):
        for band in bands:
            if any(box[1] < o[3] and o[1] < box[3] for o in band):
                band.append(box)
                break
        else:
            bands.append([box])
    return bands


def _row_layout(a, b, union) -> Change | None:
    """Items of one row kept their shapes but were redistributed horizontally."""
    h, w = a.shape[:2]
    x0, y0, x1, y1 = union
    m = 8
    cy0, cy1 = max(0, y0 - m), min(h, y1 + m)
    ca, cb = a[cy0:cy1], b[cy0:cy1]
    bg = background(ca)
    flow = item_flow(ca, cb, ink(ca, bg), ink(cb, bg))
    if not flow or flow.lost or flow.gained:
        return None
    moved = [(p, d) for p, d in flow.moves if d != (0, 0)]
    if len(moved) < 2 or any(d[1] != 0 for _, d in moved):
        return None
    bbox = (int(x0), int(y0), int(x1 - x0), int(y1 - y0))
    order = sorted(flow.moves, key=lambda m_: m_[0][0])
    gaps_a = [q[0] - p[2] for (p, _), (q, _) in zip(order, order[1:])]
    gaps_b = [(q[0] + dq[0]) - (p[2] + dp[0]) for (p, dp), (q, dq) in zip(order, order[1:])]
    dxs = sorted({int(d[0]) for _, d in moved})
    if len({gb - ga for ga, gb in zip(gaps_a, gaps_b)}) == 1 and gaps_a != gaps_b:
        d = "increased" if gaps_b[0] > gaps_a[0] else "decreased"
        return Change("spacing", bbox, f"gap between items {d}: {gaps_a[0]}px -> {gaps_b[0]}px", {"gaps": [gaps_a, gaps_b]}, d)
    return Change("alignment", bbox, f"row items redistributed horizontally (moves {dxs} px): alignment/justification changed",
                  {"moves": dxs}, "")


def _combine_moves(changes: list[Change], width: int) -> list[Change]:
    """Separate groups moving in opposite directions on one axis = spacing (padding or gap) changed."""
    moves = [c for c in changes if c.kind in ("moved", "alignment") and ("dx" in c.evidence)]
    for axis in ("dx", "dy"):
        pos = [c for c in moves if c.evidence.get(axis, 0) > 0]
        neg = [c for c in moves if c.evidence.get(axis, 0) < 0]
        if not (pos and neg):
            continue
        key = 0 if axis == "dx" else 1
        first, last = min(pos + neg, key=lambda c: c.bbox[key]), max(pos + neg, key=lambda c: c.bbox[key])
        converge = first.evidence[axis] > 0 and last.evidence[axis] < 0
        edge = first.bbox[0] < 64 or last.bbox[0] + last.bbox[2] > width - 64 if axis == "dx" else True
        d = ("increased" if edge else "decreased") if converge else ("decreased" if edge else "increased")
        what = "outer padding" if edge else "gap between items"
        x0 = min(c.bbox[0] for c in pos + neg)
        y0 = min(c.bbox[1] for c in pos + neg)
        x1 = max(c.bbox[0] + c.bbox[2] for c in pos + neg)
        y1 = max(c.bbox[1] + c.bbox[3] for c in pos + neg)
        merged = Change("spacing", (x0, y0, x1 - x0, y1 - y0),
                        f"spacing {d}: groups moved {'toward' if converge else 'away from'} each other "
                        f"({', '.join(str(c.evidence[axis]) for c in pos + neg)} px), {what} {d}", {"axis": axis}, d)
        rest = [c for c in changes if c not in pos + neg]
        return [merged] + rest
    return changes


def report(changes: list[Change], crops: list[str] | None = None) -> str:
    if not changes:
        return "no visible change"
    lines = [f"{len(changes)} change{'s' if len(changes) > 1 else ''}"]
    for i, c in enumerate(changes, 1):
        x, y, w, h = c.bbox
        lines.append(f"{i}. {c.summary}  [region x={x} y={y} w={w} h={h}]")
        if crops and i <= len(crops):
            lines.append(f"   zoom: {crops[i - 1]}")
    return "\n".join(lines)


def crop_strip(a: np.ndarray, b: np.ndarray, change: Change, margin: int = 24, max_width: int = 900) -> Image.Image:
    """Before above after, zoomed onto one change: what an agent should look at instead of two screenshots."""
    x, y, w, h = change.bbox
    mx = max(margin, (160 - w) // 2)  # tiny changes (a corner, a glyph) still get readable context
    my = max(margin, (60 - h) // 2)
    x0, y0 = max(0, x - mx), max(0, y - my)
    x1, y1 = min(a.shape[1], x + w + mx), min(a.shape[0], y + h + my)
    ca = Image.fromarray(a[y0:y1, x0:x1].astype(np.uint8))
    cb = Image.fromarray(b[y0:y1, x0:x1].astype(np.uint8))
    zoom = max(1, min(4, 160 // max(1, ca.height)))
    size = (ca.width * zoom, ca.height * zoom)
    if size[0] > max_width:
        size = (max_width, max(1, round(size[1] * max_width / size[0])))
    ca, cb = ca.resize(size, Image.NEAREST), cb.resize(size, Image.NEAREST)
    gap = 18
    out = Image.new("RGB", (size[0], size[1] * 2 + gap), (255, 0, 255))
    out.paste(ca, (0, 0))
    out.paste(cb, (0, size[1] + gap))
    from PIL import ImageDraw
    ImageDraw.Draw(out).text((4, size[1] + 3), f"before ^  after v   x={x0} y={y0} zoom {zoom}x", fill=(255, 255, 255))
    return out


def write_crops(a, b, changes, prefix: str) -> list[str]:
    paths = []
    for i, c in enumerate(changes, 1):
        path = f"{prefix}-change{i}.png"
        crop_strip(a, b, c).save(path)
        paths.append(path)
    return paths


# --------------------------------------------------------------------------- naming changes from a UI tree


@dataclass
class Node:
    role: str
    label: str
    bounds: tuple[int, int, int, int]  # left, top, right, bottom in screenshot pixels
    children: list["Node"] = field(default_factory=list)

    @property
    def area(self) -> int:
        return max(0, self.bounds[2] - self.bounds[0]) * max(0, self.bounds[3] - self.bounds[1])

    def text(self) -> str:
        if self.label:
            return self.label
        for child in self.children:
            found = child.text()
            if found:
                return found
        return ""


def load_tree(path: str) -> list[Node]:
    """A uiautomator XML dump, or JSON: [{"role", "label", "bounds": [l, t, r, b], "children": [...]}]."""
    raw = open(path, encoding="utf-8").read()
    if raw.lstrip().startswith("<"):
        import xml.etree.ElementTree as ET

        def convert(element) -> Node:
            l, t, r, b = (int(v) for v in element.get("bounds", "[0,0][0,0]").replace("][", ",").strip("[]").split(","))
            role = element.get("class", "").rsplit(".", 1)[-1]
            label = element.get("text") or element.get("content-desc") or element.get("resource-id", "").rsplit("/", 1)[-1]
            return Node(role, label, (l, t, r, b), [convert(c) for c in element.findall("node")])

        root = ET.fromstring(raw)
        return [convert(n) for n in root.findall("node")]

    def from_json(item) -> Node:
        return Node(item.get("role", ""), item.get("label", ""), tuple(int(v) for v in item["bounds"]),
                    [from_json(c) for c in item.get("children", [])])

    data = json.loads(raw)
    return [from_json(item) for item in (data if isinstance(data, list) else [data])]


def _flatten(nodes: list[Node]) -> list[Node]:
    out = []
    for n in nodes:
        out.append(n)
        out += _flatten(n.children)
    return out


def name_changes(changes: list[Change], tree: list[Node]) -> list[Change]:
    """Prefixes each change with the smallest tree node that covers it: 'Button "Pay now": ...'."""
    nodes = [n for n in _flatten(tree) if n.area > 0]
    for c in changes:
        x, y, w, h = c.bbox
        cx, cy = x + w / 2, y + h / 2

        def cover(n: Node) -> float:
            l, t, r, b = n.bounds
            ix = max(0, min(r, x + w) - max(l, x))
            iy = max(0, min(b, y + h) - max(t, y))
            return ix * iy / max(1, w * h)

        holders = [n for n in nodes if n.text() and (cover(n) > 0.6 or n.bounds[0] <= cx <= n.bounds[2] and n.bounds[1] <= cy <= n.bounds[3])]
        if not holders:
            continue
        best = min(holders, key=lambda n: n.area)
        name = f'{best.role + " " if best.role else ""}"{best.text()[:40]}"'
        c.evidence["element"] = {"role": best.role, "label": best.text(), "bounds": list(best.bounds)}
        c.summary = f"{name}: {c.summary}"
    return changes


# --------------------------------------------------------------------------- screenshot-test integrations


def split_paparazzi_delta(path: str) -> tuple[np.ndarray, np.ndarray]:
    """Paparazzi's failures/delta-<name>.png is [expected | diff | actual], each panel equally wide.

    The "expected"/"actual" labels sit at about (10, 8) in the outer panels; that corner is
    copied from expected into actual so the labels don't read as a change.
    """
    img = load(path)
    w = img.shape[1] // 3
    expected, actual = img[:, :w].copy(), img[:, 2 * w:3 * w].copy()
    label = (slice(0, 26), slice(0, min(w, 110)))
    actual[label] = expected[label]
    return expected, actual


def scan(root: str) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """Failed screenshot tests under root, as (golden path, golden pixels, actual pixels).

    Sources, in order: Roborazzi result JSONs (type "changed": golden and actual paths), Paparazzi
    failures/delta-*.png, and any <name>_actual.png beside <name>.png.
    """
    from pathlib import Path
    found, seen = [], set()
    for result in sorted(Path(root).rglob("test-results/roborazzi/**/*.json")):
        try:
            data = json.loads(result.read_text())
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if not isinstance(item, dict) or item.get("type") != "changed":
                continue
            golden, actual = Path(item.get("golden_file_path", "")), Path(item.get("actual_file_path", ""))
            if golden.exists() and actual.exists() and str(actual) not in seen:
                seen.add(str(actual))
                found.append((str(golden), load(str(golden)), load(str(actual))))
    for delta in sorted(Path(root).rglob("delta-*.png")):
        a, b = split_paparazzi_delta(str(delta))
        found.append((str(delta), a, b))
    if seen:
        return found  # Roborazzi's results describe the latest run; leftover *_actual.png files may be stale
    for actual in sorted(Path(root).rglob("*_actual.png")):
        if "intermediates" in actual.parts:
            continue
        golden = actual.with_name(actual.name.replace("_actual.png", ".png"))
        if golden.exists():
            found.append((str(golden), load(str(golden)), load(str(actual))))
    return found


def _compose_causes(actual_image: str, changes: list[Change], root: str) -> list[str]:
    """Slot dumps <name>.slots.json (golden run) and <name>_actual.slots.json (this run) -> causes in code."""
    from pathlib import Path
    p = Path(actual_image)
    stem = p.stem.removesuffix("_actual").removeprefix("delta-")
    # Beside the image (Roborazzi), or with the goldens (Paparazzi: src/test/snapshots/images).
    dirs = [p.parent] + [d / "src/test/snapshots/images" for d in [Path(root).resolve(), *p.resolve().parents]
                         if (d / "src/test/snapshots/images").is_dir()]
    before, after = (next((d / (stem + suffix + ext) for d in dirs for ext in (".gz", "")
                           if (d / (stem + suffix + ext)).exists()), p.with_name(stem + suffix))
                     for suffix in (".slots.json", "_actual.slots.json"))
    if not (before.exists() and after.exists()):
        return []
    from . import compose_slots
    import os
    user = compose_slots.project_files(root) or compose_slots.project_files(os.getcwd())
    slots_before, slots_after = compose_slots.load(str(before)), compose_slots.load(str(after))
    # Screenshots saved downscaled (Roborazzi's resizeScale) are smaller than the layout they show.
    width = max((g["bounds"][2] for g in slots_before), default=0)
    scale = width / Image.open(actual_image).width if width else 1
    scale = scale if scale > 1.2 else 1
    regions = [tuple(round(v * scale) for v in c.bbox) for c in changes]
    found = compose_slots.diff(slots_before, slots_after, regions, user or None)
    module = root if compose_slots.project_files(root) else os.getcwd()
    causes = compose_slots.explain(found, user or None) + compose_slots.source_hits(found, module)
    if causes and any(" is written at " in c or " now uses " in c for c in causes):
        other = _unaccounted(found, causes, user)
        causes.append("accounts for every change in this composition" if not other else
                      f"{len(other)} other composition change(s) not accounted for: " + "; ".join(other[:2]))
    if not causes:
        everything = [c for c in compose_slots.diff(slots_before, slots_after, None, None)
                      if not c.detail.startswith("layout") and not compose_slots._reordered(c)]
        if everything:
            # Nothing changed in the project's code, something did inside a library: a dependency upgrade.
            top = everything[0]
            causes = [f"inside a library, not in your code: {top.file}:{top.line} {top.name}: "
                      f"{compose_slots._ROW.sub('', top.detail)}"[:220]]
        else:
            # 7 of 68 real code edits on Jetsnack looked like this; so do renderer upgrades and nondeterministic renders.
            causes = ["composition identical: the change is in drawing code (draw lambdas, Canvas, images), "
                      "the renderer, or the render isn't deterministic"]
    return causes


def _cause_values(cause: str) -> list[str]:
    """How a cause's value appears in recorded values: 0x..7A4040 -> #7a4040, 27.sp -> 27.0.sp, …"""
    import re
    head = cause.split(" is written at ")[0]
    values = [f"#{h.lower()}" for h in re.findall(r"0x\.\.([0-9A-Fa-f]{6})", head)]
    for number, unit in re.findall(r"(-?\d+(?:\.\d+)?)\.(dp|sp|em)\b", head):
        values += [f"{float(number):g}.0.{unit}" if "." not in number else f"{number}.{unit}", f"={number}.{unit}"]
    weights = {"Thin": 100, "ExtraLight": 200, "Light": 300, "Normal": 400, "Medium": 500, "SemiBold": 600,
               "Bold": 700, "ExtraBold": 800, "Black": 900}
    values += [f"weight={weights[w]}" for w in re.findall(r"FontWeight\.(\w+)", head) if w in weights]
    values += re.findall(r'^"(.+)"$', head)
    return values


def _unaccounted(found, causes: list[str], user) -> list[str]:
    """Composition changes that none of the reported causes explains (layout moves are consequences)."""
    from . import compose_slots
    values = [v for c in causes if " is written at " in c for v in _cause_values(c)]
    sites = {loc for c in causes if " now uses " in c for loc in _locations(c)[:1]}
    styles = {ch.new for ch in found if (ch.file, ch.line) in sites}
    def explained(ch):
        return (ch.file, ch.line) in sites or ch.new in styles or any(v in ch.new or v in ch.detail for v in values)
    calls = {(ch.file, ch.line) for ch in found if explained(ch)}  # other values of an explained call go with it
    other = []
    for ch in found:
        if ch.detail.startswith("layout") or compose_slots._reordered(ch) or (user and ch.file not in user):
            continue
        if explained(ch) or (ch.file, ch.line) in calls:
            continue
        other.append(str(ch)[:140])
    return list(dict.fromkeys(other))


def _tree_beside(image: str) -> str | None:
    """<name>.tree.json or <name>.xml next to a screenshot (with _actual/delta- stripped)."""
    from pathlib import Path
    p = Path(image)
    stem = p.stem.removeprefix("delta-").removesuffix("_actual").removesuffix("_compare")
    for candidate in (p.with_name(stem + ".tree.json"), p.with_name(stem + ".xml")):
        if candidate.exists():
            return str(candidate)
    return None


def _short_name(name: str) -> str:
    """com/example/ui.FooKt.FooPreview.dark.png -> FooPreview.dark"""
    from pathlib import Path
    parts = Path(name).stem.removeprefix("delta-").split(".")
    return ".".join(parts[-2:]) if len(parts) > 2 else Path(name).stem.removeprefix("delta-")


def _diff_lines(source: str, ref: str) -> dict[str, set[int]]:
    """{file name: line numbers changed (new side)} for `git diff REF` over the working tree."""
    import re
    import subprocess
    out = subprocess.run(["git", "-C", source, "diff", "-U0", ref, "--", "."], capture_output=True, text=True).stdout
    changed: dict[str, set[int]] = {}
    current = None
    for line in out.splitlines():
        if line.startswith("+++ "):
            current = None if line.endswith("/dev/null") else line.rsplit("/", 1)[-1]
        m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
        if m and current:
            start, count = int(m.group(3)), int(m.group(4) or 1)
            # A pure deletion has no new lines: count the line it sat next to.
            changed.setdefault(current, set()).update(range(start, start + max(count, 1)))
    return changed


def _locations(cause: str) -> list[tuple[str, int]]:
    import re
    return [(f, int(n)) for f, n in re.findall(r"([\w.]+\.kt):(\d+)", cause)]


def _triage(rows, changed: dict[str, set[int]]):
    """Per failure: the headline causes this diff explains, and those it doesn't."""
    def explained(cause: str) -> bool:
        # A call's line is where it starts; the edited argument can be a few lines below.
        return any(any(n - 1 <= c <= n + 12 for c in changed.get(f, ())) for f, n in _locations(cause))
    result = []
    for name, causes, _ in rows:
        heads = [c for c in causes if " is written at " in c or " now uses " in c] or \
            [c for c in causes if _locations(c) and ": layout " not in c and "not accounted" not in c][:3]
        if not heads:
            result.append((name, [], [], causes[:1]))
            continue
        result.append((name, [c for c in heads if explained(c)], [c for c in heads if not explained(c)], []))
    return result


def _triage_text(triage, ref: str) -> str:
    total = len(triage)
    ok = [t for t in triage if t[1] and not t[2]]
    odd = [t for t in triage if t[2]]
    unknown = [t for t in triage if not t[1] and not t[2]]
    lines = [f"Against {ref}: {len(ok)} of {total} changed screenshots are explained by lines this diff changes."]
    if odd:
        lines.append(f"! {len(odd)} not explained by this diff:")
        by: dict[str, list[str]] = {}
        for name, _, unexplained, _ in odd:
            for c in unexplained:
                by.setdefault(c, []).append(_short_name(name))
        for cause, names in sorted(by.items(), key=lambda kv: -len(kv[1])):
            lines.append(f"  {cause}\n      in {len(names)}: {', '.join(names[:3])}{', …' if len(names) > 3 else ''}")
    if unknown:
        lines.append(f"? {len(unknown)} without a cause in code (drawing code, a library or the renderer): "
                     + ", ".join(_short_name(t[0]) for t in unknown[:4]) + (", …" if len(unknown) > 4 else ""))
    return "\n".join(lines)


def _markdown(rows, triage=None) -> str:
    """Failures grouped by cause, as a PR comment."""
    groups: dict[str, list[str]] = {}
    for name, causes, changes in rows:
        written = [c for c in causes if " is written at " in c or " now uses " in c]
        keys = written or causes[:1] or [changes[0].summary if changes else "no visible change"]
        for key in keys:  # a screenshot showing two edits is listed under both
            groups.setdefault(key, []).append(_short_name(name))
    out = [f"### {len(rows)} screenshot test(s) changed", ""]
    if triage:
        odd = {_short_name(t[0]): t[2] for t in triage if t[2]}
        unknown = [_short_name(t[0]) for t in triage if not t[1] and not t[2]]
        explained = len(triage) - len(odd) - len(unknown)
        out.append(f"**{explained} of {len(triage)} explained by lines this PR changes.**")
        if odd:
            out += ["", f"⚠️ **{len(odd)} not explained by this PR's changes:**", "",
                    "| Screenshot | Cause in code |", "| --- | --- |"]
            out += [f"| {n} | " + "<br>".join(f"`{c.replace('|', chr(92) + '|')}`" for c in causes) + " |"
                    for n, causes in odd.items()]
        if unknown:
            out += ["", f"❔ {len(unknown)} without a cause in code (drawing code, a library or the renderer): "
                    + ", ".join(unknown[:8]) + (" …" if len(unknown) > 8 else "")]
        out += ["", "<details><summary>All causes</summary>", ""]
    out += ["| Cause | Screenshots |", "| --- | --- |"]
    for key, names in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        cell = key.replace("|", "\\|")
        out.append(f"| `{cell}` | {len(names)}: {', '.join(names[:5])}{' …' if len(names) > 5 else ''} |")
    if triage:
        out += ["", "</details>"]
    return "\n".join(out)


def _cause_summary(total: int, by_cause: dict[str, list[str]], identical: list[str] = ()) -> str:
    """One line per distinct top cause, with the screenshots it broke: many failures, few edits."""
    explained = len({n for names in by_cause.values() for n in names})
    library = {c: n for c, n in by_cause.items() if c.startswith("inside a library")}
    in_code = len({n for c, names in by_cause.items() if c not in library for n in names})
    in_library = len({n for names in library.values() for n in names})
    if library or identical:  # e.g. a dependency or tooling upgrade: say which kind of change each one is
        parts = [f"{in_code} changed by your code ({len(by_cause) - len(library)} cause(s))"] if in_code else []
        parts += [f"{in_library} changed inside a library ({len(library)})"] if library else []
        parts += [f"{len(identical)} with an identical composition (renderer or drawing)"] if identical else []
        lines = [f"{total} failed screenshots: " + "; ".join(parts) + ":"]
    else:
        lines = [f"{total} failed screenshots; {explained} traced to {len(by_cause)} cause(s) in code:"]
    for cause, names in sorted(by_cause.items(), key=lambda kv: -len(kv[1])):
        shown = ""
        for i, n in enumerate(names):  # as many names as fit on one line
            rest = f", +{len(names) - i} more"
            if i and len(shown) + len(_short_name(n)) + len(rest) > 90:
                shown += rest
                break
            shown += (", " if i else "") + _short_name(n)
        lines.append(f"  {cause}\n      breaks {len(names)}: {shown}")
    if identical:
        shown = ", ".join(_short_name(n) for n in identical[:3]) + (f", +{len(identical) - 3} more" if len(identical) > 3 else "")
        lines.append(f"  composition identical: the same UI drawn differently\n      in {len(identical)}: {shown}")
    if explained + len(identical) < total:
        lines.append(f"  {total - explained - len(identical)} without a cause: see the pixel reports below")
    return "\n".join(lines)


_GRADLE = """\
dependencies {
    testImplementation("androidx.compose.ui:ui-tooling-data")
}

roborazzi {
    @OptIn(com.github.takahirom.roborazzi.ExperimentalRoborazziApi::class)
    generateComposePreviewRobolectricTests {
        enable = true
        packages = listOf("%s")
        useScanOptionParametersInTester = true
        testerQualifiedClassName = "dev.diffsay.DiffsayPreviewTester"
    }
}"""

USAGE = """usage:
  diffsay init <android-module>                    set up cause-in-code recording in a Compose module
  diffsay scan <dir> [--source <module>] [--markdown] [--crops DIR]
                                                   explain every failed screenshot test under <dir>
  diffsay <before.png> <after.png> [--crops PREFIX] [--json] [--tree FILE]
                                                   what changed between two screenshots (any platform)
"""


def init(module: str) -> int:
    """Copies the recorder into <module>'s test sources and prints the Gradle lines to add."""
    import re
    from importlib.resources import files
    from pathlib import Path
    root = Path(module)
    if not (root / "src").is_dir():
        print(f"{root} has no src/ directory: pass an Android module, e.g. diffsay init app")
        return 2
    test_src = next((root / "src/test" / d for d in ("kotlin", "java") if (root / "src/test" / d).is_dir()),
                    root / "src/test/java")
    target = test_src / "dev/diffsay"
    target.mkdir(parents=True, exist_ok=True)
    build = next((root / n for n in ("build.gradle.kts", "build.gradle") if (root / n).exists()), None)
    text = build.read_text(encoding="utf-8") if build else ""
    paparazzi = "paparazzi" in text.lower() and "roborazzi" not in text.lower()
    names = ("SlotRecorder.kt", "PaparazziCauses.kt") if paparazzi else         ("SlotRecorder.kt", "RoborazziCauses.kt", "DiffsayPreviewTester.kt")
    for name in names:
        (target / name).write_text(files("diffsay").joinpath("android", name).read_text(encoding="utf-8"),
                                   encoding="utf-8")
        print(f"wrote {target / name}")
    namespace = re.search(r'namespace\s*=?\s*"([\w.]+)"', text)
    if paparazzi:
        print(f"\nAdd to {build}: testImplementation(\"androidx.compose.ui:ui-tooling-data\")\n"
              "Then use paparazzi.snapshotWithCauses(name) { … } instead of paparazzi.snapshot(name) { … },\n"
              f"record, change code, verify, and run: diffsay scan {root}/build --source {root}")
        return 0
    print(f"\nAdd to {build or root / 'build.gradle.kts'} (Roborazzi on Robolectric already set up):\n")
    print(_GRADLE % (namespace.group(1) if namespace else "com.example.app"))
    if "generateComposePreviewRobolectricTests" in text:
        print("\nThis module already generates preview tests: add the testerQualifiedClassName and "
              "useScanOptionParametersInTester lines to that block.")
    print("\nHand-written tests: use compose.captureWithCauses(path) { Content() } instead.\n"
          f"Then record goldens, change code, compare, and run: diffsay scan {root}/build --source {root}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0 if argv else 2
    if argv[0] == "init":
        if len(argv) != 2:
            print("usage: diffsay init <android-module-dir>")
            return 2
        return init(argv[1])
    if argv and argv[0] == "scan":
        parser = argparse.ArgumentParser(prog="diffsay scan", description="explain every failed screenshot test under a directory")
        parser.add_argument("root")
        parser.add_argument("--crops", metavar="DIR", help="write zoomed before/after strips here")
        parser.add_argument("--source", help="module directory with src/ (default: found above ROOT or the cwd)")
        parser.add_argument("--markdown", action="store_true", help="a PR-comment summary instead of the full report")
        parser.add_argument("--diff", metavar="REF", help="split failures into those explained by `git diff REF` "
                            "(this PR) and those no changed line explains")
        args = parser.parse_args(argv[1:])
        failures = scan(args.root)
        if not failures:
            print(f"no screenshot-test failures found under {args.root}")
            return 0
        details, by_cause, rows, identical = [], {}, [], []
        for name, a, b in failures:
            changes = compare(a, b)
            tree = _tree_beside(name)
            if tree:
                name_changes(changes, load_tree(tree))
            causes = _compose_causes(name, changes, args.source or args.root)
            if causes and causes[0].startswith("composition identical"):
                identical.append(name)
            elif causes:
                # Where the value is written (Type.kt) beats where it's used (each Text): one edit, one group.
                written = [c for c in causes if " is written at " in c or " now uses " in c]
                for cause in written or causes[:1]:  # a change of two edits lists both
                    by_cause.setdefault(cause, []).append(name)
            crops = None
            if args.crops:
                import os
                os.makedirs(args.crops, exist_ok=True)
                crops = write_crops(a, b, changes, os.path.join(args.crops, os.path.splitext(os.path.basename(name))[0]))
            cause_text = ("cause in code (composition diff):\n" + "\n".join(f"  {c}" for c in causes) + "\npixels:\n") if causes else ""
            if "accounts for every change in this composition" in causes:
                # The pixel heuristics would only re-describe the same change, sometimes wrongly; in a study, an
                # agent went hunting for those "other" changes. Say what they are instead.
                pixels = f"{len(changes)} changed region(s), all effects of the causes above"
                if crops:
                    pixels += "; zoom: " + ", ".join(crops)
                details.append(f"== {name}\n{cause_text}{pixels}\n")
            else:
                details.append(f"== {name}\n{cause_text}{report(changes, crops)}\n")
            rows.append((name, causes, changes))
        triage = _triage(rows, _diff_lines(args.source or args.root, args.diff)) if args.diff else None
        if args.markdown:
            print(_markdown(rows, triage))
            return 1
        if triage:
            print(_triage_text(triage, args.diff) + "\n")
        if len(failures) > 1 and (by_cause or identical):
            print(_cause_summary(len(failures), by_cause, identical))
            complete = sum(any(c == "accounts for every change in this composition" for c in r[1]) for r in rows)
            partial = sum(any("not accounted for" in c for c in r[1]) for r in rows)
            if complete or partial:
                print(f"  these causes account for every composition change in {complete} of {len(rows)}"
                      + (f"; {partial} also show other changes (see below)" if partial else ""))
            print()
        print("\n".join(details))
        return 1
    parser = argparse.ArgumentParser(prog="diffsay", description=__doc__.split("\n\n")[0])
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--crops", metavar="PREFIX", help="write PREFIX-changeN.png zoom strips for each change")
    parser.add_argument("--tree", help="UI tree of the after screen (uiautomator XML or JSON) to name each change")
    args = parser.parse_args(argv)
    a, b = load(args.before), load(args.after)
    changes = compare(a, b)
    if args.tree:
        name_changes(changes, load_tree(args.tree))
    crops = write_crops(a, b, changes, args.crops) if args.crops and changes else None
    if args.json:
        print(json.dumps([{**asdict(c), "zoom": crops[i] if crops else None} for i, c in enumerate(changes)], indent=2))
    else:
        print(report(changes, crops))
    return 1 if changes else 0


if __name__ == "__main__":
    sys.exit(main())
