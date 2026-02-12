"""Built-in geography theme.

Standard earth-tone theme with blue oceans, green/brown land, and white
ice caps.  This is the default theme shipped with globe_term.
"""

from __future__ import annotations

from globe_term.themes.base import Theme

#: The built-in geography theme.
#:
#: Color pair indices follow curses conventions:
#:   0 = black, 1 = red, 2 = green, 3 = yellow/brown,
#:   4 = blue, 5 = magenta, 6 = cyan, 7 = white
#:
#: The shading_chars gradient provides visible depth even in monochrome
#: mode: spaces for deep ocean, denser characters for shallow water and
#: land surfaces, and the heaviest glyphs for lit terrain peaks.
GEOGRAPHY_THEME = Theme(
    name="geography",
    description="Standard earth tones: blue oceans, green land, white ice caps",
    ocean_char="~",
    land_char="#",
    coastline_char="+",
    ice_char="*",
    shading_chars=" .:-=+*#%@",
    ocean_fg=4,   # blue foreground
    ocean_bg=0,   # black background
    land_fg=2,    # green foreground
    land_bg=0,    # black background
    border_fg=7,  # white foreground for coastlines
    background_char=" ",
    use_unicode=False,
    use_braille=False,
)
