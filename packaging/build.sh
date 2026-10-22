#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="${REPO_ROOT}/dist"
BUILD_ROOT="${TMPDIR:-/tmp}/keyboarddm-pyinstaller-build-${UID}"
BUILD_VENV="${TMPDIR:-/tmp}/keyboarddm-build-venv-${UID}"

cd "${REPO_ROOT}"

if [[ "$(uname -m)" != "x86_64" ]]; then
    echo "ERROR: KeyboardDM Linux preview must be built on x86_64 (found $(uname -m))." >&2
    exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required to create the isolated build environment." >&2
    exit 1
fi

rm -rf -- "${BUILD_ROOT}" "${BUILD_VENV}"
python3 -m venv "${BUILD_VENV}"
"${BUILD_VENV}/bin/python" -m pip install --disable-pip-version-check \
    --requirement "${REPO_ROOT}/requirements.txt" \
    "PySide6==6.12.0" "pyserial==3.5" "pyinstaller==6.22.3"

mkdir -p "${DIST_DIR}" "${BUILD_ROOT}/work" "${BUILD_ROOT}/spec"
rm -f -- "${DIST_DIR}/KeyboardDM" "${DIST_DIR}/VERSION.txt" \
    "${DIST_DIR}/SHA256SUMS" "${DIST_DIR}"/KeyboardDM-*-linux-x86_64.tar.gz

"${BUILD_VENV}/bin/pyinstaller" \
    --noconfirm \
    --clean \
    --onefile \
    --name KeyboardDM \
    --paths "${REPO_ROOT}" \
    --distpath "${DIST_DIR}" \
    --workpath "${BUILD_ROOT}/work" \
    --specpath "${BUILD_ROOT}/spec" \
    "${SCRIPT_DIR}/entry.py"
chmod 0755 "${DIST_DIR}/KeyboardDM"

COMMIT_SHA="$(git rev-parse HEAD)"
SHORT_SHA="$(git rev-parse --short=7 HEAD)"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
PYTHON_VERSION="$("${BUILD_VENV}/bin/python" -c 'import platform; print(platform.python_version())')"
QT_VERSION="$("${BUILD_VENV}/bin/python" -c 'from PySide6.QtCore import qVersion; print(qVersion())')"

cat > "${DIST_DIR}/VERSION.txt" <<EOF
App: Keyboard DM
Commit: ${COMMIT_SHA}
Build date (UTC): ${BUILD_DATE}
Host architecture: $(uname -m)
Python: ${PYTHON_VERSION}
Qt: ${QT_VERSION}
EOF

(
    cd "${DIST_DIR}"
    sha256sum KeyboardDM > SHA256SUMS
)

ARCHIVE_NAME="KeyboardDM-${SHORT_SHA}-linux-x86_64.tar.gz"
STAGE_DIR="${BUILD_ROOT}/archive"
mkdir -p "${STAGE_DIR}"
install -m 0755 "${DIST_DIR}/KeyboardDM" "${STAGE_DIR}/KeyboardDM"
install -m 0644 "${DIST_DIR}/VERSION.txt" "${STAGE_DIR}/VERSION.txt"
install -m 0644 "${DIST_DIR}/SHA256SUMS" "${STAGE_DIR}/SHA256SUMS"
tar --sort=name --owner=0 --group=0 --numeric-owner \
    --mtime="@${SOURCE_DATE_EPOCH:-$(git show -s --format=%ct HEAD)}" \
    -C "${STAGE_DIR}" -cf - KeyboardDM VERSION.txt SHA256SUMS \
    | gzip -n > "${DIST_DIR}/${ARCHIVE_NAME}"

echo "Built ${DIST_DIR}/KeyboardDM"
echo "Archive ${DIST_DIR}/${ARCHIVE_NAME}"
cat "${DIST_DIR}/SHA256SUMS"
