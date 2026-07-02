# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pymupdf4llm>=0.0.17",
#     "markitdown[docx,pptx,xlsx]>=0.1.1",
# ]
# ///
"""Convert documents to LLM-ready Markdown.

PDFs are converted with pymupdf4llm (pipe tables, figure extraction,
multi-column reading order). Everything else goes through Microsoft's
markitdown (DOCX, PPTX, XLSX, HTML, EPUB, CSV, ...).

Usage:
    uv run convert.py INPUT [INPUT ...] [-o OUTPUT_DIR] [--force] [--no-images]
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

MARKITDOWN_EXTENSIONS = {
    ".docx", ".doc", ".pptx", ".xlsx", ".xls", ".html", ".htm",
    ".epub", ".csv", ".json", ".xml", ".rtf", ".odt",
}
SUPPORTED_EXTENSIONS = MARKITDOWN_EXTENSIONS | {".pdf"}

# Average extractable characters per page below which a PDF is
# probably a scan (image-only) and needs OCR instead.
SCANNED_CHARS_PER_PAGE = 200


def collect_inputs(raw_paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in raw_paths:
        path = Path(raw).expanduser().resolve()
        if path.is_dir():
            found = sorted(
                p for p in path.iterdir()
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
            )
            if not found:
                print(f"WARNING: no supported documents found in {path}")
            files.extend(found)
        elif path.is_file():
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                print(f"WARNING: skipping unsupported file type: {path}")
            else:
                files.append(path)
        else:
            print(f"ERROR: not found: {path}")
    return files


def fix_hyphenation(md: str) -> str:
    # Join words broken across line ends by hyphenation. Conservative:
    # only lowercase-to-lowercase joins, so legit compounds like
    # "state-of-the-art" written on one line are untouched.
    return re.sub(r"([a-z])-\n([a-z])", r"\1\2", md)


def tidy_markdown(md: str) -> str:
    md = md.replace("\r\n", "\n")
    md = fix_hyphenation(md)
    # Strip trailing whitespace per line, collapse 3+ blank lines to one.
    md = re.sub(r"[ \t]+$", "", md, flags=re.M)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


def normalize_image_links(md: str) -> str:
    # Markdown image links must use forward slashes even on Windows.
    def repl(match: re.Match) -> str:
        return match.group(0).replace("\\", "/")

    return re.sub(r"!\[[^\]]*\]\([^)]+\)", repl, md)


def count_tables(md: str) -> int:
    # Each pipe table has exactly one header separator line.
    return len(re.findall(r"^\s*\|?[\s:|-]*-{3,}[\s:|-]*\|[\s:|-]*$", md, re.M))


def frontmatter(source: Path, converter: str, pages: int | None) -> str:
    lines = [
        "---",
        f"source: {source.name}",
        f"converter: {converter}",
        f"converted: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
    ]
    if pages is not None:
        lines.append(f"pages: {pages}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def convert_pdf(source: Path, out_dir: Path, extract_images: bool) -> tuple[str, int, int]:
    """Returns (markdown, page_count, images_extracted)."""
    import fitz  # PyMuPDF, pulled in by pymupdf4llm
    import pymupdf4llm

    doc = fitz.open(source)
    pages = doc.page_count
    total_chars = sum(len(page.get_text()) for page in doc)
    doc.close()

    if pages and total_chars / pages < SCANNED_CHARS_PER_PAGE:
        print(
            f"WARNING: {source.name} yields almost no text "
            f"({total_chars} chars over {pages} pages). It is likely a "
            "scanned/image-only PDF and needs OCR; the Markdown output "
            "will be mostly empty."
        )

    images_dir = out_dir / f"{source.stem}_images"
    kwargs = {}
    if extract_images:
        kwargs = {
            "write_images": True,
            "image_path": str(images_dir),
            "image_format": "png",
            "dpi": 150,
        }
    md = pymupdf4llm.to_markdown(str(source), **kwargs)

    images_extracted = 0
    if extract_images and images_dir.is_dir():
        images_extracted = sum(1 for p in images_dir.iterdir() if p.is_file())
        if images_extracted == 0:
            images_dir.rmdir()
        else:
            # Rewrite absolute image paths to be relative to the .md file
            # so the output folder is portable. pymupdf4llm may emit either
            # separator style, so replace both forms.
            md = md.replace(images_dir.as_posix(), images_dir.name)
            md = md.replace(str(images_dir), images_dir.name)

    md = normalize_image_links(md)
    md = tidy_markdown(md)
    return md, pages, images_extracted


def convert_other(source: Path) -> str:
    from markitdown import MarkItDown

    result = MarkItDown().convert(str(source))
    return tidy_markdown(result.text_content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("inputs", nargs="+", help="Files or directories to convert")
    parser.add_argument("-o", "--output-dir", help="Directory for .md output (default: next to each input)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing .md outputs")
    parser.add_argument("--no-images", action="store_true", help="Skip figure extraction from PDFs")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    files = collect_inputs(args.inputs)
    if not files:
        print("ERROR: nothing to convert.")
        return 1

    failures = 0
    for source in files:
        out_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else source.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{source.stem}.md"

        if out_path.exists() and not args.force:
            print(f"SKIPPED: {out_path} already exists (use --force to overwrite)")
            continue

        try:
            if source.suffix.lower() == ".pdf":
                md, pages, images = convert_pdf(source, out_dir, not args.no_images)
                converter = "pymupdf4llm"
            else:
                md = convert_other(source)
                pages, images = None, 0
                converter = "markitdown"
        except Exception as exc:  # noqa: BLE001 - report and continue the batch
            print(f"ERROR: failed to convert {source.name}: {exc}")
            failures += 1
            continue

        tables = count_tables(md)
        out_path.write_text(frontmatter(source, converter, pages) + md, encoding="utf-8")

        summary = [f"OK: {out_path}", f"converter={converter}"]
        if pages is not None:
            summary.append(f"pages={pages}")
        summary.append(f"tables={tables}")
        summary.append(f"images={images}")
        print(" | ".join(summary))

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
