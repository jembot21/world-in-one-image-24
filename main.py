#!/usr/bin/env python3
"""Render the 24 November 2026 front page, using only bundled assets."""

import hashlib
import json
import os
from pathlib import Path
import sys
from functools import lru_cache
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parent
OUTPUT = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
sys.dont_write_bytecode = True


def load_vendored_pillow():
    """Native wheel extensions need real files; unpack beside the output."""
    abi = f"cp{sys.version_info.major}{sys.version_info.minor}"
    if abi not in ("cp313", "cp312") or sys.implementation.name != "cpython":
        raise RuntimeError("Use CPython 3.13 (or the bundled 3.12 fallback).")
    wheels = sorted((ROOT / "vendor").glob(f"pillow-12.0.0-{abi}-{abi}-*.whl"))
    if not wheels:
        raise RuntimeError(f"The bundled Pillow wheel for {abi} is missing.")
    wheel = wheels[0]
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()[:16]
    cache = OUTPUT / ".pillow" / f"{abi}-{digest}"
    with ZipFile(wheel) as archive:
        for name in sorted(archive.namelist()):
            # Pillow's package and its adjacent native libraries are sufficient.
            if not name.endswith("/") and name.startswith(("PIL/", "pillow.libs/")):
                destination = cache / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                content = archive.read(name)
                if not destination.is_file() or destination.read_bytes() != content:
                    destination.write_bytes(content)
    sys.path.insert(0, str(cache.resolve()))


load_vendored_pillow()
from PIL import Image, ImageDraw, ImageFont  # noqa: E402


SCALE = 2
PAPER = "#f4f0e5"
CARD = "#fbf8f0"
INK = "#172722"
MUTED = "#505a52"
RULE = "#babeb2"
RED = "#c32c32"
TEAL = "#267c74"
SKY = "#dfece7"
GOLD = "#efbb4d"
WHITE = "#fffaf0"
BLUE = "#245b8b"
image = Image.new("RGB", (1024 * SCALE, 1024 * SCALE), PAPER)
draw = ImageDraw.Draw(image)


@lru_cache(maxsize=None)
def font(size, bold=False):
    weight = "Bold" if bold else "Regular"
    other = "Regular" if bold else "Bold"
    for candidate in (
        ROOT / "fonts" / f"LiberationSans-{weight}.ttf",
        ROOT / "fonts" / f"LiberationSans-{other}.ttf",
    ):
        if candidate.is_file():
            try:
                return ImageFont.truetype(
                    str(candidate), round(size * SCALE),
                    layout_engine=ImageFont.Layout.BASIC,
                )
            except OSError:
                pass
    # Pillow embeds a scalable font, so even a machine with no fonts can render.
    return ImageFont.load_default(size=round(size * SCALE))


def box(coords, fill, outline=None, width=1):
    draw.rectangle(tuple(round(v * SCALE) for v in coords), fill=fill,
                   outline=outline, width=round(width * SCALE))


def ellipse(coords, fill):
    draw.ellipse(tuple(round(v * SCALE) for v in coords), fill=fill)


def line(points, fill=INK, width=1):
    draw.line([(round(x * SCALE), round(y * SCALE)) for x, y in points],
              fill=fill, width=round(width * SCALE))


def polygon(points, fill):
    draw.polygon([(round(x * SCALE), round(y * SCALE)) for x, y in points], fill=fill)


def text(x, y, content, size, bold=False, fill=INK):
    draw.text((round(x * SCALE), round(y * SCALE)), content, font=font(size, bold),
              fill=fill, anchor="lt")


def wrap(content, size, bold, width):
    result = []
    for paragraph in content.split("\n"):
        current = ""
        for word in paragraph.split():
            trial = f"{current} {word}" if current else word
            if font(size, bold).getlength(trial) / SCALE <= width:
                current = trial
            else:
                if not current or font(size, bold).getlength(word) / SCALE > width:
                    raise ValueError(f"Word cannot fit in text column: {word}")
                result.append(current)
                current = word
        result.append(current)
    return result


