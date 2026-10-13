#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$project_root/src"

cd "$project_root"
exec python3 -m qq_group_overlap live "$@"
