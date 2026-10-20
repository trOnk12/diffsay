"""Explains a Compose screenshot diff from the composition itself.

A slot-table dump (see `android/SlotRecorder.kt`) lists every composable call with its source
file:line, pixel bounds and parameter values. Comparing the dump from the golden run with the dump
from the failing run gives the cause in code ("CheckoutScreen.kt:72 Button shape: 8.dp -> 24.dp"),
which pixels alone can't: a radius, a padding and a colour can all look alike at the edges.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

# Object identities differ between runs and say nothing about the UI.
_IDENTITY = re.compile(r"@[0-9a-f]{4,}|\{[0-9a-f]{6,} ")
_LAMBDA = re.compile(r"\$\$Lambda|\$lambda|Lambda\$|ComposableLambda")
_COLOUR_PARAMS = {"color", "containerColor", "contentColor", "backgroundColor", "tint", "borderColor"}
_TEXT_UNIT_PARAMS = {"fontSize", "lineHeight", "letterSpacing"}


@dataclass
class SlotChange:
    file: str
    line: int
    name: str
    bounds: tuple[int, int, int, int]
    detail: str
    depth: int
    chain: tuple = ()  # (file, line) of the project's call sites from the root down to this change
    new: str = ""  # the full new value, for matching it against the sources
    old: str = ""

    def __str__(self) -> str:
        where = f"{self.file}:{self.line}" if self.line > 0 else self.file or "?"
        return f"{where} {self.name}: {self.detail}"


_OBJECT_REF = re.compile(r"^[\w.$]+@[0-9a-f]+$")


def _signature(g) -> str:
    """Name plus the first text found below: stable across runs, distinct for siblings like list rows."""
    def first_text(node, budget=[0]):
        for p in node["params"]:
            if p["name"] == "text" and p["value"]:
                return p["value"][:30]
        if node["name"] in ("Text", "BasicText") and not node["params"]:
            # Newer compilers: no parameter names, but the text is the first plain remembered value.
            for value in node.get("data", []):
                if isinstance(value, str) and value and "(" not in value and not _OBJECT_REF.match(value):
                    return value[:30]
        for c in node["children"]:
            t = first_text(c)
            if t:
                return t
        return ""
    return f'{g["name"]}|{first_text(g)}'


def _first_named(g, user_files=None):
    """The outermost descendant with a name and source file (a lazy item's own composable),
    preferring calls written in the project over library internals."""
    fallback = None
    queue = list(g["children"])
    while queue:
        node = queue.pop(0)
        if node["file"] and node["name"] and node["line"] > 0:
            if not user_files or node["file"] in user_files:
                return node
            fallback = fallback or node
        queue.extend(node["children"])
    return fallback


def _item_label(by_key, key) -> str:
    """Text that identifies the repeated row/item a change happened in, if any."""
    for cut in range(len(key), 0, -1):
        entry = by_key.get(key[:cut])
        anc = entry and (entry[1] or entry[0])
        label = anc and _signature(anc).split("|")[1]
        if label:
            return label
    return ""


def _roots(dump):
    """Subcompositions (lazy items, dialogs) come in hash order; sort them by position."""
    def anchor(g):  # the first call with a source location: tells apart roots that share bounds and text
        queue = [g]
        while queue:
            node = queue.pop(0)
            if node["file"] and node["name"]:
                return f'{node["file"]}:{node["line"]}'
            queue += node["children"]
        return ""
    return sorted(dump, key=lambda g: (g["bounds"][1], g["bounds"][0], g["bounds"][3], _signature(g), anchor(g)))


def _align(before_children, after_children):
    """Pairs children by content, so inserting, removing or reordering a row doesn't shift every key."""
    import difflib
    sa = [_signature(g) for g in before_children]
    sb = [_signature(g) for g in after_children]
    pairs, blocks = [], []
    matcher = difflib.SequenceMatcher(a=sa, b=sb, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            pairs += list(zip(range(i1, i2), range(j1, j2)))
        else:
            blocks.append((list(range(i1, i2)), list(range(j1, j2))))
    # Moved items (lazy rows come back in another order): same content anywhere among the leftovers.
    left_b = {j: sb[j] for _, bs in blocks for j in bs}
    moved = {}
    for a_side, _ in blocks:
        for i in a_side:
            if sa[i].split("|", 1)[1]:
                j = next((j for j, s in left_b.items() if s == sa[i]), None)
                if j is not None:
                    moved[i] = j
                    del left_b[j]
    pairs += moved.items()
    only_a, only_b = [], []
    for a_side, b_side in blocks:
        # Same composables with changed content (a theme around edited text, next to a group that came or
        # went): pair by name in order, and report only the rest as added/removed.
        rest_b = [j for j in b_side if j in left_b]
        for i in (i for i in a_side if i not in moved):
            j = next((j for j in rest_b if sa[i].split("|")[0] == sb[j].split("|")[0]), None)
            if j is None:
                only_a.append(i)
            else:
                rest_b = rest_b[rest_b.index(j) + 1:]  # keep order: later a's pair with later b's
                pairs.append((i, j))
                del left_b[j]
    only_b = sorted(left_b)
    return pairs, only_a, only_b


def _walk_pairs(before, after, path=(), depth=0, out=None):
    """Yields (key, before_group|None, after_group|None, depth) over two trees aligned by content."""
    out = [] if out is None else out
    pairs, only_a, only_b = _align(before, after)
    for i, j in pairs:
        key = path + ((after[j]["name"], j),)
        out.append((key, before[i], after[j], depth))
        _walk_pairs(before[i]["children"], after[j]["children"], key, depth + 1, out)
    for i in only_a:
        out.append((path + (("-" + before[i]["name"], i),), before[i], None, depth))
    for j in only_b:
        out.append((path + ((after[j]["name"], j),), None, after[j], depth))
    return out


_COLOR_CTOR = re.compile(r"Color\(([0-9.]+), ([0-9.]+), ([0-9.]+), ([0-9.]+)(?:, [^)]*\)?)?")


def _hex(match) -> str:
    r, g, b, a = (float(v) for v in match.groups())
    text = f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"
    return text if a >= 0.999 else f"{text}@{a:.2f}"


def _decode_packed(value: str) -> str:
    """Packed Compose value classes stored as Long: Color (ARGB in the high 32 bits) or TextUnit (sp/em)."""
    import struct
    raw = int(value) & 0xFFFFFFFFFFFFFFFF
    high, low = raw >> 32, raw & 0xFFFFFFFF
    if high in (1, 2) and low:
        number = struct.unpack("f", struct.pack("I", low))[0]
        return f"{number:g}{'sp' if high == 1 else 'em'}"
    if low == 0 and high:
        return f"#{high & 0xFFFFFF:06x}" + ("" if high >> 24 == 0xFF else f"@{(high >> 24) / 255:.2f}")
    return value


_PLUMBING = re.compile(r"CompositionLocal|ProvidedValue|ValueHolder|RecomposeScope|CompositionContext|"
                       r"SnapshotMutableState|DerivedState|MotionScheme|Scope(Impl)?\b|Ripple|Indication")
_HASHLIKE = re.compile(r"(?<![\w.#])-?\d{8,}(?![\w.])")


def _sort_maps(value: str) -> str:
    """{b=2, a=1} and {a=1, b=2} are the same map; property order varies between runs."""
    def sort(m):
        inner = m.group(1)
        if "{" in inner:
            return m.group(0)
        return "{" + ", ".join(sorted(p.strip() for p in inner.split(", "))) + "}"
    return re.sub(r"\{([^{}]*)\}", sort, value)


def _decode(name: str, value: str) -> str:
    value = _COLOR_CTOR.sub(_hex, _IDENTITY.sub("", value))
    if name.startswith("value "):
        if re.fullmatch(r"-?\d{10,}", value):
            decoded = _decode_packed(value)
            return decoded if decoded != value else "<hash>"
        if _PLUMBING.search(value) or re.fullmatch(r"[\w.$]+", value) and "." in value:
            return "<runtime>"  # composition plumbing or a bare object identity, not UI data
        if re.fullmatch(r"-?\d{8,}", value):
            return "<hash>"
        if re.fullmatch(r"-?[0-9a-z]{9,14}", value) and re.search(r"\d", value) and re.search(r"[a-z]", value):
            return "<key>"  # rememberSaveable's generated keys
        value = _HASHLIKE.sub("<id>", value)
    value = _sort_maps(value)
    if name in _COLOUR_PARAMS and re.fullmatch(r"-?\d+", value):
        packed = int(value) & 0xFFFFFFFFFFFFFFFF
        argb = packed >> 32
        return f"#{argb & 0xFFFFFF:06x}" + ("" if argb >> 24 == 0xFF else f" alpha {(argb >> 24) / 255:.2f}")
    if name in _TEXT_UNIT_PARAMS and re.fullmatch(r"-?\d+", value):
        import struct
        raw = int(value) & 0xFFFFFFFFFFFFFFFF
        kind = raw >> 32
        number = struct.unpack("f", struct.pack("I", raw & 0xFFFFFFFF))[0]
        return f"{number:g}{ {1: 'sp', 2: 'em'}.get(kind, '') }" if kind in (1, 2) else "unspecified"
    return value


def _short(old: str, new: str, limit: int = 90) -> tuple[str, str]:
    """Trims the common prefix/suffix of two long values so the difference stays readable."""
    if len(old) <= limit and len(new) <= limit:
        return old, new
    start = 0
    while start < min(len(old), len(new)) and old[start] == new[start]:
        start += 1
    end = 0
    while end < min(len(old), len(new)) - start and old[-1 - end] == new[-1 - end]:
        end += 1
    start = max(0, start - 20)
    cut = lambda s: ("…" if start else "") + s[start:len(s) - end + 20 if end > 20 else len(s)][:limit] + ("…" if end > 20 else "")
    return cut(old), cut(new)


def project_files(start: str) -> set[str]:
    """Kotlin file names under the nearest enclosing directory that has a src/ folder."""
    from pathlib import Path
    here = Path(start).resolve()
    for d in [here, *here.parents]:
        if (d / "src").is_dir():
            # Test sources hold the harness (captureWithCauses, previews' wrappers), not the UI under test.
            return {p.name for p in (d / "src").rglob("*.kt") if not any(part.startswith("test") or
                    part.startswith("androidTest") for part in p.relative_to(d / "src").parts[:1])}
    return set()


def source_hits(changes: list[SlotChange], module: str, limit: int = 3) -> list[str]:
    """Where new text literals live in the project's sources. Data-driven changes (a list item's title,
    a flag that makes a badge appear) render in one place but are written in another."""
    from pathlib import Path
    here = Path(module).resolve()
    src = next((d / "src" for d in [here, *here.parents] if (d / "src").is_dir()), None)
    if not src:
        return []
    files = [(p, p.read_text(encoding="utf-8", errors="replace").splitlines()) for p in sorted(src.rglob("*.kt"))]
    wanted = []
    for c in changes:
        m = re.match(r"text: .* -> (.+)$", c.detail)
        if m:
            wanted.append(m.group(1))
        m = re.search(r' (?:added|removed) in "(.+?)"', c.detail)
        if m:
            wanted.append(m.group(1))
        m = re.search(r" added \((.+?)\)$", c.detail)
        if m:
            wanted.append(m.group(1))
    patterns = []
    for c in changes:
        m = re.match(r"[^:]+: (.*) -> (.*?)(?: \(inside .*)?(?: in \".*\")?$", c.detail)
        if not m:
            continue
        old, new = m.group(1), m.group(2)
        start = len(patterns)
        # Modifier elements with units: padding(10.0.dp) is written padding(10.dp) or padding(all = 10.dp).
        for name, number, unit in re.findall(r"(\w+)\([^()]*?(-?\d+(?:\.\d+)?)\.(dp|sp)", new):
            if f"{number}.{unit}" not in old:
                n = number[:-2] if number.endswith(".0") else number
                patterns.append((f"{name}({n}.{unit})", re.compile(rf"\b{name}\([^)]*?\b{re.escape(n)}(?:\.0)?\.{unit}")))
        for number, unit in re.findall(r"(?<![\w.])(-?\d+(?:\.\d+)?)(sp|em)\b", new):
            if number + unit not in old:
                n = number[:-2] if number.endswith(".0") else number
                patterns.append((f"{n}.{unit}", re.compile(rf"(?<![\w.]){re.escape(n)}(?:\.0)?\.{unit}\b")))
        for key_, number, unit in re.findall(r"(\w+)=(-?\d+(?:\.\d+)?)\.(sp|dp|em)\b", new):
            if f"{key_}={number}.{unit}" not in old:
                n = number[:-2] if number.endswith(".0") else number
                patterns.append((f"{key_} = {n}.{unit}", re.compile(rf"(?<![\w.]){re.escape(n)}(?:\.0)?\.{unit}\b")))
        weights = {100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Normal", 500: "Medium", 600: "SemiBold",
                   700: "Bold", 800: "ExtraBold", 900: "Black"}
        for w in re.findall(r"FontWeight\(weight=(\d+)\)", new):
            if f"FontWeight(weight={w})" not in old and int(w) in weights:
                patterns.append((f"FontWeight.{weights[int(w)]}", re.compile(rf"FontWeight\.{weights[int(w)]}\b")))
        for rgb in re.findall(r"#([0-9a-f]{6})", new):
            if f"#{rgb}" not in old:
                patterns.append((f"0x..{rgb.upper()}", re.compile(rf"0x[0-9a-fA-F]{{2}}{rgb}\b", re.I)))
        context = _literals(c.new) if c.new else []
        patterns[start:] = [(label, pattern, (context, c)) for label, pattern in patterns[start:]]
    chains = {f for c in changes for f in c.chain}
    hits = []
    lines_of = {path.name: lines for path, lines in files}
    swapped = {}
    for c in changes:
        # A Text that now uses another theme style: old and new values each match a whole, different block.
        if "TextStyle(" not in c.new or (c.file, c.line) in swapped:
            continue
        before, after = _best_block(files, _literals(c.old)), _best_block(files, _literals(c.new))
        if before and after and before[:2] != after[:2]:
            swapped[(c.file, c.line)] = c
            hits.append(f"{c.file}:{c.line} now uses {after[2]} ({after[0]}:{after[1]}) instead of {before[2]}")
    # That style's own values (FontWeight.SemiBold) aren't separate causes.
    styles = [c.new for c in swapped.values()]
    patterns = [(l, p, x) for l, p, x in patterns if (x[1].file, x[1].line) not in swapped
                and not any(_literals_match(p, s) for s in styles)]
    for label, pattern, (context, change) in patterns:
        if any(h.startswith(label + " is written") for h in hits):
            continue
        where = [(path.name, number) for path, lines in files if "Test" not in path.name
                 for number, text in enumerate(lines, 1) if pattern.search(text)]
        end = _call_end(lines_of.get(change.file, []), change.line)
        own = [(f, n) for f, n in where if f == change.file and change.line <= n <= end]
        if len(where) > 2 and len(own) == 1:
            where = own  # written in the arguments of the very call that changed
        own_chain = set(change.chain) or chains
        if len(where) > 2 and own_chain:
            # Ambiguous literal: keep matches inside the calls that drew the changed pixels.
            near = [(f, n) for f, n in where if any(f == cf and 0 <= n - cl <= 40 for cf, cl in own_chain)]
            where = near if near else where
        if len(where) > 2 and context:
            # Still ambiguous, e.g. FontWeight.Light in a theme's Type.kt: keep the block that also holds the
            # changed object's other values (the rest of that TextStyle).
            scored = [(_context_score(lines_of[f], n, context, pattern), f, n) for f, n in where]
            best = max(s for s, _, _ in scored)
            top = [(f, n) for s, f, n in scored if s == best]
            if best >= 2 and len(top) <= 2:
                where = top
        if 1 <= len(where) <= 2:  # a near-unique literal points somewhere; a common one would just add noise
            hits.append(f"{label} is written at " + ", ".join(f"{f}:{n}" for f, n in where))
        if len(hits) >= limit:
            return hits
    for literal in dict.fromkeys(w for w in wanted if len(w) >= 3):
        for path, lines in files:
            for number, text in enumerate(lines, 1):
                if f'"{literal}' in text and "Test" not in path.name:
                    hits.append(f'"{literal}" is written at {path.name}:{number}')
                    break
            if len(hits) >= limit:
                return hits
    return hits


def _literals(value: str) -> list:
    """Source patterns for the literal values inside a recorded value: 14.0.sp, FontWeight(weight=300), #rrggbb."""
    weights = {100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Normal", 500: "Medium", 600: "SemiBold",
               700: "Bold", 800: "ExtraBold", 900: "Black"}
    value = re.sub(r"fonts=\[.*?\]", "", value)  # a font family's own weights aren't the style's values
    found = {}
    for number, unit in re.findall(r"(?<![\w.])(-?\d+(?:\.\d+)?)\.?(sp|dp|em)\b", value):
        n = number[:-2] if number.endswith(".0") else number
        if n.lstrip("-") not in ("0", "NaN"):
            body = re.escape(n.lstrip("-"))
            found[f"{n}{unit}"] = re.compile(rf"(?<![\w.]){body}(?:\.0)?\)?\.{unit}\b")
    for w in re.findall(r"FontWeight\(weight=(\d+)\)", value):
        if int(w) in weights:
            found[f"w{w}"] = re.compile(rf"FontWeight\.{weights[int(w)]}\b")
    for rgb in re.findall(r"#([0-9a-f]{6})", value):
        found[rgb] = re.compile(rf"0x[0-9a-fA-F]{{2}}{rgb}\b", re.I)
    return list(found.values())


def _call_end(lines: list[str], start: int) -> int:
    """Last line of the call that opens on line `start` (1-based), by balancing parentheses."""
    if not 1 <= start <= len(lines):
        return start
    depth, opened = 0, False
    for number in range(start, min(len(lines), start + 60) + 1):
        for ch in re.sub(r'"[^"]*"', "", lines[number - 1].split("//")[0]):
            if ch == "(":
                depth, opened = depth + 1, True
            elif ch == ")":
                depth -= 1
        if opened and depth <= 0:
            return number
    return start


def _literals_match(pattern, value: str) -> bool:
    return any(p.pattern == pattern.pattern for p in _literals(value))


def _best_block(files, literals: list):
    """(file, header line, name) of the one argument block, e.g. `titleMedium = TextStyle(`, holding most of
    these literal values; None when it isn't clear."""
    if len(literals) < 3:
        return None
    indent = lambda s: len(s) - len(s.lstrip())
    scores = {}
    for path, lines in files:
        if "Test" in path.name:
            continue
        for number, text in enumerate(lines):
            if not any(p.search(text) for p in literals):
                continue
            level, lo, hi = indent(text), number, number
            while lo > 0 and lines[lo - 1].strip() and indent(lines[lo - 1]) >= level:
                lo -= 1
            while hi + 1 < len(lines) and lines[hi + 1].strip() and indent(lines[hi + 1]) >= level:
                hi += 1
            if (path.name, lo) not in scores and lo > 0:
                block = lines[lo:hi + 1]
                name = re.match(r"\s*(?:val\s+)?(\w+)\s*[=:(]", lines[lo - 1])
                scores[(path.name, lo)] = (sum(1 for p in literals if any(p.search(s) for s in block)),
                                           name.group(1) if name else "?")
    if not scores:
        return None
    best = max(s for s, _ in scores.values())
    top = [(f, lo, name) for (f, lo), (s, name) in scores.items() if s == best]
    return top[0] if best >= 3 and len(top) == 1 else None


def _context_score(lines: list[str], number: int, context: list, own) -> int:
    """How many of the changed object's other literal values sit in the same argument block as line `number`."""
    indent = lambda s: len(s) - len(s.lstrip())
    level = indent(lines[number - 1])
    lo = hi = number - 1
    while lo > 0 and lines[lo - 1].strip() and indent(lines[lo - 1]) >= level:
        lo -= 1
    while hi + 1 < len(lines) and lines[hi + 1].strip() and indent(lines[hi + 1]) >= level:
        hi += 1
    block = [lines[i] for i in range(lo, hi + 1) if i != number - 1]
    return sum(1 for p in context if p.pattern != own.pattern and any(p.search(s) for s in block))


def load(path: str):
    if str(path).endswith(".gz"):
        import gzip
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    return json.load(open(path, encoding="utf-8"))


def _shape(value: str) -> str:
    """RoundedCornerShape(topStart = CornerSize(size = 8.0.dp), ... all equal) -> RoundedCornerShape(8.0.dp)."""
    def compact(m):
        sizes = re.findall(r"CornerSize\(size = ([^)]+)\)", m.group(0))
        return f"RoundedCornerShape({sizes[0]})" if sizes and len(set(sizes)) == 1 else m.group(0)
    return re.sub(r"RoundedCornerShape\(topStart = CornerSize\(size = [^)]+\), topEnd = CornerSize\(size = [^)]+\), "
                  r"bottomEnd = CornerSize\(size = [^)]+\), bottomStart = CornerSize\(size = [^)]+\)\)", compact, value)


def _chain_elements(chain: str) -> list[str]:
    """Splits a modifier chain at top-level dots: padding(16.0.dp).background(#fff) -> 2 elements."""
    parts, depth, current = [], 0, ""
    for ch in chain:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "." and depth == 0 and current and current[-1] == ")":
            parts.append(current)
            current = ""
            continue
        current += ch
    if current:
        parts.append(current)
    return parts


def _chain_change(old: str, new: str) -> tuple[str, str]:
    """Only the modifier elements that differ, so the reader sees clip(...) -> clip(...), not the whole chain."""
    import difflib
    a, b = _chain_elements(old), _chain_elements(new)
    if sorted(a) == sorted(b) and a != b:
        def names(chain):
            return ".".join(e.split("(")[0] for e in chain)
        return f"order {names(a)}", f"order {names(b)}"
    removed, added = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op != "equal":
            removed += a[i1:i2]
            added += b[j1:j2]
    return ".".join(removed) or "(none)", ".".join(added) or "(none)"


def _key_text(key) -> str:
    return "/".join(f"{name}#{index}" for name, index in key)


def noise(before, after) -> list[str]:
    """Values that differ between two runs of unchanged code: '<path>|<param>' entries to ignore later."""
    found = []
    for key, ga, gb, _ in _walk_pairs(_roots(before), _roots(after)):
        if ga is None or gb is None:
            continue
        pa = _values(ga)
        pb = _values(gb)
        found += [f"{_key_text(key)}|{n}" for n in set(pa) | set(pb) if pa.get(n) != pb.get(n)]
    return sorted(set(found))


def _values(g) -> dict[str, str]:
    values = {p["name"]: _decode(p["name"], p["value"]) for p in g["params"]}
    if not values:
        values = {f"value {i + 1}": _decode(f"value {i + 1}", v) for i, v in enumerate(g.get("data", []))}
    if g.get("modifiers"):
        values["modifier chain"] = _decode("modifier chain", g["modifiers"])
    return values


def diff(before, after, regions: list[tuple[int, int, int, int]] | None = None,
         user_files: set[str] | None = None, ignore: set[str] | None = None) -> list[SlotChange]:
    """Parameter, modifier, layout and structure changes between two slot dumps, outermost first.

    [regions] (x, y, w, h) limits layout-only changes to composables that overlap a changed area;
    [user_files] attributes changes inside library code to the nearest call site in the project.
    """
    walked = _walk_pairs(_roots(before), _roots(after))
    by_key = {k: (ga, gb, d) for k, ga, gb, d in walked}
    changes: list[SlotChange] = []
    reported: dict[tuple, set] = {}

    def site(key, g, depth):
        if not user_files or g["file"] in user_files:
            return g, depth, ""
        for cut in range(len(key) - 1, 0, -1):
            entry = by_key.get(key[:cut])
            if not entry:
                continue
            anc = entry[1] or entry[0]
            if anc["file"] in user_files:
                inner = f"{g['name']} at {g['file']}:{g['line']}" if g["line"] > 0 and g["name"] else ""
                return anc, entry[2], f" (inside {inner})" if inner else ""
        return g, depth, ""

    def overlaps(bounds) -> bool:
        if not regions:
            return True
        l, t, r, btm = bounds
        return any(l < x + w + 8 and x - 8 < r and t < y + h + 8 and y - 8 < btm for x, y, w, h in regions)

    for key, ga, gb, depth in sorted(walked, key=lambda w: (w[3], w[0])):
        if ga is None or gb is None:
            g = gb or ga
            if not (g["file"] and g["name"]):
                g = _first_named(g, user_files) or g
            if g["file"] and g["name"]:
                at, at_depth, via = site(key, g, depth)
                what = "added" if ga is None else "removed"
                label = _signature(g).split("|")[1]
                # The enclosing row/item says *which* one: 'Badge added in "Design review: onboarding"'.
                for cut in range(len(key) - 1, 0, -1):
                    entry = by_key.get(key[:cut])
                    anc = entry and (entry[1] or entry[0])
                    anc_label = anc and _signature(anc).split("|")[1]
                    if anc_label and anc_label != label:
                        what += f' in "{anc_label}"'
                        break
                changes.append(SlotChange(at["file"], at["line"], at["name"], tuple(g["bounds"]),
                                          f"{g['name']} {what}{' (' + label + ')' if label else ''}{via if at is not g else ''}",
                                          at_depth))
            continue
        # Newer Compose compilers' parameter metadata isn't readable by ui-tooling-data, but the values the
        # composer remembered are; _values() falls back to comparing them by position.
        pa, pb = _values(ga), _values(gb)
        if (ga.get("modifiers") or gb.get("modifiers")) and "modifier chain" not in pa:
            pa["modifier chain"] = ""
        if (ga.get("modifiers") or gb.get("modifiers")) and "modifier chain" not in pb:
            pb["modifier chain"] = ""
        for name in sorted(set(pa) | set(pb)):
            old, new = _shape(pa.get(name, "(default)")), _shape(pb.get(name, "(default)"))
            if old == new or "λ" in (old, new) or _LAMBDA.search(old) or _LAMBDA.search(new):
                continue
            if min(len(old), len(new)) >= 1900 and old[:1800] == new[:1800]:
                continue  # both cut off by the recorder; the visible part is identical
            if ignore and f"{_key_text(key)}|{name}" in ignore:
                continue
            if any((name, new) in reported.get(key[:cut], ()) or (new,) in reported.get(key[:cut], ())
                   for cut in range(1, len(key))):
                continue
            reported.setdefault(key, set()).update({(name, new), (new,)})
            if name in ("modifier", "modifier chain"):
                o, n = _chain_change(old, new)
                o, n = _shape(o), _shape(n)
            else:
                o, n = old, new
            o, n = _short(o, n)
            at, at_depth, via = site(key, gb, depth)
            chain = tuple((e[1] or e[0])["file"] and ((e[1] or e[0])["file"], (e[1] or e[0])["line"])
                          for e in (by_key.get(key[:cut]) for cut in range(1, len(key) + 1)) if e)
            item = _item_label(by_key, key)
            where = f' in "{item}"' if item and item not in (o + n) else ""
            changes.append(SlotChange(at["file"], at["line"], at["name"] or "(group)", tuple(at["bounds"]),
                                      f"{name}: {o} -> {n}{via}{where}", at_depth,
                                      tuple(c for c in chain if c and c[0] in (user_files or {c[0]})), new, old))
    param_sites = {(c.file, c.line, c.name) for c in changes}
    for key, ga, gb, depth in sorted(walked, key=lambda w: (w[3], w[0])):
        if ga is None or gb is None or ga["bounds"] == gb["bounds"] or not gb["file"]:
            continue
        if (gb["file"], gb["line"], gb["name"]) in param_sites or (user_files and gb["file"] not in user_files):
            continue
        if not overlaps(gb["bounds"]) or not any(ga["bounds"]):
            continue
        l0, t0, r0, b0 = ga["bounds"]
        l1, t1, r1, b1 = gb["bounds"]
        parts = []
        if (l1 - l0, t1 - t0) != (0, 0):
            parts.append(f"moved ({l1 - l0:+d}, {t1 - t0:+d})px")
        if (r1 - l1, b1 - t1) != (r0 - l0, b0 - t0):
            parts.append(f"size {r0 - l0}x{b0 - t0} -> {r1 - l1}x{b1 - t1}px")
        changes.append(SlotChange(gb["file"], gb["line"], gb["name"] or "(group)", tuple(gb["bounds"]),
                                  "layout " + ", ".join(parts), depth + 1000))
    changes.sort(key=lambda c: c.depth)
    return changes


def explain(changes: list[SlotChange], user_files: set[str] | None = None, limit: int = 6) -> list[str]:
    """Cause lines for a report; with [user_files], library internals are skipped."""
    shown = [c for c in changes if not user_files or c.file in user_files]
    seen, unique = set(), []
    for c in shown:  # one line per call site and detail
        if (c.file, c.line, c.detail) not in seen:
            seen.add((c.file, c.line, c.detail))
            unique.append(c)
    shown = unique
    direct = {(c.file, c.line) for c in shown if "(inside " not in c.detail and not c.detail.startswith("layout")}
    shown = [c for c in shown if "(inside " not in c.detail or (c.file, c.line) not in direct]
    # The same edit in every row of a list: one line, with the row count.
    rows: dict[tuple, list[SlotChange]] = {}
    for c in shown:
        rows.setdefault((c.file, c.line, _ROW.sub("", c.detail)), []).append(c)
    lines = []
    for (file, line, detail), group in rows.items():
        first = group[0]
        text = str(first) if len(group) == 1 else f"{str(first)} (+{len(group) - 1} more rows)"
        lines.append((first, text))
    params = [x for x in lines if not x[0].detail.startswith("layout") and not _reordered(x[0])]
    shuffled = [x for x in lines if not x[0].detail.startswith("layout") and _reordered(x[0])]
    layout = [x for x in lines if x[0].detail.startswith("layout")]
    # Only the outermost few layout effects: everything inside a moved box moves too. Lists that only
    # changed order (shuffled sample data) come last.
    return [text for _, text in (params + layout[:3] + shuffled)[:limit]]


_ROW = re.compile(r' in "[^"]*"$')


def _reordered(c: SlotChange) -> bool:
    """A long list value whose elements only changed order, e.g. sample data built with shuffled()."""
    if len(c.new) < 200 or "[" not in c.new:
        return False
    from collections import Counter
    return c.old != c.new and Counter(c.old) == Counter(c.new)
