"""Tests for the theme base class, geography theme, matrix theme, registry, and discovery."""

from __future__ import annotations

import pytest

from globe_term.themes import ThemeRegistry, get_theme, list_themes
from globe_term.themes.base import Theme
from globe_term.themes.geography import GEOGRAPHY_THEME
from globe_term.themes.matrix import MATRIX_THEME


# ---------------------------------------------------------------------------
# Unit: Theme dataclass instantiation with all fields
# ---------------------------------------------------------------------------


class TestThemeDataclass:
    """Theme dataclass creation and field defaults."""

    def test_create_theme_with_all_fields(self) -> None:
        theme = Theme(
            name="test",
            description="A test theme",
            ocean_char="~",
            land_char="#",
            coastline_char="+",
            ice_char="*",
            shading_chars=" .:-=+*#%@",
            ocean_fg=4,
            ocean_bg=0,
            land_fg=2,
            land_bg=0,
            border_fg=7,
            background_char=" ",
            use_unicode=False,
            use_braille=False,
        )
        assert theme.name == "test"
        assert theme.description == "A test theme"
        assert theme.ocean_char == "~"
        assert theme.land_char == "#"
        assert theme.coastline_char == "+"
        assert theme.ice_char == "*"
        assert theme.shading_chars == " .:-=+*#%@"
        assert theme.ocean_fg == 4
        assert theme.ocean_bg == 0
        assert theme.land_fg == 2
        assert theme.land_bg == 0
        assert theme.border_fg == 7
        assert theme.background_char == " "
        assert theme.use_unicode is False
        assert theme.use_braille is False

    def test_create_theme_with_defaults(self) -> None:
        theme = Theme(name="minimal")
        assert theme.name == "minimal"
        assert theme.description == ""
        assert theme.ocean_char == "~"
        assert theme.land_char == "#"
        assert theme.coastline_char == "+"
        assert theme.ice_char == "*"
        assert isinstance(theme.shading_chars, str)
        assert len(theme.shading_chars) > 0
        assert theme.ocean_fg == 4
        assert theme.ocean_bg == 0
        assert theme.land_fg == 2
        assert theme.land_bg == 0
        assert theme.border_fg == 7
        assert theme.background_char == " "
        assert theme.use_unicode is False
        assert theme.use_braille is False

    def test_theme_is_frozen(self) -> None:
        theme = Theme(name="frozen")
        with pytest.raises(AttributeError):
            theme.name = "mutated"  # type: ignore[misc]

    def test_theme_type_validation_rejects_bad_name(self) -> None:
        with pytest.raises(TypeError, match="name"):
            Theme(name=123)  # type: ignore[arg-type]

    def test_theme_type_validation_rejects_bad_color(self) -> None:
        with pytest.raises(TypeError, match="ocean_fg"):
            Theme(name="bad", ocean_fg="blue")  # type: ignore[arg-type]

    def test_theme_type_validation_rejects_bad_bool(self) -> None:
        with pytest.raises(TypeError, match="use_unicode"):
            Theme(name="bad", use_unicode="yes")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Unit: get_theme returns correct theme by name
# ---------------------------------------------------------------------------


class TestGetTheme:
    """get_theme registry lookup."""

    def test_get_geography_theme(self) -> None:
        theme = get_theme("geography")
        assert theme is GEOGRAPHY_THEME
        assert theme.name == "geography"

    def test_get_unknown_theme_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="Unknown theme 'nonexistent'"):
            get_theme("nonexistent")

    def test_error_message_lists_available_themes(self) -> None:
        with pytest.raises(KeyError, match="geography"):
            get_theme("nonexistent")


# ---------------------------------------------------------------------------
# Unit: Geography theme has valid color values
# ---------------------------------------------------------------------------


