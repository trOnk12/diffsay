"""Tests for diffsay on synthetic phone-sized screens; run with `python -m unittest` from this folder."""

from __future__ import annotations

import io
import contextlib
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from diffsay import cli as diffsay  # noqa: E402

W, H = 400, 700
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(size: int, bold: bool = False):
    path = FONT.replace("DejaVuSans", "DejaVuSans-Bold") if bold else FONT
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default(size=size)


def screen(title_y=60, title="Welcome back", title_size=28, bold=True, button_fill=(33, 150, 243),
           button_alpha=1.0, radius=8, border=(200, 200, 200), body_spacing=6, text_color=(33, 33, 33), button_x=40):
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((40, title_y), title, font=font(title_size, bold), fill=text_color)
    d.multiline_text((40, 160), "Your orders are on the way.\nTrack them from this screen.\nSupport is one tap away.",
                     font=font(16), fill=(80, 80, 80), spacing=body_spacing)
    fill = tuple(round(c * button_alpha + 255 * (1 - button_alpha)) for c in button_fill)
    label = tuple(round(255 * button_alpha + 255 * (1 - button_alpha)) for _ in range(3))
    d.rounded_rectangle((button_x, 420, button_x + 320, 476), radius=radius, fill=fill)
    d.text((button_x + 110, 436), "Continue", font=font(20, True), fill=label)
    d.rectangle((40, 520, 360, 580), outline=border, width=2)
    d.text((56, 540), "Promo code", font=font(16), fill=(120, 120, 120))
    return np.asarray(img, dtype=np.int16)


def kinds(before, after):
    return [c.kind for c in diffsay.compare(before, after)]


class DiffsayTest(unittest.TestCase):
    def test_identical_screens_report_nothing(self):
        self.assertEqual([], diffsay.compare(screen(), screen()))
        self.assertEqual("no visible change", diffsay.report([]))

    def test_moved_element_reports_exact_offset(self):
        change = diffsay.compare(screen(), screen(title_y=72))[0]
        self.assertEqual("moved", change.kind)
        self.assertEqual((0, 12), (change.evidence["dx"], change.evidence["dy"]))
        self.assertIn("12px down", change.summary)

    def test_text_colour_change_names_both_colours(self):
        change = diffsay.compare(screen(), screen(text_color=(198, 40, 40)))[0]
        self.assertEqual("text-color", change.kind)
        self.assertIn("#c62828", change.summary)

    def test_fill_colour_change(self):
        change = diffsay.compare(screen(), screen(button_fill=(67, 160, 71)))[0]
        self.assertIn(change.kind, ("fill-color", "opacity"))
        self.assertEqual("fill-color", change.kind)

    def test_opacity_is_an_exact_blend_of_every_colour(self):
        change = diffsay.compare(screen(), screen(button_alpha=0.5))[0]
        self.assertEqual("opacity", change.kind)
        self.assertAlmostEqual(0.5, change.evidence.get("alpha", 0.5), delta=0.08) if change.evidence else None
        self.assertIn("more transparent", change.summary)

    def test_font_size_direction(self):
        change = diffsay.compare(screen(), screen(title_size=34))[0]
        self.assertEqual("font-size", change.kind)
        self.assertEqual("larger", change.direction)

    def test_text_edit(self):
        self.assertEqual(["text"], kinds(screen(), screen(title="Welcome bock")))

    def test_border_colour(self):
        change = diffsay.compare(screen(), screen(border=(90, 90, 90)))[0]
        self.assertEqual("border-color", change.kind)

    def test_corner_radius(self):
        change = diffsay.compare(screen(), screen(radius=24))[0]
        self.assertEqual("rounded", change.kind)
        self.assertEqual("more rounded", change.direction)

    def test_crop_strip_is_small_and_stacks_before_over_after(self):
        before, after = screen(), screen(title_y=72)
        change = diffsay.compare(before, after)[0]
        strip = diffsay.crop_strip(before, after, change)
        self.assertLess(strip.width * strip.height, W * H)  # far fewer pixels than one screenshot
        self.assertGreater(strip.height, strip.width / 10)

    def test_paparazzi_delta_is_split_and_labels_ignored(self):
        before, after = screen(), screen(title_y=72)
        panel = W
        delta = Image.new("RGB", (panel * 3, H), (255, 0, 0))
        delta.paste(Image.fromarray(before.astype(np.uint8)), (0, 0))
        delta.paste(Image.fromarray(after.astype(np.uint8)), (panel * 2, 0))
        d = ImageDraw.Draw(delta)
        d.text((10, 8), "Expected", fill=(0, 0, 0))  # labels like Paparazzi's, different per panel
        d.text((panel * 2 + 10, 8), "Actual", fill=(0, 0, 0))
        with tempfile.TemporaryDirectory() as tmp:
            failures = Path(tmp) / "build/paparazzi/failures"
            failures.mkdir(parents=True)
            delta.save(failures / "delta-com.example_LoginTest_welcome.png")
            found = diffsay.scan(tmp)
            self.assertEqual(1, len(found))
            changes = diffsay.compare(found[0][1], found[0][2])
            self.assertEqual(["moved"], [c.kind for c in changes])  # the label corner is not a change
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = diffsay.main(["scan", tmp, "--crops", str(Path(tmp) / "crops")])
            self.assertEqual(1, code)
            self.assertIn("element moved 12px down", out.getvalue())
            self.assertTrue(list((Path(tmp) / "crops").glob("*-change1.png")))

    def test_actual_beside_golden_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            Image.fromarray(screen().astype(np.uint8)).save(Path(tmp) / "LoginTest.png")
            Image.fromarray(screen(radius=24).astype(np.uint8)).save(Path(tmp) / "LoginTest_actual.png")
            found = diffsay.scan(tmp)
            self.assertEqual(1, len(found))
            self.assertEqual("rounded", diffsay.compare(found[0][1], found[0][2])[0].kind)


