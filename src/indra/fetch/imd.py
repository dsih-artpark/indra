import io
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import pandas as pd
import typer

from indra.emails import Report, Status
from indra.io import get_params, retry_session, upload_data_to_s3

logger = logging.getLogger(__name__)
logging.captureWarnings(True)

app = typer.Typer()

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

    # Drop the WEATHER_ICON, WEATHER_MESSAGE, BACKGROUND, and BACKGROUND_URL columns
    df = df.drop(columns=["WEATHER_ICON", "WEATHER_MESSAGE", "BACKGROUND", "BACKGROUND_URL"])
    if datacode == "imd_Station_API":
        # Validate and fix the date and time columns, and use them to create a new timestamp column
        df["Date"] = pd.to_datetime(df["Date of Observation"], errors='coerce')
        df.drop(columns=["Date of Observation"], inplace=True)
        df['Time'] = df['Time'].astype(str).str.zfill(2)
        df.insert(0, 'timestamp', df.apply(
            lambda row: f"{row['Date'].strftime('%Y-%m-%d')}T{row['Time']}:00:00.00+05:30", axis=1
        ))
        # Clean the Station and Sunset columns to remove all trailing and leading \r, \n, \t, and spaces
        df["Station"] = df["Station"].str.strip("\r\n\t ")
        df["Sunset"] = df["Sunset"].str.strip("\r\n\t ")

        # Ensure that 'Sunrise', 'Sunset', 'Moonrise', 'Moonset' are in the correct format of HH:MM:SS
        df["Sunrise"] = pd.to_datetime(df["Sunrise"], errors='coerce', format='%H:%M').dt.strftime('%H:%M')
        df["Sunset"] = pd.to_datetime(df["Sunset"], errors='coerce', format='%H:%M').dt.strftime('%H:%M')
        df["Moonrise"] = pd.to_datetime(df["Moonrise"], errors='coerce', format='%H:%M').dt.strftime('%H:%M')
        df["Moonset"] = pd.to_datetime(df["Moonset"], errors='coerce', format='%H:%M').dt.strftime('%H:%M')

        mapper_dict = {
            "Station": "stationName",
            "Station Id": "stationID",
            "timestamp": "timestamp",
            'Mean Sea Level Pressure': 'meanSeaLevelPressure',
            'Wind Direction': 'windDirection',
            'Wind Speed KMPH': 'windSpeed',
            'Temperature': 'temperature',
            'Weather Code': 'weatherCode',
            'Nebulosity': 'nebulosity',
            'Humidity': 'humidity',
            'Last 24 hrs Rainfall': 'last24hrsRainfall',
            'Feel Like': 'feelLike',
            "Sunrise": "sunrise",
            "Sunset": "sunset",
            "Moonrise": "moonrise",
            "Moonset": "moonset",
        }

        numeric_cols = ['meanSeaLevelPressure', 'windSpeed', 'temperature', 'nebulosity', 'humidity', 'last24hrsRainfall', 'feelLike']



        for expected_cols in mapper_dict.keys():
            if expected_cols not in df.columns:
                logger.warning(f"Expected column {expected_cols} not found in the DataFrame")
        # Rename the columns
        df.rename(columns=mapper_dict, inplace=True)

        # Convert the numeric columns to float
        for col in numeric_cols:
            df[col] = df[col].replace('NA', None)
            df[col] = df[col].replace('', None)
            df[col] = df[col].astype(float)

        # Convert Station Name to All Caps
        df["stationName"] = df["stationName"].str.upper()
        # Drop the Date and Time columns
        df = df.drop(columns=["Date", "Time"])

    elif datacode == "imd_AWS_ARG":
        # Validate and fix the date and time columns, and use them to create a new timestamp column
        df["DATE"] = pd.to_datetime(df["DATE"], errors='coerce')
        df['TIME'] = pd.to_datetime(df['TIME'], errors='coerce', format='%H:%M:%S')
        df.rename(columns= {"ID": "stationID"}, inplace=True)

        df.insert(0, 'timestamp', df.apply(
            lambda row: f"{row['DATE'].strftime('%Y-%m-%d')}T{row['TIME'].strftime('%H:%M:%S.00+05:30')}", axis=1
        ))

        # Drop the Date and Time columns
        df = df.drop(columns=["DATE", "TIME"])


    return df

