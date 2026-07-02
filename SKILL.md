---
name: doc-to-markdown
description: |
  Converts documents into clean, LLM-ready Markdown while preserving tables
  (as pipe tables) and figures (extracted as image files). Activate this skill
  whenever the user asks to convert a PDF, paper, research paper, article,
  document, DOCX, PPTX, XLSX, HTML, or EPUB to Markdown; to "make this paper
  readable", "prep this paper/PDF for the LLM", "extract this PDF", or
  "markdownify" a file; or to batch-convert a folder of papers. Also activate
  when the user wants to read, summarize, or analyze a PDF and a Markdown
  conversion would make that materially cheaper or more accurate — offer the
  conversion first.
version: 1.0
---

# doc-to-markdown

Converts documents to Markdown that is efficient to feed to an LLM, using a
hybrid engine:

- **PDF** → `pymupdf4llm` — real pipe tables, figures extracted to files,
  correct reading order on two-column academic papers.
- **Everything else** (DOCX, PPTX, XLSX, HTML, EPUB, CSV, ...) → Microsoft's
  `markitdown`.

The converter is `scripts/convert.py` inside this skill's directory
(`~/.claude/skills/doc-to-markdown/`). It is fully self-contained: `uv run`
reads its inline dependency block and installs everything into uv's cache on
first use (~30s once, instant afterwards). Requires `uv` on PATH.

## Step 1 — Resolve inputs and output location

1. Identify the file(s) or folder to convert. Resolve to absolute paths and
   confirm they exist before running anything.
2. Output location: default is **next to each source file**. If the user gave
   a destination, pass it with `-o`.
3. **Hard rule**: never overwrite an existing `.md` without asking. The script
   enforces this — it skips existing outputs unless `--force` is passed. If it
   reports `SKIPPED`, ask the user before re-running with `--force`.

## Step 2 — Run the converter

```powershell
uv run "$env:USERPROFILE\.claude\skills\doc-to-markdown\scripts\convert.py" "<input.pdf>" [-o "<output-dir>"]
```

macOS/Linux:

```bash
uv run ~/.claude/skills/doc-to-markdown/scripts/convert.py "<input.pdf>" [-o "<output-dir>"]
```

- Multiple files or a whole directory can be passed in one call.
- `--no-images` skips figure extraction if the user only wants text.
- Each converted file prints a summary line:
  `OK: <path> | converter=... | pages=N | tables=N | images=N`

## Step 3 — Verify the output (every conversion)

Check and report each:

1. **Exists and is non-trivial**: the `.md` file exists and its size is
   plausible for the source (a 10-page paper should not be 2 KB).
2. **Structure survived**: the file contains `#` headings and, if the source
   had tables, pipe tables (`| ... |` rows) — not run-on plain text.
3. **Figures**: if `images=N` with N > 0, a `<stem>_images/` folder sits next
   to the `.md` and the image links inside the Markdown are relative and use
   forward slashes.
4. **Warnings relayed**: if the script printed a scanned-PDF warning, tell the
   user their PDF is image-only and needs OCR — do not present a near-empty
   `.md` as a successful conversion.

## Step 4 — Quality pass (PDFs)

Skim the generated Markdown for artifacts the script cannot fix mechanically,
and fix them with targeted edits:

- Repeated per-page header/footer noise (journal name, page numbers, arXiv
  banner lines) — delete the repeats.
- Heading levels that came out wrong (e.g. section titles rendered as bold
  text instead of `##`) — promote them.
- Table fragments split across a page break — merge into one table.
- A mangled references section — reformat as a list, one entry per line.

**Hard rule**: never alter scientific content — numbers, units, equations,
author names, citations, or quoted text. Formatting fixes only. If a table is
too garbled to fix confidently, leave it and flag it to the user instead.

## Step 5 — Report

Report to the user: output path(s), page/table/image counts from the summary
lines, any quality fixes applied in Step 4, and any warnings.

## Failure modes

- **Scanned/image-only PDF** (warning from the script): the PDF has no text
  layer. Suggest OCR options: `ocrmypdf` (adds a text layer, then re-run this
  skill) or markitdown's Azure Document Intelligence integration.
- **Encrypted/password-protected PDF**: the script will error. Ask the user
  for a decrypted copy.
- **Garbled pymupdf4llm output** (rare — unusual layouts): ask the user
  whether plain-text extraction is acceptable, then fall back to markitdown
  (tables and figures will be lost):
  ```
  uv run --with "markitdown[pdf]" python -c "from markitdown import MarkItDown; print(MarkItDown().convert(r'<file>').text_content)"
  ```
  and write the output to the `.md` yourself.
- **`uv` not installed**: point the user to https://docs.astral.sh/uv/ —
  Windows: `winget install astral-sh.uv`.

## Quick reference — happy path

```
User: "convert E:\papers\attention.pdf to markdown"
  ↓
uv run ~/.claude/skills/doc-to-markdown/scripts/convert.py E:\papers\attention.pdf
  ↓
OK: E:\papers\attention.md | converter=pymupdf4llm | pages=11 | tables=4 | images=3
  ↓
Verify: headings ✓, pipe tables ✓, attention_images/ has 3 PNGs ✓
  ↓
Quality pass: removed repeated arXiv footer, fixed References formatting
  ↓
Report to user.
```
