"""
Shared visual constants and small SVG helpers used by every generator
(portrait, headings, stats) so the whole profile reads as one system rather
than five different widgets glued together.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# One fill colour per theme — no per-character or per-bar rainbow colouring.
INK_LIGHT = "#1b1f24"   # ink used on the light-mode SVG (GitHub light bg)
INK_DARK = "#c9d1d9"    # ink used on the dark-mode SVG  (GitHub dark bg)
MUTED_LIGHT = "#57606a"  # secondary/dim text, light mode
MUTED_DARK = "#8b949e"   # secondary/dim text, dark mode

FONT_FAMILY = "ProfileMono"


def svg_open(width_px: float, height_px: float, display_width: int, label: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" '
        f'viewBox="0 0 {width_px:.2f} {height_px:.2f}" width="{display_width}" '
        f'role="img" aria-label="{label}">'
    )


def style_block(font_face_css: str, ink: str, muted: str, extra: str = "") -> str:
    return (
        f"<style>{font_face_css}"
        f"text{{font-family:'{FONT_FAMILY}',ui-monospace,monospace;fill:{ink};}}"
        f".muted{{fill:{muted};}}"
        f".rule{{stroke:{muted};stroke-width:1;}}"
        f"{extra}</style>"
    )


def picture_tag(light_path: str, dark_path: str, alt: str, width: int | None = None) -> str:
    """<picture> is one of the few tags GitHub's README sanitiser keeps, so
    this is how a single README line serves a light SVG and a dark SVG."""
    w_attr = f' width="{width}"' if width else ""
    return (
        "<picture>"
        f'<source media="(prefers-color-scheme: dark)" srcset="{dark_path}">'
        f'<img src="{light_path}" alt="{alt}"{w_attr}>'
        "</picture>"
    )
