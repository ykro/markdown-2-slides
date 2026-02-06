#!/usr/bin/env python3
"""
md2slides - Generate PowerPoint presentations from Markdown using Gemini image generation.

Usage:
    uv run md2slides.py slides.md
    uv run md2slides.py slides.md --output presentation.pptx
    uv run md2slides.py slides.md --test          # Generate only the first slide
    uv run md2slides.py slides.md --range 1-5     # Generate slides 1 through 5
    uv run md2slides.py slides.md --open          # Open the file after generation
"""

import argparse
import os
import re
import subprocess
import sys
import time
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
from pptx import Presentation
from pptx.util import Inches
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.text import Text

# ─── Configuration ──────────────────────────────────────────────────────────────

MASTER_STYLE = (
    "Generate a SINGLE 16:9 widescreen slide image with a clean, polished, professional look.\n\n"

    "COLOR PALETTE (use ONLY these):\n"
    "Background #FAFAF8, accent teal #1A7A7A, warm accent coral #E07A5F (only for emphasized terms), "
    "title #1C1C28, body #44444F, structural lines #E8E8E8, card fill #F2F6F6.\n\n"

    "TYPOGRAPHY:\n"
    "Font: geometric sans-serif (Inter style). Title: large bold near-black. Body: medium regular dark gray. "
    "Emphasized words: coral #E07A5F, medium weight, same size as body.\n\n"

    "LAYOUT STRUCTURE (every slide identical):\n"
    "- A thin solid teal vertical stripe flush against the left edge, running the full height of the slide.\n"
    "- Title positioned in the upper-left area with generous top and left margins.\n"
    "- A short teal accent line (roughly thumbnail-width) directly under the title.\n"
    "- Main content area begins below the accent line, with matching left margin and comfortable right margin.\n"
    "- A faint gray horizontal hairline near the very bottom of the slide.\n\n"

    "CRITICAL RULES:\n"
    "- The ONLY text that may appear on the slide is the exact Spanish content provided below under SLIDE CONTENT. "
    "Render every word EXACTLY as given. Do NOT add, remove, translate, or alter ANY word.\n"
    "- DO NOT render ANY numbers, percentages, measurements, hex codes, or technical terms from these instructions. "
    "These instructions describe style only and must NEVER appear as visible text.\n"
    "- DO NOT render: photographs, illustrations, clip art, icons, emoji, logos, slide numbers, "
    "watermarks, page numbers, or any decorative numerals.\n"
    "- Text must be sharp, anti-aliased, and legible at projection size.\n"
)

PROMPT_TEXT_SLIDE = """{master_style}

SLIDE CONTENT (render ONLY this text):
Title: {title}
Subtitle: {takeaway}
Body: {body}

SLIDE-SPECIFIC LAYOUT:
- The subtitle is a single short sentence in semi-bold teal, placed directly below the teal accent line, before the body text. It acts as the key takeaway.
- Body text is left-aligned, filling the full content area width.
- Emphasized terms appear in coral, medium weight, same size as body text.
- The right side is clean whitespace. NO decorative circles, shapes, or background elements.
- The bottom fifth of the slide is empty. The design is pure typography and whitespace.
"""

PROMPT_BULLET_SLIDE = """{master_style}

SLIDE CONTENT (render ONLY this text):
Title: {title}
Subtitle: {takeaway}
{body}

SLIDE-SPECIFIC LAYOUT:
- The subtitle is a single short sentence in semi-bold teal, placed directly below the teal accent line, before the bullet cards.
- Each bullet is a horizontal card: light teal-gray fill, slightly rounded corners, with a solid teal left border.
- If the bullet has a "Label: description" format, render the label in semi-bold TEAL (not coral) and the description in regular dark gray. Labels are structural, not emphasis.
- If no colon, use a small teal dot before the text in dark gray.
- Cards are evenly spaced vertically, spanning about three-quarters of the slide width.
- Only terms explicitly listed as emphasized appear in coral. Card labels always use teal.
- NO decorative elements beyond the cards and the standard layout frame.
"""