def text_block(content, x, y, width, height, size, bold=False, fill=INK, minimum=None):
    minimum = size if minimum is None else minimum
    for candidate in range(size, minimum - 1, -1):
        rows = wrap(content, candidate, bold, width)
        leading = round(candidate * 1.14)
        if len(rows) * leading <= height:
            for index, row in enumerate(rows):
                text(x, y + index * leading, row, candidate, bold, fill)
            return y + len(rows) * leading
    raise ValueError(f"Text does not fit its panel: {content}")


def centered(content, x, y, width, size, bold=False, fill=INK):
    actual = font(size, bold).getlength(content) / SCALE
    text(x + (width - actual) / 2, y, content, size, bold, fill)


def illustration(kind, bounds):
    """Seven flat editorial drawings, in a fixed 100 by 100 coordinate space."""
    x, y, w, h = bounds

    def points(items):
        return [(x + u * w / 100, y + v * h / 100) for u, v in items]

    def r(a, b, c, d, color):
        box((x + a * w / 100, y + b * h / 100,
             x + c * w / 100, y + d * h / 100), color)

    def e(a, b, c, d, color):
        ellipse((x + a * w / 100, y + b * h / 100,
                 x + c * w / 100, y + d * h / 100), color)

    def p(items, color):
        polygon(points(items), color)

    def l(items, color=INK, weight=2):
        line(points(items), color, weight)

    r(0, 0, 100, 100, SKY)
    if kind == "pacific":
        e(63, 8, 91, 43, GOLD)
        for ray in (((76, 0), (76, 5)), ((96, 22), (100, 22)),
                    ((56, 23), (61, 23)), ((93, 5), (89, 10))):
            l(ray, GOLD, 2)
        r(0, 68, 100, 100, TEAL)
        e(12, 69, 89, 101, "#e9cd8a")
        l(((0, 82), (15, 82)), WHITE)
        l(((88, 91), (100, 91)), WHITE)
        for trunk, crown in ((32, 29), (61, 41)):
            p(((trunk, 84), (trunk + 5, 84), (trunk + 9, crown),
               (trunk + 5, crown)), "#715838")
            cx = trunk + 7
            for leaf in (
                ((cx, crown), (cx - 25, crown - 7), (cx - 15, crown + 2)),
                ((cx, crown), (cx - 22, crown + 15), (cx - 13, crown + 4)),
                ((cx, crown), (cx + 21, crown - 11), (cx + 13, crown + 1)),
                ((cx, crown), (cx + 25, crown + 11), (cx + 14, crown + 2)),
                ((cx, crown), (cx + 2, crown - 20), (cx - 5, crown - 5)),
            ):
                p(leaf, INK)
    elif kind == "markets":
        for level in (25, 50, 75):
            l(((4, level), (96, level)), RULE, 1)
        for left, top in ((10, 75), (29, 62), (48, 49), (67, 25)):
            r(left, top, left + 12, 96, TEAL)
        l(((6, 71), (29, 64), (45, 67), (65, 40), (91, 13)), RED, 4)
        p(((91, 4), (94, 32), (76, 12)), RED)
    elif kind == "ukraine":
        l(((9, 18), (9, 92)), INK, 2)
        l(((56, 28), (56, 92)), INK, 2)
        r(10, 18, 47, 37, "#2375b9")
        r(10, 38, 47, 57, GOLD)
        r(57, 28, 95, 41, WHITE)
        r(57, 42, 95, 54, BLUE)
        r(57, 55, 95, 67, RED)
        l(((40, 89), (52, 9)), RED, 4)
    elif kind == "carrier":
        r(0, 77, 100, 100, TEAL)
        p(((5, 61), (95, 61), (81, 82), (23, 82)), "#637b7a")
        r(13, 55, 96, 62, INK)
        r(63, 33, 78, 55, "#8eaaa5")
        r(60, 29, 81, 34, INK)
        l(((72, 29), (72, 12)), INK, 2)
        l(((66, 17), (83, 17)), INK, 2)
        for left in (25, 40, 54):
            p(((left, 45), (left + 3, 51), (left + 10, 53),
               (left + 3, 55), (left - 4, 53)), INK)
        l(((0, 90), (22, 90)), WHITE)
        l(((49, 94), (80, 94)), WHITE)
    elif kind == "factory":
        p(((15, 67), (9, 38), (25, 49), (31, 8), (46, 34),
           (56, 14), (70, 41), (86, 25), (92, 69)), RED)
        p(((24, 65), (24, 43), (38, 52), (42, 25), (56, 54),
           (69, 39), (77, 66)), GOLD)
        r(13, 66, 94, 97, "#82958c")
        p(((13, 66), (13, 56), (37, 66), (37, 55), (62, 66),
           (62, 55), (86, 66)), INK)
        r(84, 45, 93, 68, INK)
        for left in (23, 43, 63):
            r(left, 77, left + 10, 88, WHITE)
    elif kind == "crowd":
        r(67, 7, 98, 69, TEAL)
        r(73, 17, 92, 59, WHITE)
        l(((96, 35), (71, 35)), RED, 3)
        p(((69, 35), (79, 26), (79, 44)), RED)
        e(5, 3, 23, 25, "#bccdc6")
        e(18, 7, 36, 27, "#bccdc6")
        for cx, cy, coat in ((12, 41, BLUE), (34, 35, RED), (56, 44, TEAL),
                             (24, 66, TEAL), (47, 68, BLUE), (72, 67, RED)):
            e(cx - 6, cy - 8, cx + 6, cy + 7, "#dbab80")
            p(((cx - 10, cy + 9), (cx + 10, cy + 9),
               (cx + 13, cy + 32), (cx - 13, cy + 32)), coat)
    elif kind == "apec":
        for left in (5, 37, 69):
            l(((left, 7), (left, 52)), INK, 1)
        r(6, 7, 31, 36, WHITE)
        for top in (7, 15, 23, 31):
            r(6, top, 31, top + 3, RED)
        r(6, 7, 16, 22, BLUE)
        e(9, 11, 12, 15, WHITE)
        r(38, 7, 63, 36, RED)
        p(((46, 12), (48, 17), (53, 17), (49, 20), (50, 25),
           (46, 22), (42, 25), (43, 20), (39, 17), (44, 17)), GOLD)
        r(70, 7, 95, 16, WHITE)
        r(70, 17, 95, 26, BLUE)
        r(70, 27, 95, 36, RED)
        p(((0, 64), (21, 55), (39, 80), (22, 97), (0, 88)), TEAL)
        p(((100, 64), (80, 55), (62, 80), (80, 97), (100, 88)), RED)
        p(((23, 60), (39, 54), (58, 66), (75, 63), (78, 79),
           (56, 94), (37, 79)), "#dcae83")
        p(((77, 60), (59, 53), (42, 64), (39, 76), (48, 80),
           (59, 70), (71, 78)), "#edc39a")
        l(((42, 76), (56, 85), (67, 77)), INK, 1)
    else:
        raise ValueError(f"Unknown illustration: {kind}")


