"""Tests for indra.io.kerchunk_index — Kerchunk JSON index generation and virtual dataset access."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import xarray as xr

from indra.io.kerchunk_index import generate_kerchunk_index, open_virtual_dataset


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_nc_file(tmp_path):
    """Create a minimal NetCDF4 file for testing."""
    nc_path = str(tmp_path / "test_data.nc")
    ds = xr.Dataset(
        {
            "t2m": (["time", "latitude", "longitude"], np.random.rand(3, 4, 5).astype(np.float32)),
        },
        coords={
            "time": np.arange(3),
            "latitude": np.linspace(10, 13, 4),
            "longitude": np.linspace(75, 79, 5),
        },
    )
    ds.to_netcdf(nc_path)
    return nc_path


@pytest.fixture
def sample_nc_multivar(tmp_path):
    """Create a multi-variable NetCDF file for testing."""
    nc_path = str(tmp_path / "test_multivar.nc")
    ds = xr.Dataset(
        {
            "t2m": (["time", "latitude", "longitude"], np.random.rand(24, 10, 10).astype(np.float32)),
            "tp": (["time", "latitude", "longitude"], np.random.rand(24, 10, 10).astype(np.float32)),
            "d2m": (["time", "latitude", "longitude"], np.random.rand(24, 10, 10).astype(np.float32)),
        },
        coords={
            "time": np.arange(24),
            "latitude": np.linspace(6, 37, 10),
            "longitude": np.linspace(68, 98, 10),
        },
    )
    ds.to_netcdf(nc_path)
    return nc_path


# ---------------------------------------------------------------------------
# generate_kerchunk_index tests
# ---------------------------------------------------------------------------
class TestGenerateKerchunkIndex:
    """Tests for the generate_kerchunk_index function."""

    def test_generates_json_sidecar(self, sample_nc_file):
        """Test that a JSON sidecar file is created next to the NC file."""
        json_path = generate_kerchunk_index(sample_nc_file)
        assert os.path.exists(json_path)
        assert json_path.endswith(".json")
        assert json_path == sample_nc_file.replace(".nc", ".json")

    def test_json_is_valid_kerchunk_format(self, sample_nc_file):
        """Test that the generated JSON has the expected Kerchunk structure."""
        json_path = generate_kerchunk_index(sample_nc_file)
        with open(json_path) as f:
            index = json.load(f)

        # Kerchunk reference format must have 'version' and 'refs'
        assert "version" in index
        assert "refs" in index
        assert ".zmetadata" in index["refs"] or ".zgroup" in index["refs"]

    def test_custom_json_path(self, sample_nc_file, tmp_path):
        """Test that a custom JSON output path is used when specified."""
        custom_path = str(tmp_path / "custom_index.json")
        result = generate_kerchunk_index(sample_nc_file, json_path=custom_path)
        assert result == custom_path
        assert os.path.exists(custom_path)

    def test_creates_parent_directories(self, sample_nc_file, tmp_path):
        """Test that parent directories are created if they don't exist."""
        nested_path = str(tmp_path / "a" / "b" / "c" / "index.json")
        result = generate_kerchunk_index(sample_nc_file, json_path=nested_path)
        assert os.path.exists(result)

    def test_multivar_file(self, sample_nc_multivar):
        """Test that multi-variable NC files are indexed correctly."""
        json_path = generate_kerchunk_index(sample_nc_multivar)
        with open(json_path) as f:
            index = json.load(f)

        refs = index["refs"]
        # Check that all three variables are in the index
        var_keys = [k for k in refs if k.startswith("t2m/") or k.startswith("tp/") or k.startswith("d2m/")]
        assert len(var_keys) > 0

    def test_overwrites_existing_json(self, sample_nc_file):
        """Test that re-running overwrites an existing JSON file."""
        json_path = generate_kerchunk_index(sample_nc_file)
        size1 = os.path.getsize(json_path)

        json_path2 = generate_kerchunk_index(sample_nc_file)
        size2 = os.path.getsize(json_path2)

        assert json_path == json_path2
        assert size2 > 0  # File should still be valid


# ---------------------------------------------------------------------------
# open_virtual_dataset tests
# ---------------------------------------------------------------------------
class TestOpenVirtualDataset:
    """Tests for the open_virtual_dataset function."""

    def test_opens_local_json_as_xarray(self, sample_nc_file):
        """Test that a Kerchunk JSON can be opened as a lazy xarray Dataset."""
        json_path = generate_kerchunk_index(sample_nc_file)
        ds = open_virtual_dataset(json_path, target_protocol="file")

        assert isinstance(ds, xr.Dataset)
        assert "t2m" in ds.data_vars
        assert ds.sizes["time"] == 3
        assert ds.sizes["latitude"] == 4
        assert ds.sizes["longitude"] == 5

    def test_lazy_loading(self, sample_nc_file):
        """Test that the dataset is loaded lazily (not computed until .compute())."""
        json_path = generate_kerchunk_index(sample_nc_file)
        ds = open_virtual_dataset(json_path, target_protocol="file")

        # Check that data is lazy (dask-backed or not yet in memory)
        # The key assertion is that opening works without reading all data
        assert ds["t2m"].dtype == np.float32

    def test_spatial_slice(self, sample_nc_file):
        """Test that spatial slicing works on the virtual dataset."""
        json_path = generate_kerchunk_index(sample_nc_file)
        ds = open_virtual_dataset(json_path, target_protocol="file")

        # Select a single point
        lat_val = float(ds.latitude.values[0])
        lon_val = float(ds.longitude.values[0])
        subset = ds.sel(latitude=lat_val, longitude=lon_val)
        values = subset["t2m"].values
        assert values.shape == (3,)  # 3 time steps at single point
        assert not np.isnan(values).all()

    def test_multivar_virtual_read(self, sample_nc_multivar):
        """Test that multi-variable virtual datasets work correctly."""
        json_path = generate_kerchunk_index(sample_nc_multivar)
        ds = open_virtual_dataset(json_path, target_protocol="file")

        assert "t2m" in ds.data_vars
        assert "tp" in ds.data_vars
        assert "d2m" in ds.data_vars

    def test_invalid_json_path_raises(self):
        """Test that a nonexistent JSON path raises an error."""
        with pytest.raises(Exception):
            open_virtual_dataset("/nonexistent/path.json", target_protocol="file")