PROMPT_DIAGRAM_SLIDE = """{master_style}

SLIDE CONTENT (render ONLY this text):
Title: {title}
{description_block}

DIAGRAM TO DRAW:
{diagram}

SLIDE-SPECIFIC LAYOUT:
- If there is a description line, render it in semi-bold teal directly below the teal accent line.
- The diagram is centered and occupies the majority of the slide area.
- ENTRY nodes (first node in the flow) and EXIT nodes (last node): use a light coral-tinted fill with thin coral border, to visually distinguish them from processing nodes.
- PROCESSING nodes (all middle nodes): white fill with thin teal border and a very subtle shadow.
- Node text: small, near-black, centered inside each node.
- Arrows: thin teal lines with clean triangular arrowheads.
- Preferred flow direction: left-to-right. Generous spacing between nodes.
- NO decorative elements beyond the diagram and the standard layout frame.
"""

MODEL_NAME = "gemini-3-pro-image-preview"

console = Console()

# ─── Markdown Parsing ───────────────────────────────────────────────────────────


def parse_markdown(filepath: str) -> list[dict]:
    """Parse a markdown file into a list of slide dicts with title and body."""
    text = Path(filepath).read_text(encoding="utf-8")

    # Split by --- separators
    raw_slides = re.split(r"^---\s*$", text, flags=re.MULTILINE)

    slides = []
    for raw in raw_slides:
        raw = raw.strip()
        if not raw:
            continue

        # Extract title (### heading)
        title_match = re.match(r"^###\s+(.+)$", raw, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else "Slide"

        # Extract body (everything after the title line)
        if title_match:
            body = raw[title_match.end() :].strip()
        else:
            body = raw

        # Skip slides that look like meta-questions (not real content)
        if body.startswith("**¿") or body.startswith("¿"):
            continue

        slides.append({"title": title, "body": body})

    return slides


def classify_slide(body: str) -> str:
    """Classify a slide body into: 'diagram', 'bullets', or 'text'."""
    if "```" in body:
        return "diagram"
    if re.search(r"^\*\s+", body, re.MULTILINE):
        return "bullets"
    return "text"


def clean_markdown(text: str) -> str:
    """Strip markdown syntax, converting bold markers to emphasis hints for the prompt."""
    # Extract bold terms for emphasis instruction
    bold_terms = re.findall(r"\*\*(.+?)\*\*", text)
    # Remove ** markers
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # Remove * italic markers
    cleaned = re.sub(r"\*(.+?)\*", r"\1", cleaned)
    return cleaned, bold_terms


def clean_diagram(text: str) -> str:
    """Convert ASCII diagram notation to plain node descriptions.

    Strips [], replaces --> with →, cleans up alignment characters.
    """
    cleaned = text
    # [Node Text] → Node Text
    cleaned = re.sub(r"\[([^\]]+)\]", r"\1", cleaned)
    # --> and <--- to arrows
    cleaned = cleaned.replace("<---", "←")
    cleaned = cleaned.replace("-->", "→")
    cleaned = cleaned.replace("<--", "←")
    cleaned = cleaned.replace("->", "→")
    cleaned = cleaned.replace("<-", "←")
    return cleaned


def split_takeaway_and_body(body: str) -> tuple[str, str]:
    """Split slide body into a takeaway (first sentence) and remaining body.

    Returns (takeaway, remaining_body). The takeaway becomes the subtitle,
    and the remaining body is the detail text — no duplication.
    """
    cleaned, emphasis = clean_markdown(body)
    # Remove code blocks for takeaway extraction
    text_only = re.sub(r"```\w*\n.*?```", "", cleaned, flags=re.DOTALL).strip()
    # Remove bullet markers
    text_only = re.sub(r"^[•*]\s+", "", text_only, flags=re.MULTILINE).strip()

    if not text_only:
        return "", cleaned

    # Split into sentences
    parts = re.split(r"(?<=[.!?])\s+", text_only, maxsplit=1)
    takeaway = parts[0].rstrip(".")

    # Truncate takeaway to ~12 words
    words = takeaway.split()
    if len(words) > 12:
        takeaway = " ".join(words[:12]) + "..."

    # Remaining body is everything after the first sentence
    remaining = parts[1] if len(parts) > 1 else ""

    # Re-add emphasis hints to remaining
    if emphasis and remaining:
        remaining += f"\n\n(Render these terms in coral-orange: {', '.join(emphasis)})"

    return takeaway, remaining


def build_prompt(slide: dict) -> str:
    """Build the full image generation prompt for a slide based on its type."""
    title = slide["title"]
    body = slide["body"]
    slide_type = classify_slide(body)
    styled = MASTER_STYLE

    if slide_type == "diagram":
        code_match = re.search(r"```\w*\n(.*?)```", body, re.DOTALL)
        raw_description = re.sub(r"```\w*\n.*?```", "", body, flags=re.DOTALL).strip()
        description, _ = clean_markdown(raw_description)
        diagram = clean_diagram(code_match.group(1).strip()) if code_match else ""
        desc_block = f"Description: {description}" if description else ""
        return PROMPT_DIAGRAM_SLIDE.format(
            master_style=styled,
            title=title,
            description_block=desc_block,
            diagram=diagram,
        )
    elif slide_type == "bullets":
        # For bullets, use the full body — no takeaway split needed
        lines = body.split("\n")
        formatted_lines = []
        all_emphasis = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            cleaned_line, emphasis = clean_markdown(stripped)
            cleaned_line = re.sub(r"^[•*]\s+", "", cleaned_line).strip()
            if cleaned_line:
                formatted_lines.append(cleaned_line)
                all_emphasis.extend(emphasis)
        bullet_body = "Bullet points:\n" + "\n".join(f"  • {l}" for l in formatted_lines if l)
        if all_emphasis:
            bullet_body += f"\n\n(Render these terms in coral-orange: {', '.join(all_emphasis)})"
        # No subtitle for bullet slides — the cards ARE the content
        return PROMPT_BULLET_SLIDE.format(
            master_style=styled,
            title=title,
            takeaway="",
            body=bullet_body,
        )
    else:
        # For text slides: first sentence → subtitle, rest → body (no duplication)
        takeaway, remaining = split_takeaway_and_body(body)
        return PROMPT_TEXT_SLIDE.format(
            master_style=styled,
            title=title,
            takeaway=takeaway,
            body=remaining or "(title-only slide — leave the body area empty with elegant whitespace)",
        )


# ─── Image Generation ───────────────────────────────────────────────────────────


def create_client() -> genai.Client:
    """Create and return a Gemini API client."""
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        console.print("[red bold]Error:[/] GEMINI_API_KEY not found in .env file")
        sys.exit(1)
    return genai.Client(api_key=api_key)


def generate_slide_image(client: genai.Client, slide: dict, index: int, output_dir: Path) -> Path | None:
    """Generate an image for a single slide and save it to disk."""
    prompt = build_prompt(slide)

    image_path = output_dir / f"slide_{index:03d}.png"

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio="16:9",
                    ),
                ),
            )

            # Extract image from response
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image_data = part.inline_data.data
                    img = Image.open(BytesIO(image_data))
                    img.save(str(image_path), "PNG")
                    return image_path

            console.print(f"  [yellow]Warning: No image in response for slide {index}[/]")
            return None

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower():
                wait = 15 * (attempt + 1)
                console.print(f"  [yellow]Rate limited. Waiting {wait}s...[/]")
                time.sleep(wait)
            elif attempt < max_retries - 1:
                console.print(f"  [yellow]Attempt {attempt + 1} failed: {error_msg}. Retrying...[/]")
                time.sleep(5)
            else:
                console.print(f"  [red]Failed after {max_retries} attempts: {error_msg}[/]")
                return None

    return None


