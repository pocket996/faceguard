"""Package the user-supplied artwork as lossless PNG and Windows multi-size ICO.

No redraw, color replacement or background removal. The canonical PNG retains
the decoded source pixels; icon frames are ordinary high-quality resizes.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'src/faceguard/ui'
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=UI / 'brand.png')
    args = parser.parse_args()
    with Image.open(args.source) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
    if image.width != image.height:
        raise ValueError('The supplied app icon must be square; do not stretch it.')
    # New images omit unrelated source metadata while retaining the artwork.
    clean = Image.new('RGB', image.size)
    clean.paste(image)
    clean.save(UI / 'brand.png', optimize=True)
    clean.save(UI / 'brand.ico', sizes=[(size, size) for size in SIZES])
    print(f'PNG: {image.width}x{image.height}; ICO: {", ".join(map(str, SIZES))} px')


if __name__ == '__main__':
    main()
