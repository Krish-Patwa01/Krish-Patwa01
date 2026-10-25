"""
One-time (re-run only when wording/charset changes) setup: builds the
committed .woff2 font subsets that generate_stats.py reads and inlines every
night. Keeping this step out of the nightly workflow is what lets that
script stay stdlib-only — see its docstring.

Usage:
    python scripts/build_font_subsets.py
"""
from __future__ import annotations

import string
from pathlib import Path

import lib_font

FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"

RAMP = " .`:-=+*cs#%@"

# everything the stats/streak/langs/year SVGs might need to print: digits,
# letters (language names, labels), common punctuation and the arrow used
# in streak date ranges.
DATA_CHARS = string.ascii_letters + string.digits + " .,:%-–—()/'→+"


def main():
    FONTS_DIR.mkdir(exist_ok=True)

    ramp_bytes = lib_font.subset_to_woff2_bytes(RAMP)
    (FONTS_DIR / "subset-ramp.woff2").write_bytes(ramp_bytes)
    print(f"wrote subset-ramp.woff2 ({len(ramp_bytes)} bytes)")

    reg_bytes = lib_font.subset_to_woff2_bytes(DATA_CHARS, lib_font.REGULAR_TTF)
    (FONTS_DIR / "subset-data-regular.woff2").write_bytes(reg_bytes)
    print(f"wrote subset-data-regular.woff2 ({len(reg_bytes)} bytes)")

    bold_bytes = lib_font.subset_to_woff2_bytes(DATA_CHARS, lib_font.BOLD_TTF)
    (FONTS_DIR / "subset-data-bold.woff2").write_bytes(bold_bytes)
    print(f"wrote subset-data-bold.woff2 ({len(bold_bytes)} bytes)")


if __name__ == "__main__":
    main()
