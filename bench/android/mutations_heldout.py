"""Real-source mutation benchmark: patch a screen, run Roborazzi compare, keep outputs, restore."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

APP = Path(os.environ.get("DIFFSAY_SAMPLE_APP", "sample-app"))  # a Compose app built from sample-src
SRC = APP / "app/src/main/java/dev/sample"
OUT = Path(os.environ.get("DIFFSAY_BENCH_OUT", "realbench_heldout"))

# (id, screen test, file, old, new, expected cause keyword(s) — any must appear in a top cause line)
MUTATIONS = [
    ("L01", "login", "LoginScreen.kt", 'Text("Welcome back", style = MaterialTheme.typography.headlineMedium)', 'Text("Welcome back", style = MaterialTheme.typography.headlineSmall)', ["style", "fontSize", "24"]),
    ("L02", "login", "LoginScreen.kt", 'color = Color(0xFF6B6B6B),', 'color = Color(0xFF9E9E9E),', ["#9e9e9e"]),
    ("L03", "login", "LoginScreen.kt", 'padding(horizontal = 28.dp, vertical = 40.dp)', 'padding(horizontal = 20.dp, vertical = 40.dp)', ["20.0.dp", "padding"]),
    ("L04", "login", "LoginScreen.kt", 'label = { Text("Email") }', 'label = { Text("Email address") }', ["Email address"]),
    ("L05", "login", "LoginScreen.kt", 'OutlinedTextField(value = "ada@example.com"', 'OutlinedTextField(value = "ada.lovelace@example.com"', ["ada.lovelace@example.com"]),
    ("L06", "login", "LoginScreen.kt", 'horizontalArrangement = Arrangement.End', 'horizontalArrangement = Arrangement.Start', ["Arrangement", "Start", "moved"]),
    ("L07", "login", "LoginScreen.kt", 'Button(onClick = {}, enabled = true', 'Button(onClick = {}, enabled = false', ["enabled"]),
    ("L08", "login", "LoginScreen.kt", 'fillMaxWidth().height(52.dp)', 'fillMaxWidth().height(44.dp)', ["44.0.dp"]),
    ("L09", "login", "LoginScreen.kt", 'border(1.dp, Color(0xFFE0E0E0), RoundedCornerShape(8.dp)).padding(12.dp)', 'padding(12.dp).border(1.dp, Color(0xFFE0E0E0), RoundedCornerShape(8.dp))', ["border", "padding"]),
    ("L10", "login", "LoginScreen.kt", 'Text("New here? Create an account", textAlign = TextAlign.Center, color = Color(0xFF1A73E8))', 'Text("New here? Create an account", textAlign = TextAlign.Center, color = Color(0xFF0B57D0))', ["#0b57d0"]),
    ("D11", "product", "ProductScreen.kt", 'aspectRatio(1.6f)', 'aspectRatio(2.0f)', ["aspectRatio", "2.0"]),
    ("D12", "product", "ProductScreen.kt", 'maxLines = 2, overflow', 'maxLines = 1, overflow', ["maxLines"]),
    ("D13", "product", "ProductScreen.kt", 'tint = Color(0xFFFFB300)', 'tint = Color(0xFFE65100)', ["#e65100"]),
    ("D14", "product", "ProductScreen.kt", 'Text(" 4.6 (212 reviews)"', 'Text(" 4.7 (213 reviews)"', ["4.7 (213 reviews)"]),
    ("D15", "product", "ProductScreen.kt", 'Text("$129.00", fontSize = 26.sp', 'Text("$119.00", fontSize = 26.sp', ["$119.00"]),
    ("D16", "product", "ProductScreen.kt", 'fun ProductScreen(inStock: Boolean = true)', 'fun ProductScreen(inStock: Boolean = false)', ["removed", "In stock"]),
    ("D17", "product", "ProductScreen.kt", 'LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp))', 'LazyRow(horizontalArrangement = Arrangement.spacedBy(14.dp))', ["spacedBy", "14.0.dp", "horizontalArrangement"]),
    ("D18", "product", "ProductScreen.kt", 'selected = size == "M")', 'selected = size == "L")', ["#263238", "color", "L"]),
    ("D19", "product", "ProductScreen.kt", 'shape = RoundedCornerShape(6.dp),', 'shape = RoundedCornerShape(18.dp),', ["18.0.dp"]),
    ("D20", "product", "ProductScreen.kt", 'val SIZES = listOf("XS", "S", "M", "L", "XL")', 'val SIZES = listOf("XS", "S", "M", "L", "XL", "XXL")', ["added", "XXL"]),
    ("I21", "inbox", "InboxScreen.kt", 'CenterAlignedTopAppBar(title = { Text("Inbox") })', 'CenterAlignedTopAppBar(title = { Text("Messages") })', ["Messages"]),
    ("I22", "inbox", "InboxScreen.kt", 'Modifier.size(44.dp).clip(CircleShape)', 'Modifier.size(40.dp).clip(CircleShape)', ["40.0.dp"]),
    ("I23", "inbox", "InboxScreen.kt", 'background(Color(0xFF90CAF9))', 'background(Color(0xFFA5D6A7))', ["#a5d6a7"]),
    ("I24", "inbox", "InboxScreen.kt", 'Spacer(Modifier.width(12.dp))', 'Spacer(Modifier.width(16.dp))', ["16.0.dp", "width"]),
    ("I25", "inbox", "InboxScreen.kt", 'Text(thread.preview, fontSize = 13.sp, color = Color(0xFF757575), maxLines = 1)', 'Text(thread.preview, fontSize = 14.sp, color = Color(0xFF757575), maxLines = 1)', ["14sp"]),
    ("I26", "inbox", "InboxScreen.kt", 'Thread("Alan Turing", "Can machines think? Let\'s discuss tonight", "Yesterday", 0)', 'Thread("Alan Turing", "Can machines think? Let\'s discuss tonight", "Yesterday", 3)', ["added", "Badge", "Alan Turing"]),
    ("I27", "inbox", "InboxScreen.kt", 'Thread("Katherine Johnson", "Trajectory numbers attached", "Mon", 1)', 'Thread("Katherine Johnson", "Trajectory numbers attached", "Tue", 1)', ["Tue"]),
    ("I28", "inbox", "InboxScreen.kt", 'fontWeight = if (thread.unread > 0) FontWeight.Bold else FontWeight.Normal', 'fontWeight = if (thread.unread > 0) FontWeight.SemiBold else FontWeight.Normal', ["weight=600"]),
    ("I29", "inbox", "InboxScreen.kt", 'padding(horizontal = 16.dp, vertical = 10.dp)', 'padding(horizontal = 16.dp, vertical = 14.dp)', ["14.0.dp", "vertical"]),
    ("I30", "inbox", "InboxScreen.kt", 'Text(thread.time, fontSize = 12.sp, color = Color(0xFF9E9E9E))', 'Text(thread.time, fontSize = 12.sp, color = Color(0xFF616161))', ["#616161"]),
]


def gradle(task: str, log: Path) -> int:
    env = {"ANDROID_HOME": "/opt/android-sdk", "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": "/root"}
    import os
    env = {**os.environ, **env}
    return subprocess.run(["timeout", "900", "bash", "./gradlew", task, "--console=plain", "-q"], cwd=APP,
                          stdout=log.open("w"), stderr=subprocess.STDOUT, env=env).returncode


def main() -> None:
    only = set(sys.argv[1:])
    OUT.mkdir(parents=True, exist_ok=True)
    roborazzi = APP / "app/build/outputs/roborazzi"
    if not only or "baseline" in only:
        shutil.rmtree(roborazzi, ignore_errors=True)
        rc = gradle(":app:recordRoborazziDebug", OUT / "record.log")
        print("baseline", rc, flush=True)
        shutil.rmtree(OUT / "baseline", ignore_errors=True)
        shutil.copytree(roborazzi, OUT / "baseline")
    for mid, screen, file, old, new, expect in MUTATIONS:
        if only and mid not in only:
            continue
        path = SRC / file
        original = path.read_text()
        assert original.count(old) == 1, f"{mid}: anchor not unique/absent"
        path.write_text(original.replace(old, new))
        try:
            for f in roborazzi.glob("*_actual*"):
                f.unlink()
            for f in roborazzi.glob("*_compare*"):
                f.unlink()
            rc = gradle(":app:compareRoborazziDebug", OUT / f"{mid}.log")
            dest = OUT / mid
            shutil.rmtree(dest, ignore_errors=True)
            dest.mkdir()
            for f in roborazzi.glob(f"dev.sample.ScreensScreenshotTest.{screen}*"):
                shutil.copy(f, dest / f.name)
            (dest / "meta.json").write_text(json.dumps({"id": mid, "screen": screen, "file": file, "old": old, "new": new,
                                                        "expect": expect, "edited_line": original[:original.index(old)].count("\n") + 1}))
            print(mid, rc, len(list(dest.iterdir())), flush=True)
        finally:
            path.write_text(original)


if __name__ == "__main__":
    main()
