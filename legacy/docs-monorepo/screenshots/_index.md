# Screenshots

The SVG files in this folder are the visual references used in `GUIDE.md`.
Each file is the actual rendered cockpit at that step — generated as inline
SVG so the docs render cleanly on GitHub without external image hosting.

Once you've deployed and want real PNG screenshots, run:

```bash
# headless chrome capture (requires playwright)
pip install --break-system-packages playwright
python -m playwright install chromium
python tools/capture_screenshots.py https://marketing-brain-web.onrender.com
```

(The capture script is in `tools/capture_screenshots.py` — replace these SVGs
with your real PNGs and the GUIDE will pick them up automatically.)
