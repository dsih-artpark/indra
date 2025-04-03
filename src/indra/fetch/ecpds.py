import logging
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Annotated, Optional, Union

import typer
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError

from indra.emails import Report, Status
from indra.io import download_from_url, get_params, retry_session, upload_data_to_s3

logger = logging.getLogger(__name__)
logging.captureWarnings(True)

app = typer.Typer()


def last_date_of_ecpds_data(*,
                          ecpds_url: str = "https://data.ecmwf.int/forecasts/"
                          ):
    """Retrieve the last date of forecast data from ECMWF's ECPDS.

    This function retrieves the last date of forecast data from ECMWF's ECPDS based on the specified parameters.

    :param str ecpds_url:
        The base URL of the ECPDS.

        **Default**: ``"https://data.ecmwf.int/forecasts/"``

    :returns:
        The last date of forecast data from ECMWF's ECPDS, or None if no valid dates are found.

    :raises HTTPError:
        If there is an issue with the HTTP request.

    **Example:**

    ```python
    last_date = last_date_of_ecpds_data()
    print(f"Last forecast date: {last_date}")
    ```
    """

    logger.debug(f"Request URL: {ecpds_url}")

    session = retry_session(max_retries=10, backoff_factor=0.5)
    response = session.get(url=ecpds_url, timeout=10)
    if response.status_code != 200:
        logger.error(f"Failed to retrieve the directory: {response.status_code}")
        return None

    # Parse the HTML content
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find all links in the directory listing
    links = soup.find_all('a')

    # Extract dates from the folder names
    dates = []
    for link in links:
        href = link.get('href')
        if href and href.endswith('/'):  # Only consider directories
            try:
                # Convert the folder name to a date
                date = datetime.strptime(href.split('/')[2], '%Y%m%d')
                dates.append(date)
            except ValueError:
                continue  # Skip if the format is incorrect

    # Find the latest date
    if dates:
        # Find the maximum date in the list
        max_date = max(dates)
        # Create a datetime object for 8:49 UTC on the max date
        threshold_time = datetime.combine(max_date, time(8, 49), tzinfo=timezone.utc)

        # Get the current time in UTC
        current_time_utc = datetime.now(timezone.utc)

        # Check if the current time is past 8:49 UTC on the max date
        # This is a quick fix to account for the fact that the operational forecast is uploaded at 8:34 UTC.
        # Adding a 15-minute buffer to account for potential delays.
        if current_time_utc > threshold_time:
            result_date = max_date
        else:
            # If not, return the previous date (if it exists)
            previous_date = max_date - timedelta(days=1)
            result_date = previous_date if previous_date in dates else None

        if result_date is None:
            logger.error("No valid dates found in ECPDS.")
            return None
        else:
            return result_date
    else:
        logger.error("No valid dates found in ECPDS.")
        return None


