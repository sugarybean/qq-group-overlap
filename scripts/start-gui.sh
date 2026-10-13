#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

exec env PYTHONPATH=src python3 -m qq_group_overlap.gui "$@"
