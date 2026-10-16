#!/usr/bin/env python3
"""Generate fixture images for the prep_photos.sh test (needs ImageMagick).

  make_photos.py DIR

Creates two submission directories under DIR:
  exif/     three JPEGs whose EXIF capture times disagree with their file-name order, one of
            them 2400x1800 with EXIF orientation 6 (must come out upright, 1350x1800)
  natural/  heic, webp, PNG (3000x2000), jpeg, a 2-page PDF, notes.txt and answer.nb,
            with names that need natural, case-insensitive ordering
"""
import shutil
import struct
import subprocess
import sys
from pathlib import Path

IM = "magick" if shutil.which("magick") else "convert"


def run(*args):
    subprocess.run([IM, *map(str, args)], check=True)


def exif_app1(orientation=None, capture=None):
    """A big-endian EXIF APP1 segment with Orientation and/or DateTimeOriginal."""
    n0 = (1 if orientation else 0) + (1 if capture else 0)
    ifd0_size = 2 + n0 * 12 + 4
    exif_off = 8 + ifd0_size
    str_off = exif_off + (2 + 12 + 4 if capture else 0)
    b = b"MM\x00\x2a" + struct.pack(">I", 8) + struct.pack(">H", n0)
    if orientation:
        b += struct.pack(">HHIHH", 0x0112, 3, 1, orientation, 0)
    if capture:
        b += struct.pack(">HHII", 0x8769, 4, 1, exif_off)
    b += struct.pack(">I", 0)
    if capture:
        b += struct.pack(">H", 1) + struct.pack(">HHII", 0x9003, 2, 20, str_off) + struct.pack(">I", 0)
        b += capture.encode("ascii") + b"\0"
    payload = b"Exif\0\0" + b
    return b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload


def with_exif(path, orientation=None, capture=None):
    data = Path(path).read_bytes()
    assert data[:2] == b"\xff\xd8"
    Path(path).write_bytes(data[:2] + exif_app1(orientation, capture) + data[2:])


def picture(path, size, label):
    run("-size", size, "gradient:white-gray70", "-fill", "black", "-pointsize", "120",
        "-gravity", "center", "-annotate", "0", label, path)


def main(out):
    out = Path(out)
    ex, nat = out / "exif", out / "natural"
    for d in (ex, nat):
        d.mkdir(parents=True, exist_ok=True)
    # file-name order is 0001, 0002, 0010; capture order is 0010, 0001, 0002
    picture(ex / "IMG_0001.jpg", "1600x1200", "second")
    with_exif(ex / "IMG_0001.jpg", capture="2026:10:13 10:05:00")
    picture(ex / "IMG_0002.JPG", "2400x1800", "third")
    with_exif(ex / "IMG_0002.JPG", orientation=6, capture="2026:10:13 10:09:00")
    picture(ex / "IMG_0010.jpg", "1200x900", "first")
    with_exif(ex / "IMG_0010.jpg", capture="2026:10:13 10:01:00")

    picture(nat / "a1.heic", "800x600", "a1")
    picture(nat / "B2.webp", "800x600", "B2")
    picture(nat / "c 3.PNG", "3000x2000", "c3")
    picture(nat / "d10.jpeg", "400x300", "d10")
    (nat / "notes.txt").write_text("not an image\n")
    (nat / "answer.nb").write_text("(* notebook *)\n")
    tex = nat / "e.tex"
    tex.write_text("\\documentclass{article}\\begin{document}One\\newpage Two\\end{document}\n")
    subprocess.run(["pdflatex", "-interaction=batchmode", "-output-directory", str(nat), str(tex)],
                   check=True, stdout=subprocess.DEVNULL)
    for junk in ("e.tex", "e.aux", "e.log"):
        (nat / junk).unlink()


if __name__ == "__main__":
    main(sys.argv[1])
