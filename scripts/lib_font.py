"""
Shared helper: subset a TTF down to only the characters a given SVG needs,
convert it to WOFF2, and return it as a base64 string ready to drop into an
inline @font-face data URI.

Why subsetting at all: an external font URL can't work here (the SVGs load
through an <img> tag, and browsers refuse subresource fetches for image
documents), so every SVG has to carry its own copy of the font. A full
JetBrains Mono TTF is ~275 KB; inlined raw that's enormous per file. A
13-character ramp subset is ~1.3 KB. Subset per role, not once for everything.
"""
from __future__ import annotations

import base64
import subprocess
import sys
import tempfile
from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"
REGULAR_TTF = FONTS_DIR / "JetBrainsMono-Regular.ttf"
BOLD_TTF = FONTS_DIR / "JetBrainsMono-Bold.ttf"


def subset_to_woff2_bytes(characters: str, src_ttf: Path = REGULAR_TTF) -> bytes:
    """Subset src_ttf to exactly `characters`, return raw WOFF2 bytes."""
    unique_chars = "".join(sorted(set(characters)))
    with tempfile.TemporaryDirectory() as td:
        out_path = Path(td) / "subset.woff2"
        cmd = [
            sys.executable,
            "-m",
            "fontTools.subset",
            str(src_ttf),
            f"--text={unique_chars}",
            "--flavor=woff2",
            "--layout-features=",
            "--no-hinting",
            f"--output-file={out_path}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"pyftsubset failed for chars {unique_chars!r}:\n{result.stderr}"
            )
        return out_path.read_bytes()


def subset_to_woff2_base64(characters: str, src_ttf: Path = REGULAR_TTF) -> str:
    """Subset src_ttf to exactly `characters`, return base64-encoded WOFF2 bytes."""
    return base64.b64encode(subset_to_woff2_bytes(characters, src_ttf)).decode("ascii")


def font_face_css(family: str, b64: str, weight: int = 400) -> str:
    """A single @font-face block with the font data inlined as a data URI."""
    return (
        f"@font-face{{font-family:'{family}';font-weight:{weight};"
        f"src:url(data:font/woff2;charset=utf-8;base64,{b64}) format('woff2');}}"
    )
