#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
BINARY="${REPO_ROOT}/dist/KeyboardDM"

if [[ ! -x "${BINARY}" ]]; then
    echo "ERROR: built executable not found at ${BINARY}; run packaging/build.sh first." >&2
    exit 1
fi

if env -u VIRTUAL_ENV -u PYTHONPATH QT_QPA_PLATFORM=offscreen \
    "${BINARY}" --smoke; then
    echo "Packaged KeyboardDM smoke test succeeded without a build venv."
else
    status=$?
    echo "ERROR: packaged KeyboardDM smoke test failed (exit ${status})." >&2
    exit "${status}"
fi
