import io
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import pandas as pd
import requests
import typer

from indra.emails import Report, Status
from indra.io import get_params, retry_session, upload_data_to_s3

# Get current working directory
cwd = os.getcwd()

logger = logging.getLogger(__name__)
logging.captureWarnings(True)

app = typer.Typer()

# Download and save data from the IMD URL
def download_imd_district_rain(url, folder, filename_prefix):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            json_data = response.json()
            df = pd.DataFrame(json_data)
            d_date = datetime.now().strftime('%Y-%m-%d_%H-00-00')
            folder_date = datetime.now().strftime('%Y_%m_%d')
            folder_path = os.path.join(cwd, folder_date)
            os.makedirs(folder_path, exist_ok=True)
            filename = f"{filename_prefix}_{d_date}.csv"
            file_path = os.path.join(folder_path, filename)
            df.to_csv(file_path, index=False)
            print(f"[✔] Data downloaded and saved as {filename}")
            return file_path
        else:
            print(f"[✖] Failed to download data. HTTP Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"[!] Error during request: {e}")
    return None

# Download the data (can be extended for more sources)
def download_data():
    new_files = []
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            download_imd_district_rain,
            'https://mausam.imd.gov.in/api/districtwise_rainfall_api.php',
            'IMD_District_Rainfall',
            'IMD_Districtwise_Rainfall'
        )
        new_files.append(future.result())
    return [f for f in new_files if f]


