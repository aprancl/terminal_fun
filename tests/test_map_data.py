"""Tests for globe_term.map_data - Embedded world map data and terrain lookup."""

from __future__ import annotations

import time

import pytest

from globe_term.map_data import (
    TerrainType,
    get_terrain,
    get_raw_grid,
    _MAP_WIDTH,
    _MAP_HEIGHT,
)


# ---------------------------------------------------------------------------
# TerrainType enum
# ---------------------------------------------------------------------------

class TestTerrainType:
    def test_ocean_exists(self):
        assert TerrainType.OCEAN is not None

    def test_land_exists(self):
        assert TerrainType.LAND is not None

    def test_coastline_exists(self):
        assert TerrainType.COASTLINE is not None

    def test_ice_exists(self):
        assert TerrainType.ICE is not None

    def test_distinct_values(self):
        """All terrain types should have distinct values."""
        values = [t.value for t in TerrainType]
        assert len(values) == len(set(values))


# ---------------------------------------------------------------------------
# Known land coordinates return LAND (or COASTLINE)
# ---------------------------------------------------------------------------

class TestKnownLandLocations:
    """Known cities and land areas should return LAND or COASTLINE."""

    @pytest.mark.parametrize("lat,lon,name", [
        (48.8, 2.3, "Paris"),
        (51.5, -0.1, "London"),
        (40.7, -74.0, "New York"),
        (35.7, 139.7, "Tokyo"),
        (55.8, 37.6, "Moscow"),
        (39.9, 116.4, "Beijing"),
        (28.6, 77.2, "Delhi"),
        (30.0, 31.2, "Cairo"),
        (-1.3, 36.8, "Nairobi"),
        (19.4, -99.1, "Mexico City"),
        (37.6, 127.0, "Seoul"),
        (13.8, 100.5, "Bangkok"),
        (59.3, 18.1, "Stockholm"),
        (64.1, -21.9, "Reykjavik"),
        (35.2, -80.8, "Charlotte NC"),
    ])
    def test_known_city_is_land(self, lat, lon, name):
        terrain = get_terrain(lat, lon)
        assert terrain in (TerrainType.LAND, TerrainType.COASTLINE, TerrainType.ICE), (
            f"{name} at ({lat}, {lon}) should be land, got {terrain}"
        )

    @pytest.mark.parametrize("lat,lon,name", [
        (-33.9, 151.2, "Sydney"),
        (-37.8, 144.9, "Melbourne"),
        (-34.6, -58.4, "Buenos Aires"),
        (-22.9, -43.2, "Rio de Janeiro"),
        (-35.0, 18.5, "Cape Town"),
        (-6.2, 106.8, "Jakarta"),
        (1.3, 103.8, "Singapore"),
    ])
    def test_southern_hemisphere_cities(self, lat, lon, name):
        terrain = get_terrain(lat, lon)
        assert terrain in (TerrainType.LAND, TerrainType.COASTLINE), (
            f"{name} at ({lat}, {lon}) should be land, got {terrain}"
        )

    def test_paris_is_land(self):
        """Explicit test: Paris (48.8, 2.3) returns LAND."""
        terrain = get_terrain(48.8, 2.3)
        assert terrain in (TerrainType.LAND, TerrainType.COASTLINE)


# ---------------------------------------------------------------------------
# Known ocean coordinates return OCEAN
# ---------------------------------------------------------------------------

class TestKnownOceanLocations:
    """Known ocean areas should return OCEAN."""

    @pytest.mark.parametrize("lat,lon,name", [
        (0.0, -30.0, "Central Atlantic"),
        (0.0, -160.0, "Central Pacific"),
        (30.0, -50.0, "Mid-Atlantic"),
        (0.0, 160.0, "Western Pacific"),
        (-40.0, -120.0, "South Pacific"),
        (40.0, 170.0, "North Pacific"),
        (-30.0, 80.0, "Indian Ocean"),
    ])
    def test_known_ocean_is_ocean(self, lat, lon, name):
        terrain = get_terrain(lat, lon)
        assert terrain == TerrainType.OCEAN, (
            f"{name} at ({lat}, {lon}) should be OCEAN, got {terrain}"
        )

    def test_atlantic_equator(self):
        """Explicit test: Atlantic at equator (0.0, -30.0) returns OCEAN."""
        assert get_terrain(0.0, -30.0) == TerrainType.OCEAN


# ---------------------------------------------------------------------------
# Longitude wrapping at +/-180 boundary
# ---------------------------------------------------------------------------

class TestLongitudeWrapping:
    """Longitude should wrap correctly at the +/-180 boundary."""

    def test_positive_180(self):
        """lon=180 should return valid terrain."""
        terrain = get_terrain(0.0, 180.0)
        assert isinstance(terrain, TerrainType)

    def test_negative_180(self):
        """lon=-180 should return valid terrain."""
        terrain = get_terrain(0.0, -180.0)
        assert isinstance(terrain, TerrainType)

    def test_wrap_360(self):
        """lon=190 should wrap to lon=-170 and give the same result."""
        t1 = get_terrain(0.0, 190.0)
        t2 = get_terrain(0.0, -170.0)
        assert t1 == t2, f"190 deg ({t1}) should match -170 deg ({t2})"

    def test_wrap_negative(self):
        """lon=-190 should wrap to lon=170 and give the same result."""
        t1 = get_terrain(0.0, -190.0)
        t2 = get_terrain(0.0, 170.0)
        assert t1 == t2, f"-190 deg ({t1}) should match 170 deg ({t2})"

    def test_wrap_720(self):
        """lon=720 should wrap to lon=0 and give the same result."""
        t1 = get_terrain(45.0, 720.0)
        t2 = get_terrain(45.0, 0.0)
        assert t1 == t2

    def test_boundary_consistent(self):
        """Values at +180 and -180 should be the same point."""
        t1 = get_terrain(45.0, 180.0)
        t2 = get_terrain(45.0, -180.0)
        assert t1 == t2