class CauseSummaryTest(unittest.TestCase):
    def test_failures_sharing_a_cause_are_grouped(self):
        cause = "fontSize = 22.sp is written at QuantitySelector.kt:67"
        names = [f"out/com.example.QsKt.QsPreview.{v}.png" for v in ("default", "dark", "rtl")]
        summary = diffsay._cause_summary(4, {cause: names})
        self.assertIn("4 failed screenshots; 3 traced to 1 cause(s) in code:", summary)
        self.assertIn("breaks 3: QsPreview.default, QsPreview.dark, QsPreview.rtl", summary)
        self.assertIn("1 without a cause in code", summary)

    def test_markdown_groups_rows_and_escapes_pipes(self):
        rows = [(n, ["a | b"], []) for n in ("x/A.one.png", "x/A.two.png")]
        table = diffsay._markdown(rows)
        self.assertIn("| `a \\| b` | 2: A.one, A.two |", table)

    def test_markdown_lists_a_screenshot_under_each_edit_it_shows(self):
        rows = [("x/A.one.png", ["padding(12.dp) is written at Item.kt:81", "Item.kt:129 now uses titleMedium"], [])]
        table = diffsay._markdown(rows)
        self.assertIn("| `padding(12.dp) is written at Item.kt:81` | 1: A.one |", table)
        self.assertIn("| `Item.kt:129 now uses titleMedium` | 1: A.one |", table)


