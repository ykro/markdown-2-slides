# CLAUDE.md

## Project Overview

This is a Python CLI tool that converts Markdown files into professional PowerPoint presentations using Gemini AI for image generation.

## Architecture

- `md2slides.py` - Main script with all logic
- `pyproject.toml` - uv project configuration
- `slides.md` - Example input markdown file

## Key Components

### Slide Types

1. **Text slides** - Single paragraph with optional subtitle
2. **Bullet slides** - List items rendered as styled cards
3. **Diagram slides** - ASCII diagrams converted to infographics

### Prompt System

The image generation uses a layered prompt system:
- `MASTER_STYLE` - Brand colors, typography, layout grid (shared by all)
- `PROMPT_TEXT_SLIDE` / `PROMPT_BULLET_SLIDE` / `PROMPT_DIAGRAM_SLIDE` - Type-specific layouts

### Design Decisions

- **No decorative elements on text slides** - Whitespace IS the design
- **Labels use teal, key terms use coral** - Semantic color distinction
- **Entry/exit nodes in diagrams use coral** - Visual flow indicators
- **First sentence becomes subtitle** - Prevents duplication, creates hierarchy

## Commands

```bash
# Install dependencies
uv sync

# Run with test mode
uv run python md2slides.py slides.md --test --open

# Run full generation
uv run python md2slides.py slides.md --open
```

## Environment

Requires `.env` file with:
```
GEMINI_API_KEY=<your_key>
```

## Known Issues

- Rate limiting on Gemini API - script has retry logic with exponential backoff
- Some prompt instructions may leak into generated images - use natural language positioning instead of percentages/pixels
