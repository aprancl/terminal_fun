"""Embedded simplified world map data.

Provides a 360x180 degree resolution bitmap of the Earth's surface,
compressed and base64-encoded for embedding directly in source code.
Supports O(1) terrain lookup by latitude and longitude.
"""

import base64
import enum
import zlib
from typing import Tuple


class TerrainType(enum.Enum):
    """Classification of terrain at a given coordinate."""

    OCEAN = 0
    LAND = 1
    COASTLINE = 2
    ICE = 3


# Grid dimensions: 1 degree per cell
_MAP_WIDTH = 360
_MAP_HEIGHT = 180

# Compressed world map bitmap (360x180, 1 bit per pixel).
# Rows go from 90N (row 0) to 89S (row 179).
# Columns go from 180W (col 0) to 179E (col 359).
# Encoding: zlib-compressed, then base64-encoded.
_MAP_DATA_B64 = (
    "eNrt2NFtgzAQANBD98HnbdCM4rX6B1UH6AhdJaO4ygDNJ5WQr5AEbGM7wdikVOI+8hEeKLbPdw4A"
    "eySFYDPkZjAy11vB6L9hEVbWbKDxgHpL2Bqbov5jCserWbDg77wY9VDmYeJITN7xJWCWQkIU7iMK"
    "V9lxc8shH679GNUmcKWEI4tobG+X7JjsjRmFPRswjIsxX30lOwoX9ndPxWohhjG99RpJmIs/HuPG"
    "xFac5FJcWROUE1+z7OjtdNalaEx2SzpcWqYuL1ULSzGaa+Li8rgYg7kmTr1dEU8OEVGYgvhdX1iI"
    "z/AawioFd8mjhhQlXSbXw9SfhBQk4QO3IVyLs4udmhrEIBpwmwYqSMfg7tcLpnRMx8kA+/3bBPFt"
    "f8/B2HoxMqRimPTMyyqr7hnpGG/axC8A3a9bA3cZprx/tlAXUnqISXeKZ2GfjsbDCBPwyfXrYTTa"
    "o4nh8Bg3Q0Hhz9kYSq5xA/h65R4mt+3Mxdh6d+wwux3+UU/AwtMqzD7N/HUfYwAje95gLMaC3zLj"
    "xsXI7FnPpbib55wYrMo44tJ3qErAOncyYDSPa23oVJuIS2OuMmDSO97EhXdRyHw7JdMwp+BQFaL+"
    "3r/H0OeMjYUKFk1aEwuZgO8W+41iGfOefRuY6k3gPf5h8B577LFHZPwC9Tmb3g=="
)

# Decode and decompress the map data at import time.
# This is a one-time cost (~< 1ms) that produces a bytes object
# for O(1) indexed lookup.
_map_bytes: bytes = zlib.decompress(base64.b64decode(_MAP_DATA_B64))


def _latlon_to_grid(lat: float, lon: float) -> Tuple[int, int]:
    """Convert latitude/longitude to grid row and column.

    Args:
        lat: Latitude in degrees (-90 to 90).
        lon: Longitude in degrees (-180 to 180).

    Returns:
        Tuple of (row, col) indices into the grid.
    """
    # Wrap longitude to [-180, 180)
    lon = ((lon + 180.0) % 360.0) - 180.0

    # Clamp latitude to valid range
    lat = max(-89.5, min(89.5, lat))

    # Convert to grid indices using nearest-neighbor
    row = int(round(90.0 - lat))
    col = int(round(lon + 180.0))

    # Clamp to grid bounds
    row = max(0, min(_MAP_HEIGHT - 1, row))
    col = max(0, min(_MAP_WIDTH - 1, col))

    return row, col


def _get_bit(row: int, col: int) -> int:
    """Get the bit value at a grid position.

    Args:
        row: Grid row (0 = 90N, 179 = 89S).
        col: Grid column (0 = 180W, 359 = 179E).

    Returns:
        1 if land, 0 if ocean.
    """
    byte_idx = (row * _MAP_WIDTH + col) // 8
    bit_idx = (row * _MAP_WIDTH + col) % 8
    return (_map_bytes[byte_idx] >> (7 - bit_idx)) & 1


def _is_coastline(row: int, col: int) -> bool:
    """Check if a land cell is on the coastline.

    A cell is coastline if it is land and at least one of its
    4-connected neighbors is ocean.

    Args:
        row: Grid row.
        col: Grid column.

    Returns:
        True if the cell is a coastline cell.
    """
    if _get_bit(row, col) == 0:
        return False

    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr = row + dr
        nc = (col + dc) % _MAP_WIDTH  # Wrap longitude
        if 0 <= nr < _MAP_HEIGHT and _get_bit(nr, nc) == 0:
            return True

    return False


def get_terrain(lat: float, lon: float) -> TerrainType:
    """Look up the terrain type at a given coordinate.

    Uses nearest-neighbor mapping from floating-point coordinates
    to the 1-degree grid. Longitude wraps at +/-180 degrees.
    Latitude is clamped to [-89.5, 89.5].

    Args:
        lat: Latitude in degrees (-90 to 90).
        lon: Longitude in degrees, wraps at +/-180.

    Returns:
        TerrainType indicating the terrain at the coordinate.
    """
    row, col = _latlon_to_grid(lat, lon)

    if _get_bit(row, col) == 0:
        return TerrainType.OCEAN

    # Check for ice caps (approximate: Antarctica < -60, Arctic > 75)
    if lat < -60.0 or lat > 75.0:
        return TerrainType.ICE

    if _is_coastline(row, col):
        return TerrainType.COASTLINE

    return TerrainType.LAND


def get_raw_grid() -> Tuple[bytes, int, int]:
    """Return the raw map data for bulk access.

    Returns:
        Tuple of (bitmap_bytes, width, height) where bitmap_bytes
        is a packed bitfield of land/ocean data.
    """
    return _map_bytes, _MAP_WIDTH, _MAP_HEIGHT
