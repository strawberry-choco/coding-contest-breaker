#!/usr/bin/env python3
"""Render a statement PDF's pages to images for visual reading.

Usage:
    python3 render_statement.py <statement.pdf> [--outdir DIR] [--dpi 300]
                                [--pages 1-4,7] [--crop PAGE:fx:fy:fw:fh ...]

Renders pages with pdftoppm (poppler) into --outdir (default
/tmp/<pdf-stem>-render), so render artifacts never land in the level
directory. Read every full page; when table characters are too small to read
reliably (image readers downsample large pages, so small text goes illegible),
re-render just that region with --crop: fractions of the page (0..1), format
PAGE:fx:fy:fw:fh where x/y is the top-left corner and w/h the size. Crops come
out at native dpi and keep small text legible. Repeat --crop to crop several
regions.

Recipe: render all pages (batches of ~8 for long PDFs) -> read them -> crop
any I/O table or fine print that stays illegible -> transcribe character by
character. Never pair columns by position in `pdftotext -layout` output; its
column alignment shifts between differently-structured blocks.

Exit codes: 0 ok, 2 tooling/format error, 3 bad usage.
"""
from __future__ import annotations

import argparse
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path


def die(msg: str, code: int = 2):
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def parse_pages(spec: str) -> list[int]:
    """Expand a page spec like 'all', '3', '1-4,7' into a page list."""
    spec = spec.strip().lower()
    if spec == "all":
        return []
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            pages.extend(range(int(a), int(b) + 1))
        elif part:
            pages.append(int(part))
    if not pages or any(p < 1 for p in pages):
        die(f"bad --pages spec: {spec!r}", 3)
    return pages


def png_size(path: Path) -> tuple[int, int]:
    """Width/height from the PNG IHDR chunk (no imaging deps)."""
    with open(path, "rb") as fh:
        head = fh.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        die(f"not a PNG: {path}")
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def page_size_pts(pdf: Path, page: int) -> tuple[float, float]:
    """Page size in points via pdfinfo (per-page, layouts may vary)."""
    try:
        out = subprocess.run(
            ["pdfinfo", "-f", str(page), "-l", str(page), str(pdf)],
            capture_output=True, text=True, check=True).stdout
    except FileNotFoundError:
        die("pdfinfo not found — install poppler (brew install poppler)")
    except subprocess.CalledProcessError as e:
        die(f"pdfinfo failed for page {page}: {e.stderr.strip()}")
    m = re.search(r"size:\s*([\d.]+)\s*x\s*([\d.]+)\s*pts", out)
    if not m:
        die(f"could not parse page size for page {page}")
    return float(m.group(1)), float(m.group(2))


