# Third-party notices

LANist vendors the Windows x64 build of tkinterdnd2 so that dragging files into
the host window works without a separate install.

- tkinterdnd2 0.6.4 — https://github.com/pmgagne/tkinterdnd2 — MIT License
- tkdnd 2.10.3 — https://github.com/petasis/tkdnd — Tcl/Tk License

The host window renders the access URL as a QR code with a single-file copy of
Project Nayuki's QR Code generator. It is vendored so the window works without
installing anything and without internet access.

- qrcodegen (Python) — https://github.com/nayuki/QR-Code-generator — MIT License
- File: `lanist/vendor/qrcodegen.py` (about 38 KB)

Space Grotesk is bundled for the browser page title and is served from the
program itself, so the page works without internet access.

- Space Grotesk (variable, latin subsets) — https://github.com/floriankarsten/space-grotesk — SIL Open Font License 1.1
- Files: `lanist/web/fonts/space-grotesk-500.woff2`, `space-grotesk-700.woff2`, `OFL.txt` (about 26 KB total)

The tkdnd Tcl files keep their upstream copyright and permission notice in
their headers. The Python wrapper is used under its upstream MIT license.

If you prefer not to redistribute these binaries, delete `lanist/vendor/` and
install tkinterdnd2 from PyPI instead:

```bash
pip install tkinterdnd2
```
