"""3D sphere math, rotation, projection.

Provides the Globe class for managing sphere rotation state and projecting
a 3D sphere onto a 2D terminal grid. Each screen cell maps to a (lat, lon)
coordinate on the sphere surface, or is marked as empty (not on the sphere).

The projection uses inverse ray-sphere intersection: for each screen cell,
a ray is cast from the viewer through the screen plane. If the ray hits the
unit sphere, the intersection point is transformed back through the inverse
rotation to recover the original (lat, lon) on the map.

Shading is computed from the dot product of the surface normal at the hit
point with a configurable light direction vector.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

# Type aliases
# Each cell in the projected grid is either None (empty / not on sphere)
# or a tuple of (latitude, longitude, shade_value).
# latitude: -90..90, longitude: -180..180, shade: 0.0..1.0
CellResult = Optional[Tuple[float, float, float]]

# Minimum and maximum zoom bounds
MIN_ZOOM = 0.2
MAX_ZOOM = 5.0

# Auto-rotation defaults
# Base angular velocity: 2*pi radians over 45 seconds (~1 rotation per 45s at speed=1.0)
AUTO_ROTATE_BASE_SPEED = 2.0 * math.pi / 45.0
# Maximum allowed speed multiplier to prevent absurd rotation rates
MAX_AUTO_SPEED = 20.0
# Idle threshold: seconds of no input before auto-rotation begins
IDLE_THRESHOLD = 2.5

# Default light direction (normalized): upper-right, slightly toward viewer
_LIGHT_DIR = (0.5, 0.5, 0.7071067811865476)  # normalized (0.5, 0.5, 1/sqrt(2))


def _normalize(x: float, y: float, z: float) -> Tuple[float, float, float]:
    """Normalize a 3D vector to unit length."""
    length = math.sqrt(x * x + y * y + z * z)
    if length < 1e-12:
        return (0.0, 0.0, 0.0)
    inv = 1.0 / length
    return (x * inv, y * inv, z * inv)


def _dot(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    """Dot product of two 3D vectors."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def latlon_to_xyz(lat: float, lon: float) -> Tuple[float, float, float]:
    """Convert latitude/longitude (degrees) to a unit-sphere 3D point.

    Convention:
        x = right, y = up, z = toward viewer
        lat=0, lon=0 faces the viewer (positive z).

    Args:
        lat: Latitude in degrees (-90 to 90).
        lon: Longitude in degrees (-180 to 180).

    Returns:
        (x, y, z) on the unit sphere.
    """
    lat_r = math.radians(lat)
    lon_r = math.radians(lon)
    cos_lat = math.cos(lat_r)
    x = cos_lat * math.sin(lon_r)
    y = math.sin(lat_r)
    z = cos_lat * math.cos(lon_r)
    return (x, y, z)


def xyz_to_latlon(x: float, y: float, z: float) -> Tuple[float, float]:
    """Convert a 3D unit-sphere point back to (lat, lon) in degrees.

    Args:
        x, y, z: Coordinates on the unit sphere.

    Returns:
        (latitude, longitude) in degrees.
    """
    lat = math.degrees(math.asin(max(-1.0, min(1.0, y))))
    lon = math.degrees(math.atan2(x, z))
    return (lat, lon)


def rotate_x(x: float, y: float, z: float, angle: float) -> Tuple[float, float, float]:
    """Rotate a 3D point around the X axis by *angle* radians.

    Args:
        x, y, z: Input coordinates.
        angle: Rotation angle in radians.

    Returns:
        Rotated (x, y, z).
    """
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return (x, y * cos_a - z * sin_a, y * sin_a + z * cos_a)


def rotate_y(x: float, y: float, z: float, angle: float) -> Tuple[float, float, float]:
    """Rotate a 3D point around the Y axis by *angle* radians.

    Args:
        x, y, z: Input coordinates.
        angle: Rotation angle in radians.

    Returns:
        Rotated (x, y, z).
    """
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return (x * cos_a + z * sin_a, y, -x * sin_a + z * cos_a)


