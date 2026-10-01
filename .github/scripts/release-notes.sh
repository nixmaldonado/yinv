#!/usr/bin/env bash
# Print GitHub release notes for VERSION: its CHANGELOG.md section plus an
# install footer. Exits non-zero if the section is missing or empty.
#
#   .github/scripts/release-notes.sh 0.2.0
set -euo pipefail

version="${1:?usage: release-notes.sh VERSION}"

section=$(awk -v hdr="## [$version]" '
  index($0, hdr) == 1 { found = 1; next }
  found && /^## \[/   { exit }
  found               { print }
' CHANGELOG.md | sed -e '/./,$!d')

if [ -z "$section" ]; then
  echo "CHANGELOG.md has no notes under '## [$version]'" >&2
  exit 1
fi

printf '%s\n\n### Install\n- Homebrew: `brew upgrade yinv`\n- PyPI: https://pypi.org/project/yinv/%s/\n' \
  "$section" "$version"