def retrieve_data_from_ecpds(*,
                             get_latest_date: bool = True,
                             custom_date: Optional[datetime] = None,
                             zulu_utc_timestamp: str = "00z",
                             model: str = "ifs",
                             resolution: str = "0p25",
                             forecast_type: str = "oper",
                             forecast_times: Optional[Union[list, str]] = None,
                             ecpds_base_url: str = "https://data.ecmwf.int/forecasts",
                             raise_error: bool = True,
                             chunk: bool = True,
                             chunk_size: int = 1048576,
                             output_dir: str = "~/.dsih-data"
                             ):
    """Retrieve operational forecast data from ECMWF's ECPDS.

    This function retrieves operational forecast data from ECMWF's ECPDS based on the specified parameters.

    :param bool get_latest_date:
        Whether to retrieve the latest available forecast data.

        **Default**: ``True``

    :param Optional[datetime] custom_date:
        The date of the forecast data to retrieve. Ignored if `get_latest_date` is True.

    :param str zulu_utc_timestamp:
        The zulu UTC timestamp of the forecast data to retrieve.

        **Default**: ``"00z"``

    :param str model:
        The model to retrieve the forecast data from.

        **Default**: ``"ifs"``

    :param str resolution:
        The resolution of the forecast data to retrieve.

        **Default**: ``"0p25"``

    :param str forecast_type:
        The type of forecast data to retrieve.

        **Default**: ``"oper"``

    :param Optional[Union[list, str]] forecast_times:
        The timestamps of the forecast data to retrieve.

        **Default**: ``["0h", "6h"]``

    :param str ecpds_base_url:
        The base URL of the ECPDS.

        **Default**: ``"https://data.ecmwf.int/forecasts"``

    :param bool raise_error:
        Whether to raise an error if the download fails.

        **Default**: ``True``

    :param bool chunk:
        Whether to download the file in chunks and show progress.

        **Default**: ``True``

    :param int chunk_size:
        The size of each chunk in bytes.

        **Default**: ``1048576``

    :param str output_dir:
        The directory to save the downloaded data.

        **Default**: ``"~/.dsih-data"``

    :returns:
        True if the data was downloaded successfully, False otherwise.

    :raises HTTPError:
        If there is an issue with the HTTP request.

    :raises ValueError:
        If invalid parameters are provided.

    **Example:**

    ```python
    success = retrieve_data_from_ecpds(
        get_latest_date=True,
        forecast_times=["0h", "6h"],
        output_dir="./ecpds_data"
    )
    if success:
        print("Data retrieved successfully.")
    ```
    """
    if forecast_times is None:
        forecast_times = ["0h", "6h"]
    if get_latest_date:
        date = last_date_of_ecpds_data()
        if date is None:
            raise ValueError(f"No date found in ECPDS url {ecpds_base_url}.")
    else:
        if date is None:
            raise ValueError("No date provided.")
        else:
            logger.error("Custom dates are not yet supported. Raising Error...")
            raise ValueError("Custom dates are not yet supported.")
        # This line is for the future. This will allow the user to pass a custom date. It will not be used in the current implementation.
        date = custom_date

    if model != "ifs":
        raise ValueError("Only 'ifs' model is currently supported")

    if resolution != "0p25":
        raise ValueError("Only '0p25' resolution is currently supported")

    if forecast_type != "oper":
        raise ValueError("Only 'oper' forecast type is currently supported")

    # Convert date string to format needed for URL
    formatted_date = date.strftime("%Y%m%d")
    formatted_date_with_time = date.strftime("%Y%m%d%H%M%S")

    forecast_times = forecast_times if isinstance(forecast_times, list) else [forecast_times]

    grib_successes = [None] * len(forecast_times)
    index_successes = [None] * len(forecast_times)
    for i, forecast_time in enumerate(forecast_times):
        url = (
            f"{ecpds_base_url}/{formatted_date}/{zulu_utc_timestamp}/{model}/"
            f"{resolution}/{forecast_type}/{formatted_date_with_time}-{forecast_time}-{forecast_type}-fc.grib2"
        )
        logger.debug(f"Attempting to retrieve data from URL: {url}")
        filename = f"{formatted_date_with_time}-{forecast_time}-{forecast_type}-fc.grib2"
        grib_success = download_from_url(url=url,
                                         output_dir=output_dir,
                                         filename=filename,
                                         raise_error=False,
                                         chunk=chunk,
                                         chunk_size=chunk_size)
        if grib_success:
            index_url = url.replace(".grib2", ".index")
            index_filename = filename.replace(".grib2", ".index")
            index_success = download_from_url(url=index_url,
                                              output_dir=output_dir,
                                              filename=index_filename,
                                              raise_error=False,
                                              chunk=False)
        if not grib_success:
            index_success = False
        grib_successes[i] = grib_success
        index_successes[i] = index_success

    if all(grib_successes) and all(index_successes):
        logger.info(f"Successfully retrieved data and index files from ECPDS for date {date}")
        return True
    elif raise_error:
        logger.error(f"Failed to retrieve data and index files from ECPDS for date {date}")
        raise HTTPError(f"Failed to retrieve data and index files from ECPDS for date {date}")
    else:
        logger.warning(f"Failed to retrieve data and index files from ECPDS for date {date}")
        return False