def clean_imd_data(df: pd.DataFrame, datacode: str, live=False) -> pd.DataFrame:
    """Clean the IMD data.

    This function cleans the IMD data.

    :param pd.DataFrame df:
        The IMD data to clean.

    :param str datacode:
        The data code for the specific dataset.

    :param bool live:
        Whether the data is live or not.

    :return:
        The cleaned IMD data as a pandas DataFrame.
    """
    # Drop the WEATHER_ICON, WEATHER_MESSAGE, BACKGROUND, and BACKGROUND_URL columns if they exist
    columns_to_drop = ["WEATHER_ICON", "WEATHER_MESSAGE", "BACKGROUND", "BACKGROUND_URL"]
    existing_columns = [col for col in columns_to_drop if col in df.columns]
    if existing_columns:
        df = df.drop(columns=existing_columns)

    if datacode == "imd_Station_API":
        # Check if required columns exist before processing
        required_columns = ["Date of Observation", "Time"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            for col in missing_columns:
                logger.warning(f"Required column '{col}' not found in the DataFrame")
                # Add empty columns for missing required fields
                df[col] = None

        # Validate and fix the date and time columns, and use them to create a new timestamp column
        df["Date"] = pd.to_datetime(df["Date of Observation"], errors="coerce")
        df.drop(columns=["Date of Observation"], inplace=True)

        # Handle Time column safely
        if "Time" in df.columns:
            df["Time"] = df["Time"].astype(str).str.zfill(2)
        else:
            df["Time"] = "00"  # Default value

        # Create timestamp safely
        def create_timestamp(row):
            try:
                if pd.notna(row['Date']):
                    return f"{row['Date'].strftime('%Y-%m-%d')}T{row['Time']}:00:00.00+05:30"
                else:
                    return None
            except (ValueError, AttributeError):
                return None

        df.insert(0, "timestamp", df.apply(create_timestamp, axis=1))

        # Clean string columns safely
        for col in ["Station", "Sunset"]:
            if col in df.columns and df[col].dtype == object:
                df[col] = df[col].str.strip("\r\n\t ") if hasattr(df[col], 'str') else df[col]

        # Ensure that time columns are in the correct format
        time_columns = ["Sunrise", "Sunset", "Moonrise", "Moonset"]
        for col in time_columns:
            if col in df.columns:
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce", format="%H:%M").dt.strftime("%H:%M")
                except AttributeError:
                    # This happens when all values are None/NaT
                    pass

        mapper_dict = {
            "Station": "stationName",
            "Station Id": "stationID",
            "timestamp": "timestamp",
            "Mean Sea Level Pressure": "meanSeaLevelPressure",
            "Wind Direction": "windDirection",
            "Wind Speed KMPH": "windSpeed",
            "Temperature": "temperature",
            "Weather Code": "weatherCode",
            "Nebulosity": "nebulosity",
            "Humidity": "humidity",
            "Last 24 hrs Rainfall": "last24hrsRainfall",
            "Feel Like": "feelLike",
            "Sunrise": "sunrise",
            "Sunset": "sunset",
            "Moonrise": "moonrise",
            "Moonset": "moonset",
        }

        # Check for expected columns and warn if missing
        for expected_col in mapper_dict.keys():
            if expected_col not in df.columns:
                logger.warning(f"Expected column '{expected_col}' not found in the DataFrame")
                # Add the column with None values to avoid KeyError during renaming
                df[expected_col] = None

        # Rename the columns
        df.rename(columns=mapper_dict, inplace=True)

        numeric_cols = ["meanSeaLevelPressure", "windSpeed", "temperature", "nebulosity", "humidity", "last24hrsRainfall", "feelLike"]

        # Convert the numeric columns to float safely
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].replace(["NA", ""], None)
                try:
                    df[col] = df[col].astype(float)
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert column '{col}' to float, keeping as is")

        # Convert Station Name to All Caps if it exists and is string type
        if "stationName" in df.columns and df["stationName"].dtype == object:
            df["stationName"] = df["stationName"].str.upper()

        # Drop the Date and Time columns if they exist
        columns_to_drop = ["Date", "Time"]
        existing_columns = [col for col in columns_to_drop if col in df.columns]
        if existing_columns:
            df = df.drop(columns=existing_columns)

    elif datacode == "imd_AWS_ARG":
        # Check if required columns exist before processing
        required_columns = ["DATE", "TIME"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            for col in missing_columns:
                logger.warning(f"Required column '{col}' not found in the DataFrame")
                # Add empty columns for missing required fields
                df[col] = None

        # Validate and fix the date and time columns safely
        if "DATE" in df.columns:
            df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
        else:
            df["DATE"] = pd.NaT

        if "TIME" in df.columns:
            df["TIME"] = pd.to_datetime(df["TIME"], errors="coerce", format="%H:%M:%S")
        else:
            df["TIME"] = pd.NaT

        # Handle ID column renaming safely
        if "ID" in df.columns:
            df.rename(columns={"ID": "stationID"}, inplace=True)

        # Create timestamp safely
        def create_aws_timestamp(row):
            try:
                if pd.notna(row['DATE']) and pd.notna(row['TIME']):
                    return f"{row['DATE'].strftime('%Y-%m-%d')}T{row['TIME'].strftime('%H:%M:%S.00+05:30')}"
                else:
                    return None
            except (ValueError, AttributeError):
                return None

        df.insert(0, "timestamp", df.apply(create_aws_timestamp, axis=1))

        # Drop the Date and Time columns if they exist
        columns_to_drop = ["DATE", "TIME"]
        existing_columns = [col for col in columns_to_drop if col in df.columns]
        if existing_columns:
            df = df.drop(columns=existing_columns)

    return df

@app.callback(invoke_without_command=True)
def main(
    *,
    ctx: typer.Context,
    yaml_path: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, resolve_path=True, help="Path to YAML configuration file containing IMD parameters"),
    ],
    directory: Annotated[Optional[str], typer.Option("--directory", "-d", help="Directory to store the data")] = None,
    run_summary_path: Annotated[Optional[str], typer.Option("--run-summary-path", "-r", help="Path to the run summary file")] = None,
    email: Annotated[Optional[bool], typer.Option("--email", "-e", help="Send email with the run summary")] = False,
    download_frequency: Annotated[Optional[str], typer.Option("--download-frequency", "-f", help="Download frequency")] = "hourly",
) -> None:
    parent_config = ctx.obj or {}

    if run_summary_path is None:
        run_summary_path = Path.cwd() / f"run_summaries/{download_frequency}/imd_{datetime.now().strftime('%Y_%m_%d')}.csv"

    run_summary_path.parent.mkdir(parents=True, exist_ok=True)

    # Read the YAML file with params
    params = get_params(yaml_path)
    shared_params = params["shared_params"]
        # check if required shared_params are present
    required_shared_params = ["s3_bucket", "email_recipients"]
    for param in required_shared_params:
        if param not in shared_params:
            message = f"Missing required parameter: {param}"
            logger.error(message)
            raise ValueError(message)
    required_imd_params = ["url", "ds_id", "ds_name", "extension"]
    for datacode in params.keys():
        if datacode.startswith("district_rainfall_"):
            for param in required_imd_params:
                if param not in params[datacode]:
                    message = f"Missing required parameter: {param} for {datacode}"
                    logger.error(message)
                    raise ValueError(message)

    # Create a list to store the logs of the run summary
    log_lines = []

    try:
        while True:
            # Define timecode to be the 0th minute of the current hour
            if download_frequency == "hourly":
                timecode = datetime.strptime(datetime.now().strftime("%Y-%m-%dT%H:00:00"), "%Y-%m-%dT%H:%M:%S")
                version = "v1_hourly"
            elif download_frequency == "15mins":
                current_minute = datetime.now().minute
                version = "v2_15min_firehose"
                if 0 <= current_minute < 15:
                    timecode = datetime.strptime(datetime.now().strftime("%Y-%m-%dT%H:00:00"), "%Y-%m-%dT%H:%M:%S")
                elif 15 <= current_minute < 30:
                    timecode = datetime.strptime(datetime.now().strftime("%Y-%m-%dT%H:15:00"), "%Y-%m-%dT%H:%M:%S")
                elif 30 <= current_minute < 45:
                    timecode = datetime.strptime(datetime.now().strftime("%Y-%m-%dT%H:30:00"), "%Y-%m-%dT%H:%M:%S")
                else:
                    timecode = datetime.strptime(datetime.now().strftime("%Y-%m-%dT%H:45:00"), "%Y-%m-%dT%H:%M:%S")
            else:
                if params["shared_params"]["raise_error"]:
                    raise ValueError("Invalid download frequency")
                else:
                    logger.error("Invalid download frequency, using hourly")
                    version = "v1_hourly"
                    timecode = datetime.strptime(datetime.now().strftime("%Y-%m-%dT%H:00:00"), "%Y-%m-%dT%H:%M:%S")
            logger.debug(f"Timecode: {timecode}")
            if directory is None:
                logger.info("Using a Named Temporary Directory to store the data")
                directory = tempfile.TemporaryDirectory().name
            else:
                logger.info(f"Using the directory {directory} to store the data")

            logger.debug(f"Request timecode: {timecode}")
            date = timecode.strftime("%Y_%m_%d")
            time = timecode.strftime("%H_%M_%S")

            # Iterate over both datacodes
            datacodes = [datacode for datacode in params.keys() if datacode.startswith("district_rainfall_")]
            list_of_status_codes = {}
            for datacode in datacodes:
                # Counting the number of files downloaded and uploaded
                no_downloads = 0
                no_uploads = 0

                imd_params = params[datacode]
                logger.debug(f"Requesting Data Code: {datacode}")
                url = imd_params["url"]
                logger.debug(f"Request URL: {url}")

                folder = Path(directory) / f"{datacode.removeprefix('imd_')}"
                filepath = folder / f"{time}.csv"
                filepath.parent.mkdir(parents=True, exist_ok=True)
                try:
                    logger.info(f"Downloading {datacode} to {filepath}")
                    session = retry_session(retries=6, backoff_factor=5)
                    response = session.get(url, timeout=20)
                    logger.debug(f"Response status code: {response.status_code}")
                    list_of_status_codes[datacode] = response.status_code
                    # Check if the response status code is 200 (OK)
                    if response.status_code == 200:
                        logger.info(f"Data downloaded successfully from {url}")
                        try:
                            raw_df = pd.read_json(io.StringIO(response.text))
                            # df = clean_imd_data(raw_df, live=True, datacode=datacode)
                            # logger.info("Data cleaned successfully")
                            # df.to_csv(filepath, index=False)
                            raw_df.to_csv(filepath, index=False)
                            logger.debug(f"Data saved to {filepath}")
                            no_downloads += 1
                        except ValueError as e:
                            logger.warning(f"Failed to parse JSON for {datacode}: {e}")
                            with open(filepath, "w", encoding="utf-8") as f:
                                f.write(response.text)
                            logger.debug(f"Raw data saved to {filepath} instead")
                    else:
                        message = f"Downloading {datacode} failed due to status code {response.status_code}"
                        logger.error(message)

                except Exception as e:
                    logger.error(f"Error downloading {datacode} for {timecode}: {e}")
                # upload the data to S3
                s3_prefix = f"{imd_params['ds_id']}-{imd_params['ds_name']}/{imd_params[version]['folder_name']}/{date}"

                if no_downloads == 0 and list_of_status_codes[datacode] not in [400, 401, 404]:
                    logger.info(f"no file to upload to {s3_prefix}")
                    critical_report = Report(
                        job_name=f"IMD {download_frequency.capitalize()} Job: {time}", email_recipients=shared_params["email_recipients"]
                    )
                    message = f"Downloading {datacode} failed: {list_of_status_codes[datacode]}; hence no files to upload to S3"
                    critical_report.add_a_status_report("IMD Data Retrieval", Status.CRITICAL, message)
                    critical_report.add_attachment(f"logs/{parent_config.get('log_file')}")
                    critical_report.send_email()
                elif no_downloads == 0 and list_of_status_codes[datacode] in [400, 401, 404]:
                    logger.info(f"no file to upload to {s3_prefix}")
                    message = f"Downloading {datacode} failed: {list_of_status_codes[datacode]}; hence no files to upload to S3"
                    logger.error(message)
                else:
                    failed_uploads = upload_data_to_s3(
                        upload_dir=folder,
                        Bucket=shared_params["s3_bucket"],
                        Prefix=s3_prefix,
                        extension=imd_params["extension"],
                        raise_error=imd_params["raise_error"],
                    )
                    if failed_uploads == 0:
                        logger.info(f"Uploaded data to {s3_prefix}")
                        no_uploads += 1
                    else:
                        logger.error(f"Failed to upload data to {s3_prefix}")
                log_lines.append(f"{timecode},{datacode.removeprefix('imd_')},{no_downloads},{no_uploads}")
            break
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        if not run_summary_path.exists():
            with open(run_summary_path, "w") as f:
                f.write("timecode,datacode,download,upload")
        if len(log_lines) > 0:
            with open(run_summary_path, "a") as f:
                f.write("\n")
                f.write("\n".join(log_lines))
        else:
            logger.error("No data was downloaded or uploaded")

        if (timecode.hour == 23 and timecode.minute == 0) or email:
            logger.info("Timecode: %s", timecode)
            logger.info("Sending email...")
            report = Report(
                job_name=f"IMD {download_frequency.capitalize()} Job Summary: {date}", email_recipients=shared_params["email_recipients"]
            )
            df = pd.read_csv(run_summary_path)

            expected_files = len(df)

            download_success = df["download"].sum()
            upload_success = df["upload"].sum()

            if download_success == 0:
                message = f"None of the {expected_files} files were downloaded"
                logger.error(message)
                report.add_a_status_report("IMD Data Download", Status.CRITICAL, message)
            elif expected_files > download_success > 0:
                message = f"Only {download_success} out of {expected_files} files were downloaded"
                logger.error(message)
                report.add_a_status_report("IMD Data Download", Status.ERROR, message)
            else:
                message = f"All {expected_files} files were downloaded"
                logger.info(message)
                report.add_a_status_report("IMD Data Download", Status.SUCCESS, message)

            if upload_success == 0:
                message = f"None of the {expected_files} files were uploaded"
                logger.error(message)
                report.add_a_status_report("IMD Data Upload", Status.CRITICAL, message)
            elif expected_files > upload_success > 0:
                if upload_success == download_success:
                    message = f"All {upload_success} files among the {download_success} downloaded files were uploaded"
                    logger.info(message)
                    report.add_a_status_report("IMD Data Upload", Status.SUCCESS, message)
                else:
                    message = f"Only {upload_success} out of {download_success} files were uploaded"
                    logger.error(message)
                    report.add_a_status_report("IMD Data Upload", Status.ERROR, message)
            else:
                message = f"All {expected_files} files were uploaded"
                logger.info(message)
                report.add_a_status_report("IMD Data Upload", Status.SUCCESS, message)

            if report.any_criticals() or report.any_errors():
                report.add_attachment(str(run_summary_path))
                report.add_attachment(f"logs/{parent_config.get('log_file')}")

            report.send_email()
            logger.info("Email sent")