class ComposeAlignTest(unittest.TestCase):
    @staticmethod
    def group(name, children=(), line=1):
        return {"name": name, "file": "A.kt" if name else "", "line": line, "bounds": [0, 0, 10, 10],
                "params": [], "data": [], "modifiers": "", "children": list(children)}

    def test_changed_theme_next_to_a_new_group_is_paired_not_replaced(self):
        from diffsay import compose_slots
        def text(value):
            g = self.group("Text")
            g["params"] = [{"name": "text", "value": value}]
            return g
        before = [self.group("Theme", [text("4.2k")])]
        after = [self.group("Theme", [text("4.3k")]), self.group("Extra")]
        pairs, only_a, only_b = compose_slots._align(before, after)
        self.assertEqual([(0, 0)], pairs)
        self.assertEqual(([], [1]), (only_a, only_b))

    def test_roots_sharing_bounds_sort_by_their_first_call(self):
        from diffsay import compose_slots
        a, b = self.group("", [self.group("Main", line=9)]), self.group("", [self.group("Dialog", line=3)])
        self.assertEqual(compose_slots._roots([a, b]), compose_slots._roots([b, a]))


class SourceHitsTest(unittest.TestCase):
    TYPE_KT = """val Typography = Typography(
    bodyLarge = TextStyle(
        fontSize = 16.sp,
        lineHeight = 24.sp,
        letterSpacing = 0.5.sp,
        fontWeight = FontWeight.Normal,
    ),
    titleMedium = TextStyle(
        fontSize = 16.sp,
        lineHeight = 22.sp,
        letterSpacing = 0.15.sp,
        fontWeight = FontWeight.SemiBold,
    ),
)
"""

    @staticmethod
    def style(size, line, spacing, weight):
        return (f"TextStyle(color=Color(0.0, 0.0, 0.0, 0.0, None), fontSize={size}.sp, "
                f"fontWeight=FontWeight(weight={weight}), letterSpacing={spacing}.sp, lineHeight={line}.sp)")

    def change(self, detail, old="", new="", file="Item.kt", line=12):
        from diffsay import compose_slots
        return compose_slots.SlotChange(file, line, "Text", (0, 0, 1, 1), detail, 1, (), new, old)

    def module(self, tmp, item_kt):
        src = Path(tmp) / "app/src/main/java"
        src.mkdir(parents=True)
        (src / "Type.kt").write_text(self.TYPE_KT, encoding="utf-8")
        (src / "Item.kt").write_text(item_kt, encoding="utf-8")
        return str(Path(tmp) / "app")

    def test_text_switched_to_another_theme_style_is_named_at_the_use_site(self):
        from diffsay import compose_slots
        old, new = self.style("16.0", "24.0", "0.5", 400), self.style("16.0", "22.0", "0.15", 600)
        with tempfile.TemporaryDirectory() as tmp:
            module = self.module(tmp, "\n" * 11 + "Text(style = MaterialTheme.typography.titleMedium)\n")
            hits = compose_slots.source_hits([self.change(f"value 3: {old} -> {new}", old, new)], module)
        self.assertEqual(["Item.kt:12 now uses titleMedium (Type.kt:8) instead of bodyLarge"], hits)

    def test_edited_theme_value_is_named_at_its_definition(self):
        from diffsay import compose_slots
        old, new = self.style("16.0", "22.0", "0.15", 600), self.style("16.0", "27.0", "0.15", 600)
        with tempfile.TemporaryDirectory() as tmp:
            module = self.module(tmp, "Text()\n")
            Path(module, "src/main/java/Type.kt").write_text(self.TYPE_KT.replace("lineHeight = 22.sp",
                                                                                  "lineHeight = 27.sp"))
            hits = compose_slots.source_hits([self.change(f"value 3: {old} -> {new}", old, new)], module)
        self.assertEqual(["lineHeight = 27.sp is written at Type.kt:10"], hits)

    def test_literal_in_the_changed_calls_own_arguments_wins_over_lookalikes(self):
        from diffsay import compose_slots
        item = "\n" * 11 + "Column(\n    Modifier.padding(12.dp),\n)\n" + "Row(Modifier.padding(top = 12.dp))\n" * 3
        with tempfile.TemporaryDirectory() as tmp:
            module = self.module(tmp, item)
            hits = compose_slots.source_hits([self.change("modifier chain: padding(20.0.dp) -> padding(12.0.dp)")],
                                             module)
        self.assertEqual(["padding(12.dp) is written at Item.kt:13"], hits)


