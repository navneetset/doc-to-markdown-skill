# doc-to-markdown

A [Claude Code skill](https://code.claude.com/docs/en/skills) that converts
documents — research papers especially — into clean, LLM-ready Markdown while
preserving **tables** (as Markdown pipe tables) and **figures** (extracted as
PNG files, linked inline).

Once installed, just ask Claude Code things like:

> convert this paper to markdown
> prep E:\papers\attention.pdf for the LLM
> batch-convert my papers folder

## Why a hybrid engine?

Microsoft's [markitdown](https://github.com/microsoft/markitdown) is excellent
for Office formats, but its default PDF path (pdfminer.six) extracts plain
text only: tables lose their structure, figures are dropped, and two-column
academic papers come out with scrambled reading order. So this skill routes:

| Input | Engine | You get |
|---|---|---|
| PDF | [pymupdf4llm](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/) | pipe tables, figures as PNGs, multi-column reading order |
| DOCX, PPTX, XLSX, HTML, EPUB, CSV, … | [markitdown](https://github.com/microsoft/markitdown) | faithful structural Markdown |

The converter also does an LLM-efficiency pass: joins hyphenated line breaks,
collapses blank-line runs, and prepends YAML frontmatter (source, page count,
converter, date). The skill then has Claude verify the output and fix
remaining artifacts (repeated page headers, mangled references) without ever
touching scientific content.

## Requirements

- [Claude Code](https://claude.com/claude-code)
- [uv](https://docs.astral.sh/uv/) on PATH (`winget install astral-sh.uv` /
  `curl -LsSf https://astral.sh/uv/install.sh | sh`). No other setup — the
  converter declares its own dependencies inline and uv installs them into
  its cache on first run.

## Install

Clone anywhere, then link (or just copy) the folder into your global skills
directory as `doc-to-markdown`:

**Windows (PowerShell):**

```powershell
git clone https://github.com/navneetset/doc-to-markdown-skill
New-Item -ItemType Junction "$env:USERPROFILE\.claude\skills\doc-to-markdown" -Target "$PWD\doc-to-markdown-skill"
```

**macOS / Linux:**

```bash
git clone https://github.com/navneetset/doc-to-markdown-skill
ln -s "$PWD/doc-to-markdown-skill" ~/.claude/skills/doc-to-markdown
```

New Claude Code sessions will pick the skill up automatically.

## Use without Claude Code

The converter is a plain script; it works standalone:

```bash
uv run scripts/convert.py paper.pdf                 # paper.md + paper_images/ next to it
uv run scripts/convert.py papers/ -o converted/     # batch a folder
uv run scripts/convert.py paper.pdf --no-images     # text and tables only
```

## Licensing note

This project is MIT-licensed. It depends at runtime on
[PyMuPDF](https://github.com/pymupdf/PyMuPDF) (via pymupdf4llm), which is
**AGPL-3.0** — fine for personal and internal use; consult the AGPL if you
plan to embed this in a distributed or hosted product.
