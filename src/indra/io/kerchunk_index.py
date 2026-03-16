"""Kerchunk index generation and virtual dataset access.

Generates lightweight JSON byte-range indexes from NetCDF4/HDF5 files,
allowing xarray to lazily read only the required chunks from local or
S3-hosted NetCDF files without downloading them in full.
"""

import logging
import os

import fsspec
import ujson
import xarray as xr
from kerchunk.hdf import SingleHdf5ToZarr

logger = logging.getLogger(__name__)


def generate_kerchunk_index(nc_path: str, json_path: str | None = None) -> str:
    """Create a Kerchunk JSON sidecar index for a NetCDF4/HDF5 file.

    The index maps every variable's byte offsets inside the NetCDF file so
    that downstream readers can perform targeted byte-range reads instead of
    downloading the whole file.

    :param str nc_path:
        Absolute path to the source ``.nc`` file (local or fsspec-compatible).
    :param str | None json_path:
        Where to write the JSON index.  Defaults to the same directory and
        basename as *nc_path* with a ``.json`` extension.
    :returns:
        The path the JSON index was written to.
    """
    if json_path is None:
        json_path = os.path.splitext(nc_path)[0] + ".json"

    logger.info("Generating Kerchunk index: %s → %s", nc_path, json_path)

    with fsspec.open(nc_path, "rb", default_fill_cache=False) as fobj:
        h5chunks = SingleHdf5ToZarr(fobj, nc_path)
        index = h5chunks.translate()

    os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as fp:
        ujson.dump(index, fp)

    logger.info("Kerchunk index written: %s", json_path)
    return json_path


def open_virtual_dataset(
    json_ref: str,
    target_protocol: str = "file",
    remote_protocol: str | None = None,
    storage_options: dict | None = None,
) -> xr.Dataset:
    """Open a Kerchunk JSON index as a lazy xarray Dataset.

    Under the hood this uses fsspec's ``ReferenceFileSystem`` so that
    xarray reads only the byte ranges it actually needs.

    :param str json_ref:
        Path or URL to the Kerchunk ``.json`` index.  Can be a local path
        or an ``s3://`` URL.
    :param str target_protocol:
        Protocol of the **data files** referenced inside the JSON
        (``"file"`` for local, ``"s3"`` for S3-hosted NetCDFs).
    :param str | None remote_protocol:
        Protocol used to **fetch the JSON itself** when it lives on a
        remote store (e.g. ``"s3"``).  Leave ``None`` for local JSON files.
    :param dict | None storage_options:
        Extra kwargs forwarded to the fsspec filesystem (e.g. AWS creds).
    :returns:
        A lazily-loaded :class:`xarray.Dataset`.
    """
    ref_opts: dict = {"fo": json_ref, "target_protocol": target_protocol}
    if remote_protocol is not None:
        ref_opts["remote_protocol"] = remote_protocol
    if storage_options is not None:
        ref_opts["target_options"] = storage_options

    mapper = fsspec.get_mapper("reference://", **ref_opts)
    ds = xr.open_dataset(mapper, engine="zarr", consolidated=False)
    logger.debug("Opened virtual dataset from %s — dims=%s", json_ref, dict(ds.sizes))
    return ds
