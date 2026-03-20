import logging
import os

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


def _safe_remove(path: str) -> None:
    """Remove a file if it exists, swallowing OSErrors."""
    try:
        os.remove(path)
    except OSError:
        pass

def download_from_s3(
    *,
    bucket: str,
    key: str,
    local_path: str,
    overwrite: bool = False,
) -> str:
    """Download a single file from S3 to a local path.

    :param str bucket:
        Name of the S3 bucket.
    :param str key:
        S3 object key (e.g. ``boundaries/GBA_zone.geojson``).
    :param str local_path:
        Absolute path to save the file locally.
    :param bool overwrite:
        If ``True``, re-download even if the local file exists.
        Default: ``False``.
    :returns:
        The *local_path* the file was written to.
    :raises FileNotFoundError:
        If the S3 key does not exist.
    :raises PermissionError:
        If AWS credentials are missing or invalid.
    :raises ClientError:
        On any other S3/boto3 error.
    """
    if not overwrite and os.path.exists(local_path):
        logger.info("File already exists locally, skipping download: %s", local_path)
        return local_path

    dirpath = os.path.dirname(local_path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)

    client = boto3.client("s3")
    logger.info("Downloading s3://%s/%s → %s", bucket, key, local_path)

    tmp_path = local_path + ".tmp"
    try:
        client.download_file(Bucket=bucket, Key=key, Filename=tmp_path)
    except NoCredentialsError as exc:
        _safe_remove(tmp_path)
        raise PermissionError(
            "AWS credentials not found. Configure them via environment variables "
            "(AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY), ~/.aws/credentials, "
            "or an IAM role."
        ) from exc
    except ClientError as exc:
        _safe_remove(tmp_path)
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in ("404", "NoSuchKey"):
            raise FileNotFoundError(
                f"S3 key not found: s3://{bucket}/{key}"
            ) from exc
        raise
    except Exception:
        _safe_remove(tmp_path)
        raise

    os.replace(tmp_path, local_path)

    logger.info("Download complete: %s", local_path)
    return local_path
