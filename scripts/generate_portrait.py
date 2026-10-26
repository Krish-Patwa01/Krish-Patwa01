"""
Turns a headshot into a self-typing ASCII portrait SVG.

Pipeline (see the write-up this was built from for why each stage exists):
  1. rembg cut-out      -> everything outside the subject forced to white,
                            which maps to the blank end of the ramp
  2. bilateral filter    -> smooths skin while keeping edges
  3. CLAHE, clip ~3.0     -> local contrast per tile instead of one flat tone
  4. darkening curve      -> (v/255)^1.7, keeps glasses/brows/lips from
                            washing out into mid-gray
  5. map to ramp          -> ' .`:-=+*cs#%@', leading space clears the
                            background to nothing

Output: two SVGs (light-mode ink on transparent, dark-mode ink on
transparent) with a per-row typing animation in SMIL, and the font
subsetted + base64-inlined so it renders identically cross-platform.

Usage:
    python scripts/generate_portrait.py <source-photo> [--cols 90]
"""
from __future__ import annotations

import argparse
import io
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import cv2
import numpy as np
from PIL import Image
from rembg import new_session, remove

# u2net is rembg's classic ~176 MB matting model. It's smaller and faster to
# fetch than the newer default (bria-rmbg, ~1 GB) and plenty for a portrait
# cut-out where everything we need is "forced to white or not".
_REMBG_SESSION = new_session("u2net")

import lib_font

REPO_ROOT = Path(__file__).resolve().parent.parent
RAMP = " .`:-=+*cs#%@"  # light -> dark, 13 levels
FONT_SIZE = 12.9
CHAR_W = round(FONT_SIZE * 0.600, 3)   # 7.74 — the advance width GitHub's
                                         # monospace stack actually renders at
CELL_H = round(CHAR_W / 0.48, 3)        # row height consistent with the
                                         # cols * (h/w) * 0.48 row-count rule
ROW_STAGGER = 0.09   # seconds between each row starting to type
ROW_DUR = 0.30       # seconds for a single row's wipe-in


def cutout_on_white(img_rgb: np.ndarray) -> np.ndarray:
    """rembg cut-out, composited onto solid white so the background maps to
    the blank end of the ramp instead of filling with '@'."""
    pil_in = Image.fromarray(img_rgb)
    buf = io.BytesIO()
    pil_in.save(buf, format="PNG")
    cut = remove(buf.getvalue(), session=_REMBG_SESSION)
    pil_cut = Image.open(io.BytesIO(cut)).convert("RGBA")
    white_bg = Image.new("RGBA", pil_cut.size, (255, 255, 255, 255))
    composited = Image.alpha_composite(white_bg, pil_cut).convert("RGB")
    return np.array(composited)


def to_ascii_grid(img_rgb: np.ndarray, cols: int) -> list[str]:
    h, w = img_rgb.shape[:2]
    rows = max(1, round(cols * (h / w) * 0.48))

    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)

    # smooth skin while keeping edges
    smoothed = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

    # local contrast per tile, so a flatly-lit face doesn't stay one tone
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    contrasted = clahe.apply(smoothed)

    small = cv2.resize(contrasted, (cols, rows), interpolation=cv2.INTER_AREA)

    # darkening curve: push shadows down harder than highlights, so brows/
    # eyes/mouth survive instead of washing into mid-gray
    normalized = (small.astype(np.float64) / 255.0) ** 1.7
    ink = 1.0 - normalized  # 0 = background/white, 1 = full shadow

    ramp_len = len(RAMP)
    indices = np.clip((ink * (ramp_len - 1)).round().astype(int), 0, ramp_len - 1)

    lines = ["".join(RAMP[i] for i in row) for row in indices]
    return lines