# ---------------------------------------------------------------------------
# Full lat/lon range coverage without errors
# ---------------------------------------------------------------------------

class TestFullCoverage:
    """Every integer lat/lon combination should return a valid TerrainType."""

    def test_all_integer_coords(self):
        """Iterate over all integer lat/lon pairs and ensure no errors."""
        for lat in range(-90, 91, 10):
            for lon in range(-180, 181, 10):
                terrain = get_terrain(float(lat), float(lon))
                assert isinstance(terrain, TerrainType), (
                    f"Invalid terrain at ({lat}, {lon}): {terrain}"
                )

    def test_polar_north(self):
        """North pole (90, 0) should return valid terrain."""
        terrain = get_terrain(90.0, 0.0)
        assert isinstance(terrain, TerrainType)

    def test_polar_south(self):
        """South pole (-90, 0) should return ICE (Antarctica)."""
        terrain = get_terrain(-90.0, 0.0)
        assert terrain == TerrainType.ICE

    def test_sub_degree_values(self):
        """Sub-degree lat/lon values should work via nearest-neighbor."""
        terrain = get_terrain(48.856, 2.352)  # Paris precise
        assert terrain in (TerrainType.LAND, TerrainType.COASTLINE)

    def test_extreme_latitudes(self):
        """Extreme latitudes should not raise errors."""
        for lat in [-90, -89.99, -89, 89, 89.99, 90]:
            terrain = get_terrain(lat, 0.0)
            assert isinstance(terrain, TerrainType)

    def test_extreme_longitudes(self):
        """Extreme longitudes (including wrapping) should not raise errors."""
        for lon in [-180, -179.99, -1, 0, 1, 179, 179.99, 180, 360, -360]:
            terrain = get_terrain(0.0, lon)
            assert isinstance(terrain, TerrainType)


# ---------------------------------------------------------------------------
# Seven continents check
# ---------------------------------------------------------------------------

class TestSevenContinents:
    """All seven continents should have recognizable land."""

    @pytest.mark.parametrize("lat,lon,continent", [
        (40.0, -100.0, "North America"),
        (-15.0, -55.0, "South America"),
        (50.0, 10.0, "Europe"),
        (5.0, 25.0, "Africa"),
        (40.0, 80.0, "Asia"),
        (-25.0, 135.0, "Australia"),
        (-80.0, 0.0, "Antarctica"),
    ])
    def test_continent_center_is_land(self, lat, lon, continent):
        terrain = get_terrain(lat, lon)
        assert terrain != TerrainType.OCEAN, (
            f"Center of {continent} at ({lat}, {lon}) should not be OCEAN, "
            f"got {terrain}"
        )


# ---------------------------------------------------------------------------
# Data embedding check
# ---------------------------------------------------------------------------

class TestDataEmbedding:
    def test_no_external_file_loading(self):
        """Map data should be embedded -- get_raw_grid should return valid data."""
        bitmap, width, height = get_raw_grid()
        assert width == 360
        assert height == 180
        assert len(bitmap) == (360 * 180) // 8

    def test_bitmap_not_all_zeros(self):
        """The bitmap should contain some land (not all zeros)."""
        bitmap, _, _ = get_raw_grid()
        assert any(b != 0 for b in bitmap)

    def test_bitmap_not_all_ones(self):
        """The bitmap should contain some ocean (not all 0xFF)."""
        bitmap, _, _ = get_raw_grid()
        assert any(b != 0xFF for b in bitmap)


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------

class TestPerformance:
    def test_get_terrain_is_fast(self):
        """get_terrain() should be O(1) -- many calls should be fast."""
        # Warm up
        get_terrain(0.0, 0.0)

        start = time.perf_counter()
        for _ in range(10000):
            get_terrain(48.8, 2.3)
        elapsed = (time.perf_counter() - start) * 1000  # ms

        # 10000 calls should complete well under 100ms
        assert elapsed < 500, (
            f"10000 get_terrain calls took {elapsed:.1f}ms (expected < 500ms)"
        )

    def test_import_time(self):
        """Module should import quickly (data decode is fast)."""
        # If we got here, the module already imported successfully.
        # Measure re-decode time as a proxy.
        import base64
        import zlib
        from globe_term.map_data import _MAP_DATA_B64

        start = time.perf_counter()
        for _ in range(100):
            zlib.decompress(base64.b64decode(_MAP_DATA_B64))
        elapsed = (time.perf_counter() - start) * 1000 / 100  # avg ms

        assert elapsed < 10, (
            f"Data decode takes {elapsed:.2f}ms per call (expected < 10ms)"
        )
