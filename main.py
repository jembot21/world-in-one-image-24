#!/usr/bin/env python3
"""Render the supplied 24 November news digest, offline and deterministically."""

from dataclasses import dataclass
from functools import lru_cache
import hashlib
from io import BytesIO
import itertools
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parent
WIDTH = HEIGHT = 1024
SCALE = 3
MAX_PNG_BYTES = 1024 * 1024
PAPER = "#F5F1E8"
INK = "#191916"
RED = "#BB3029"


def load_pillow():
    """Use installed Pillow, or unpack the matching bundled CPython wheel."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        return Image, ImageDraw, ImageFont
    except ImportError:
        # An incomplete installed package must not mask the complete wheel.
        for name in tuple(sys.modules):
            if name == "PIL" or name.startswith("PIL."):
                del sys.modules[name]

    tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    wheels = sorted((ROOT / "vendor").glob(f"pillow-12.0.0-{tag}-{tag}-*.whl"))
    if sys.implementation.name != "cpython" or len(wheels) != 1:
        raise RuntimeError(
            f"Pillow is unavailable and no unique vendored wheel matches {tag}. "
            "Use CPython 3.12 or 3.13 on manylinux x86-64, or install Pillow."
        )
    wheel = wheels[0]
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    cache_root = Path(tempfile.gettempdir()) / "makefun-news24-pillow-cache"
    output = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")).resolve()
    if cache_root.resolve().is_relative_to(output):
        raise RuntimeError("The output directory must not contain the OS temp cache.")
    cache = cache_root / f"{tag}-{digest[:20]}"
    if not (cache / ".ready").is_file():
        cache_root.mkdir(parents=True, exist_ok=True)
        # Publish a complete extraction atomically; simultaneous runs can reuse it.
        with tempfile.TemporaryDirectory(prefix="unpack-", dir=cache_root) as stage:
            unpacked = Path(stage) / "pillow"
            with zipfile.ZipFile(wheel) as archive:
                archive.extractall(unpacked)
            (unpacked / ".ready").write_text(digest, encoding="ascii")
            try:
                unpacked.rename(cache)
            except OSError:
                if not (cache / ".ready").is_file():
                    raise
    sys.path.insert(0, str(cache))
    from PIL import Image, ImageDraw, ImageFont
    return Image, ImageDraw, ImageFont


Image, ImageDraw, ImageFont = load_pillow()


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float


class TextOverflow(ValueError):
    """Fail before writing an image rather than clipping or dropping words."""


class Newspaper:
    def __init__(self):
        self.image = Image.new("RGB", (WIDTH * SCALE, HEIGHT * SCALE), PAPER)
        self.draw = ImageDraw.Draw(self.image)
        self.text_boxes = []

    @staticmethod
    def px(value):
        return int(round(value * SCALE))

    @staticmethod
    @lru_cache(maxsize=None)
    def font(size, bold=False):
        weight = "Bold" if bold else "Regular"
        return ImageFont.truetype(
            str(ROOT / "fonts" / f"LiberationSans-{weight}.ttf"),
            Newspaper.px(size),
            layout_engine=ImageFont.Layout.BASIC,
        )

    @staticmethod
    def line_width(line, font):
        left, _, right, _ = font.getbbox(line)
        return max(font.getlength(line), right - left)

    def wrap(self, text, font, width, single_line=False):
        if single_line:
            return [text]
        lines = []
        for word in text.split():
            if self.line_width(word, font) > width:
                return None
            candidate = f"{lines[-1]} {word}" if lines else word
            if lines and self.line_width(candidate, font) <= width:
                lines[-1] = candidate
            else:
                lines.append(word)
        return lines

    def layout(self, text, width, size, *, bold=False, leading=None, single_line=False):
        font = self.font(size, bold)
        lines = self.wrap(text, font, self.px(width), single_line)
        if not lines:
            return None
        pitch = self.px(leading if leading is not None else size * 1.16)
        bounds = [font.getbbox(line) for line in lines]
        ink_top = min(b[1] for b in bounds)
        height = max(i * pitch + b[3] - ink_top for i, b in enumerate(bounds))
        fits_width = all(self.line_width(line, font) <= self.px(width) for line in lines)
        return font, lines, pitch, ink_top, height, fits_width

    def text_height(self, text, width, size, **style):
        """Reserve whole pixels using the same wrapping and ink metrics as drawing."""
        layout = self.layout(text, width, size, **style)
        if layout is None or not layout[5]:
            raise TextOverflow(f"Cannot wrap {text!r} within {width} pixels")
        return math.ceil(layout[4] / SCALE)

    def text(self, text, box, size, *, bold=False, color=INK, leading=None,
             single_line=False, align="left", min_size=None):
        """Fit every word and record the actual ink bounds of every text box."""
        minimum = size if min_size is None else min_size
        for font_pixels in range(self.px(size), self.px(minimum) - 1, -1):
            used_size = font_pixels / SCALE
            layout = self.layout(
                text, box.w, used_size, bold=bold, leading=leading,
                single_line=single_line,
            )
            if layout is None:
                continue
            font, lines, pitch, ink_top, height, fits_width = layout
            if fits_width and height <= self.px(box.h):
                break
        else:
            raise TextOverflow(f"Cannot fit {text!r} into {box}")

        actual_bounds = []
        for i, line in enumerate(lines):
            left, _, right, _ = font.getbbox(line)
            x = self.px(box.x)
            if align == "center":
                x += (self.px(box.w) - (right - left)) // 2
            elif align == "right":
                x += self.px(box.w) - (right - left)
            position = (x - left, self.px(box.y) - ink_top + i * pitch)
            ink = self.draw.textbbox(position, line, font=font)
            if not (
                ink[0] >= self.px(box.x) and ink[1] >= self.px(box.y)
                and ink[2] <= self.px(box.x + box.w)
                and ink[3] <= self.px(box.y + box.h)
                and 0 <= ink[0] <= ink[2] <= WIDTH * SCALE
                and 0 <= ink[1] <= ink[3] <= HEIGHT * SCALE
            ):
                raise TextOverflow(f"Ink for {line!r} escapes {box}: {ink}")
            actual_bounds.append(ink)
            self.draw.text(position, line, font=font, fill=color)
        if " ".join(lines) != " ".join(text.split()):
            raise TextOverflow(f"Words lost while fitting {text!r}")
        self.text_boxes.append({
            "text": text, "box": box, "size": used_size,
            "lines": len(lines), "ink": actual_bounds,
        })
        return height / SCALE

    def line(self, points, color=INK, width=0.6):
        self.draw.line(
            [(self.px(x), self.px(y)) for x, y in points],
            fill=color, width=max(1, self.px(width)),
        )

    def rectangle(self, box, fill=None, outline=None, width=1):
        self.draw.rectangle(
            (self.px(box.x), self.px(box.y),
             self.px(box.x + box.w), self.px(box.y + box.h)),
            fill=fill, outline=outline, width=self.px(width),
        )

    def icon(self, kind, box):
        """Ten small, flat illustrations, using only geometric Pillow shapes."""
        def point(x, y):
            return self.px(box.x + x * box.w / 32), self.px(box.y + y * box.h / 32)

        def polygon(points, color=RED):
            self.draw.polygon([point(x, y) for x, y in points], fill=color)

        def rect(coords, color=RED):
            self.draw.rectangle((*point(*coords[:2]), *point(*coords[2:])), fill=color)

        def ellipse(coords, color=RED):
            self.draw.ellipse((*point(*coords[:2]), *point(*coords[2:])), fill=color)

        def stroke(points, width=2, color=RED):
            self.draw.line([point(x, y) for x, y in points], fill=color,
                           width=max(1, self.px(width * box.w / 32)))

        if kind == "chart":
            stroke([(3, 3), (3, 28), (29, 28)], 1.6)
            stroke([(6, 23), (12, 17), (17, 19), (23, 5), (29, 14)], 3)
            polygon([(24, 13), (29, 14), (29, 8)])
        elif kind == "scales":
            stroke([(16, 3), (16, 27)], 2.2)
            stroke([(4, 9), (28, 9)], 2)
            for x in (7, 25):
                stroke([(x, 9), (x - 4, 18), (x + 4, 18), (x, 9)], 1)
                polygon([(x - 5, 18), (x + 5, 18), (x + 3, 22), (x - 3, 22)])
            polygon([(11, 26), (21, 26), (24, 29), (8, 29)])
        elif kind == "ship":
            rect((8, 10, 23, 18))
            rect((11, 5, 15, 10))
            polygon([(2, 19), (30, 19), (24, 26), (8, 26)])
            stroke([(3, 29), (9, 28), (15, 29), (21, 28), (28, 29)], 1.5)
        elif kind == "flame":
            polygon([(16, 2), (21, 11), (25, 8), (29, 19), (26, 26),
                     (20, 30), (11, 30), (5, 26), (3, 19), (9, 9),
                     (11, 17), (15, 12)])
            polygon([(16, 17), (22, 26), (18, 29), (13, 28), (11, 25)], PAPER)
        elif kind == "shield":
            polygon([(16, 2), (29, 7), (27, 21), (22, 27), (16, 31),
                     (10, 27), (5, 21), (3, 7)])
            stroke([(16, 7), (16, 24)], 2, PAPER)
            stroke([(10, 15), (22, 15)], 2, PAPER)
        elif kind == "sun":
            ellipse((9, 9, 23, 23))
            for a, b in [((16, 2), (16, 6)), ((16, 26), (16, 30)),
                         ((2, 16), (6, 16)), ((26, 16), (30, 16)),
                         ((5, 5), (8, 8)), ((24, 24), (27, 27)),
                         ((5, 27), (8, 24)), ((24, 8), (27, 5))]:
                stroke([a, b], 2)
        elif kind == "islands":
            ellipse((20, 3, 28, 11))
            polygon([(3, 22), (10, 13), (17, 22)])
            polygon([(15, 22), (21, 17), (28, 22)])
            stroke([(3, 25), (10, 24), (17, 25), (24, 24), (29, 25)], 2)
            stroke([(6, 29), (13, 28), (20, 29), (27, 28)], 1.5)
        elif kind == "accord":
            stroke([(8, 9), (24, 9), (16, 25), (8, 9)], 2)
            for x, y in ((8, 9), (24, 9), (16, 25)):
                ellipse((x - 5, y - 5, x + 5, y + 5))
        elif kind == "store":
            rect((5, 11, 27, 28))
            polygon([(2, 11), (6, 4), (26, 4), (30, 11)])
            rect((10, 15, 14, 20), PAPER)
            rect((19, 16, 24, 28), PAPER)
            stroke([(3, 29), (29, 29)], 1.5)
        elif kind == "trophy":
            polygon([(7, 3), (25, 3), (23, 17), (19, 21), (13, 21), (9, 17)])
            stroke([(8, 7), (3, 7), (4, 15), (10, 17)], 2)
            stroke([(24, 7), (29, 7), (28, 15), (22, 17)], 2)
            rect((14, 20, 18, 27))
            rect((9, 27, 23, 30))
        else:
            raise ValueError(f"Unknown illustration: {kind}")

    def masthead(self, date):
        self.rectangle(Box(0, 0, 1024, 5), fill=RED)
        self.text("THE WORLD IN ONE IMAGE", Box(24, 12, 976, 46), 54,
                  bold=True, align="center", single_line=True)
        self.text(date.upper(), Box(24, 56, 976, 36), 44,
                  bold=True, align="center", single_line=True)
        self.line([(24, 100), (1000, 100)], RED, 2)
        return 110

    def leads(self, stories, top):
        icons = ("chart", "scales", "ship", "flame", "shield", "sun",
                 "islands", "accord", "store", "trophy")
        measured = []
        for story in stories:
            measured.append({
                "kicker": self.text_height(story["kicker"], 440, 9.5,
                                           bold=True, single_line=True),
                "headline": self.text_height(story["headline"], 440, 17,
                                             bold=True, single_line=True),
                "body": self.text_height(story["body"], 374, 11.5, leading=14),
                "value": self.text_height(story["stat"]["value"], 85, 25,
                                          bold=True, single_line=True),
                "label": self.text_height(story["stat"]["label"], 85, 9.5,
                                          leading=10.7),
            })

        y = top
        for row in range(5):
            pair = measured[row * 2:row * 2 + 2]
            kicker_height = max(item["kicker"] for item in pair)
            headline_height = max(item["headline"] for item in pair)
            header_height = max(28, kicker_height + 4 + headline_height)
            body_height = max(max(item["body"], item["value"] + 4 + item["label"])
                              for item in pair)
            body_top = y + header_height + 4
            row_bottom = body_top + body_height + 3

            for column, item in enumerate(pair):
                index = row * 2 + column
                story = stories[index]
                x = 24 + column * 500
                self.icon(icons[index], Box(x, y, 28, 28))
                self.text(story["kicker"], Box(x + 36, y, 440, kicker_height), 9.5,
                          bold=True, color=RED, single_line=True)
                self.text(story["headline"],
                          Box(x + 36, y + kicker_height + 4, 440, headline_height),
                          17, bold=True, single_line=True)

                # Share spare height above and below each body, instead of leaving
                # it all below the final line. The pair uses one common card height.
                body_y = body_top + (body_height - item["body"]) // 2
                self.text(story["body"], Box(x, body_y, 374, item["body"]),
                          11.5, leading=14)
                stat_height = item["value"] + 4 + item["label"]
                stat_y = body_top + (body_height - stat_height) // 2
                self.line([(x + 383, body_top),
                           (x + 383, body_top + body_height)], RED, 0.6)
                self.text(story["stat"]["value"],
                          Box(x + 391, stat_y, 85, item["value"]), 25,
                          bold=True, color=RED, single_line=True)
                self.text(story["stat"]["label"],
                          Box(x + 391, stat_y + item["value"] + 4, 85, item["label"]),
                          9.5, leading=10.7)
                if row < 4:
                    self.line([(x, row_bottom), (x + 476, row_bottom)], width=0.5)
            y = row_bottom + (6 if row < 4 else 0)
        self.line([(512, top), (512, y)], width=0.6)
        return y

    def numbers(self, numbers, top):
        padding = 11
        value_height = 26
        label_height = max(self.text_height(item["label"], 110, 9.5, leading=10.7)
                           for item in numbers)
        height = padding * 2 + value_height + 3 + label_height
        self.rectangle(Box(24, top, 976, height), fill=RED)
        for index, item in enumerate(numbers):
            x = 24 + index * 122
            if index:
                self.line([(x, top + padding), (x, top + height - padding)], PAPER, 0.5)
            self.text(item["value"], Box(x + 6, top + padding, 110, value_height), 24,
                      bold=True, color=PAPER, align="center", single_line=True)
            self.text(item["label"],
                      Box(x + 6, top + padding + value_height + 3, 110, label_height), 9.5,
                      color=PAPER, align="center", leading=10.7)
        return top + height

    def briefs(self, stories, top):
        self.text("AROUND THE WORLD", Box(24, top, 700, 17), 13, bold=True)
        self.text("16 MORE STORIES", Box(780, top + 3, 220, 13), 9.5,
                  color=RED, bold=True, align="right", single_line=True)
        self.line([(24, top + 19), (1000, top + 19)], width=0.6)
        content_top = top + 27
        content_bottom = 981

        # Balance consecutive stories by measured height, preserving reading order.
        measured = [(self.text_height(story["headline"], 312, 12, bold=True, leading=13),
                     self.text_height(story["body"], 312, 11, leading=12.2))
                    for story in stories]
        heights = [headline + 2 + body for headline, body in measured]
        gap = 10

        def column_height(start, end):
            return sum(heights[start:end]) + max(0, end - start - 1) * gap

        splits = min(
            itertools.combinations(range(1, len(stories)), 2),
            key=lambda ab: (
                max(column_height(0, ab[0]), column_height(ab[0], ab[1]),
                    column_height(ab[1], len(stories))),
                ab,
            ),
        )
        boundaries = (0, *splits, len(stories))
        for column in range(3):
            start, end = boundaries[column:column + 2]
            if column_height(start, end) > content_bottom - content_top:
                raise TextOverflow("Briefs cannot fit above the footer")
            x = 24 + column * 332
            y = content_top
            for index in range(start, end):
                story = stories[index]
                headline_height, body_height = measured[index]
                self.text(story["headline"], Box(x, y, 312, headline_height),
                          12, bold=True, leading=13)
                y += headline_height + 2
                self.text(story["body"], Box(x, y, 312, body_height), 11, leading=12.2)
                y += body_height
                if index < end - 1:
                    # Blend ink into the paper for a light rule, without a new hue.
                    self.line([(x, y + gap // 2), (x + 312, y + gap // 2)],
                              "#C9C6BE", 0.35)
                    y += gap
            if column:
                self.line([(x - 10, content_top), (x - 10, content_bottom)], width=0.5)

    def footer(self, date):
        self.rectangle(Box(24, 989, 976, 24), outline=RED, width=1)
        self.text("DATE CHECK", Box(33, 995, 76, 12), 9.5, bold=True, color=RED,
                  single_line=True)
        self.line([(113, 994), (113, 1008)], RED, 0.6)
        self.text(f"Every story happened or was first reported on {date}.",
                  Box(124, 994, 865, 14), 10.5, single_line=True)

    def png_bytes(self):
        image = self.image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True, compress_level=9)
        result = buffer.getvalue()
        if len(result) > MAX_PNG_BYTES:
            # A bounded palette retains smooth text if an encoder produces a larger PNG.
            buffer = BytesIO()
            image.quantize(colors=128, dither=Image.Dither.NONE).save(
                buffer, format="PNG", optimize=True, compress_level=9,
            )
            result = buffer.getvalue()
        if len(result) > MAX_PNG_BYTES:
            raise ValueError(f"PNG exceeds 1 MiB: {len(result)} bytes")
        return result


def read_stories():
    stories = json.loads((ROOT / "stories.json").read_text(encoding="utf-8"))
    if set(stories) != {"date", "leads", "numbers", "briefs"}:
        raise ValueError("Expected date, leads, numbers and briefs")
    if stories["date"] != "Tuesday 24 November 2026":
        raise ValueError("This entry is for Tuesday 24 November 2026")
    if tuple(len(stories[name]) for name in ("leads", "numbers", "briefs")) != (10, 8, 16):
        raise ValueError("Expected exactly 10 leads, 8 numbers and 16 briefs")
    for story in stories["leads"]:
        if set(story) != {"kicker", "headline", "body", "stat"}:
            raise ValueError("Each lead requires a kicker, headline, body and stat")
        if set(story["stat"]) != {"value", "label"}:
            raise ValueError("Each lead stat requires a value and label")
    for number in stories["numbers"]:
        if set(number) != {"value", "label"}:
            raise ValueError("Each number requires a value and label")
    for brief in stories["briefs"]:
        if set(brief) != {"headline", "body"}:
            raise ValueError("Each brief requires a headline and body")
    return stories


def render(stories):
    newspaper = Newspaper()
    top = newspaper.masthead(stories["date"])
    top = newspaper.leads(stories["leads"], top)
    top = newspaper.numbers(stories["numbers"], top + 10)
    newspaper.briefs(stories["briefs"], top + 11)
    newspaper.footer(stories["date"])
    return newspaper.png_bytes(), newspaper.text_boxes


def main():
    png, boxes = render(read_stories())
    output = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "entry.png"
    destination.write_bytes(png)
    print(json.dumps({
        "file": str(destination), "width": WIDTH, "height": HEIGHT,
        "bytes": len(png), "text_boxes_checked": len(boxes), "text_overflows": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
