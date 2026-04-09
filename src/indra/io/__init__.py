import yaml

from indra.io.download import download_from_url, retry_session
from indra.io.kerchunk_index import generate_kerchunk_index, open_virtual_dataset
from indra.io.s3_read import download_from_s3
from indra.io.upload import upload_data_to_s3, upload_single_file_to_s3


def get_params(yaml_path):
    """Load and return the YAML configuration file as a dict.

    :raises FileNotFoundError: If the config file does not exist.
    :raises ValueError: If the config file contains invalid YAML.
    """
    try:
        with open(yaml_path, 'r') as file:
            params = yaml.safe_load(file)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Config file not found: {yaml_path}. "
            "Check the path you provided to the command."
        )
    except yaml.YAMLError as exc:
        raise ValueError(
            f"Failed to parse config file '{yaml_path}': {exc}. "
            "Check for syntax errors in your YAML."
        ) from exc
    if not isinstance(params, dict):
        raise ValueError(
            f"Config file '{yaml_path}' did not parse as a YAML mapping. "
            "Ensure the file is a valid YAML key-value document."
        )
    return params

__all__ = [
    "download_from_s3",
    "download_from_url",
    "generate_kerchunk_index",
    "get_params",
    "open_virtual_dataset",
    "retry_session",
    "upload_data_to_s3",
    "upload_single_file_to_s3",
]