# ─── PowerPoint Assembly ────────────────────────────────────────────────────────


def create_pptx(image_paths: list[Path | None], output_path: str):
    """Create a PowerPoint presentation from generated slide images."""
    prs = Presentation()

    # Set widescreen 16:9 dimensions using exact EMU values
    from pptx.util import Emu
    prs.slide_width = Emu(12192000)
    prs.slide_height = Emu(6858000)

    blank_layout = prs.slide_layouts[6]  # Blank layout

    for img_path in image_paths:
        slide = prs.slides.add_slide(blank_layout)

        # Remove any inherited placeholder shapes that may cover content
        for ph in list(slide.placeholders):
            sp = ph._element
            sp.getparent().remove(sp)

        if img_path and img_path.exists():
            # Add image covering the full slide
            slide.shapes.add_picture(
                str(img_path),
                left=0,
                top=0,
                width=prs.slide_width,
                height=prs.slide_height,
            )

    prs.save(output_path)


# ─── CLI ────────────────────────────────────────────────────────────────────────


def parse_range(range_str: str, total: int) -> tuple[int, int]:
    """Parse a range string like '1-5' into (start, end) 0-indexed."""
    if "-" in range_str:
        parts = range_str.split("-")
        start = max(1, int(parts[0])) - 1
        end = min(total, int(parts[1]))
        return start, end
    else:
        idx = int(range_str) - 1
        return idx, idx + 1


