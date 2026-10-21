"""Records diffsay slot dumps in Element X's Paparazzi harness, for the previews the AGP 9 PR changed."""
import os, re, shutil
from pathlib import Path
EX = Path(os.environ.get("EX", "element-x-android"))
M = 'maven("https://maven-central.storage-download.googleapis.com/maven2/")'
s = EX / "settings.gradle.kts"; t = s.read_text()
if M not in t:
    t = re.sub(r"(pluginManagement \{\s*repositories \{)", r"\1\n        google()\n        " + M, t, count=1)
    t = re.sub(r"(dependencyResolutionManagement \{.*?repositories \{)", lambda m: m.group(1) + "\n        " + M, t, count=1, flags=re.S)
    s.write_text(t)
for f in EX.glob("plugins/settings.gradle.kts"):
    t = f.read_text()
    if M not in t:
        t = re.sub(r"(repositories \{)", r"\1\n        " + M, t)
        f.write_text(t)
pb = EX / "plugins/build.gradle.kts"; t2 = pb.read_text()
if M not in t2:
    pb.write_text(t2.replace("repositories {\n    mavenCentral()", "repositories {\n    " + M + "\n    mavenCentral()", 1))
ps = EX / "plugins/settings.gradle.kts"; t3 = ps.read_text()
if "pluginManagement" not in t3:
    ps.write_text("pluginManagement {\n    repositories {\n        " + M + "\n        gradlePluginPortal()\n    }\n}\n\n" + t3)
st = EX / "tests/uitests/src/test/kotlin/base/ScreenshotTest.kt"; t = st.read_text()
t = t.replace("        paparazzi.snapshot {", "        paparazzi.snapshotWithCauses {", 1)
if "import dev.diffsay.snapshotWithCauses" not in t:
    t = t.replace("package base\n", "package base\n\nimport dev.diffsay.snapshotWithCauses\n", 1)
st.write_text(t)
cp = EX / "tests/uitests/src/test/kotlin/base/ComposablePreviewProvider.kt"; t = cp.read_text()
only = [l.strip() for l in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ex_classes.txt")) if l.strip()]
if "DIFFSAY_ONLY" not in t:
    t = t.replace("            .filter { composablePreview -> composablePreview.methodName.endsWith(\"A11yPreview\").not() }",
                  "            .filter { composablePreview -> composablePreview.methodName.endsWith(\"A11yPreview\").not() }\n"
                  "            .filter { it.methodName.removeSuffix(\"Preview\") in DIFFSAY_ONLY }", 1)
    t += "\nprivate val DIFFSAY_ONLY = setOf(" + ", ".join(f'"{c}"' for c in only) + ")\n"
    cp.write_text(t)
d = EX / "tests/uitests/src/test/kotlin/dev/diffsay"; d.mkdir(parents=True, exist_ok=True)
for kt in ("SlotRecorder.kt", "PaparazziCauses.kt"):
    shutil.copy(os.path.join(os.environ["DIFFSAY_ANDROID"], kt), d / kt)
b = EX / "tests/uitests/build.gradle.kts"; t = b.read_text()
if "ui-tooling-data" not in t:
    t = t.replace("    testImplementation(libs.test.junit)\n",
                  "    testImplementation(libs.test.junit)\n    testImplementation(platform(libs.androidx.compose.bom))\n"
                  "    testImplementation(\"androidx.compose.ui:ui-tooling-data\")\n", 1)
    b.write_text(t)
(EX / "local.properties").write_text("sdk.dir=/opt/android-sdk\n")
print("patched; DIFFSAY_ONLY", len(only), "previews")
