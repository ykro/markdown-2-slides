# CLAUDE.md

## Project Overview

Python CLI tool that converts Markdown files into PowerPoint presentations. Each slide is generated as an image by Gemini AI (`gemini-3-pro-image-preview`), then assembled into a 16:9 `.pptx`.

## Architecture

Single-file project: `md2slides.py` (~510 lines), organized in 4 sections:

| Section | Lines | Responsibility |
|---------|-------|----------------|
| Configuration | 36–120 | `MASTER_STYLE` + 3 type-specific prompt templates |
| Parsing | 122–290 | Markdown parsing, slide classification, text cleaning |
| Image Generation | 292–350 | Gemini API calls with retry/backoff |
| PowerPoint + CLI | 352–510 | `.pptx` assembly, argparse, rich UI |

Supporting files:
- `pyproject.toml` — uv project config, dependencies
- `slides.md` — Example input (50 slides, Spanish, AI for business)
- `.env` — Gemini API key (not committed)

## Commands

```bash
uv sync                                              # Install dependencies
uv run python md2slides.py slides.md --test --open   # First slide only
uv run python md2slides.py slides.md --range 1-5     # Specific range
uv run python md2slides.py slides.md --open          # All slides
```

## Slide Types

| Type | Detection | Template |
|------|-----------|----------|
| `text` | No bullets, no code block | `PROMPT_TEXT_SLIDE` |
| `bullets` | Lines starting with `*` | `PROMPT_BULLET_SLIDE` |
| `diagram` | Contains triple-backtick block | `PROMPT_DIAGRAM_SLIDE` |

## Prompt System

Layered architecture — all templates share `MASTER_STYLE` as base:

- **`MASTER_STYLE`** — Color palette (descriptive names, hex codes isolated in parenthetical), typography, layout grid, content rules, visual hierarchy
- **Type templates** — Each receives `{master_style}` + type-specific content and layout instructions

### Key Prompt Engineering Decisions

- **Hex codes are isolated** from prompt body into a parenthetical labeled "NEVER render" to prevent leakage
- **Emphasis instructions live outside SLIDE CONTENT** in a separate `EMPHASIS INSTRUCTIONS` block
- **Bullet labels (ending with `:`) are filtered** from emphasis — they use teal (structural), not coral (emphasis)
- **Takeaway/subtitle split only happens** when first sentence is ≤12 words; longer sentences stay as full body text instead of being truncated
- **Title-only slides** get a `NOTE:` outside the content section instead of a fallback string inside `Body:`
- **Instructions use positive framing** ("render ONLY...") over excessive negatives ("DO NOT...")
- **Layout uses relative references** ("one-third the title width") instead of ambiguous terms ("thumbnail-width")
- **No hardcoded language** — prompt says "in its original language" instead of "Spanish"

## Important Rules

- When modifying prompts, do NOT change code logic unless explicitly asked
- The boundary between SLIDE CONTENT and instructions must stay absolute — never mix instruction text into content fields
- Test prompt changes with `--range 1-10` covering all 3 slide types before full generation
- After prompt changes, verify with: `uv run python -c "from md2slides import parse_markdown, build_prompt; ..."`

## Known Issues

- Rate limiting on Gemini API — script has retry logic with exponential backoff (15s × attempt)
- Image generation is non-deterministic — same prompt can produce different layouts across runs
- 2s pause between slides to avoid rate limits; full 50-slide generation takes several minutes

## Dependencies

`google-genai`, `python-pptx`, `Pillow`, `rich`, `python-dotenv`
