"""Built-in matrix theme.

Green-on-black, digital/futuristic aesthetic inspired by The Matrix.
Uses green shading for all terrain types with distinct characters to
differentiate land from ocean even in monochrome mode.

Color pair indices follow curses conventions:
  0 = black, 1 = red, 2 = green, 3 = yellow/brown,
  4 = blue, 5 = magenta, 6 = cyan, 7 = white

The theme uses green (2) for land and ocean foreground, with different
character palettes to create visual contrast.  Land uses bright green
(standard green) and ocean uses dark green (cyan as a darker stand-in
on 8-color terminals, mapped to index 6).  Borders use bright
white-green (index 2 with different chars) to pop against the
background.

Shading chars evoke a digital/binary aesthetic: digits, slashes, and
block-like characters that suggest cascading data streams.
"""

from __future__ import annotations

from globe_term.themes.base import Theme

#: The built-in matrix theme.
#:
#: All terrain rendered in green-on-black.  Land uses bright green (2)
#: and ocean uses cyan (6) as a darker-green stand-in on standard
#: 8-color terminals.  Borders use green (2) with distinct character.
#:
#: Character choices evoke digital/cyber aesthetics:
#:   - Ocean shading: spaces through dots to tildes — subdued, watery
#:   - Land shading: digits and symbols — dense, digital-rain feel
#:   - Coastline: ``|`` — a vertical bar suggesting a data boundary
#:   - Ice: ``*`` — a bright node / spark
#:   - Background: space — pure black void
#:
#: In monochrome mode the distinct characters for each terrain type
#: (``~`` for ocean, ``0`` for land, ``|`` for coast, ``*`` for ice)
#: provide clear differentiation without relying on colour.
MATRIX_THEME = Theme(
    name="matrix",
    description="Green-on-black digital/futuristic aesthetic",
    ocean_char="~",
    land_char="0",
    coastline_char="|",
    ice_char="*",
    shading_chars=" .:;=+01#@",
    ocean_fg=6,   # cyan — darker green on 8-color terminals
    ocean_bg=0,   # black
    land_fg=2,    # green — bright green
    land_bg=0,    # black
    border_fg=2,  # green — same family, different char distinguishes
    background_char=" ",
    use_unicode=False,
    use_braille=False,
)
