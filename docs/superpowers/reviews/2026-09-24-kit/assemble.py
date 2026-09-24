"""Rebuild the review document from the header, the baseline and the pass reports."""
import pathlib, re, sys
S = pathlib.Path(sys.argv[1]); out = pathlib.Path(sys.argv[2])
order = ["1","2","3","4","5","6","7","8","9","10","11","12","13a","13b","sweep-code","sweep-docs"]
parts = [(S / "header.md").read_text(encoding="utf-8"), (S / "baseline.md").read_text(encoding="utf-8")]
if (S / "summary.md").exists(): parts.append((S / "summary.md").read_text(encoding="utf-8"))
for p in order:
    f = S / "reports" / f"pass-{p}.md"
    if not f.exists(): continue
    t = f.read_text(encoding="utf-8", newline="
")
    v = S / "reports" / f"verify-{p}.md"
    if v.exists(): t = t.rstrip() + "\n\n" + v.read_text(encoding="utf-8", newline="
")
    parts.append(t)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n\n".join(x.strip() for x in parts) + "\n", encoding="utf-8", newline="\n")
