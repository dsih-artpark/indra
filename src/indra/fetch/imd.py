import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import pandas as pd
import typer
from requests.exceptions import HTTPError

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

def retrieve_live_data_from_imd(datacode: str, timecode: str, params: dict):
    """Retrieve live data from the Indian Meteorological Department (IMD).

    This function fetches live data from the IMD using the specified URL and data code.

    :param str url:
        The URL to download the data from.

    :param str datacode:
        The data code for the specific dataset.

    :return:
        The path to the downloaded data.

    :raises HTTPError:
        If there is an issue with the HTTP request, and the status code is not 200.

    **Example:**

    This function is used to retrieve live data from the IMD. You need to find the correct URL & datacode for the data you want to retrieve.
    The function will only work if your IP address is whitelisted by the IMD, otherwise you will get a 403 error.
    For example, to retrieve live data for the IMD station data, you can use the following URL and datacode:
    URL: https://mausam.imd.gov.in/api/current_wx_api.php
    datacode: C_WX

    ```python
    retrieve_live_data_from_imd(
        url="https://mausam.imd.gov.in/api/current_wx_api.php",
        datacode="C_WX"
    )
    ```
    """

    shared_params = params['shared_params']
    imd_params = params[datacode]
    logger.debug(f"Requesting Data Code: {datacode}")
    url = imd_params['url']
    logger.debug(f"Request URL: {url}")

    logger.debug(f"Request timecode: {timecode}")
    logger.debug(f"Current Date and Time: {datetime.now()}")
    logger.info(f"Initating Download of {datacode} Data")
    session = retry_session(retries=3)
    response = session.get(url, timeout=10)  # Timeout after 10 seconds
    logger.debug(f"Response status code: {response.status_code}")

    shared_params = params['shared_params']
    imd_params = params[datacode] # Params for the specific IMD dataset

    # Check if the response status code is 200 (OK)
    if response.status_code == 200:
        logger.info(f"Data downloaded successfully from {url}")
        df = clean_imd_data(pd.read_json(io.StringIO(response.text)), live=True, datacode=datacode)
        logger.info("Data cleaned successfully")

        # Save the data to a CSV file
        timecode = datetime.strptime(timecode, "%Y-%m-%dT%H:%M:%S")
        date = timecode.strftime("%Y_%m_%d")
        time = timecode.strftime("%H_%M_%S")

        # Setting S3 Prefix
        s3_prefix = f"{imd_params['ds_id']}-{imd_params['ds_name']}/{imd_params['folder_name']}/{date}"
        output_dir = Path(shared_params['local_data_dir']).expanduser() / Path(shared_params['s3_bucket']) / Path(s3_prefix)
        output_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_dir / f"{time}.csv", index=False)
        logger.debug(f"Data saved to {output_dir / f'{time}.csv'}")

        # Upload the data to S3
        upload_data_to_s3(upload_dir=output_dir, Bucket=shared_params['s3_bucket'], Prefix=s3_prefix, extension=imd_params['extension'])
        logger.debug(f"Data uploaded to {s3_prefix}")
    else:
        logger.error(f"Failed to download data from {url}. HTTP Status code: {response.status_code}")
        raise HTTPError(f"Failed to download data from {url}. HTTP Status code: {response.status_code}")

@app.callback(invoke_without_command=True)
def main(
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
    timecode: Annotated[
        Optional[str],
        typer.Option(
            "--timecode",
            "-t",
            help="Timecode to retrieve data for"
        )
    ] = None
) -> None:
    params = get_params(yaml_path)
    if timecode is None:
        timecode = datetime.now().strftime("%Y-%m-%dT%H:00:00")
    for datacode in params.keys():
        if datacode.startswith("imd_"):
            retrieve_live_data_from_imd(datacode=datacode, timecode=timecode, params=params)
