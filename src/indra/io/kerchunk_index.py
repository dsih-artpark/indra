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


def _rewrite_refs(index: dict, old_url: str, new_url: str) -> None:
    """Replace *old_url* with *new_url* in all Kerchunk reference entries.

    Handles both styles emitted by ``SingleHdf5ToZarr``:
    - **Templates**: ``{"templates": {"u": "/local/path/file.nc"}}`` where
      refs use ``"{{u}}"`` as the URL.
    - **Direct refs**: ``{"refs": {"var/0.0": ["/local/path/file.nc", off, len]}}``.
    """
    # Rewrite templates (if kerchunk used them)
    for key, val in index.get("templates", {}).items():
        if old_url in val:
            index["templates"][key] = val.replace(old_url, new_url)

    # Rewrite individual chunk references
    for val in index.get("refs", {}).values():
        if isinstance(val, list) and len(val) >= 1 and isinstance(val[0], str):
            if old_url in val[0]:
                val[0] = val[0].replace(old_url, new_url)


def generate_kerchunk_index(
    nc_path: str,
    json_path: str | None = None,
    *,
    target_url: str | None = None,
) -> str:
    """Create a Kerchunk JSON sidecar index for a NetCDF4/HDF5 file.

    The index maps every variable's byte offsets inside the NetCDF file so
    that downstream readers can perform targeted byte-range reads instead of
    downloading the whole file.

    :param str nc_path:
        Absolute path to the source ``.nc`` file (local or fsspec-compatible).
    :param str | None json_path:
        Where to write the JSON index.  Defaults to the same directory and
        basename as *nc_path* with a ``.json`` extension.
    :param str | None target_url:
        If provided, rewrite all embedded file references in the generated
        index from *nc_path* to *target_url*.  This lets you generate the
        index from a fast local read but have it point at an S3 (or other
        remote) copy of the same file.  Example::

            generate_kerchunk_index(
                "/tmp/era5_land_2t_2022_01.nc",
                target_url="s3://bucket/prefix/era5_land_2t_2022_01.nc",
            )
    :returns:
        The path the JSON index was written to.
    """
    if json_path is None:
        if "://" in nc_path:
            raise ValueError(
                f"nc_path is a remote URL ({nc_path.split('://')[0]}://...) "
                "but no explicit json_path was provided. Please supply a local "
                "or writable json_path for the Kerchunk index output."
            )
        json_path = os.path.splitext(nc_path)[0] + ".json"

    logger.info("Generating Kerchunk index: %s → %s", nc_path, json_path)

    with fsspec.open(nc_path, "rb", default_fill_cache=False) as fobj:
        h5chunks = SingleHdf5ToZarr(fobj, nc_path)
        index = h5chunks.translate()

    if target_url is not None:
        logger.info("Rewriting refs: %s → %s", nc_path, target_url)
        _rewrite_refs(index, nc_path, target_url)

    os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as fp:
        ujson.dump(index, fp)

    logger.info("Kerchunk index written: %s", json_path)
    return json_path


def open_virtual_dataset(
    json_ref: str,
    target_protocol: str = "file",
    remote_protocol: str | None = None,
    remote_options: dict | None = None,
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
    :param dict | None remote_options:
        Extra kwargs forwarded to the filesystem that serves the **data
        files** (e.g. S3 credentials / region for S3-hosted NetCDFs).
    :param dict | None storage_options:
        Deprecated alias for *remote_options*.  If both are given,
        *remote_options* takes precedence.
    :returns:
        A lazily-loaded :class:`xarray.Dataset`.
    """
    # remote_options takes precedence over the legacy storage_options alias
    _remote_opts = remote_options or storage_options

    ref_opts: dict = {"fo": json_ref, "remote_protocol": target_protocol}
    if remote_protocol is not None:
        ref_opts["target_protocol"] = remote_protocol
    if _remote_opts is not None:
        ref_opts["remote_options"] = _remote_opts

    mapper = fsspec.get_mapper("reference://", **ref_opts)
    ds = xr.open_dataset(mapper, engine="zarr", consolidated=False)
    logger.debug("Opened virtual dataset from %s — dims=%s", json_ref, dict(ds.sizes))
    return ds
