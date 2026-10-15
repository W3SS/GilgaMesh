#!/usr/bin/env bash
# Inicia as sessões `claude remote-control` (usado manualmente e pelo serviço de boot).
set -euo pipefail
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
mesh_start_claude
