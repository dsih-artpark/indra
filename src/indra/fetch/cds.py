import io
import itertools
import logging
import os
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Optional, Union

import cdsapi
import typer
from requests.exceptions import HTTPError

from indra.emails import Report, Status
from indra.io import get_params, upload_data_to_s3

logger = logging.getLogger(__name__)
logging.captureWarnings(True)

app = typer.Typer()

def last_date_of_cds_data(suppress_output=True):
    """
    Returns the last date for which ERA5 data is available on the CDS.

    This function uses the CDS API to determine the most recent date for which data is available.
    It handles potential errors related to authentication and data availability.

    :param bool suppress_output:
        Whether to suppress the output of the CDS API client.

        **Default**: ``True``

    :returns:
        The last date for which ERA5 data is available and the standard output and error messages from the CDS API client.

    :raises HTTPError:
        If there is an issue with the HTTP request.

    :raises Exception:
        For any other exceptions that occur during the data retrieval process.

    **Example:**

    ```python
    last_date, output = last_date_of_cds_data()
    print(f"Last available date: {last_date}")
    ```
    """
    if suppress_output:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            client = cdsapi.Client()
        std_op = stdout.getvalue() + "\n" + stderr.getvalue()
    else:
        client = cdsapi.Client()
    # Setting a temporary directory for output
    output_dir = TemporaryDirectory().name

    # Setting some sample defaults for a trial request
    current_date = datetime.now()
    sample_bounds_nwse = [12, 76, 11, 77]
    variables = ["2m_temperature"]
    dataset = "reanalysis-era5-single-levels"
    product_type = "reanalysis"
    format = "netcdf"

    # Setting up request parameters
    request = dict()
    request["product_type"] = product_type
    request["format"] = format
    request["day"] = [current_date.strftime("%d")]
    request["month"] = [current_date.strftime("%m")]
    request["year"] = [current_date.strftime("%Y")]
    request["variable"] = variables
    request["area"] = sample_bounds_nwse

    try:
        client.retrieve(dataset, request, output_dir)
    except HTTPError as e:
        error_msg = str(e)
        if error_msg.startswith("401"):
            # Error due to invalid credentials
            logger.error("Access to CDS API is not authorized. Check your credentials.")
            raise
        elif error_msg.startswith("400"):
            latest_timestamp_msg = error_msg.split(".")[-1].strip()
            latest_timestamp = datetime.strptime(latest_timestamp_msg[-16:-1], "%Y-%m-%d %H:%M")
            logger.info(f"Latest timestamp available on CDS: {latest_timestamp.strftime('%Y-%m-%d %H:%M')}")
            return latest_timestamp, std_op
        else:
            logger.error(f"Failed to retrieve data from CDS: {error_msg}")
            raise
    except Exception as e:
        logger.error(f"Failed to retrieve data from CDS: {str(e).replace(os.linesep, ' ')!s}")
        raise

def check_cds_credentials(raiseError: bool = True, suppress_output: bool = True, get_latest_date: bool = False):
    """Check for the existence of the .cdsapirc credentials file.

    This function checks whether the .cdsapirc file exists in the user's home directory.
    If the file does not exist and `raiseError` is True, a FileNotFoundError is raised.
    If the file does not exist and `raiseError` is False, a warning is logged and the function returns False.
    If the file exists, a message is logged and the function returns True.

    :param bool raiseError:
        Whether to raise an error if the credentials file is not found.

        **Default**: ``True``

    :param bool suppress_output:
        Whether to suppress the output of the CDS API client.

        **Default**: ``True``

    :param bool get_latest_date:
        Whether to return the latest available date from CDS.

        **Default**: ``False``

    :returns:
        True if the credentials file exists, False otherwise. Optionally returns the latest date if `get_latest_date` is True.

    :raises FileNotFoundError:
        If the credentials file is not found and `raiseError` is True.

    **Example:**

    ```python
    exists, latest_date = check_cds_credentials(get_latest_date=True)
    if exists:
        print(f"Credentials verified. Latest date: {latest_date}")
    else:
        print("Credentials not found.")
    ```
    """

    path = Path.home() / ".cdsapirc"
    cds = "Climate data Store (CDS)"
    if not os.path.exists(path) and raiseError:
        logger.error(f"The credentials file for the {cds} was not found.")
        raise FileNotFoundError(f"The credentials file for the {cds} was not found.")
    elif not os.path.exists(path) and not raiseError:
        logger.warning(f"The credentials file for the {cds} was not found. Check README.md for more details.")
        return False
    else:
        latest_date, std_op = last_date_of_cds_data(suppress_output=suppress_output)
        logger.info(f"CDS Credentials Verified at: \"{path}\"")
        if get_latest_date:
            return True, latest_date
        return True

