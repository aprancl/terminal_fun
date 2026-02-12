"""Theme registry, discovery, and loading.

Provides the :class:`ThemeRegistry` class for managing themes, plus
module-level convenience functions :func:`get_theme` and :func:`list_themes`.

Built-in themes are auto-discovered from Python modules in the
``globe_term.themes`` package.  Any module that defines a module-level
:class:`Theme` instance will have it registered automatically.

**Creating a new built-in theme:**

1. Create a new ``.py`` file under ``globe_term/themes/`` (e.g.
   ``my_theme.py``).
2. Define a module-level ``Theme`` instance::

       from globe_term.themes.base import Theme

       MY_THEME = Theme(
           name="my_theme",
           description="A cool custom theme",
           ocean_char="~",
           land_char="#",
           # ... remaining fields use defaults from Theme dataclass
       )

3. The registry will pick it up automatically on next import.

**Required vs optional fields:**

Only ``name`` is required (it has no default).  All other fields have
sensible defaults defined on the ``Theme`` dataclass.  See
:class:`globe_term.themes.base.Theme` for the full field reference.

**Architecture note:**

The :class:`ThemeRegistry` is designed so that external theme sources
(user config directories, pip-installed plugins, etc.) can be added in
the future via :meth:`ThemeRegistry.register` without changing the
discovery mechanism.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Iterator

from globe_term.themes.base import Theme


class ThemeRegistry:
    """Registry that discovers, validates, and serves themes.

    Themes are stored in an internal dictionary keyed by name.  Built-in
    themes are loaded lazily the first time the registry is queried.

    Parameters
    ----------
    auto_discover : bool
        If ``True`` (default), automatically discover built-in themes
        from the ``globe_term.themes`` package on first access.
    """

    def __init__(self, *, auto_discover: bool = True) -> None:
        self._themes: dict[str, Theme] = {}
        self._auto_discover = auto_discover
        self._discovered = False

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, theme: Theme) -> None:
        """Register a theme instance.

        Parameters
        ----------
        theme : Theme
            A validated ``Theme`` instance.  Its ``name`` field is used
            as the registry key.

        Raises
        ------
        TypeError
            If *theme* is not a :class:`Theme` instance.
        ValueError
            If the theme fails validation (missing or invalid fields).
        """
        if not isinstance(theme, Theme):
            raise TypeError(
                f"Expected a Theme instance, got {type(theme).__name__}"
            )
        self._validate(theme)
        self._themes[theme.name] = theme

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> Theme:
        """Return a theme by name.

        Parameters
        ----------
        name : str
            The theme identifier (e.g. ``"geography"``).

        Returns
        -------
        Theme
            The theme instance matching *name*.

        Raises
        ------
        KeyError
            If no theme with the given name is registered.  The error
            message lists all available theme names.
        """
        self._ensure_discovered()
        try:
            return self._themes[name]
        except KeyError:
            available = ", ".join(sorted(self._themes))
            raise KeyError(
                f"Unknown theme '{name}'. Available themes: {available}"
            ) from None

    def list_themes(self) -> list[str]:
        """Return a sorted list of all registered theme names."""
        self._ensure_discovered()
        return sorted(self._themes)

    def __len__(self) -> int:
        self._ensure_discovered()
        return len(self._themes)

    def __iter__(self) -> Iterator[str]:
        self._ensure_discovered()
        return iter(sorted(self._themes))

    def __contains__(self, name: str) -> bool:
        self._ensure_discovered()
        return name in self._themes

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_builtin(self) -> None:
        """Scan ``globe_term.themes`` for modules exporting Theme instances.

        Each ``.py`` module in the package (excluding ``__init__`` and
        ``base``) is imported.  Any module-level attribute that is a
        :class:`Theme` instance is registered.

        Modules that fail to import are silently skipped so that a single
        broken theme file does not crash the application.
        """
        import globe_term.themes as _pkg

        for module_info in pkgutil.iter_modules(_pkg.__path__):
            if module_info.name in ("base",):
                continue
            try:
                mod = importlib.import_module(
                    f"globe_term.themes.{module_info.name}"
                )
            except Exception:  # noqa: BLE001
                continue

            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if isinstance(attr, Theme):
                    self._themes[attr.name] = attr

        self._discovered = True

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(theme: Theme) -> None:
        """Validate that a theme has all required data.

        The ``Theme.__post_init__`` already checks types at construction
        time, but this method provides an additional layer for themes
        that may be constructed externally or deserialized.

        Raises
        ------
        ValueError
            If a required field is missing or clearly invalid.
        """
        if not theme.name or not theme.name.strip():
            raise ValueError("Theme 'name' must be a non-empty string")

        if not theme.shading_chars or len(theme.shading_chars) < 2:
            raise ValueError(
                "Theme 'shading_chars' must contain at least 2 characters "
                f"for a visible gradient, got {len(theme.shading_chars)!r}"
            )

        # Curses color indices must be in the standard range.
        color_fields = ("ocean_fg", "ocean_bg", "land_fg", "land_bg", "border_fg")
        for field_name in color_fields:
            value = getattr(theme, field_name)
            if not (0 <= value <= 255):
                raise ValueError(
                    f"Theme color field '{field_name}' must be 0-255, "
                    f"got {value}"
                )

        # Character fields must be single characters (or empty for optional).
        char_fields = (
            "ocean_char", "land_char", "coastline_char", "ice_char",
            "background_char",
        )
        for field_name in char_fields:
            value = getattr(theme, field_name)
            if len(value) != 1:
                raise ValueError(
                    f"Theme character field '{field_name}' must be a "
                    f"single character, got {value!r}"
                )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_discovered(self) -> None:
        """Trigger auto-discovery if it hasn't happened yet."""
        if self._auto_discover and not self._discovered:
            self.discover_builtin()


# ======================================================================
# Module-level singleton and convenience functions
# ======================================================================

_registry = ThemeRegistry()


def get_theme(name: str) -> Theme:
    """Return a built-in theme by name.

    Parameters
    ----------
    name : str
        The theme identifier (e.g. ``"geography"``).

    Returns
    -------
    Theme
        The :class:`Theme` instance matching *name*.

    Raises
    ------
    KeyError
        If no theme with the given name is registered.
        The error message lists all available theme names.
    """
    return _registry.get(name)


def list_themes() -> list[str]:
    """Return a sorted list of all available theme names."""
    return _registry.list_themes()