class TestGeographyTheme:
    """Geography theme correctness."""

    def test_geography_has_blue_ocean(self) -> None:
        assert GEOGRAPHY_THEME.ocean_fg == 4  # curses.COLOR_BLUE

    def test_geography_has_green_land(self) -> None:
        assert GEOGRAPHY_THEME.land_fg == 2  # curses.COLOR_GREEN

    def test_geography_has_white_border(self) -> None:
        assert GEOGRAPHY_THEME.border_fg == 7  # curses.COLOR_WHITE

    def test_geography_name(self) -> None:
        assert GEOGRAPHY_THEME.name == "geography"

    def test_geography_has_description(self) -> None:
        assert len(GEOGRAPHY_THEME.description) > 0

    def test_geography_shading_chars_gradient(self) -> None:
        """Shading chars should have multiple levels for visible depth."""
        assert len(GEOGRAPHY_THEME.shading_chars) >= 5

    def test_geography_color_values_are_valid_curses_indices(self) -> None:
        """All color indices should be in the standard curses range 0-7."""
        for field_name in ("ocean_fg", "ocean_bg", "land_fg", "land_bg", "border_fg"):
            value = getattr(GEOGRAPHY_THEME, field_name)
            assert 0 <= value <= 7, f"{field_name}={value} outside curses range"

    def test_geography_works_monochrome(self) -> None:
        """Shading chars alone should convey terrain without color.

        In monochrome mode, different characters for ocean, land, coastline
        and ice must be distinguishable, and shading_chars must have enough
        levels to convey depth.
        """
        chars = {
            GEOGRAPHY_THEME.ocean_char,
            GEOGRAPHY_THEME.land_char,
            GEOGRAPHY_THEME.coastline_char,
            GEOGRAPHY_THEME.ice_char,
        }
        # All terrain characters should be distinct
        assert len(chars) == 4, "Terrain characters must be distinct for monochrome"
        # Shading should provide gradual depth
        assert len(GEOGRAPHY_THEME.shading_chars) >= 5

    def test_geography_provides_renderer_info(self) -> None:
        """Theme must provide enough info for the renderer to work."""
        # Renderer needs: terrain chars, color indices, shading, background
        assert GEOGRAPHY_THEME.ocean_char
        assert GEOGRAPHY_THEME.land_char
        assert GEOGRAPHY_THEME.shading_chars
        assert GEOGRAPHY_THEME.background_char
        assert isinstance(GEOGRAPHY_THEME.ocean_fg, int)
        assert isinstance(GEOGRAPHY_THEME.land_fg, int)


# ---------------------------------------------------------------------------
# Unit: Matrix theme instantiation and correctness
# ---------------------------------------------------------------------------


class TestMatrixTheme:
    """Matrix theme correctness and visual distinctness."""

    def test_matrix_name(self) -> None:
        assert MATRIX_THEME.name == "matrix"

    def test_matrix_has_description(self) -> None:
        assert len(MATRIX_THEME.description) > 0
        assert "green" in MATRIX_THEME.description.lower() or "digital" in MATRIX_THEME.description.lower()

    def test_matrix_green_on_black_land(self) -> None:
        """Land should use green foreground on black background."""
        assert MATRIX_THEME.land_fg == 2   # curses.COLOR_GREEN
        assert MATRIX_THEME.land_bg == 0   # curses.COLOR_BLACK

    def test_matrix_green_family_ocean(self) -> None:
        """Ocean should use a green-family color (green or cyan) on black."""
        assert MATRIX_THEME.ocean_fg in (2, 6)  # green or cyan
        assert MATRIX_THEME.ocean_bg == 0        # black

    def test_matrix_green_borders(self) -> None:
        """Borders should use a green-family color."""
        assert MATRIX_THEME.border_fg in (2, 6)  # green or cyan

    def test_matrix_black_background(self) -> None:
        """Background char should be a space (renders as black)."""
        assert MATRIX_THEME.background_char == " "

    def test_matrix_color_values_are_valid_curses_indices(self) -> None:
        """All color indices should be in the standard curses range 0-7."""
        for field_name in ("ocean_fg", "ocean_bg", "land_fg", "land_bg", "border_fg"):
            value = getattr(MATRIX_THEME, field_name)
            assert 0 <= value <= 7, f"{field_name}={value} outside curses range"

    def test_matrix_shading_chars_gradient(self) -> None:
        """Shading chars should have multiple levels for visible depth."""
        assert len(MATRIX_THEME.shading_chars) >= 5

    def test_matrix_works_monochrome(self) -> None:
        """In monochrome mode, terrain characters must be distinct."""
        chars = {
            MATRIX_THEME.ocean_char,
            MATRIX_THEME.land_char,
            MATRIX_THEME.coastline_char,
            MATRIX_THEME.ice_char,
        }
        assert len(chars) == 4, "Terrain characters must be distinct for monochrome"
        assert len(MATRIX_THEME.shading_chars) >= 5

    def test_matrix_provides_renderer_info(self) -> None:
        """Theme must provide enough info for the renderer to work."""
        assert MATRIX_THEME.ocean_char
        assert MATRIX_THEME.land_char
        assert MATRIX_THEME.shading_chars
        assert MATRIX_THEME.background_char
        assert isinstance(MATRIX_THEME.ocean_fg, int)
        assert isinstance(MATRIX_THEME.land_fg, int)

    def test_matrix_is_frozen(self) -> None:
        with pytest.raises(AttributeError):
            MATRIX_THEME.name = "mutated"  # type: ignore[misc]

    def test_matrix_is_valid_theme_instance(self) -> None:
        """MATRIX_THEME is a proper Theme instance."""
        assert isinstance(MATRIX_THEME, Theme)

    def test_matrix_visually_distinct_from_geography(self) -> None:
        """Matrix theme must differ from geography in color scheme and/or characters."""
        # Colors must differ (geography uses blue ocean, matrix uses green/cyan)
        assert MATRIX_THEME.ocean_fg != GEOGRAPHY_THEME.ocean_fg
        # Land character differs
        assert MATRIX_THEME.land_char != GEOGRAPHY_THEME.land_char
        # Description differs
        assert MATRIX_THEME.description != GEOGRAPHY_THEME.description

    def test_matrix_land_and_ocean_distinguishable(self) -> None:
        """Land and ocean must be distinguishable via color or character."""
        # Either different foreground colors or different characters
        colors_differ = MATRIX_THEME.land_fg != MATRIX_THEME.ocean_fg
        chars_differ = MATRIX_THEME.land_char != MATRIX_THEME.ocean_char
        assert colors_differ or chars_differ, (
            "Land and ocean must be distinguishable through shade/character differences"
        )


