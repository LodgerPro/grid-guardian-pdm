"""
Grid Guardian — generate QR code pointing at the deployed dashboard.

The dashboard URL is expected to be the GitHub Pages address. Adjust the
DEFAULT_URL constant or pass --url on the CLI.

Output: artifacts/qr_demo.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import qrcode

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "artifacts" / "qr_demo.png"

# Set this to the actual deployed URL. Falls back to a localhost placeholder.
DEFAULT_URL = "https://lodgerpro.github.io/grid-guardian-pdm/"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL,
                        help="Demo URL to encode (default: %(default)s)")
    args = parser.parse_args()

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(args.url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0a0e16", back_color="white")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    kb = OUT.stat().st_size / 1024
    print(f"[make_qr] wrote {OUT}  ({kb:.1f} KB)")
    print(f"[make_qr] encoded URL: {args.url}")


if __name__ == "__main__":
    sys.exit(main())
