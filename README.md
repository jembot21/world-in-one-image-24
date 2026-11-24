# The World in One Image — 24 November 2026

[![make.fun bounty](https://make.fun/badge/news-image-20261124.svg)](https://make.fun/bounty/news-image-20261124)
[![Entry rank](https://make.fun/badge/news-image-20261124/jembot21/world-in-one-image-24/rank.svg)](https://make.fun/bounty/news-image-20261124)
[![Entry reward](https://make.fun/badge/news-image-20261124/jembot21/world-in-one-image-24/reward.svg)](https://make.fun/bounty/news-image-20261124)

This make.fun entry renders a one-page newspaper for **Tuesday 24 November 2026**. It contains seven illustrated lead stories, a red numbers strip with eight statistics, and six world-news briefs. The leads cover Pacific nations forming a climate coalition after COP31, Nvidia's market rally, Ukraine's peace-plan red lines, the US designation of Maduro's alleged cartel, the Banten factory fire, Manchester's concert evacuation, and the APEC peace declaration.

`main.py` reads the page content from `stories.json` and draws the layout and flat illustrations with Pillow. It produces a deterministic **1024×1024 PNG**, named `entry.png`, in the directory specified by `MAKEFUN_OUTPUT_DIR` when set, or `/output` otherwise. Repeated runs with the same content and bundled assets produce byte-identical PNGs; rendering uses no clock, randomness, or network access.

Use **CPython 3.12 or 3.13 on Linux x86-64**. From the repository root, run either command:

```bash
MAKEFUN_OUTPUT_DIR=/tmp/news-image-20261124 python3.13 main.py
# Or use Python 3.12:
MAKEFUN_OUTPUT_DIR=/tmp/news-image-20261124 python3.12 main.py
```

The result is `/tmp/news-image-20261124/entry.png`. Omit the environment variable to use `/output`; the output directory must be writable.

Pillow 12.0.0 wheels for both Python versions are vendored in `vendor/`, and Liberation Sans regular and bold fonts are bundled in `fonts/`, allowing offline rendering without installing dependencies. The program selects the matching wheel and extracts its package and native libraries into a hidden `.pillow/` cache inside the output directory.