# ---------------------------------------------------------------------------
# Unit: Matrix theme registered and discoverable via registry
# ---------------------------------------------------------------------------


class TestMatrixThemeDiscovery:
    """Matrix theme is auto-discovered and selectable."""

    def test_matrix_selectable_via_get_theme(self) -> None:
        """get_theme('matrix') returns the MATRIX_THEME instance."""
        theme = get_theme("matrix")
        assert theme is MATRIX_THEME
        assert theme.name == "matrix"

    def test_registry_discovers_matrix(self) -> None:
        """Auto-discovery finds the matrix theme."""
        registry = ThemeRegistry()
        names = registry.list_themes()
        assert "matrix" in names

    def test_list_themes_includes_matrix(self) -> None:
        result = list_themes()
        assert "matrix" in result

    def test_matrix_in_error_message_for_unknown_theme(self) -> None:
        """Error message for unknown theme lists matrix as available."""
        with pytest.raises(KeyError) as exc_info:
            get_theme("nonexistent")
        msg = str(exc_info.value)
        assert "matrix" in msg


# ---------------------------------------------------------------------------
# Unit: ThemeRegistry discovers built-in themes
# ---------------------------------------------------------------------------


class TestThemeRegistry:
    """ThemeRegistry creation, discovery, and lookup."""

    def test_registry_discovers_builtin_themes(self) -> None:
        """Auto-discovery finds at least the geography theme."""
        registry = ThemeRegistry()
        names = registry.list_themes()
        assert "geography" in names

    def test_registry_discover_finds_all_theme_modules(self) -> None:
        """Every Theme instance in themes/ package modules is registered."""
        registry = ThemeRegistry()
        # geography.py defines GEOGRAPHY_THEME; it must be found.
        assert "geography" in registry

    def test_registry_no_auto_discover(self) -> None:
        """When auto_discover is False, registry starts empty."""
        registry = ThemeRegistry(auto_discover=False)
        assert len(registry) == 0

    def test_registry_manual_register(self) -> None:
        """Manually registered themes are available via get()."""
        registry = ThemeRegistry(auto_discover=False)
        theme = Theme(name="custom", description="Custom theme")
        registry.register(theme)
        assert registry.get("custom") is theme

    def test_registry_register_rejects_non_theme(self) -> None:
        """register() raises TypeError for non-Theme objects."""
        registry = ThemeRegistry(auto_discover=False)
        with pytest.raises(TypeError, match="Expected a Theme instance"):
            registry.register({"name": "bad"})  # type: ignore[arg-type]

    def test_registry_duplicate_name_last_wins(self) -> None:
        """Registering a theme with a duplicate name replaces the old one."""
        registry = ThemeRegistry(auto_discover=False)
        theme_a = Theme(name="dup", description="first")
        theme_b = Theme(name="dup", description="second")
        registry.register(theme_a)
        registry.register(theme_b)
        assert registry.get("dup") is theme_b
        assert registry.get("dup").description == "second"

    def test_registry_len(self) -> None:
        registry = ThemeRegistry(auto_discover=False)
        assert len(registry) == 0
        registry.register(Theme(name="one"))
        assert len(registry) == 1

    def test_registry_contains(self) -> None:
        registry = ThemeRegistry(auto_discover=False)
        registry.register(Theme(name="present"))
        assert "present" in registry
        assert "absent" not in registry

    def test_registry_iter(self) -> None:
        registry = ThemeRegistry(auto_discover=False)
        registry.register(Theme(name="beta"))
        registry.register(Theme(name="alpha"))
        assert list(registry) == ["alpha", "beta"]


