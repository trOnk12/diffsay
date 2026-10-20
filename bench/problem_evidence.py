"""Counts golden-screenshot churn in public Android repos (numbers in docs/problem.md).

    python problem_evidence.py /tmp/evidence     # blobless clones, ~1 min
"""
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPOS = {
    "android/nowinandroid": ("*/screenshots/*.png", None, r"updates? screenshots"),
    "element-hq/element-x-android": ("tests/uitests/src/test/snapshots/*", "2025-01-01", r"updates? screenshots"),
}


def churn(repo_dir: Path, pathspec: str, since: str | None, bot: str) -> None:
    args = ["git", "-C", str(repo_dir), "log", "--format=C|%h|%an|%s", "--name-only"]
    if since:
        args.append(f"--since={since}")
    lines = subprocess.run(args + ["--", pathspec], capture_output=True, text=True, check=True).stdout.splitlines()
    commits, files, kinds = 0, Counter(), Counter()
    current = None
    for line in lines:
        if line.startswith("C|"):
            _, h, author, subject = line.split("|", 3)
            commits += 1
            s, a = subject.lower(), author.lower()
            current = ("bot re-record" if re.search(bot, s) else
                       "dependency bump" if "renovate" in a or "dependabot" in a or re.search(r"\b(bump|update dependenc|upgrade)", s)
                       else "other")
        elif line.strip() and current:
            files[current] += 1
    total = sum(files.values())
    print(f"{repo_dir.name}: {commits} commits, {total} golden changes")
    for kind, n in files.most_common():
        print(f"  {kind}: {n} ({n / total:.0%})")


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "evidence")
    out.mkdir(exist_ok=True)
    for repo, (spec, since, bot) in REPOS.items():
        d = out / repo.split("/")[1]
        if not d.exists():
            subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout",
                            f"https://github.com/{repo}", str(d)], check=True)
        churn(d, spec, since, bot)
