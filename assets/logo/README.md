# The DDD mark

One stem, three bowls: a **D**, drawn three times, sharing the single upright they are all
declarations of. It is the tool's own subject - one component owns the definition of a
variable and the others read it, so the inner bowl is solid and the two outside it are
echoes, drawn in the accent rather than in the ink.

| file | for |
| --- | --- |
| [ddd-mark.svg](ddd-mark.svg) | the mark on a light background |
| [ddd-mark-dark.svg](ddd-mark-dark.svg) | the mark on a dark background |
| [ddd-mark-mono.svg](ddd-mark-mono.svg) | one colour, taken from `currentColor` - html, a one colour print, an engraving |
| [ddd-logo.svg](ddd-logo.svg) / [ddd-logo-dark.svg](ddd-logo-dark.svg) | the horizontal lockup, mark plus wordmark |
| [ddd-icon.svg](ddd-icon.svg) | the tile, for a launcher, an avatar or an extension listing |
| [ddd-favicon.svg](ddd-favicon.svg) | 16 px and below: a single D, because three arcs cannot resolve there |
| `ddd-icon-{128,256,512}.png` | the same tile where a raster is required - the vsix icon, a package index |

The wordmark carries no font. Each `D` is a path - a 20 unit stem and a bowl of radius 50
over a counter of radius 30 - so the letters are built the way the mark is, and a machine
without the typeface still renders them.

## Colours

| role | hex | where |
| --- | --- | --- |
| ink | `#123540` | the stem and its bowl, the wordmark, the icon tile |
| accent | `#1590A6` | the middle bowl |
| accent light | `#35BBD1` | the outer bowl |
| paper | `#F2FAFC` | the stem on a dark background |

On dark the two accents move up a step - `#2C93A8` outside, `#4FC9DC` inside - so that the
outer bowl does not out-shout the stem it belongs to.

## Using it

**Clear space** is the width of the stem (20 units of the 256 grid, a twelfth of the mark's
height) on every side; nothing else sits inside that.

**Minimum size** is 26 px tall for the mark: below that the 9 unit gaps between the bowls
close and it turns into a blob. Under 24 px use `ddd-favicon.svg`, which is the letter alone.

Do not recolour a single bowl, redraw the mark with a stroke width other than 20, or set the
wordmark in a font: the letters and the arcs share one construction, and a substituted `D`
shows.

## Re-exporting the rasters

The pngs are screenshots of `ddd-icon.svg`, so they follow the svg and are never edited by
hand. Any headless browser does it:

```bash
printf '<style>html,body{margin:0}img{display:block;width:128px;height:128px}</style><img src="ddd-icon.svg">' > icon.html
chrome --headless=new --hide-scrollbars --window-size=128,128 --screenshot=ddd-icon-128.png icon.html
```
