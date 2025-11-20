#!/usr/bin/env python3
"""
Scan markdown files for large fenced code blocks and report findings.

Usage: python scripts/check_docs_snippets.py --max-lines 100

This script writes a summary to `reports/docs_snippet_report.txt` and
exits with 0 so it can be used as a non-blocking check in CI. It prints
results to stdout.
"""
import argparse
import re
from pathlib import Path

FENCE_RE = re.compile(r"^(```+)([^\n]*)$")


def scan_file(path: Path, max_lines: int):
    findings = []
    with path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    n = len(lines)
    while i < n:
        m = FENCE_RE.match(lines[i].rstrip("\n"))
        if m:
            fence = m.group(1)
            lang = m.group(2).strip()
            start = i
            i += 1
            # find closing fence
            while i < n and not lines[i].rstrip("\n").startswith(fence):
                i += 1
            # i now at closing fence or EOF
            end = i
            block_lines = end - start - 1
            if block_lines >= max_lines:
                findings.append(
                    {
                        "file": str(path),
                        "start_line": start + 1,
                        "end_line": end + 1,
                        "lines": block_lines,
                        "lang": lang,
                    }
                )
        i += 1
    return findings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-lines", type=int, default=100)
    parser.add_argument("--paths", nargs="*", default=["docs", "*/docs", "**/docs"])
    parser.add_argument("--report", type=str, default="reports/docs_snippet_report.txt")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    md_files = set()
    # collect markdown files under docs/ in all workspace roots and top-level
    for pattern in ["docs/**/*.md", "**/docs/**/*.md", "**/*.md"]:
        for p in root.glob(pattern):
            # skip .git and node_modules
            if any(part in (".git", "node_modules") for part in p.parts):
                continue
            md_files.add(p)

    findings_all = []
    for md in sorted(md_files):
        findings = scan_file(md, args.max_lines)
        findings_all.extend(findings)

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    if not findings_all:
        print("No large fenced code blocks found.")
        if report_path.exists():
            report_path.unlink()
        return 0

    with report_path.open("w", encoding="utf-8") as out:
        out.write("Large fenced code blocks (>={})\n\n".format(args.max_lines))
        for f in findings_all:
            line = f"{f['file']}:{f['start_line']}-{f['end_line']} ({f['lines']} lines) language='{f['lang']}'\n"
            out.write(line)
            print(line.strip())

    print(f"Wrote report to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