def fetch_and_upload_ecpds_data(*,
                                yaml_path: Path,
                                get_latest_date: bool = True,
                                log_level: str = "DEBUG",
                                custom_date: Optional[str] = None,
                                log_filename: Optional[str] = None,
                                ) -> tuple[bool, int, datetime]:
    """
    Process CDS ERA5 daily data

    :param Path yaml_path:
        The path to the YAML configuration file.

    :param bool get_latest_date:
        Whether to retrieve the latest available forecast data.

        **Default**: ``True``

    :param Optional[str] custom_date:
        The date of the forecast data to retrieve. Ignored if `get_latest_date` is True.

    :param Optional[str] log_filename:
        The filename of the log file.
    """
    params = get_params(yaml_path=yaml_path)
    ecpds_params = params['ecpds']
    shared_params = params['shared_params']

    latest_date = last_date_of_ecpds_data()

    s3_prefix = f"{ecpds_params['ds_id']}-{ecpds_params['ds_name']}/{ecpds_params['folder_name']}/{latest_date.strftime('%Y')}"
    local_region_dir = Path(shared_params['local_data_dir']).expanduser() / Path(shared_params['s3_bucket']) / Path(s3_prefix)
    local_region_dir.mkdir(parents=True, exist_ok=True)

    retrieve_data_from_ecpds(get_latest_date=get_latest_date, custom_date=custom_date, ecpds_base_url=ecpds_params['url'],
                                            output_dir=local_region_dir, zulu_utc_timestamp=ecpds_params['zulu_utc_timestamp'],
                                            resolution=ecpds_params['resolution'],
                                            model=ecpds_params['model'], forecast_type=ecpds_params['forecast_type'],
                                            forecast_times=ecpds_params['forecast_times'],
                                            raise_error=ecpds_params['raise_error'], chunk=ecpds_params['chunk'],
                                            chunk_size=ecpds_params['chunk_size'])


    upload_success = [None] * len(ecpds_params['extensions'])
    no_files = [None] * len(ecpds_params['extensions'])

    for i, extension in enumerate(ecpds_params['extensions']):
        no_files[i] = len(list(local_region_dir.glob(f"*.{extension}")))
        upload_success[i] = upload_data_to_s3(upload_dir=local_region_dir, Bucket=shared_params['s3_bucket'],
                                     Prefix=s3_prefix, extension=extension)

    upload_success = all(upload_success)
    no_files = sum(no_files)

    return upload_success, no_files, latest_date


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    yaml_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            resolve_path=True,
            help="Path to YAML configuration file containing ECPDS parameters"
        )
    ],
    get_latest_date: Annotated[
        bool,
        typer.Option(
            "--get-latest-date/--custom-date",
            "-g/-c",
            help="Use current month for date range, or use dates from config"
        )
    ] = True,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug/--no-debug",
            "-d/-D",
            help="Enable debug mode, send email without actually downloading data"
        )
    ] = False,
    debug_upload_success: Annotated[
        bool,
        typer.Option(
            "--debug-upload-success/--no-debug-upload-success",
            "-u/-U",
            help="When debug mode is enabled, what should the upload_success be set to. If True, run will simulate a successful upload."
        )
    ] = False,
    custom_date: Annotated[
        Optional[str],
        typer.Option(
            "--custom-date",
            "-c",
            help="Date to retrieve forecast data for"
        )
    ] = None
) -> None:
    """
    Process ECPDS forecast data
    """
    parent_config = ctx.obj or {}
    params = get_params(yaml_path=yaml_path)
    email_recipients = params['shared_params']['email_recipients']
    ecpds_params = params['ecpds']

    report = Report(
        job_name="ECPDS Daily Job",
        email_recipients=email_recipients
    )

    try:
        if not debug:
            upload_success, no_files, latest_timestamp = fetch_and_upload_ecpds_data(
                yaml_path=yaml_path,
                get_latest_date=get_latest_date,
                custom_date=custom_date,
                log_level=parent_config.get("log_level", "INFO"),
                log_filename=parent_config.get("log_file")
            )

        else:
            upload_success = debug_upload_success
            no_files = 0
            latest_timestamp = datetime.now()

        dataset_name = ecpds_params['ds_name'].replace('_', ' ')
        dataset_source = ecpds_params['ds_source']
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if upload_success:
            message = (
                f"All {no_files} files obtained from {dataset_name} "
                f"on {dataset_source} have been successfully uploaded to S3 on {current_date}.\n"
                f"The last timestamp of data availability for {dataset_name} is {latest_timestamp} UTC, "
                f"when checked at approximately {current_timestamp} UTC."
            )
            report.add_a_status_report('ECPDS Upload', Status.SUCCESS, message)
        else:
            message = (
                    f"One or more files from {dataset_name} "
                    f"on {dataset_source} have failed to upload to S3 on {current_date}.\n"
                    f"The last timestamp of data availability for {dataset_name} is {latest_timestamp} UTC, "
                    f"when checked at approximately {current_timestamp} UTC.\n"
                    f"Detailed health of the run can be found in the attached debug log file."
                )
            report.add_a_status_report('ECPDS Upload', Status.ERROR, message)
    except Exception as e:
        report.add_a_status_report('General', Status.CRITICAL, f'Exception raised: {e}')
    finally:
        if report.any_criticals():
            report.add_attachment(f'logs/{parent_config.get("log_file")}')
        report.send_email()

if __name__ == "__main__":
    app()

__all__ = ["app", "fetch_and_upload_ecpds_data", "last_date_of_ecpds_data", "main", "retrieve_data_from_ecpds"]
