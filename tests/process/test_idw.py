"""Tests for indra.process.idw — Inverse Distance Weighting interpolation utilities."""

import math

import numpy as np
import pytest

from indra.process.idw import haversine, idw_interpolate


# ---------------------------------------------------------------------------
# haversine tests
# ---------------------------------------------------------------------------
class TestHaversine:
    """Tests for the haversine distance function."""

    def test_zero_distance_for_same_point(self):
        """Test that distance between a point and itself is zero."""
        dist = haversine(12.9716, 77.5946, 12.9716, 77.5946)
        assert dist == 0.0

    def test_known_distance_equator(self):
        """Test distance along the equator (1 degree = ~111.19 km)."""
        dist = haversine(0.0, 0.0, 0.0, 1.0)
        assert abs(dist - 111.19) < 0.1  # Allow small floating point variation

    def test_known_distance_meridian(self):
        """Test distance along a meridian (1 degree = ~111.19 km)."""
        dist = haversine(0.0, 0.0, 1.0, 0.0)
        assert abs(dist - 111.19) < 0.1

    def test_symmetric(self):
        """Test that distance A->B is same as B->A."""
        dist1 = haversine(12.9716, 77.5946, 13.0, 78.0)
        dist2 = haversine(13.0, 78.0, 12.9716, 77.5946)
        assert dist1 == dist2

    def test_antipodes(self):
        """Test distance between antipodal points (half Earth circumference)."""
        # Earth radius = 6371 km. pi * r = 20015.08 km
        dist = haversine(0.0, 0.0, 0.0, 180.0)
        assert abs(dist - 20015.08) < 1.0


# ---------------------------------------------------------------------------
# idw_interpolate tests
# ---------------------------------------------------------------------------
class TestIdwInterpolate:
    """Tests for the IDW interpolation function."""

    @pytest.fixture
    def simple_grid(self):
        """Fixture providing a simple 4-point grid around the origin."""
        # 4 points forming a square around (0,0)
        # Top-right, Bottom-right, Bottom-left, Top-left
        d_lat = 0.1
        d_lon = 0.1
        grid_lats = np.array([d_lat, -d_lat, -d_lat, d_lat])
        grid_lons = np.array([d_lon, d_lon, -d_lon, -d_lon])
        # Values at those points
        grid_values = np.array([10.0, 20.0, 30.0, 40.0])
        return grid_lats, grid_lons, grid_values

    def test_exact_match_returns_grid_value(self, simple_grid):
        """Test that if target is exactly on a grid point, it returns that value."""
        grid_lats, grid_lons, grid_values = simple_grid
        target_lat = grid_lats[0]
        target_lon = grid_lons[0]

        val, count = idw_interpolate(target_lat, target_lon, grid_lats, grid_lons, grid_values, radius_km=50.0)
        assert val == grid_values[0]
        assert count == 1

    def test_center_interpolation(self, simple_grid):
        """Test that target exactly in the middle gets equal weighting."""
        grid_lats, grid_lons, grid_values = simple_grid
        target_lat = 0.0
        target_lon = 0.0

        val, count = idw_interpolate(target_lat, target_lon, grid_lats, grid_lons, grid_values, radius_km=50.0)
        # Distances to all 4 corners are identical, so it should be the strict average
        assert val == pytest.approx(np.mean(grid_values))
        assert count == 4

    def test_closer_point_has_higher_weight(self, simple_grid):
        """Test that points closer to the target influence the value more."""
        grid_lats, grid_lons, grid_values = simple_grid
        # Move target closer to the top-right corner (which has value 10.0)
        target_lat = 0.08
        target_lon = 0.08

        val, count = idw_interpolate(target_lat, target_lon, grid_lats, grid_lons, grid_values, radius_km=50.0)
        assert val < 25.0  # Mean is 25.0, should be skewed towards 10.0
        assert count == 4

    def test_points_outside_radius_ignored(self, simple_grid):
        """Test that points outside the search radius are not included."""
        grid_lats, grid_lons, grid_values = simple_grid
        target_lat = grid_lats[0] + 0.05
        target_lon = grid_lons[0] + 0.05

        # Radius extremely small, only the closest point should match
        val, count = idw_interpolate(target_lat, target_lon, grid_lats, grid_lons, grid_values, radius_km=10.0)
        assert val == grid_values[0]
        assert count == 1

    def test_no_points_within_radius_returns_nan(self, simple_grid):
        """Test that if the radius is too small to catch any points, NaN is returned."""
        grid_lats, grid_lons, grid_values = simple_grid
        target_lat = 5.0
        target_lon = 5.0

        val, count = idw_interpolate(target_lat, target_lon, grid_lats, grid_lons, grid_values, radius_km=10.0)
        assert math.isnan(val)
        assert count == 0

    def test_handles_nan_grid_values_gracefully(self, simple_grid):
        """Test that NaN values in the grid are ignored during weighting."""
        grid_lats, grid_lons, grid_values = simple_grid
        # Set one point to NaN
        grid_values[0] = np.nan
        target_lat = 0.0
        target_lon = 0.0

        val, count = idw_interpolate(target_lat, target_lon, grid_lats, grid_lons, grid_values, radius_km=50.0)
        # Should be the mean of the remaining 3 valid points
        assert val == pytest.approx(np.mean([20.0, 30.0, 40.0]))
        assert count == 4  # All 4 points are within radius; count reflects spatial coverage

    def test_all_nans_returns_nan(self, simple_grid):
        """Test that if all points in radius are NaN, returns NaN."""
        grid_lats, grid_lons, grid_values = simple_grid
        grid_values[:] = np.nan
        target_lat = 0.0
        target_lon = 0.0

        val, count = idw_interpolate(target_lat, target_lon, grid_lats, grid_lons, grid_values, radius_km=50.0)
        assert math.isnan(val)
        assert count == 4  # 4 points within radius; count reflects spatial coverage not valid-NaN status
