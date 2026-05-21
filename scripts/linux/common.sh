#!/usr/bin/env bash

set -euo pipefail

LINUX_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${LINUX_SCRIPT_DIR}/../.." && pwd)"
VENV_DIR="${VENV_DIR:-${PROJECT_ROOT}/.venv}"

activate_project_venv() {
    if [[ ! -f "${VENV_DIR}/bin/activate" ]]; then
        printf 'Missing Linux virtual environment at %s\n' "${VENV_DIR}" >&2
        printf 'Run: bash scripts/linux/setup.sh\n' >&2
        exit 1
    fi

    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
    cd "${PROJECT_ROOT}"
}