def main():
    parser = argparse.ArgumentParser(
        description="Generate PowerPoint slides from Markdown using Gemini AI"
    )
    parser.add_argument("input", help="Path to the markdown file")
    parser.add_argument("--output", "-o", default=None, help="Output .pptx path")
    parser.add_argument("--test", action="store_true", help="Generate only the first slide")
    parser.add_argument("--range", dest="slide_range", default=None, help="Slide range, e.g. '1-5' or '3'")
    parser.add_argument("--open", dest="open_file", action="store_true", help="Open the file after generation")
    parser.add_argument("--image-dir", default=None, help="Directory to store generated images")

    args = parser.parse_args()

    # ── Header ──
    console.print()
    console.print(Panel.fit(
        "[bold white]md2slides[/] — Markdown to Presentation Generator",
        subtitle="Powered by Gemini AI",
        border_style="blue",
    ))
    console.print()

    # ── Parse Markdown ──
    input_path = Path(args.input)
    if not input_path.exists():
        console.print(f"[red bold]Error:[/] File not found: {args.input}")
        sys.exit(1)

    slides = parse_markdown(args.input)
    total = len(slides)
    console.print(f"[bold]Parsed[/] {total} slides from [cyan]{input_path.name}[/]")

    # ── Determine range ──
    if args.test:
        start, end = 0, 1
    elif args.slide_range:
        start, end = parse_range(args.slide_range, total)
    else:
        start, end = 0, total

    selected_slides = slides[start:end]
    console.print(f"[bold]Generating[/] slides {start + 1}–{end} ({len(selected_slides)} slides)")
    console.print()

    # ── Show slide summary ──
    table = Table(title="Slides to Generate", show_lines=False, border_style="dim")
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", style="bold")
    table.add_column("Type", style="cyan", width=14)

    for i, s in enumerate(selected_slides, start=start + 1):
        stype = classify_slide(s["body"]) if s["body"] else "title only"
        table.add_row(str(i), s["title"], stype)

    console.print(table)
    console.print()

    # ── Setup output ──
    output_path = args.output or input_path.with_suffix(".pptx")
    image_dir = Path(args.image_dir) if args.image_dir else input_path.parent / "slide_images"
    image_dir.mkdir(parents=True, exist_ok=True)

    # ── Generate images ──
    client = create_client()
    image_paths: list[Path | None] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Generating slides...", total=len(selected_slides))

        for i, slide in enumerate(selected_slides, start=start + 1):
            progress.update(task, description=f"Slide {i}: {slide['title'][:40]}")
            img_path = generate_slide_image(client, slide, i, image_dir)
            image_paths.append(img_path)
            progress.advance(task)

            # Brief pause between requests to avoid rate limiting
            if i < end:
                time.sleep(2)

    # ── Report results ──
    success = sum(1 for p in image_paths if p is not None)
    failed = len(image_paths) - success
    console.print()
    console.print(f"[green bold]Generated:[/] {success}/{len(image_paths)} slide images")
    if failed:
        console.print(f"[yellow]Skipped:[/] {failed} slides (generation failed)")

    # ── Build PowerPoint ──
    console.print()
    console.print(f"[bold]Building[/] PowerPoint → [cyan]{output_path}[/]")
    create_pptx(image_paths, str(output_path))
    console.print("[green bold]Done![/]")

    # ── Open file ──
    if args.open_file:
        console.print(f"[dim]Opening {output_path}...[/]")
        if sys.platform == "darwin":
            subprocess.run(["open", str(output_path)])
        elif sys.platform == "win32":
            os.startfile(str(output_path))
        else:
            subprocess.run(["xdg-open", str(output_path)])


if __name__ == "__main__":
    main()