def panel(x, y, width, height, accent):
    box((x, y, x + width, y + height), CARD, RULE)
    box((x, y, x + width, y + 4), accent)


def kicker(story, index, x, y, size=13):
    text(x, y, f"{index:02d} / {story['kicker']}", size, True, TEAL)


def masthead(date):
    text(28, 14, "WORLD DESK  /  THE DAILY PICTURE", 12, True, TEAL)
    text(28, 38, "The World in One Image", 64, True)
    text(28, 106, date, 28, True, RED)
    line(((28, 140), (996, 140)), INK, 3)


def top_leads(leads):
    pacific, markets = leads[:2]
    panel(28, 153, 574, 198, TEAL)
    kicker(pacific, 1, 42, 164)
    text_block(pacific["headline"], 42, 187, 366, 76, 34, True, minimum=33)
    text_block(pacific["body"], 42, 269, 366, 74, 16, minimum=15)
    illustration("pacific", (432, 187, 155, 94))
    text(435, 289, pacific["stat"]["value"], 42, True, TEAL)
    text_block(pacific["stat"]["label"], 435, 334, 153, 14, 11)

    panel(616, 153, 380, 198, TEAL)
    kicker(markets, 2, 630, 164)
    text_block(markets["headline"], 630, 190, 240, 75, 32, True, minimum=31)
    centered(markets["stat"]["value"], 879, 189, 103, 31, True, TEAL)
    centered(markets["stat"]["label"], 879, 224, 103, 10, True)
    illustration("markets", (883, 240, 98, 25))
    text_block(markets["body"], 630, 274, 352, 69, 16, minimum=15)


