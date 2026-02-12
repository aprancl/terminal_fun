"""Theme base class / dataclass definition.

Defines the Theme dataclass that serves as a declarative format for all
globe_term visual themes. Each theme specifies characters, colors, and
rendering options that the renderer uses to display the globe.
"""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class Theme:
    """Declarative theme definition for globe rendering.

    A theme provides all the information the renderer needs to select
    characters and colors for each terrain type.  Themes are immutable
    (frozen) to prevent accidental mutation during rendering.

    Color fields (``*_fg``, ``*_bg``) store curses color-pair indices.
    The renderer is responsible for initializing curses color pairs that
    correspond to these indices.

    Attributes:
        name: Unique theme identifier used for lookup (e.g. ``"geography"``).
        description: Human-readable description of the theme.
        ocean_char: Character used for ocean terrain cells.
        land_char: Character used for land terrain cells.
        coastline_char: Character used for coastline borders (optional).
        ice_char: Character used for polar ice caps (optional).
        shading_chars: Gradient string from lightest to darkest, used for
            depth and lighting effects (e.g. ``" .:-=+*#%@"``).
        ocean_fg: Foreground curses color-pair index for ocean.
        ocean_bg: Background curses color-pair index for ocean.
        land_fg: Foreground curses color-pair index for land.
        land_bg: Background curses color-pair index for land.
        border_fg: Foreground curses color-pair index for borders/coastlines.
        background_char: Character for empty space outside the globe.
        use_unicode: Whether the theme uses Unicode block characters.
        use_braille: Whether the theme uses Braille characters for
            sub-character resolution rendering.
    """

    # Identity
    name: str
    description: str = ""

    # Terrain characters
    ocean_char: str = "~"
    land_char: str = "#"
    coastline_char: str = "+"
    ice_char: str = "*"
    shading_chars: str = " .:-=+*#%@"

    # Color pair indices (curses)
    ocean_fg: int = 4   # blue
    ocean_bg: int = 0   # black
    land_fg: int = 2    # green
    land_bg: int = 0    # black
    border_fg: int = 7  # white

    # Background / empty space
    background_char: str = " "

    # Rendering capability flags
    use_unicode: bool = False
    use_braille: bool = False

    def __post_init__(self) -> None:
        """Validate field types after initialization."""
        for f in fields(self):
            value = getattr(self, f.name)
            if not isinstance(value, f.type if isinstance(f.type, type) else _resolve_type(f.type)):
                raise TypeError(
                    f"Theme field '{f.name}' expects {f.type}, "
                    f"got {type(value).__name__}"
                )


def _resolve_type(annotation: str | type) -> type:
    """Resolve a type annotation string to a type object.

    Handles the ``from __future__ import annotations`` case where all
    annotations are stored as strings.
    """
    type_map = {"str": str, "int": int, "bool": bool, "float": float}
    if isinstance(annotation, str):
        return type_map.get(annotation, str)
    return annotation  # type: ignore[return-value]
