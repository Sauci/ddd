"""Rebuild the review document from the header, the baseline and the pass reports.

Usage: python assemble.py KIT_DIRECTORY OUTPUT_FILE
"""

import pathlib
import re
import sys

kit = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])


def order(path: pathlib.Path) -> tuple[int, str]:
    number = re.search(r"pass-(\d+)", path.name)
    return (int(number.group(1)), path.name) if number else (10_000, path.name)


parts = [(kit / "header.md").read_text(encoding="utf-8"), (kit / "baseline.md").read_text(encoding="utf-8")]
if (kit / "summary.md").exists():
    parts.append((kit / "summary.md").read_text(encoding="utf-8"))
if (kit / "coordinator-notes.md").exists():
    parts.append((kit / "coordinator-notes.md").read_text(encoding="utf-8"))
for report in sorted((kit / "reports").glob("pass-*.md"), key=order):
    text = report.read_text(encoding="utf-8")
    verdict = report.with_name(report.name.replace("pass-", "verify-"))
    if verdict.exists():
        text = text.rstrip() + "\n\n" + verdict.read_text(encoding="utf-8")
    parts.append(text)
for name in ("sweep-code.md", "sweep-docs.md"):
    sweep = kit / "reports" / name
    if sweep.exists():
        parts.append(sweep.read_text(encoding="utf-8"))
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n\n".join(part.strip() for part in parts) + "\n", encoding="utf-8", newline="\n")