def numbers_strip(numbers):
    box((0, 365, 1024, 454), RED)
    text(28, 371, "THE DAY IN NUMBERS", 10, True, WHITE)
    for index, number in enumerate(numbers):
        x = 28 + index * 121
        if index:
            line(((x, 386), (x, 447)), "#df7977", 1)
        centered(number["value"], x + 3, 387, 115, 30, True, WHITE)
        for row, label in enumerate(number["label"].split("\n")):
            centered(label, x + 3, 423 + row * 14, 115, 12, False, WHITE)


def middle_leads(leads):
    for index, x, width, art, accent in (
        (2, 28, 313, "ukraine", RED),
        (3, 355, 312, "carrier", TEAL),
        (4, 681, 315, "factory", RED),
    ):
        story = leads[index]
        panel(x, 469, width, 202, accent)
        kicker(story, index + 1, x + 14, 481, 12)
        text_block(story["headline"], x + 14, 505, width - 111, 62,
                   27, True, minimum=26)
        illustration(art, (x + width - 92, 505, 78, 56))
        text_block(story["body"], x + 14, 574, width - 28, 68,
                   15, minimum=14)
        line(((x + 14, 643), (x + width - 14, 643)), RULE, 1)
        text(x + 14, 649, story["stat"]["value"], 20, True, accent)
        text(x + 77, 655, story["stat"]["label"], 11, False, MUTED)


def lower_leads(leads):
    for index, x, width, art in ((5, 28, 476, "crowd"), (6, 518, 478, "apec")):
        story = leads[index]
        panel(x, 685, width, 134, TEAL)
        kicker(story, index + 1, x + 14, 697, 12)
        text_block(story["headline"], x + 14, 720, width - 138, 31,
                   26, True, minimum=24)
        text_block(story["body"], x + 14, 757, width - 138, 54,
                   15, minimum=14)
        centered(story["stat"]["value"], x + width - 112, 699, 98, 29, True, TEAL)
        centered(story["stat"]["label"], x + width - 112, 732, 98, 10, True)
        illustration(art, (x + width - 110, 755, 96, 50))


def briefs_section(briefs):
    line(((28, 832), (996, 832)), INK, 2)
    text(28, 843, "BRIEFS  /  THE REST OF THE WORLD", 14, True, TEAL)
    for x in (348, 674):
        line(((x, 866), (x, 1006)), RULE, 1)
    line(((28, 936), (996, 936)), RULE, 1)
    for index, brief in enumerate(briefs):
        row, column = divmod(index, 3)
        x = (28, 355, 681)[column]
        y = (866, 942)[row]
        text_block(brief["headline"], x, y, 306, 18, 15, True, minimum=14)
        text_block(brief["body"], x, y + 21, 306, 45, 13, minimum=12)


def main():
    with (ROOT / "stories.json").open(encoding="utf-8") as source:
        stories = json.load(source)
    for key, required in (("leads", 7), ("numbers", 8), ("briefs", 6)):
        if len(stories[key]) != required:
            raise ValueError(f"stories.json must contain {required} {key}.")
    masthead(stories["date"])
    top_leads(stories["leads"])
    numbers_strip(stories["numbers"])
    middle_leads(stories["leads"])
    lower_leads(stories["leads"])
    briefs_section(stories["briefs"])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    destination = OUTPUT / "entry.png"
    final = image.resize((1024, 1024), Image.Resampling.LANCZOS)
    final.save(destination, format="PNG", compress_level=9, optimize=False)
    payload = destination.read_bytes()
    if len(payload) >= 1024 * 1024:
        raise RuntimeError("The PNG exceeds the 1 MiB limit.")
    print(f"{destination}: 1024x1024, {len(payload)} bytes, "
          f"sha256 {hashlib.sha256(payload).hexdigest()}")


if __name__ == "__main__":
    main()
