#!/usr/bin/env bash
# Print the Gwyddion release every shipped artifact is built from.
#
# The value lives under [tool.gwyconvert] in ../pyproject.toml, so one edit
# there reaches every build. This is its only reader: nothing else needs to
# know where the key sits or how the file is spelled.
#
# Callers:
#   ci/build-gwyddion.sh          — builds this release
#   .github/workflows/pytest.yml  — reports it beside the version the
#                                   distribution package ships
#
# Upstream releases: https://sourceforge.net/projects/gwyddion/files/gwyddion/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYPROJECT="$SCRIPT_DIR/../pyproject.toml"

# awk, not Python's tomllib: this runs on Rocky 8 and inside manylinux_2_28,
# whose system python3 is 3.6 and parses no TOML. Scoped to the
# [tool.gwyconvert] table so a key of the same name in another table cannot
# be picked up by accident.
version="$(awk '
  /^[[:space:]]*\[/ {
    in_table = ($0 ~ /^[[:space:]]*\[tool\.gwyconvert\][[:space:]]*$/)
    next
  }
  in_table && /^[[:space:]]*gwyddion-version[[:space:]]*=/ {
    if (match($0, /"[^"]*"/)) {
      print substr($0, RSTART + 1, RLENGTH - 2)
      exit
    }
  }
' "$PYPROJECT")"

if [ -z "$version" ]; then
  echo "error: no gwyddion-version under [tool.gwyconvert] in $PYPROJECT." \
       "Every build takes its Gwyddion release from that key; restore it" \
       "rather than hardcoding a version somewhere else." >&2
  exit 1
fi

printf '%s\n' "$version"
