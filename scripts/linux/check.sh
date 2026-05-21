#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"

activate_project_venv
python receiver.py --self-test "LINUX SELF TEST"

cat <<'EOF'

The Python protocol self-test passed without using speakers or a microphone.
Use bash scripts/linux/list_devices.sh before the first audio demo.
EOF
