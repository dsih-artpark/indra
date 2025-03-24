import yaml

from indra.io.download import download_from_url
from indra.io.upload import upload_data_to_s3


def get_params(yaml_path):
    with open(yaml_path, 'r') as file:
        params = yaml.safe_load(file)
    return params

__all__ = ["download_from_url", "get_params", "upload_data_to_s3"]