def build_svg(lines: list[str], ink_color: str, font_b64: str) -> str:
    cols = max(len(l) for l in lines)
    rows = len(lines)
    width_px = cols * CHAR_W
    height_px = rows * CELL_H
    row_width_px = cols * CHAR_W

    font_face = lib_font.font_face_css("PortraitRamp", font_b64)

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" '
        f'viewBox="0 0 {width_px:.2f} {height_px:.2f}" width="460" '
        f'role="img" aria-label="ASCII portrait">'
    )
    parts.append(f"<style>{font_face}"
                  f"text{{font-family:'PortraitRamp',ui-monospace,monospace;"
                  f"font-size:{FONT_SIZE}px;fill:{ink_color};"
                  # Chrome's SVG2 text layout follows CSS white-space, not
                  # xml:space — without this, runs of leading spaces (which
                  # form the actual silhouette) collapse and every row
                  # slams to x=0, smearing the whole portrait leftward.
                  f"white-space:pre;}}"
                  f".cursor{{fill:{ink_color};}}</style>")

    for i, line in enumerate(lines):
        if not line.strip():
            continue  # fully blank row — nothing to type, nothing to draw
        row_y_top = i * CELL_H
        baseline = row_y_top + CELL_H * 0.80
        begin = round(i * ROW_STAGGER, 3)
        clip_id = f"c{i}"
        text_escaped = xml_escape(line)

        parts.append(f'<clipPath id="{clip_id}">')
        parts.append(
            f'<rect x="0" y="{row_y_top:.2f}" width="0" height="{CELL_H:.2f}">'
            f'<animate attributeName="width" from="0" to="{row_width_px:.2f}" '
            f'begin="{begin}s" dur="{ROW_DUR}s" fill="freeze" calcMode="linear"/>'
            f"</rect>"
        )
        parts.append("</clipPath>")

        parts.append(
            f'<text x="0" y="{baseline:.2f}" clip-path="url(#{clip_id})">'
            f"{text_escaped}</text>"
        )

        # a small block riding the wipe edge as a cursor, freezing away once
        # the row finishes so it reads as travelling down the page
        cursor_w = CHAR_W * 0.55
        cursor_h = CELL_H * 0.75
        cursor_y = row_y_top + CELL_H * 0.12
        parts.append(
            f'<rect class="cursor" x="0" y="{cursor_y:.2f}" '
            f'width="{cursor_w:.2f}" height="{cursor_h:.2f}">'
            f'<animate attributeName="x" from="0" to="{row_width_px:.2f}" '
            f'begin="{begin}s" dur="{ROW_DUR}s" fill="freeze" calcMode="linear"/>'
            f'<animate attributeName="opacity" from="1" to="0" '
            f'begin="{begin + ROW_DUR}s" dur="0.01s" fill="freeze"/>'
            f"</rect>"
        )

    parts.append("</svg>")
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path, help="path to the source headshot")
    ap.add_argument("--cols", type=int, default=90)
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "svg")
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(args.source).convert("RGB")
    img_rgb = np.array(img)

    print(f"[1/4] removing background, compositing onto white...")
    cut = cutout_on_white(img_rgb)

    print(f"[2/4] filtering, contrasting, mapping to {args.cols}-col ramp...")
    lines = to_ascii_grid(cut, args.cols)
    print(f"      -> {len(lines)} rows x {max(len(l) for l in lines)} cols")

    print("[3/4] subsetting + inlining font...")
    used_chars = "".join(sorted(set("".join(lines))))
    font_b64 = lib_font.subset_to_woff2_base64(used_chars or RAMP)

    print("[4/4] writing light/dark SVGs...")
    light_svg = build_svg(lines, ink_color="#1b1f24", font_b64=font_b64)
    dark_svg = build_svg(lines, ink_color="#c9d1d9", font_b64=font_b64)

    (args.out_dir / "portrait-light.svg").write_text(light_svg, encoding="utf-8")
    (args.out_dir / "portrait-dark.svg").write_text(dark_svg, encoding="utf-8")

    # also keep the plain-text grid around — handy for debugging/tuning
    (args.out_dir / "portrait-preview.txt").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    print(f"done -> {args.out_dir / 'portrait-light.svg'}")
    print(f"        {args.out_dir / 'portrait-dark.svg'}")


if __name__ == "__main__":
    main()
