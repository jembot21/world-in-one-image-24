# The World in One Image — 24 November 2026

[![Bounty](https://make.fun/badge/news-image-20261124.svg)](https://make.fun/bounty/news-image-20261124)
[![Entry rank](https://make.fun/badge/news-image-20261124/jembot21/world-in-one-image-24/rank.svg)](https://make.fun/bounty/news-image-20261124)
[![Entry reward](https://make.fun/badge/news-image-20261124/jembot21/world-in-one-image-24/reward.svg)](https://make.fun/bounty/news-image-20261124)

This make.fun entry renders a one-page newspaper for Tuesday 24 November 2026:
ten illustrated lead stories, a red numbers strip with eight statistics, and
sixteen world-news briefs.

The lead topics are the markets reversal, the Huawei verdict, the Hormuz claim
and denial, the Banten fire toll, Ukraine's deadline, Venezuela's rejection, the
COP31 Pacific bloc, the APEC declaration, the Cartagena siege, and Senegal's
reinstated title.

`main.py` reads the content from `stories.json` and draws the newspaper layout
and flat geometric illustrations with Pillow. It produces a deterministic
1024 × 1024 PNG named `entry.png` in the directory specified by
`MAKEFUN_OUTPUT_DIR` when set, otherwise in `/output`. Rendering uses no clock,
randomness, or network access, and repeated runs produce byte-identical PNGs.
No timestamps are added to the image.

Run from the repository root with CPython 3.12 or 3.13 on Linux x86-64
(manylinux-compatible). No dependency installation is needed. For example,
render into a fresh scratch output directory outside the repository:

```sh
scratch_output="$(mktemp -d /tmp/news24-output.XXXXXX)"
MAKEFUN_OUTPUT_DIR="$scratch_output" python3.12 main.py
```

Use `python3.13` in place of `python3.12` for CPython 3.13. The generated image
is at `$scratch_output/entry.png`. To use the default `/output` directory, run
`python3.12 main.py` with `MAKEFUN_OUTPUT_DIR` unset.

Pillow 12.0.0 wheels for both CPython versions are vendored in `vendor/`, and
Liberation Sans Regular and Bold fonts are bundled in `fonts/`, so rendering
works offline. If Pillow is already installed, the program uses it. Otherwise,
it extracts the matching vendored wheel into a wheel-hash cache under the
operating system's temp directory, in `makefun-news24-pillow-cache/`. This cache
stays outside the output directory and is reused on subsequent runs; no package
installation or download occurs.

The only generated output file is `entry.png`, capped at 1 MiB. Successful runs
print JSON containing its path, dimensions, byte size, and number of checked
text boxes. Text is measured before drawing, and every line's actual ink bounds
are checked; overflow or lost words fail the render before the PNG is written.

The project is licensed under the [MIT License](LICENSE). The bundled fonts'
license is in [fonts/LICENSE.txt](fonts/LICENSE.txt).
