# markdown-2-slides

CLI tool that converts Markdown files into professional PowerPoint presentations. Each slide is generated as an image using Gemini AI, then assembled into a `.pptx` file.

## How It Works

```
slides.md → parse → classify → build prompt → Gemini API → PNG → python-pptx → slides.pptx
```

1. Parses Markdown separated by `---` into individual slides
2. Classifies each slide as **text**, **bullets**, or **diagram**
3. Builds a layered prompt (shared style + type-specific layout)
4. Gemini generates a 16:9 image per slide
5. Images are assembled as full-bleed slides in a `.pptx`

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Gemini API key

## Setup

```bash
git clone https://github.com/ykro/markdown-2-slides.git
cd markdown-2-slides
uv sync
```

Create a `.env` file:

```
GEMINI_API_KEY=your_api_key_here
```

## Usage

```bash
# Generate all slides
uv run python md2slides.py slides.md --open

# Test with first slide only
uv run python md2slides.py slides.md --test --open

# Generate a range
uv run python md2slides.py slides.md --range 5-10 --open

# Custom output path
uv run python md2slides.py slides.md --output presentation.pptx

# Custom image directory
uv run python md2slides.py slides.md --image-dir ./my_images
```

## Markdown Format

```markdown
### Text Slide Title

Body text goes here. **Bold terms** will be highlighted in coral-orange.

---

### Bullet Slide

* **Label:** Description text
* **Another:** More description

---

### Diagram Slide

Optional description text.

\`\`\`text
[Input] --> [Process] --> [Output]
\`\`\`

---
```

### Slide Types

| Type | Trigger | Behavior |
|------|---------|----------|
| **Text** | Plain paragraph | If first sentence is short (≤12 words), it becomes a teal subtitle. Otherwise, full text renders as body. |
| **Bullets** | Lines starting with `*` | Each bullet becomes a styled card. `**Label:** description` format renders label in teal. |
| **Diagram** | Contains a code block | ASCII notation (`[Node] --> [Node]`) is converted to a visual flowchart. Entry/exit nodes use coral. |

## Design System

Professional consulting-firm aesthetic with a fixed palette:

| Element | Color | Hex |
|---------|-------|-----|
| Background | Warm off-white | `#FAFAF8` |
| Accent | Deep teal | `#1A7A7A` |
| Emphasis | Coral-orange | `#E07A5F` |
| Title text | Near-black | `#1C1C28` |
| Body text | Dark gray | `#44444F` |
| Card fill | Pale teal-gray | `#F2F6F6` |

Layout structure (every slide):
- Thin teal vertical stripe on the left edge
- Title in bold near-black with teal accent line below
- Optional subtitle in semi-bold teal (short first sentences only)
- Body content spanning full width, left to right margin
- Faint gray hairline near the bottom

## Prompt Architecture

The image generation uses a layered prompt system to ensure visual consistency:

- **`MASTER_STYLE`** — Shared across all slides: color palette, typography, layout grid, content rules, and visual hierarchy
- **`PROMPT_TEXT_SLIDE`** — Typography-focused layout with optional subtitle
- **`PROMPT_BULLET_SLIDE`** — Horizontal cards with teal left borders
- **`PROMPT_DIAGRAM_SLIDE`** — Node-and-arrow flowcharts with coral entry/exit nodes

Emphasis instructions and structural labels are kept in separate prompt sections to prevent instruction leakage into the generated images.

## License

MIT
