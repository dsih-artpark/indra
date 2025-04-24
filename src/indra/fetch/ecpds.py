import logging
import os
import tempfile
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Annotated, Optional

import typer
from bs4 import BeautifulSoup

from indra.emails import Report, Status
from indra.io import download_from_url, get_params, retry_session, upload_data_to_s3

logger = logging.getLogger(__name__)
logging.captureWarnings(True)

app = typer.Typer()


@app.command("latest-date-of-data")
def last_date_of_ecpds_data(*, base_url: str = "https://data.ecmwf.int/forecasts/"):
    """Retrieve the last date of forecast data from ECMWF's ECPDS.

    This function retrieves the last date of forecast data from ECMWF's ECPDS based on the specified parameters.

    :param str ecpds_url:
        The base URL of the ECPDS.

        **Default**: ``"https://data.ecmwf.int/forecasts/"``

    :returns:
        The last date of forecast data from ECMWF's ECPDS, or None if no valid dates are found.

    **Example:**

    ```python
    last_date = last_date_of_ecpds_data()
    print(f"Last forecast date from ECPDS: {last_date}")
    ```
    """

    logger.debug(f"Request URL: {base_url}")

    session = retry_session(retries=10)
    response = session.get(url=base_url, timeout=10)
    if response.status_code != 200:
        logger.error(f"Failed to retrieve the directory: {response.status_code}")
        return None

    # Parse the HTML content
    soup = BeautifulSoup(response.text, "html.parser")
    links = soup.find_all("a")

    # Extract dates from the folder names
    dates = []
    for link in links:
        href = link.get("href")
        if not href or href == "home" or "github.com" in href:
            continue

        # Extract the date part regardless of path structure
        date_str = href.strip("/").split("/")[-1]

        try:
            # Convert the folder name to a date
            date = datetime.strptime(date_str, "%Y%m%d")
            dates.append(date)
        except ValueError:
            logger.debug(f"Skipping non-date folder: {date_str}")
            continue

    # Find the latest date if any dates are retrieved
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
        logger.error("No valid dates found in ECPDS. Dates returned is empty.")
        return None


def construct_ecpds_urls(
    *,
    date: datetime,
    configs: list[dict],
    base_url: str = "https://data.ecmwf.int/forecasts/",
):
    """Construct the URL for the ECPDS data.

    This function constructs the URL for the ECPDS data based on the specified parameters.

    :param datetime date:
        The date of the forecast data.

    :param list[dict] configs:
        The configurations of the forecast data to retrieve.
        Each dictionary contains the following keys:
        - reference_time: The reference time of the forecast data.
        - model: The model of the forecast data.
        - resolution: The resolution of the forecast data.
        - stream: The stream of the forecast data.
        - step: The step of the forecast data. String of format "0h", "6h", "12h", etc.
        - type: The type of the forecast data. "fc" for forecast, "ef" for ensemble forecast.

    :param str ecpds_base_url:
        The base URL of the ECPDS.
    """
    try:
        formatted_date = date.strftime("%Y%m%d")
    except AttributeError:
        raise ValueError("Invalid date format: expected a datetime object") from None

    if not base_url.endswith("/"):
        base_url += "/"

    urls = []
    for config in configs:
        for each_format in config["format"]:
            url = (
                f"{base_url}{formatted_date}/{config['reference_time']}z/{config['model']}/"
                f"{config['resolution']}/{config['stream']}/{formatted_date}{config['reference_time']}0000"
                f"-{config['step']}-{config['stream']}-{config['type']}.{each_format}"
            )
            urls.append(url)
    return urls


