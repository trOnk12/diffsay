"""Real-source mutation benchmark: patch a screen, run Roborazzi compare, keep outputs, restore."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

APP = Path(os.environ.get("DIFFSAY_SAMPLE_APP", "sample-app"))  # a Compose app built from sample-src
SRC = APP / "app/src/main/java/dev/sample"
OUT = Path(os.environ.get("DIFFSAY_BENCH_OUT", "realbench"))

# (id, screen test, file, old, new, expected cause keyword(s) — any must appear in a top cause line)
MUTATIONS = [
    ("S01", "settings", "SettingsScreen.kt", 'TopAppBar(title = { Text("Settings") })', 'TopAppBar(title = { Text("Preferences") })', ["Preferences"]),
    ("S02", "settings", "SettingsScreen.kt", "fontSize = 12.sp,", "fontSize = 14.sp,", ["14sp", "fontSize"]),
    ("S03", "settings", "SettingsScreen.kt", "color = Color(0xFF1565C0),", "color = Color(0xFF2E7D32),", ["#2e7d32"]),
    ("S04", "settings", "SettingsScreen.kt", "color = Color(0xFFE0E0E0))", "color = Color(0xFF9E9E9E))", ["#9e9e9e"]),
    ("S05", "settings", "SettingsScreen.kt", "HorizontalDivider(Modifier.padding(horizontal = 16.dp)", "HorizontalDivider(Modifier.padding(horizontal = 0.dp)", ["0.0.dp", "padding"]),
    ("S06", "settings", "SettingsScreen.kt", "Switch(checked = false, onCheckedChange = {})", "Switch(checked = true, onCheckedChange = {})", ["checked"]),
    ("S07", "settings", "SettingsScreen.kt", "Spacer(Modifier.height(24.dp))", "Spacer(Modifier.height(48.dp))", ["48.0.dp"]),
    ("S08", "settings", "SettingsScreen.kt", 'Text("Sign out", color = Color(0xFFD32F2F))', 'Text("Sign out", color = Color(0xFF616161))', ["#616161"]),
    ("S09", "settings", "SettingsScreen.kt", '''            ListItem(
                headlineContent = { Text("Privacy") },
                supportingContent = { Text("Blocked users, visibility") },
                leadingContent = { Icon(Icons.Filled.Lock, contentDescription = null) },
            )
''', "", ["removed", "Privacy"]),
    ("S10", "settings", "SettingsScreen.kt", '''headlineContent = { Text("Dark mode") },''', '''headlineContent = { Text("Dark mode") },
                leadingContent = { Icon(Icons.Filled.Lock, contentDescription = null) },''', ["added", "leadingContent", "Icon"]),
    ("P11", "profile", "ProfileScreen.kt", "Modifier.size(88.dp)", "Modifier.size(72.dp)", ["72.0.dp"]),
    ("P12", "profile", "ProfileScreen.kt", "background(Color(0xFF7E57C2))", "background(Color(0xFF26A69A))", ["#26a69a"]),
    ("P13", "profile", "ProfileScreen.kt", ".clip(CircleShape)", ".clip(RoundedCornerShape(16.dp))", ["clip", "RoundedCornerShape"]),
    ("P14", "profile", "ProfileScreen.kt", 'Text("Ada Lovelace", fontSize = 24.sp', 'Text("Ada Lovelace", fontSize = 26.sp', ["26sp"]),
    ("P15", "profile", "ProfileScreen.kt", "fontSize = 24.sp, fontWeight = FontWeight.SemiBold", "fontSize = 24.sp, fontWeight = FontWeight.Bold", ["weight=700"]),
    ("P16", "profile", "ProfileScreen.kt", 'Text("Analyst · London", fontSize = 14.sp, color = Color(0xFF757575))', 'Text("Analyst · London", fontSize = 14.sp, color = Color(0xFF424242))', ["#424242"]),
    ("P17", "profile", "ProfileScreen.kt", "horizontalArrangement = Arrangement.SpaceEvenly", "horizontalArrangement = Arrangement.SpaceBetween", ["SpaceBetween", "Arrangement"]),
    ("P18", "profile", "ProfileScreen.kt", 'Stat("4.2k", "Followers")', 'Stat("4.3k", "Followers")', ["4.3k"]),
    ("P19", "profile", "ProfileScreen.kt", "Arrangement.spacedBy(8.dp)", "Arrangement.spacedBy(12.dp)", ["spacedBy", "12"]),
    ("P20", "profile", "ProfileScreen.kt", "shape = RoundedCornerShape(20.dp)", "shape = RoundedCornerShape(8.dp)", ["8.0.dp"]),
    ("P21", "profile", "ProfileScreen.kt", '''                AssistChip(onClick = {}, label = { Text("Math") })
                AssistChip(onClick = {}, label = { Text("Engines") })
                AssistChip(onClick = {}, label = { Text("Poetry") })''', '''                AssistChip(onClick = {}, label = { Text("Poetry") })
                AssistChip(onClick = {}, label = { Text("Math") })
                AssistChip(onClick = {}, label = { Text("Engines") })''', ["Poetry"]),
    ("F22", "feed", "FeedScreen.kt", "Card(shape = RoundedCornerShape(10.dp)", "Card(shape = RoundedCornerShape(16.dp)", ["16.0.dp"]),
    ("F23", "feed", "FeedScreen.kt", "contentPadding = PaddingValues(16.dp)", "contentPadding = PaddingValues(12.dp)", ["contentPadding", "12.0.dp"]),
    ("F24", "feed", "FeedScreen.kt", "Arrangement.spacedBy(10.dp)", "Arrangement.spacedBy(16.dp)", ["spacedBy", "verticalArrangement", "16.0.dp"]),
    ("F25", "feed", "FeedScreen.kt", "Text(post.title, fontSize = 16.sp)", "Text(post.title, fontSize = 17.sp)", ["17sp"]),
    ("F26", "feed", "FeedScreen.kt", "color = Color(0xFF6B7280))", "color = Color(0xFF374151))", ["#374151"]),
    ("F27", "feed", "FeedScreen.kt", "Badge(containerColor = Color(0xFFE53935))", "Badge(containerColor = Color(0xFFFB8C00))", ["#fb8c00"]),
    ("F28", "feed", "FeedScreen.kt", "containerColor = Color(0xFF00897B),", "containerColor = Color(0xFF3949AB),", ["#3949ab"]),
    ("F29", "feed", "FeedScreen.kt", ".align(Alignment.BottomEnd).padding(20.dp)", ".align(Alignment.BottomEnd).padding(28.dp)", ["28.0.dp"]),
    ("F30", "feed", "FeedScreen.kt", 'Post("Hiring update", "People", false)', 'Post("Hiring update: Q3", "People", false)', ["Hiring update: Q3"]),
    ("F31", "feed", "FeedScreen.kt", 'Post("Design review: onboarding", "Design", false)', 'Post("Design review: onboarding", "Design", true)', ["added", "Badge", "unread=true"]),
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
