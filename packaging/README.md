# Ubuntu preview packaging

Build the standalone Linux x86_64 preview from the repository root:

```sh
./packaging/build.sh
./packaging/smoke.sh
```

The build creates a fresh temporary virtual environment, installs the runtime
requirements at the preview's pinned versions (PySide6 6.12.0 and pyserial
3.5) plus PyInstaller 6.22.3, and writes `dist/KeyboardDM` plus a
self-describing `dist/KeyboardDM-<commit>-linux-x86_64.tar.gz` archive.

On the target laptop, extract the archive and run the executable. Python and a
virtual environment are not required:

```sh
tar -xzf KeyboardDM-<commit>-linux-x86_64.tar.gz
sha256sum -c SHA256SUMS
./KeyboardDM
```

## Known limitations

- The artifact is Linux x86_64 only. PyInstaller does not cross-compile.
- Linux binaries retain a glibc baseline: an artifact built on this Ubuntu host
  is expected to work on systems with the same or newer glibc, not older ones.
- Firmware installation is simulation-only in this preview; real flash read,
  write, and erase operations remain disabled. USB serial configuration is a
  separate supported interface and may require membership in the laptop's
  serial-device access group (commonly `dialout`).
- This is a portable executable and tarball, not a system installer or AppImage.