@app.callback(invoke_without_command=True)
def main(
    *,
    ctx: typer.Context,
    yaml_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            resolve_path=True,
        ),
    ],
    get_latest_date: Annotated[
        bool, typer.Option("--get-latest-date/ ", "-l/ ", help="Use current month for date range, or use dates from config")
    ] = True,
    custom_date: Annotated[Optional[str], typer.Option("--custom-date", "-c", help="Date to retrieve forecast data for")] = None,
    upload: Annotated[
        bool,
        typer.Option(
            " /--no-upload",
            " /-N",
            help="Upload the data to S3. If True, credentials must be set in the environment variables or in ~/.aws/credentials",
        ),
    ] = True,
    directory: Annotated[Optional[str], typer.Option("--directory", "-d", help="Directory to store the data")] = None,
) -> None:
    parent_config = ctx.obj or {}
    params = get_params(yaml_path)
    shared_params = params["shared_params"]
    ecpds_params = params["ecpds"]
    # check if required ecpds_params are present
    required_params = ["url", "ds_id", "ds_name", "ds_folder_name", "configs"]
    for param in required_params:
        if param not in ecpds_params:
            message = f"Missing required parameter: {param}"
            logger.error(message)
            raise ValueError(message)
    # check if required shared_params are present
    required_shared_params = ["s3_bucket", "email_recipients"]
    for param in required_shared_params:
        if param not in shared_params:
            message = f"Missing required parameter: {param}"
            logger.error(message)
            raise ValueError(message)

    report = Report(job_name="ECPDS Daily Job", email_recipients=shared_params["email_recipients"])
    try:
        while True:
            # Step 1: Get the latest date of data available
            if get_latest_date:
                last_date = last_date_of_ecpds_data(base_url=ecpds_params["url"])
                if last_date is None:
                    message = "No valid dates found in ECPDS."
                    logger.error(message)
                    report.add_a_status_report("ECPDS Latest Date Retrieval", Status.CRITICAL, message)
                    break
                else:
                    message = f"Last forecast date from ECPDS: {last_date}"
                    logger.info(message)
                    report.add_a_status_report("ECPDS Latest Date Retrieval", Status.SUCCESS, message)
            else:
                message = "Custom dates are not yet supported."
                logger.error(message)
                report.add_a_status_report("ECPDS Data Retrieval", Status.CRITICAL, message)
                break

            # Step 2: Get the data for the latest date
            urls = construct_ecpds_urls(base_url=ecpds_params["url"], date=last_date, configs=ecpds_params["configs"])
            if directory is None:
                logger.info("Using a temporary directory to store the data")
                directory = tempfile.TemporaryDirectory().name  # Named temporary directory
            else:
                logger.info(f"Using the directory {directory} to store the data")

            for url in urls:
                filename = url.split("/")[-1]
                filepath = os.path.join(directory, filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                logger.info(f"Downloading {url} to {filepath}")
                try:
                    download_success = download_from_url(
                        url=url, output_dir=directory, filename=filename, raise_error=ecpds_params["raise_error"]
                    )
                    if not download_success:
                        message = f"Downloading {url} failed"
                        logger.error(message)
                        report.add_a_status_report("ECPDS Data Retrieval", Status.ERROR, message)
                        continue
                except Exception as e:
                    message = f"Downloading {url} failed: {e}"
                    logger.error(message)
                    report.add_a_status_report("ECPDS Data Retrieval", Status.ERROR, message)

            list_files_downloaded = [
                os.path.join(directory, url.split("/")[-1]) for url in urls if os.path.exists(os.path.join(directory, url.split("/")[-1]))
            ]
            no_files_downloaded = len(list_files_downloaded)
            if no_files_downloaded == len(urls):
                message = f"All {len(urls)} files downloaded successfully"
                logger.info(message)
                report.add_a_status_report("ECPDS Data Retrieval", Status.SUCCESS, message)
            elif no_files_downloaded >= 1:
                message = f"Only {no_files_downloaded} out of {len(urls)} files downloaded"
                logger.error(message)
                report.add_a_status_report("ECPDS Data Retrieval", Status.ERROR, message)
            else:
                message = f"Download of all {len(urls)} files failed"
                logger.error(message)
                report.add_a_status_report("ECPDS Data Retrieval", Status.CRITICAL, message)

            if upload:
                logger.info("Uploading the data to S3")
                if report.any_criticals():
                    message = "Uploading the data to S3 failed because of critical errors at the data retrieval step."
                    logger.error(message)
                    report.add_a_status_report("ECPDS Data Upload", Status.CRITICAL, message)
                    break
                else:
                    s3_prefix = f"{ecpds_params['ds_id']}-{ecpds_params['ds_name']}/{ecpds_params['ds_folder_name']}"
                    failed_uploads = 0
                    total_files = len(list_files_downloaded)
                    if total_files > 0:
                        for filepath in list_files_downloaded:
                            failed_uploads += upload_data_to_s3(
                                upload_dir=directory,
                                Bucket=shared_params["s3_bucket"],
                                Prefix=s3_prefix,
                                extension=filepath.split(".")[-1],
                                raise_error=ecpds_params["raise_error"],
                            )

                    if failed_uploads == 0:
                        message = f"All {total_files} files uploaded successfully"
                        logger.info(message)
                        report.add_a_status_report("ECPDS Data Upload", Status.SUCCESS, message)
                    elif failed_uploads >= 1 and failed_uploads < total_files:
                        message = f"Only {total_files - failed_uploads} out of {total_files} files uploaded"
                        logger.error(message)
                        report.add_a_status_report("ECPDS Data Upload", Status.ERROR, message)
                    else:
                        message = f"Upload of all {total_files} files failed"
                        logger.error(message)
                        report.add_a_status_report("ECPDS Data Upload", Status.CRITICAL, message)
                break
            else:
                message = "Skipping the upload of the data to S3"
                logger.info(message)
                report.add_a_status_report("ECPDS Data Upload", Status.NOTE, message)
                break

        # Add attachments to the report if there are any critical or error reports
        if report.any_criticals() or report.any_errors():
            report.add_attachment(f"logs/{parent_config.get('log_file')}")
    except Exception as e:
        message = f"Exception raised, check the attached log file for more details: {e}"
        logger.error(message)
        report.add_a_status_report("Unexpected Error", Status.CRITICAL, message)
        report.add_attachment(f"logs/{parent_config.get('log_file')}")
    finally:
        report.send_email()


if __name__ == "__main__":
    app()

__all__ = ["app", "construct_ecpds_urls", "last_date_of_ecpds_data", "main"]
