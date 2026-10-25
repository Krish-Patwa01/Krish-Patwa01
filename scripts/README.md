# scripts

Not part of the published profile — these generate the SVGs the profile
README embeds from `svg/`.

| script | runs | needs |
|---|---|---|
| `generate_portrait.py` | once, locally, when you change the photo | pillow, numpy, opencv-python-headless, rembg, onnxruntime, fonttools |
| `generate_headings.py` | once, locally, when you change section wording | fonttools |
| `build_font_subsets.py` | once, locally, when you change the data-graphic charset | fonttools |
| `generate_stats.py` | nightly, in GitHub Actions (`.github/workflows/refresh-stats.yml`) | **stdlib only** |

`generate_stats.py` is deliberately dependency-free — it's the one that runs
unattended in CI every night, and a third-party package breaking there is
exactly the failure mode this whole setup exists to avoid. It reads the
already-built `fonts/subset-*.woff2` files rather than re-subsetting on every
run.

To regenerate everything locally:

```bash
pip install pillow numpy opencv-python-headless rembg onnxruntime fonttools brotli
python generate_portrait.py ../assets/source-photo.png --cols 90
python generate_headings.py
python build_font_subsets.py
GITHUB_TOKEN=... GH_LOGIN=your-username python generate_stats.py
```

`assets/source-photo.png` is gitignored on purpose — only the generated
SVG ever gets committed, never the source photo.