def inverse_rotate(
    x: float,
    y: float,
    z: float,
    rot_x: float,
    rot_y: float,
) -> Tuple[float, float, float]:
    """Apply the inverse of the combined rotation (Y then X) to a point.

    The forward rotation is: first rotate around X, then rotate around Y.
    The inverse is: first rotate around Y by -rot_y, then rotate around X
    by -rot_x.

    Args:
        x, y, z: Point in rotated (view) space.
        rot_x: X-axis rotation angle in radians.
        rot_y: Y-axis rotation angle in radians.

    Returns:
        Point in unrotated (map) space.
    """
    # Undo Y rotation
    x2, y2, z2 = rotate_y(x, y, z, -rot_y)
    # Undo X rotation
    return rotate_x(x2, y2, z2, -rot_x)


class Globe:
    """3D globe with rotation state and sphere-to-screen projection.

    The globe is a unit sphere centered at the origin. The viewer looks
    along the negative Z axis (the front of the sphere has positive Z).

    Attributes:
        rotation_x: Current rotation around the X axis (radians).
        rotation_y: Current rotation around the Y axis (radians).
        zoom: Current zoom level (1.0 = sphere fills ~80% of the
            smaller screen dimension).
        light_dir: Normalized (x, y, z) direction toward the light source.
        aspect_ratio: Terminal character aspect ratio (height / width).
            Typical terminal characters are about twice as tall as wide,
            so the default is 2.0.
    """

    def __init__(
        self,
        rotation_x: float = 0.0,
        rotation_y: float = 0.0,
        zoom: float = 1.0,
        light_dir: Optional[Tuple[float, float, float]] = None,
        aspect_ratio: float = 2.0,
    ) -> None:
        self.rotation_x = rotation_x
        self.rotation_y = rotation_y
        self.zoom = self._clamp_zoom(zoom)
        self.light_dir = _normalize(*(light_dir or _LIGHT_DIR))
        self.aspect_ratio = aspect_ratio

    @staticmethod
    def _clamp_zoom(zoom: float) -> float:
        """Clamp zoom to valid bounds."""
        return max(MIN_ZOOM, min(MAX_ZOOM, zoom))

    def rotate(self, dx: float, dy: float) -> None:
        """Update the rotation state by deltas.

        Args:
            dx: Rotation delta around the Y axis (radians). Positive
                values rotate the globe to the right (longitude increases).
            dy: Rotation delta around the X axis (radians). Positive
                values tilt the globe downward (latitude increases).
        """
        self.rotation_y += dx
        self.rotation_x += dy

    def set_zoom(self, zoom: float) -> None:
        """Set the zoom level, clamping to valid bounds.

        Args:
            zoom: Desired zoom level.
        """
        self.zoom = self._clamp_zoom(zoom)

    def auto_rotate(self, dt: float, speed: float = 1.0) -> None:
        """Apply auto-rotation around the Y axis.

        Rotates the globe by an amount proportional to *dt* (elapsed
        seconds) and *speed* (multiplier).  A speed of 1.0 produces
        approximately one full rotation every 45 seconds.

        Speed is clamped to [0, MAX_AUTO_SPEED].  A speed of 0 disables
        rotation entirely.

        Args:
            dt: Elapsed time in seconds since the last frame.
            speed: Rotation speed multiplier (0 = disabled).
        """
        if speed <= 0.0 or dt <= 0.0:
            return
        clamped_speed = min(speed, MAX_AUTO_SPEED)
        self.rotation_y += AUTO_ROTATE_BASE_SPEED * clamped_speed * dt

    def adjust_zoom(self, delta: float) -> None:
        """Adjust the zoom level by a signed delta, clamping to bounds.

        Positive *delta* zooms in (globe appears larger), negative *delta*
        zooms out.  The result is clamped to [MIN_ZOOM, MAX_ZOOM].

        Args:
            delta: Amount to add to the current zoom level.
        """
        self.zoom = self._clamp_zoom(self.zoom + delta)

    def project(self, width: int, height: int) -> List[List[CellResult]]:
        """Project the sphere onto a 2D terminal grid.

        For each cell in a *height* x *width* grid, determine whether a ray
        from the viewer through that cell intersects the unit sphere. If it
        does, compute the (lat, lon) of the intersection point on the
        un-rotated sphere, plus a shading value.

        The projection uses an orthographic model: rays are parallel, directed
        along the negative Z axis. The sphere has radius 1, centered at the
        origin. The screen coordinate system maps the grid so that the sphere
        radius corresponds to ``sphere_radius_pixels`` (derived from zoom and
        screen size).

        Terminal characters are taller than wide (typically ~2:1), so the
        horizontal coordinate is scaled by ``1 / aspect_ratio`` to produce
        a visually round sphere.

        Args:
            width: Number of columns in the terminal grid.
            height: Number of rows in the terminal grid.

        Returns:
            A list of *height* rows, each containing *width* entries.
            Each entry is either ``None`` (ray missed the sphere) or
            ``(lat, lon, shade)`` where lat/lon are in degrees and shade
            is 0.0 (dark) to 1.0 (bright).
        """
        if width <= 0 or height <= 0:
            return [[None] * max(width, 0) for _ in range(max(height, 0))]

        # Sphere radius in screen cells. The sphere should fill most of the
        # smaller dimension. zoom=1.0 means sphere diameter is ~80% of the
        # smaller dimension.
        half_min = min(width / self.aspect_ratio, height) * 0.5
        sphere_radius = half_min * 0.8 * self.zoom

        if sphere_radius < 0.5:
            # Sphere too small to render anything meaningful
            return [[None] * width for _ in range(height)]

        inv_radius = 1.0 / sphere_radius

        # Precompute rotation sines/cosines for the inverse rotation
        cx = math.cos(-self.rotation_x)
        sx = math.sin(-self.rotation_x)
        cy = math.cos(-self.rotation_y)
        sy = math.sin(-self.rotation_y)

        # Center of the screen
        cx_screen = (width - 1) * 0.5
        cy_screen = (height - 1) * 0.5

        result: List[List[CellResult]] = []

        for row in range(height):
            row_data: List[CellResult] = []
            # Normalized y coordinate on the screen: -1..1 maps to sphere
            # (row increases downward, so negate for y-up convention)
            ny = -(row - cy_screen) * inv_radius

            # Early row skip: if ny is outside [-1, 1], no intersection
            if ny * ny > 1.0:
                row_data = [None] * width
                result.append(row_data)
                continue

            # Maximum nx for this row (circle equation: nx^2 + ny^2 <= 1)
            max_nx_sq = 1.0 - ny * ny
            max_nx = math.sqrt(max_nx_sq)

            for col in range(width):
                # Normalized x coordinate, corrected for aspect ratio
                nx = (col - cx_screen) * inv_radius / self.aspect_ratio

                if nx * nx > max_nx_sq:
                    row_data.append(None)
                    continue

                # Point is on the sphere surface (orthographic projection).
                # The z coordinate is the front-facing hemisphere.
                nz = math.sqrt(max(0.0, 1.0 - nx * nx - ny * ny))

                # Toy-globe shading: use z-depth for subtle edge darkening.
                # Center of globe (nz=1) is fully bright, edges fade gently.
                shade = 0.3 + 0.7 * nz

                # Inverse-rotate the point to get map-space coordinates.
                # Forward rotation: Rx(rot_x) then Ry(rot_y)
                # Inverse: Ry(-rot_y) then Rx(-rot_x)
                # Inline for performance:
                # Step 1: Ry(-rot_y) on (nx, ny, nz)
                px = nx * cy + nz * sy
                py = ny
                pz = -nx * sy + nz * cy

                # Step 2: Rx(-rot_x) on (px, py, pz)
                mx = px
                my = py * cx - pz * sx
                mz = py * sx + pz * cx

                # Convert to lat/lon
                lat = math.degrees(math.asin(max(-1.0, min(1.0, my))))
                lon = math.degrees(math.atan2(mx, mz))

                row_data.append((lat, lon, shade))

            result.append(row_data)

        return result
