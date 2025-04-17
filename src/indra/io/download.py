import logging
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError
from tqdm import tqdm
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)
logging.captureWarnings(True)


def retry_session(retries, session=None, backoff_factor=1):
    """
    Returns a session with retries enabled for given HTTP codes.
    backoff is calculated as backoff between attempts = (backoff_factor) * (2 ** (no of retries failed))

    :param int retries:
        The number of retries to attempt.

    :param requests.Session session:
        The session to use for the request.

    :param int backoff_factor:
        The backoff factor to use for the retries.

    :returns:
        A session with retries enabled.

    :raises HTTPError:
        If there is an issue with the HTTP request.
    """
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[404, 500, 502, 504, 429]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def download_from_url(url: str, output_dir: str, filename: str,
                      timeout_seconds: int = 10, raise_error: bool = True,
                      chunk: bool = True, chunk_size: int = 1048576):
    """Download data from a URL and save it to a file.

    This function downloads data from a specified URL and saves it to a file in the specified directory.
    This is meant for open access data with no authentication required. It is recommended to use it with the retry_session function to
    ensure that the data is downloaded successfully.

    :param str url:
        The URL to download the data from.

    :param str output_dir:
        The directory to save the downloaded data.

    :param str filename:
        The name of the file to save the data to.

    :param int timeout_seconds:
        The number of seconds to wait before timing out the request.

        **Default**: ``10``

    :param bool raise_error:
        Whether to raise an error if the download fails.

        **Default**: ``True``

    :param bool chunk:
        Whether to download the file in chunks and show progress.

        **Default**: ``True``

    :param int chunk_size:
        The size of each chunk in bytes.

        **Default**: ``1048576``

    :returns:
        True if the data was downloaded successfully, False otherwise.

    :raises HTTPError:
        If there is an issue with the HTTP request.

    **Example:**

    ```python
    download_from_url(
        url="http://example.com/file.zip",
        output_dir="./downloads",
        filename="file.zip"
    )
    ```
    """
    logger.debug(f"Logging Get Request at url: {url}")
    session = retry_session(retries = 10)
    response = session.get(url, timeout=timeout_seconds, stream=chunk)  # Enable streaming if chunk is True

    # Check if the response status code is 200 (OK)
    if response.status_code == 200:
        logger.info(f"Data availability verified successfully from {url}")

        path = Path(output_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)

        total_size = int(response.headers.get('content-length', 0))
        if chunk and total_size <= 2 * chunk_size:
            chunk = False
            logger.info(f"Total size of data is {total_size} bytes. Overriding chunking as data is less than 2 chunks.")
        elif not chunk and total_size > 2 * chunk_size:
            chunk = True
            logger.info(f"Total size of data is {total_size} bytes. Setting chunk to True as data is greater than 1 chunk.")

        if chunk:
            logger.info(f"Writing data to file at path: {path} with chunks of size {chunk_size} bytes.")

            with open(path, "wb") as f, tqdm(
                desc=filename,
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,  # Keep this as 1024 for proper scaling in MB
            ) as bar:
                for data in response.iter_content(chunk_size=chunk_size):
                    f.write(data)
                    bar.update(len(data))  # Update the progress bar with the size of the chunk
            logger.info(f"Data written to file at path: {path}")
        else:
            logger.debug(f"Writing data to file at path: {path} without chunks")
            with open(path, "wb") as f:
                f.write(response.content)
                logger.info(f"Data written to file at path: {path}")

        return True
    else:
        if raise_error:
            logger.error(f"Failed to download data from {url}. HTTP Status code: {response.status_code}")
            raise HTTPError(f"Failed to download data from {url}. HTTP Status code: {response.status_code}")
        else:
            logger.warning(f"Failed to download data from {url}. HTTP Status code: {response.status_code}")
            return False