# ---------------------------------------------------------------------------
# Unit: list_themes returns expected theme names
# ---------------------------------------------------------------------------


class TestListThemes:
    """Module-level list_themes() function."""

    def test_list_themes_returns_list(self) -> None:
        result = list_themes()
        assert isinstance(result, list)

    def test_list_themes_includes_geography(self) -> None:
        result = list_themes()
        assert "geography" in result

    def test_list_themes_sorted(self) -> None:
        result = list_themes()
        assert result == sorted(result)


# ---------------------------------------------------------------------------
# Unit: get_theme returns correct instances
# ---------------------------------------------------------------------------


class TestGetThemeInstances:
    """get_theme returns the expected Theme instances."""

    def test_get_theme_geography_instance(self) -> None:
        theme = get_theme("geography")
        assert isinstance(theme, Theme)
        assert theme.name == "geography"

    def test_get_theme_returns_same_instance(self) -> None:
        """Multiple calls return the same object (no re-creation)."""
        t1 = get_theme("geography")
        t2 = get_theme("geography")
        assert t1 is t2


# ---------------------------------------------------------------------------
# Unit: Validation rejects incomplete theme definitions
# ---------------------------------------------------------------------------


class TestThemeValidation:
    """ThemeRegistry._validate catches invalid themes."""

    def test_validation_rejects_empty_name(self) -> None:
        """A theme with an empty name is rejected during register()."""
        registry = ThemeRegistry(auto_discover=False)
        # Build a Theme with empty name via object.__setattr__ to bypass
        # the frozen constraint (simulating deserialized data).
        theme = Theme(name="placeholder")
        object.__setattr__(theme, "name", "")
        with pytest.raises(ValueError, match="name"):
            registry.register(theme)

    def test_validation_rejects_whitespace_name(self) -> None:
        registry = ThemeRegistry(auto_discover=False)
        theme = Theme(name="placeholder")
        object.__setattr__(theme, "name", "   ")
        with pytest.raises(ValueError, match="name"):
            registry.register(theme)

    def test_validation_rejects_short_shading_chars(self) -> None:
        registry = ThemeRegistry(auto_discover=False)
        theme = Theme(name="bad_shading", shading_chars="x")
        with pytest.raises(ValueError, match="shading_chars"):
            registry.register(theme)

    def test_validation_rejects_negative_color_index(self) -> None:
        registry = ThemeRegistry(auto_discover=False)
        theme = Theme(name="bad_color", ocean_fg=4)
        object.__setattr__(theme, "ocean_fg", -1)
        with pytest.raises(ValueError, match="ocean_fg"):
            registry.register(theme)

    def test_validation_rejects_multichar_ocean(self) -> None:
        registry = ThemeRegistry(auto_discover=False)
        theme = Theme(name="bad_char")
        object.__setattr__(theme, "ocean_char", "~~")
        with pytest.raises(ValueError, match="ocean_char"):
            registry.register(theme)

    def test_validation_accepts_valid_theme(self) -> None:
        """A valid theme passes validation without errors."""
        registry = ThemeRegistry(auto_discover=False)
        theme = Theme(
            name="valid",
            description="All good",
            ocean_char="~",
            land_char="#",
        )
        registry.register(theme)
        assert "valid" in registry


# ---------------------------------------------------------------------------
# Unit: Error messages are descriptive
# ---------------------------------------------------------------------------


class TestErrorMessages:
    """Error messages from get_theme and ThemeRegistry.get are helpful."""

    def test_unknown_theme_error_lists_available(self) -> None:
        registry = ThemeRegistry()
        with pytest.raises(KeyError) as exc_info:
            registry.get("does_not_exist")
        msg = str(exc_info.value)
        assert "does_not_exist" in msg
        assert "geography" in msg

    def test_module_get_theme_error_lists_available(self) -> None:
        with pytest.raises(KeyError) as exc_info:
            get_theme("nonexistent_theme")
        msg = str(exc_info.value)
        assert "nonexistent_theme" in msg
        assert "Available themes:" in msg
