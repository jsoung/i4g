#!/usr/bin/env bash
# Optional pre-commit hook: warns about large fenced code blocks in docs.
# Install by symlinking into .git/hooks/:
#   ln -sf ../../scripts/git-hooks/check-doc-snippets.sh .git/hooks/pre-commit
# By default this prints warnings and exits 0. Set FAIL_ON_DOC_SNIPPET=1 to make it fail.

PYTHON=python3
REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$REPO_ROOT" || exit 1

$PYTHON scripts/check_docs_snippets.py --max-lines 100 --report reports/docs_snippet_report.txt || true
if [ -f reports/docs_snippet_report.txt ]; then
  echo "\n⚠️ Large fenced code blocks detected in docs (see reports/docs_snippet_report.txt):\n"
  sed -n '1,200p' reports/docs_snippet_report.txt || true
  if [ "$FAIL_ON_DOC_SNIPPET" = "1" ]; then
    echo "Failing commit because FAIL_ON_DOC_SNIPPET=1 is set."
    exit 1
  fi
fi
exit 0
