#!/usr/bin/env bash
set -euo pipefail

export MODE=paper
python -m prod_core.runner "$@"