def run_pdftoppm(pdf: Path, outdir: Path, prefix: str, dpi: int,
                 first: int, last: int, crop_px=None) -> None:
    cmd = ["pdftoppm", "-png", "-r", str(dpi), "-f", str(first),
           "-l", str(last)]
    if crop_px is not None:
        x, y, w, h = crop_px
        cmd += ["-x", str(x), "-y", str(y), "-W", str(w), "-H", str(h)]
    cmd += [str(pdf), str(outdir / prefix)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        die("pdftoppm not found — install poppler (brew install poppler)")
    except subprocess.CalledProcessError as e:
        die(f"pdftoppm failed: {e.stderr.strip()}")


def parse_crop(spec: str, page_px: dict[int, tuple[int, int]]) \
        -> tuple[int, int, int, int, int, int]:
    """Parse PAGE:fx:fy:fw:fh -> (page, x, y, w, h) in pixels."""
    parts = spec.split(":")
    if len(parts) != 5:
        die(f"bad --crop spec {spec!r} (want PAGE:fx:fy:fw:fh, fractions 0..1)",
            3)
    try:
        page = int(parts[0])
        fx, fy, fw, fh = (float(v) for v in parts[1:])
    except ValueError:
        die(f"bad --crop spec {spec!r}", 3)
    if page < 1 or page not in page_px:
        die(f"--crop page {page} was not rendered; add it to --pages", 3)
    if not all(0.0 <= v <= 1.0 for v in (fx, fy, fw, fh)) or fw <= 0 or fh <= 0:
        die(f"--crop fractions must be in 0..1 with w,h > 0: {spec!r}", 3)
    W, H = page_px[page]
    x = min(max(int(fx * W), 0), W - 1)
    y = min(max(int(fy * H), 0), H - 1)
    w = max(min(int(fw * W), W - x), 1)
    h = max(min(int(fh * H), H - y), 1)
    return page, x, y, w, h


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("pdf", help="statement PDF path")
    ap.add_argument("--outdir", default=None,
                    help="output dir (default /tmp/<pdf-stem>-render)")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--pages", default="all",
                    help="pages to render: 'all', '3', or '1-4,7'")
    ap.add_argument("--crop", action="append", default=[], metavar="P:fx:fy:fw:fh",
                    help="crop a region (fractions of the page) at native dpi")
    args = ap.parse_args(argv[1:])

    pdf = Path(args.pdf).expanduser()
    if not pdf.exists():
        die(f"PDF not found: {pdf}", 3)
    if shutil.which("pdftoppm") is None:
        die("pdftoppm not found — install poppler (brew install poppler)")

    outdir = (Path(args.outdir) if args.outdir
              else Path("/tmp") / f"{pdf.stem}-render")
    outdir.mkdir(parents=True, exist_ok=True)

    # Rendered pages are cached in outdir; invalidate the cache when --dpi
    # changes (crop pixel math depends on it).
    marker = outdir / ".dpi"
    if marker.exists() and marker.read_text().strip() != str(args.dpi):
        for old in outdir.glob("*.png"):
            old.unlink()
    marker.write_text(str(args.dpi))

    # Page count comes from pdfinfo when --pages is 'all'.
    pages = parse_pages(args.pages)
    if not pages:
        info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True,
                              text=True)
        m = re.search(r"Pages:\s+(\d+)", info.stdout)
        if not m:
            die("could not determine page count")
        pages = list(range(1, int(m.group(1)) + 1))

    # Existing renders are reused; only missing pages are rendered (in batches
    # of 8 so reading stays tractable).
    rendered: dict[int, Path] = {}
    for p in sorted(outdir.glob("page-*.png")):
        m = re.search(r"page-0*(\d+)\.png$", p.name)
        if m:
            rendered[int(m.group(1))] = p
    missing = [p for p in pages if p not in rendered]
    for i in range(0, len(missing), 8):
        batch = missing[i:i + 8]
        run_pdftoppm(pdf, outdir, "page", args.dpi, batch[0], batch[-1])
        for p in batch:
            cands = sorted(outdir.glob(f"page-0*{p}.png"))
            if cands:
                rendered[p] = cands[-1]

    page_px: dict[int, tuple[int, int]] = {}
    for p in pages:
        if p in rendered:
            page_px[p] = png_size(rendered[p])

    for path in sorted(outdir.glob("page-*.png")):
        w, h = png_size(path)
        print(f"{path}  ({w}x{h})")

    for spec in args.crop:
        page, x, y, w, h = parse_crop(spec, page_px)
        run_pdftoppm(pdf, outdir, f"crop-p{page}", args.dpi, page, page,
                     crop_px=(x, y, w, h))
        # pdftoppm names the file <prefix>-<page>.png
        out = outdir / f"crop-p{page}-{page}.png"
        if not out.exists():  # padding varies by poppler version
            cands = sorted(outdir.glob(f"crop-p{page}-*.png"))
            if not cands:
                die(f"crop produced no file for {spec!r}")
            out = cands[-1]
        cw, ch = png_size(out)
        print(f"{out}  ({cw}x{ch})  crop of page {page} at "
              f"({x},{y}) {w}x{h}px — native dpi, read character by character")

    if not args.crop:
        print("note: for any table/detail too small to read reliably, "
              "re-render that region with --crop PAGE:fx:fy:fw:fh "
              "(fractions of the page) to keep its native pixels.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