def retrieve_data_from_cds(*,
                           bounds_nwse: list,
                           start_date: str,
                           end_date: str,
                           variables: list,
                           output_dir: str,
                           region: str,
                           format: str = "netcdf",
                           extension: str = "nc",
                           dataset: str = "reanalysis-era5-single-levels",
                           product_type: str = "reanalysis",
                           overwrite: bool = True,
                           check_credentials: bool = True,
                           variable_code_dict: Optional[dict] = None
                          ):
    """Retrieve data from the Climate Data Store (CDS).

    This function retrieves climate data from the CDS based on the specified parameters.

    :param list bounds_nwse:
        List of coordinates defining the bounding box [north, west, south, east].

    :param str start_date:
        Start date for the data retrieval in the format 'YYYY-MM-DD'.

    :param str end_date:
        End date for the data retrieval in the format 'YYYY-MM-DD'.

    :param list variables:
        List of variables to retrieve.

    :param str output_dir:
        Directory where the output files will be saved.

    :param str region:
        The region for which data is being retrieved.

    :param str format:
        Format of the output files.

        **Default**: ``"netcdf"``

    :param str extension:
        File extension of the data files.

        **Default**: ``"nc"``

    :param str dataset:
        Dataset to retrieve data from.

        **Default**: ``"reanalysis-era5-single-levels"``

    :param str product_type:
        Type of product to retrieve.

        **Default**: ``"reanalysis"``

    :param bool overwrite:
        Whether to overwrite existing files.

        **Default**: ``True``

    :param bool check_credentials:
        Whether to check CDS credentials before retrieval.

        **Default**: ``True``

    :param Optional[dict] variable_code_dict:
        Dictionary mapping variable names to codes.

    :raises HTTPError:
        If there is an issue with the HTTP request.

    :raises Exception:
        For any other exceptions that occur during the data retrieval process.

    **Example:**

    ```python
    retrieve_data_from_cds(
        bounds_nwse=[12, 76, 11, 77],
        start_date="2023-01-01",
        end_date="2023-01-31",
        variables=["2m_temperature"],
        output_dir="./data",
        region="India"
    )
    ```
    """

    logger.info("Starting data retrieval from CDS")
    if check_credentials:
        logger.info("Checking CDS credentials.")
        cds_credentials_bool, last_date_of_cds_data = check_cds_credentials(get_latest_date=True)
    else:
        logger.debug("Skipping CDS credentials check.")

    client = cdsapi.Client()
    logger.info("CDS API client initialized")

    # Code to generate tuples of (year, month) pairs in provided range

    try:
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")
        logger.debug(f"Start date: {start_date}, End date: {end_date}")
    except ValueError as e:
        logger.error(f"Error parsing dates: {e}")
        raise

    date_tuples = []
    current_date = start_date

    while current_date <= end_date:
        date_tuples.append((current_date.strftime("%Y"), current_date.strftime("%m")))
        # Increment the month and set the date to the 1st
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1, day=1)

    iter_product = list(itertools.product(date_tuples, variables))

    # Check if output_dir exists, create if it doesn't
    if not os.path.exists(output_dir):
        logger.info(f"Output directory {output_dir} does not exist. Creating it...")
        os.makedirs(output_dir)
        logger.info(f"Created output directory {output_dir}")

    request = dict()
    request["product_type"] = product_type
    request["format"] = format
    request["day"] = [f"{i:02}" for i in range(1, 32)]
    request["area"] = bounds_nwse

    for (year, month), variable in iter_product:
        if variable_code_dict is not None:
            variable_code = variable_code_dict[variable]
        request["variable"] = [variable]
        request["year"] = [year]
        request["month"] = [month]

        filename = f"{region.upper()}_{year}_{month}_{variable_code}.{extension}"
        output_path = os.path.join(output_dir, filename)

        if os.path.exists(output_path) and overwrite:
            logger.warning(f"File {filename} already exists in the output directory. Overwriting...")
        elif os.path.exists(output_path) and not overwrite:
            logger.warning(f"File {filename} already exists in the output directory. Skipping...")
            continue

        logger.info(f"Downloading {filename} to {output_dir}")
        try:
            client.retrieve(dataset, request, output_path)
            logger.info(f"Downloaded {filename} to {output_dir}")
        except HTTPError as e:
            logger.warning(f"Failed to download {filename}: {str(e).replace(os.linesep, ' ')!s}")
            continue
        except Exception as e:
            logger.error(f"Failed to download {filename}: {str(e).replace(os.linesep, ' ')!s}")
            raise

