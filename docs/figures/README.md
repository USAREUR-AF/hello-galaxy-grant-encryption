# Figures

`make-figures.py` draws the figure at the top of the root README, `read-and-deny`, in a
light and a dark version for a `<picture>` element. Its facts come from
scenario 03 (`scenarios/03-read-and-deny/run.py`): the names, topics and the message the member opens; the build stops if one of them is no longer there.

```
python3 -I docs/figures/make-figures.py           # write the SVG files
python3 -I docs/figures/make-figures.py --check   # exit 1 if a committed SVG is out of date
```

Standard library only. The SVG files are self-contained: no external fonts,
styles or images.
