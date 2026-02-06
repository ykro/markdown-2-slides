# markdown-2-slides

Generate professional PowerPoint presentations from Markdown using Gemini AI image generation.

## Features

- Parses markdown slides separated by `---`
- Generates high-quality slide images using Gemini 3 Pro Image Preview
- Supports three slide types: text, bullet lists, and diagrams
- Professional consulting-firm style design with consistent branding
- Outputs a standard .pptx file

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Gemini API key

## Setup

1. Clone the repository
2. Create a `.env` file with your Gemini API key:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```
3. Install dependencies:
   ```bash
   uv sync
   ```

## Usage

```bash
# Generate all slides
uv run python md2slides.py slides.md --open

# Test with first slide only
uv run python md2slides.py slides.md --test --open

# Generate specific range
uv run python md2slides.py slides.md --range 5-10 --open

# Custom output path
uv run python md2slides.py slides.md --output presentation.pptx
```

## Markdown Format

```markdown
---

### Slide Title

Body text goes here. **Bold terms** will be highlighted in coral.

---

### Bullet Slide

* **Label:** Description text
* **Another:** More description

---

### Diagram Slide

Description text before the diagram.

\`\`\`text
[Input] --> [Process] --> [Output]
\`\`\`

---
```

## Design System

The generated slides follow a professional consulting-firm aesthetic:

- **Background**: Soft off-white (#FAFAF8)
- **Primary accent**: Deep teal (#1A7A7A)
- **Emphasis**: Coral-orange (#E07A5F)
- **Typography**: Modern geometric sans-serif

Slide structure:
- Thin teal vertical stripe on left edge
- Title in bold near-black
- Teal accent line under title
- Subtitle (key takeaway) in semi-bold teal
- Body content with generous whitespace

## License

MIT
