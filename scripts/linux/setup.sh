#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SKIP_SYSTEM_PACKAGES=false

usage() {
    cat <<'EOF'
Usage: bash scripts/linux/setup.sh [--skip-system-packages]

Default behavior on Debian/Ubuntu:
  1. Install Linux Python, GUI, and PortAudio packages with apt.
  2. Create .venv in the project root.
  3. Install requirements.txt into that virtual environment.
  4. Run the built-in receiver self-test without microphone access.

Use --skip-system-packages when those Linux packages are already installed
or when your distribution does not use apt.
EOF
}

for arg in "$@"; do
    case "${arg}" in
        --skip-system-packages)
            SKIP_SYSTEM_PACKAGES=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'Unknown option: %s\n' "${arg}" >&2
            usage >&2
            exit 2
            ;;
    esac
done

install_apt_packages() {
    local -a apt_command

    if [[ "${EUID}" -eq 0 ]]; then
        apt_command=(apt-get)
    elif command -v sudo >/dev/null 2>&1; then
        apt_command=(sudo apt-get)
    else
        printf 'apt is available, but sudo is missing. Install the listed packages as root or rerun with --skip-system-packages.\n' >&2
        exit 1
    fi

    "${apt_command[@]}" update
    "${apt_command[@]}" install -y \
        python3 \
        python3-pip \
        python3-tk \
        python3-venv \
        libportaudio2 \
        portaudio19-dev
}

if [[ "${SKIP_SYSTEM_PACKAGES}" == false ]]; then
    if command -v apt-get >/dev/null 2>&1; then
        install_apt_packages
    else
        cat <<'EOF'
No apt package manager was found.
Install Python 3, Python venv/pip support, a Matplotlib GUI backend, and
PortAudio with your Linux distribution package manager before continuing.
EOF
    fi
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    printf 'Could not find %s. Install Python 3 or set PYTHON_BIN to its executable.\n' "${PYTHON_BIN}" >&2
    exit 1
fi

"${PYTHON_BIN}" -m venv "${PROJECT_ROOT}/.venv"
# shellcheck disable=SC1091
source "${PROJECT_ROOT}/.venv/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r "${PROJECT_ROOT}/requirements.txt"

cd "${PROJECT_ROOT}"
python receiver.py --self-test "LINUX READY"

cat <<'EOF'

Linux setup finished.
List audio devices next:
  bash scripts/linux/list_devices.sh

Start the audible test in two terminals:
  bash scripts/linux/run_receiver.sh --audible
  bash scripts/linux/run_transmitter.sh --audible --message "HELLO OS LAB"
EOF