def fetch_and_upload_cds_data(
    yaml_path: Path,
    log_level: str = "DEBUG",
    current_month: bool = True,
    log_filename: Union[str, None] = None,
    ) -> tuple[bool, int, datetime]:
    """
    Process CDS ERA5 daily data
    """
    params = get_params(yaml_path=yaml_path)
    cds_params = params['cds']
    shared_params = params['shared_params']

    # Remove the logging configuration here since it's handled by CLI
    # We don't want to override the parent configuration

    latest_timestamp, _ = last_date_of_cds_data()

    if current_month:
        start_date = latest_timestamp.strftime("%Y-%m-01")
        end_date = latest_timestamp.strftime("%Y-%m-%d")
        cds_params["start_date"] = start_date
        cds_params["end_date"] = end_date

    upload_successes = []
    total_no_files = 0

    for _i, region in enumerate(cds_params['bounds_nwse'].keys()):
        s3_prefix = f"{cds_params['ds_id']}-{cds_params['ds_name']}/{cds_params['folder_name']}/{region.upper()}"
        local_region_dir = Path(shared_params['local_data_dir']).expanduser() / Path(shared_params['s3_bucket']) / Path(s3_prefix)
        local_region_dir.mkdir(parents=True, exist_ok=True)
        retrieve_data_from_cds(bounds_nwse=cds_params['bounds_nwse'][region], variables=list(cds_params['variables'].keys()),
                               output_dir=local_region_dir,
                               start_date=cds_params["start_date"], end_date=cds_params["end_date"],
                               variable_code_dict = cds_params['variables'], region=region,
                               check_credentials=False
                              )

        no_files = len(list(local_region_dir.glob(f'*.{cds_params["extension"]}')))
        upload_success = upload_data_to_s3(upload_dir=local_region_dir, Bucket=shared_params['s3_bucket'],
                                                     Prefix=s3_prefix, extension=cds_params['extension'])

        upload_successes.append(upload_success)
        total_no_files += no_files

    if all(upload_successes):
        return True, total_no_files, latest_timestamp
    else:
        return False, total_no_files, latest_timestamp

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    yaml_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            resolve_path=True,
            help="Path to YAML configuration file containing CDS parameters"
        )
    ],
    current_month: Annotated[
        bool,
        typer.Option(
            "--current-month/--custom-date",
            "-c/-C",
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
    ] = False
) -> None:
    """Process and upload CDS ERA5 daily data to S3.
    Fetches ERA5 reanalysis data from the Climate Data Store (CDS) and uploads it to S3.
    Uses the configuration from the provided YAML file for data parameters, S3 settings, and notification recipients.
    """
    # Get the parent app's logging configuration
    parent_config = ctx.obj or {}

    params = get_params(yaml_path=yaml_path)
    email_recipients = params['shared_params']['email_recipients']
    cds_params = params['cds']

    report = Report(
        job_name="CDS Daily Job",
        email_recipients=email_recipients
    )

    try:
        # Use the parent's logging configuration
        if not debug:
            upload_success, no_files, latest_timestamp = fetch_and_upload_cds_data(
                yaml_path=yaml_path,
                current_month=current_month,
                log_level=parent_config.get("log_level", "INFO"),
                log_filename=parent_config.get("log_file")
            )

        else:
            upload_success = debug_upload_success
            no_files = 0
            latest_timestamp = datetime.now()

        dataset_name = cds_params['ds_name'].replace('_', ' ')
        dataset_source = cds_params['ds_source']
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if upload_success:
            message = (
                f"All {no_files} files obtained from {dataset_name} "
                f"on {dataset_source} have been successfully uploaded to S3 on {current_date}.\n"
                f"The last timestamp of data availability for {dataset_name} is {latest_timestamp} UTC, "
                f"when checked at approximately {current_timestamp} UTC."
                f"Detailed health of the run can be found in the debug log file for the "
                f"current month on the server: logs/{parent_config.get('log_file')}"
            )
            report.add_a_status_report('CDS Upload', Status.SUCCESS, message)
        else:
            message = (
                f"One or more files from {dataset_name} "
                f"on {dataset_source} have failed to upload to S3 on {current_date}.\n"
                f"The last timestamp of data availability for {dataset_name} is {latest_timestamp} UTC, "
                f"when checked at approximately {current_timestamp} UTC.\n"
                f"Detailed health of the run can be found in the attached debug log file."
            )
            report.add_a_status_report('CDS Upload', Status.CRITICAL, message)

    except Exception as e:
        report.add_a_status_report('General', Status.CRITICAL, f'Exception raised: {e}')

    finally:
        if report.any_criticals():
            report.add_attachment(f'logs/{parent_config.get("log_file")}')
        report.send_email()

if __name__ == "__main__":
    app()

__all__ = ["app", "check_cds_credentials", "fetch_and_upload_cds_data", "last_date_of_cds_data", "main", "retrieve_data_from_cds"]