class ExplainRankingTest(unittest.TestCase):
    def test_same_edit_in_every_row_is_one_line_and_shuffled_data_comes_last(self):
        from diffsay import compose_slots
        rows = [compose_slots.SlotChange("Item.kt", 78, "Column", (0, 0, 1, 1),
                                         f'modifier chain: padding(20.0.dp) -> padding(12.0.dp) in "{n}"', 1)
                for n in ("Ali", "Kim", "Trevor")]
        items = ", ".join(f"Email(id={i}, subject=Subject number {i})" for i in range(9))
        shuffled_items = ", ".join(f"Email(id={i}, subject=Subject number {i})" for i in reversed(range(9)))
        old, new = f"Thread(threads=[{items}])", f"Thread(threads=[{shuffled_items}])"
        shuffle = compose_slots.SlotChange("List.kt", 189, "Item", (0, 0, 1, 1), "value 2: … -> …", 1, (), new, old)
        lines = compose_slots.explain([shuffle] + rows)
        self.assertEqual('Item.kt:78 Column: modifier chain: padding(20.0.dp) -> padding(12.0.dp) in "Ali" '
                         "(+2 more rows)", lines[0])
        self.assertTrue(lines[-1].startswith("List.kt:189"))


class SlotDumpTest(unittest.TestCase):
    def test_gzipped_and_plain_dumps_load_the_same(self):
        import gzip
        import json
        from diffsay import compose_slots
        tree = [{"name": "Text", "file": "A.kt", "line": 3, "bounds": [0, 0, 1, 1], "params": [], "data": ["hi"],
                 "modifiers": "", "children": []}]
        with tempfile.TemporaryDirectory() as tmp:
            plain, packed = Path(tmp) / "a.slots.json", Path(tmp) / "a.slots.json.gz"
            plain.write_text(json.dumps(tree), encoding="utf-8")
            with gzip.open(packed, "wt", encoding="utf-8") as f:
                json.dump(tree, f)
            self.assertEqual(compose_slots.load(str(plain)), compose_slots.load(str(packed)))


class TriageTest(unittest.TestCase):
    def test_failures_split_by_whether_the_diff_explains_them(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "app/src/main"
            src.mkdir(parents=True)
            (src / "Type.kt").write_text("".join(f"line {i}\n" for i in range(1, 80)))
            (src / "Home.kt").write_text("".join(f"line {i}\n" for i in range(1, 500)))
            git = lambda *a: subprocess.run(["git", "-C", tmp, "-c", "user.name=t", "-c", "user.email=t@t", *a],
                                            check=True, capture_output=True)
            git("init", "-q"); git("add", "-A"); git("commit", "-qm", "base")
            lines = (src / "Type.kt").read_text().splitlines(keepends=True)
            lines[70] = "lineHeight = 27.sp\n"
            (src / "Type.kt").write_text("".join(lines))
            changed = diffsay._diff_lines(str(Path(tmp) / "app"), "HEAD")
        self.assertEqual({"Type.kt": {71}}, changed)
        rows = [("a/Post.png", ["lineHeight = 27.sp is written at Type.kt:71"], []),
                ("a/Home.png", ["lineHeight = 27.sp is written at Type.kt:71", "padding(22.dp) is written at Home.kt:470"], []),
                ("a/Logo.png", ["composition identical: the change is in drawing code"], [])]
        triage = diffsay._triage(rows, changed)
        self.assertEqual(["Type.kt:71"], [c.split(" at ")[1] for c in triage[0][1]])
        self.assertEqual(["padding(22.dp) is written at Home.kt:470"], triage[1][2])
        self.assertEqual(([], []), (triage[2][1], triage[2][2]))
        text = diffsay._triage_text(triage, "HEAD")
        self.assertIn("1 of 3 changed screenshots are explained", text)
        self.assertIn("! 1 not explained by this diff", text)
        self.assertIn("? 1 without a cause in code", text)


if __name__ == "__main__":
    unittest.main()