@app.callback(invoke_without_command=True)
def main(*,
    ctx: typer.Context,
    yaml_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            resolve_path=True,
            help="Path to YAML configuration file containing IMD parameters"
        )
    ],
    debug: Annotated[
        bool,
        typer.Option(
            "--debug/--no-debug",
            "-d/-D",
            help="Enable debug mode, send email without actually downloading data"
        )
    ] = False,
    directory: Annotated[
        Optional[str],
        typer.Option(
            "--directory",
            "-d",
            help="Directory to store the data"
            )
    ] = None,
    run_summary_path: Annotated[
        Optional[str],
        typer.Option(
            "--run-summary-path",
            "-r",
            help="Path to the run summary file"
        )
    ] = None,
    email: Annotated[
        Optional[bool],
        typer.Option(
            "--email",
            "-e",
            help="Send email with the run summary"
        )
    ] = False,
    ) -> None:

    parent_config = ctx.obj or {}
    # Read the YAML file with params

    if run_summary_path is None:
        run_summary_path = Path.cwd() / f"run_summary_imd_{datetime.now().strftime('%Y_%m_%d')}.csv"
    params = get_params(yaml_path)
    shared_params = params['shared_params']

    lines = []
    try:
        while True:
            # Define timecode to be the 0th minute of the current hour
            timecode = datetime.strptime(datetime.now().strftime("%Y-%m-%dT%H:00:00"),"%Y-%m-%dT%H:%M:%S")
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
            for datacode in params.keys():
                if datacode.startswith("imd_"):

                    # Counting the number of files downloaded and uploaded
                    download = 0
                    upload = 0

                    imd_params = params[datacode]
                    logger.debug(f"Requesting Data Code: {datacode}")
                    url = imd_params['url']
                    logger.debug(f"Request URL: {url}")


                    folder = Path(directory) / f"{datacode.removeprefix('imd_')}"
                    filepath = folder / f"{time}.csv"
                    filepath.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        logger.info(f"Downloading {datacode} to {filepath}")
                        session = retry_session(retries=3)
                        response = session.get(url, timeout=20)
                        logger.debug(f"Response status code: {response.status_code}")
                        # Check if the response status code is 200 (OK)
                        if response.status_code == 200:
                            logger.info(f"Data downloaded successfully from {url}")
                            df = clean_imd_data(pd.read_json(io.StringIO(response.text)), live=True, datacode=datacode)
                            logger.info("Data cleaned successfully")
                            df.to_csv(filepath, index=False)
                            logger.debug(f"Data saved to {filepath}.csv")
                            download = 1
                            pass
                        else:
                            message = f"Downloading {datacode} failed due to status code {response.status_code} "
                            logger.error(message)
                    except Exception as e:
                        logger.error(f"Error downloading {datacode}: {e}")
                    #upload the data to S3
                    s3_prefix = f"{imd_params['ds_id']}-{imd_params['ds_name']}/{imd_params['folder_name']}/{date}"
                    if download ==0:
                        logger.info(f"no file to upload to {s3_prefix}")
                        upload = 0
                        critical_report = Report(
                            job_name="IMD Daily Job",
                            email_recipients=shared_params['email_recipients']
                        )
                        message = f"Downloading {datacode} failed and hence no files to upload to S3"
                        critical_report.add_a_status_report('IMD Data Retrieval', Status.CRITICAL, message)
                        critical_report.add_attachment(f"logs/{parent_config.get('log_file')}")
                        critical_report.send_email()
                    else:
                        failed_uploads = upload_data_to_s3(upload_dir=folder, Bucket=shared_params['s3_bucket'],
                                        Prefix=s3_prefix, extension=imd_params['extension'], raise_error=imd_params['raise_error'])
                        if failed_uploads == 0:
                            logger.info(f"Uploaded data to {s3_prefix}")
                            upload = 1
                        else:
                            logger.error(f"Failed to upload data to {s3_prefix}")
                    lines.append(f"{timecode},{datacode.removeprefix('imd_')},{download},{upload}")
            break
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        if not run_summary_path.exists():
            with open(run_summary_path, "w") as f:
                f.write("timecode,datacode,download,upload")
        if len(lines) > 0:
            with open(run_summary_path, "a") as f:
                f.write("\n")
                f.write("\n".join(lines))
        else:
            logger.error("No data was downloaded or uploaded")

        if timecode.hour == 23 or email:
            logger.info("Timecode: %s", timecode)
            logger.info("Sending email...")
            report = Report(
                job_name="IMD Daily Job",
                email_recipients=shared_params['email_recipients']
            )
            df = pd.read_csv(run_summary_path)

            expected_files = len(df)

            download_success = df['download'].sum()
            upload_success = df['upload'].sum()

            if download_success == 0:
                message = f"None of the {expected_files} files were downloaded"
                logger.error(message)
                report.add_a_status_report('IMD Data Download', Status.CRITICAL, message)
            elif expected_files > download_success > 0:
                message = f"Only {download_success} out of {expected_files} files were downloaded"
                logger.error(message)
                report.add_a_status_report('IMD Data Download', Status.ERROR, message)
            else:
                message = f"All {expected_files} files were downloaded"
                logger.info(message)
                report.add_a_status_report('IMD Data Download', Status.SUCCESS, message)

            if upload_success == 0:
                message = f"None of the {expected_files} files were uploaded"
                logger.error(message)
                report.add_a_status_report('IMD Data Upload', Status.CRITICAL, message)
            elif expected_files > upload_success > 0:
                if upload_success == download_success:
                    message = f"All {upload_success} files among the {download_success} downloaded files were uploaded"
                    logger.info(message)
                    report.add_a_status_report('IMD Data Upload', Status.SUCCESS, message)
                else:
                    message = f"Only {upload_success} out of {download_success} files were uploaded"
                    logger.error(message)
                    report.add_a_status_report('IMD Data Upload', Status.ERROR, message)
            else:
                message = f"All {expected_files} files were uploaded"
                logger.info(message)
                report.add_a_status_report('IMD Data Upload', Status.SUCCESS, message)

            if report.any_criticals() or report.any_errors():
                report.add_attachment(str(run_summary_path))
                report.add_attachment(f"logs/{parent_config.get('log_file')}")

            report.send_email()
