"""Render a day's share images from its snapshot (issue #671).

The images travel to X, WeChat groups and Discord on their own. WeChat does
not make a pasted URL clickable, so the bottom-right domain is the only way a
reader there finds the site again.

Input is the ``share`` block the daily run wrote into the snapshot; nothing
here reads the network, so a snapshot always renders the same images. Output:

- top3.png: the first three cards in one portrait (4:5) image, which X, WeChat
  and Discord all show uncropped on a phone.
- card-NN.png: one 1200x630 card per benchmark in the block, the size X and
  most chat apps use for a link preview.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from benchmark_radar.daily_top import DEFAULT_LIMIT, card_image_name

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_og_image import (  # noqa: E402
    BACKGROUND,
    INK,
    LIGHT,
    SLATE,
    TEAL,
    _assert_scalable_fonts,
    font,
)

WATERMARK = "benchmark-radar.org"
MARGIN = 64
TOP_SIZE = (1080, 1350)
CARD_SIZE = (1200, 630)

# Every radar item is some mix of these, so naming them on a card tells the
# reader nothing. The topical categories after them (agentic, multimodal) do.
GENERIC_CATEGORIES = frozenset({"benchmark", "evaluation", "dataset"})

# The images are English only and DejaVu has no CJK glyphs, so "Vivien Jiaqian
# Zhu 朱佳谦" would end in empty boxes.
_CJK = re.compile(r"[　-ヿ㐀-鿿가-힯＀-￯]+")

Font = ImageFont.FreeTypeFont | ImageFont.ImageFont


def _plain(text: str) -> str:
    # DataCite descriptions arrive as escaped HTML ("&lt;h3&gt;Recommended
    # Citation"), sometimes escaped twice.
    for _ in range(2):
        text = html.unescape(text)
    text = " ".join(re.sub(r"<[^>]+>", " ", text).split())
    latin = " ".join(_CJK.sub(" ", text).split())
    return latin or text


def _fit(text: str, face: Font, width: int) -> str:
    """Return ``text`` cut to ``width`` with an ellipsis when it does not fit."""
    if face.getlength(text) <= width:
        return text
    # Binary search: abstracts run to thousands of characters, and trimming one
    # character per measurement made a week of images take minutes.
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if face.getlength(text[:middle] + "…") <= width:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip(" ,·;:-") + "…"


def _wrap(text: str, face: Font, width: int, max_lines: int) -> list[str]:
    if max_lines <= 0:
        return []
    words = _plain(text).split(" ")
    lines: list[str] = []
    current = ""
    for index, word in enumerate(words):
        trial = f"{current} {word}".strip()
        if face.getlength(trial) <= width:
            current = trial
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines - 1:
            current = " ".join([current, *words[index + 1 :]])
            break
    if current:
        lines.append(current)
    # Every line, not only the last: one Hugging Face "owner/repository" token
    # can be wider than the whole text area.
    return [_fit(line, face, width) for line in lines[:max_lines]]


def _names(values: list[str], limit: int) -> str:
    shown = ", ".join(values[:limit])
    return _plain(f"{shown} et al." if len(values) > limit else shown)


def _day(value: Any) -> str:
    try:
        return date.fromisoformat(str(value or "")[:10]).strftime("%b %-d, %Y")
    except ValueError:
        return ""


def _meta_line(card: dict[str, Any]) -> str:
    topics = [
        str(name).replace("_", " ")
        for name in card.get("categories") or []
        if str(name).casefold() not in GENERIC_CATEGORIES
    ]
    parts = [str(card.get("source") or ""), _day(card.get("published_at")), *topics[:2]]
    return " · ".join(part for part in parts if part)


def _block(
    draw: ImageDraw.ImageDraw,
    card: dict[str, Any],
    x: int,
    y: int,
    width: int,
    bottom: int,
    *,
    title_size: int,
    title_lines: int,
    scale: float = 1.0,
) -> None:
    """Draw one benchmark from ``y`` down, no lower than ``bottom``."""
    body = round(22 * scale)
    step = round(body * 1.33)
    title_face = font(title_size, bold=True)
    for line in _wrap(str(card.get("title") or ""), title_face, width, title_lines):
        draw.text((x, y), line, font=title_face, fill=INK)
        y += round(title_size * 1.27)
    y += round(6 * scale)
    if card.get("authors"):
        face = font(body + 1)
        draw.text((x, y), _fit(_names(card["authors"], 3), face, width), font=face, fill=INK)
        y += step + 2
    if card.get("affiliations"):
        face = font(body + 1, bold=True)
        text = _fit(_names(card["affiliations"], 2), face, width)
        draw.text((x, y), text, font=face, fill=TEAL)
        y += step + 2
    y += round(6 * scale)
    meta = font(round(19 * scale))
    meta_height = round(19 * scale) + 8
    summary = font(body)
    lines = max(0, (bottom - meta_height - y) // step)
    for line in _wrap(str(card.get("blurb") or ""), summary, width, lines):
        draw.text((x, y), line, font=summary, fill=SLATE)
        y += step
    draw.text((x, y + 8), _meta_line(card), font=meta, fill=SLATE)


def _canvas(size: tuple[int, int]) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", size, BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 12, size[1]], fill=TEAL)
    return image, draw


def _save(image: Image.Image, draw: ImageDraw.ImageDraw, output: Path) -> Path:
    width, height = image.size
    draw.text(
        (width - MARGIN, height - 40),
        WATERMARK,
        font=font(30, bold=True),
        fill=TEAL,
        anchor="rs",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    # Text on a flat background needs few colours; a palette PNG is about a
    # third of the size, which matters once every catalog benchmark has one.
    image.quantize(colors=64, method=Image.Quantize.MEDIANCUT).save(output, optimize=True)
    return output


def render_top(cards: list[dict[str, Any]], day: str, output: Path) -> Path:
    image, draw = _canvas(TOP_SIZE)
    width = TOP_SIZE[0] - 2 * MARGIN - 70
    draw.text((MARGIN, 58), "Benchmark Radar", font=font(50, bold=True), fill=INK)
    heading = f"Top {len(cards)} benchmarks · {_day(day)}"
    draw.text((MARGIN, 124), heading, font=font(30), fill=TEAL)
    row_top, row_height = 210, 340
    draw.line([(MARGIN, row_top - 24), (TOP_SIZE[0] - MARGIN, row_top - 24)], fill=LIGHT, width=2)
    for index, card in enumerate(cards):
        top = row_top + index * row_height
        draw.text((MARGIN, top), str(index + 1), font=font(44, bold=True), fill=TEAL)
        x = MARGIN + 70
        _block(
            draw,
            card,
            x,
            top,
            width,
            top + row_height - 24,
            title_size=34,
            title_lines=2,
            scale=1.2,
        )
        if index < len(cards) - 1:
            divider = top + row_height - 16
            draw.line([(x, divider), (TOP_SIZE[0] - MARGIN, divider)], fill=LIGHT, width=1)
    return _save(image, draw, output)


def render_card(card: dict[str, Any], label: str, output: Path) -> Path:
    """One benchmark on a 1200x630 card; ``label`` names where it was featured."""
    image, draw = _canvas(CARD_SIZE)
    width = CARD_SIZE[0] - 2 * MARGIN
    draw.text((MARGIN, 40), f"Benchmark Radar · {label}", font=font(24, bold=True), fill=TEAL)
    _block(
        draw, card, MARGIN, 96, width, CARD_SIZE[1] - 80, title_size=44, title_lines=3, scale=1.3
    )
    return _save(image, draw, output)


def render_day(snapshot: dict[str, Any], output_dir: Path) -> list[Path]:
    share = snapshot.get("share") or {}
    cards = share.get("cards") or []
    if not cards:
        return []
    day = str(share.get("date") or snapshot.get("date"))
    label = f"Daily briefing · {_day(day)}"
    written = [render_top(cards[:DEFAULT_LIMIT], day, output_dir / "top3.png")]
    for index, card in enumerate(cards, start=1):
        written.append(render_card(card, label, output_dir / card_image_name(index)))
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    _assert_scalable_fonts()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    written = render_day(snapshot, args.output_dir)
    if not written:
        print(f"{args.snapshot} has no share cards; nothing rendered.")
    for path in written:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
