"""
Section headings as SVG — the only way to put a custom typeface on a
heading, since GitHub strips <style>, class, and <font> from README HTML.
Lowercase mono label with a hairline rule running to the right edge.

These are static: run once per wording change, not nightly. (Image headings
have no anchor links, so GitHub's README outline stays empty for them —
that's a fixed trade, not a bug to chase.)

Usage:
    python scripts/generate_headings.py
"""
from __future__ import annotations

from pathlib import Path

import lib_font
import lib_svg

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "svg"

FONT_SIZE = 13
CHAR_W = round(FONT_SIZE * 0.600, 3)
RULE_PAD_LEFT = 10
TOTAL_WIDTH = 760  # natural width before the width= display scale
HEIGHT = FONT_SIZE * 1.8

# label -> output slug
HEADINGS = {
    "about": "hd-about",
    "live stats": "hd-stats",
    "top languages": "hd-langs",
    "streak": "hd-streak",
    "this year": "hd-year",
    "connect": "hd-connect",
}


def build_heading_svg(label: str, ink: str, muted: str, font_b64: str) -> str:
    text_w = len(label) * CHAR_W
    baseline = HEIGHT * 0.62
    rule_y = HEIGHT * 0.55
    rule_x1 = text_w + RULE_PAD_LEFT
    font_face = lib_font.font_face_css(lib_svg.FONT_FAMILY, font_b64)

    svg = lib_svg.svg_open(TOTAL_WIDTH, HEIGHT, display_width=0, label=label)
    # width=0 placeholder replaced below since headings are sized by caller
    svg = svg.replace('width="0" ', "")
    svg += lib_svg.style_block(
        font_face, ink, muted,
        extra=f"text{{font-size:{FONT_SIZE}px;letter-spacing:0.5px;}}",
    )
    svg += f'<text x="0" y="{baseline:.2f}">{label}</text>'
    svg += (
        f'<line class="rule" x1="{rule_x1:.2f}" y1="{rule_y:.2f}" '
        f'x2="{TOTAL_WIDTH:.2f}" y2="{rule_y:.2f}"/>'
    )
    svg += "</svg>"
    return svg


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_chars = "".join(HEADINGS.keys())
    font_b64 = lib_font.subset_to_woff2_base64(all_chars)

    for label, slug in HEADINGS.items():
        light = build_heading_svg(label, lib_svg.INK_LIGHT, lib_svg.MUTED_LIGHT, font_b64)
        dark = build_heading_svg(label, lib_svg.INK_DARK, lib_svg.MUTED_DARK, font_b64)
        (OUT_DIR / f"{slug}-light.svg").write_text(light, encoding="utf-8")
        (OUT_DIR / f"{slug}-dark.svg").write_text(dark, encoding="utf-8")
        print(f"wrote {slug}-light.svg / {slug}-dark.svg")


if __name__ == "__main__":
    main()
