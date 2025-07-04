import json
import logging
import os
import tempfile
from datetime import datetime, timedelta
from ftplib import FTP
from pathlib import Path
from typing import Annotated, Optional

import typer
from dotenv import load_dotenv

from indra.io import get_params, upload_data_to_s3

logger = logging.getLogger(__name__)
logging.captureWarnings(True)

app = typer.Typer()

load_dotenv()

ksndmc_weather = json.loads(os.getenv("ksndmc_weather", "{}"))
ksndmc_rainfall = json.loads(os.getenv("ksndmc_rainfall", "{}"))
# ftp_username = 'Artpark'
# ftp_password = 'ArtK$n@2025'
# server.connect('27.34.245.74',port=8057,timeout=300) # FTP Server IP Address and Port
# download_path = "/Users/aishwaryar/Desktop/KSNDMC/2025"  # ← Change this to your desired path

def ksndmc_fetch(ftp_server_IP, ftp_server_port, ftp_username, ftp_password, download_path: str):
    """Fetches the latest weather data from KSNDMC FTP server."""
    server = FTP()
    logger.info("Connecting to KSNDMC FTP server...")
    # Connect to the FTP server
    try:
        server.connect(ksndmc_weather['ftp_server_IP'], int(ksndmc_weather['ftp_server_port']), timeout=600) # FTP Server IP & Port
        server.login(ksndmc_weather['ftp_username'], ksndmc_weather['ftp_password']) # FTP Server Username and Password
        logger.info(f"Connected to KSNDMC FTP server as {ksndmc_weather['ftp_username']}")
        server.dir() # List all directories in the FTP Server
    except Exception as e:
        logger.error(f"Failed to connect or login to the FTP server: {e}")
    try:
       # Because the upload involves data from the previous day, the date and year are derived based on that timestamp.
       # For example, if today is 2025-04-13, the script will access the file for 2025-04-12.
       yesterday = datetime.now() - timedelta(days=1)  # Get yesterday's date
       month_as_of_yest = yesterday.strftime('%B').upper()  # Get the month as of yesterday in uppercase
       year_as_of_yest = yesterday.strftime('%Y')  # Get the year as of yesterday (handles edge cases like end of year or month)
       if year_as_of_yest in server.nlst():
           # Extract only folder names
           entries = server.nlst(f'/{year_as_of_yest}')
           folder_names = [os.path.basename(entry) for entry in entries]
           if month_as_of_yest in folder_names:
                logger.info(f"Folders for the year {year_as_of_yest} and month {month_as_of_yest} exist on the server.")
                server.cwd(f'/{year_as_of_yest}/{month_as_of_yest}/') # Change Directory to the current month folder
                logger.info(f"Files in {month_as_of_yest} folder:")
                server.dir() # List all files in the current working directory
           else:
                logger.info(f"Folders for the year {year_as_of_yest} and month {month_as_of_yest} do not exist on the server.")

    except Exception as e:
        logger.error(f"Failed to change directory or list files: {e}")
        server.quit()  # Ensure the server connection is closed
        return

    logger.info(f"Current working directory: {server.pwd()}")  # Print the current working directory
    # Set your custom download path and ensure  the folder exists
    os.makedirs(download_path, exist_ok=True)
    logger.info(f"Download path set to: {download_path}")
    files=[]
    server.retrlines('LIST', files.append) # List all files in the current working directory
    if files:
        logger.info(f"Last file in the dir:{files[-1]}") # Print the last file in the list
        # Split filename, extension and rename downloaded files.
        filename, extension = os.path.splitext(files[-1].split()[-1]) #"WEATHERDATA_60MIN_13042025.csv" -> ("WEATHERDATA_60MIN_13042025", ".csv")
        date_str = filename.split('_')[-1].split('.')[0] # Extract the date from the file name
        # Parse the string into a datetime object
        formatted_date = datetime.strptime(date_str, '%d%m%Y').strftime('%d-%b-%Y').lower() # Str to date to str; Format it as: '13-apr-2025' not '13-Apr-2025'.
        # Construct the new filename with the formatted date
        new_filename = f"Weather_{formatted_date}{extension}" #Here, extension is ".csv"
        new_filepath = os.path.join(download_path, new_filename)
        # Step 1: Download to the specified path
        with open(new_filepath, 'wb') as file:
            server.retrbinary(f"RETR {filename}{extension}", file.write)
        logger.info(f"Downloaded {new_filename} successfully to {download_path}!")
    else:
        logger.error("No files found in the current directory on the FTP server.")

    server.quit()

@app.callback(invoke_without_command=True)
def main(
    *,
    ctx: typer.Context,
    yaml_path: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, resolve_path=True, help="Path to YAML configuration file containing IMD parameters"),
    ],
    directory: Annotated[Optional[str], typer.Option("--directory", "-d", help="Directory to store the data")] = None,
) -> None:

    if directory is None:
        logger.info("Using a Named Temporary Directory to store the data")
        temp_dir = tempfile.TemporaryDirectory()
        directory = temp_dir.name
        print(f"Temporary directory created at: {directory}")
    else:
        logger.info(f"Using the directory {directory} to store the data")

    params = get_params(yaml_path)
    shared_params = params["shared_params"]
    # Download the data for both max and min temperature configurations

    os.makedirs(directory, exist_ok=True)

    # Fetch KSNDMC server config from .env
    ftp_server_IP = ksndmc_weather['ftp_server_IP']
    ftp_server_port = int(ksndmc_weather['ftp_server_port'])
    ftp_username = ksndmc_weather['ftp_username']
    ftp_password = ksndmc_weather['ftp_password']
    # Fetch YAML config for KSNDMC weather data
    ksndmc_params = params['ksndmc_weather']
    download_path = os.path.join(directory, f"{ksndmc_params['ds_name']}/{ksndmc_params['folder_name']}")
    os.makedirs(download_path, exist_ok=True)
    try:
        ksndmc_fetch(ftp_server_IP=ftp_server_IP, ftp_server_port=ftp_server_port, ftp_username=ftp_username,
                     ftp_password=ftp_password, download_path=download_path)
        logger.info(f"Fetched KSNDMC data successfully to {download_path}")
    except Exception as e:
        logger.error(f"Failed to fetch KSNDMC data: {e}")

    #Upload the data to S3
    s3_prefix = f"{ksndmc_params['ds_id']}-{ksndmc_params['ds_name']}/{ksndmc_params['folder_name']}"
    failed_uploads = upload_data_to_s3(
    upload_dir=download_path,
    Bucket=shared_params["s3_bucket"],
    Prefix=s3_prefix,
    extension=ksndmc_params["extension"],
    raise_error=ksndmc_params["raise_error"],)

    if failed_uploads == 0:
        logger.info(f"Uploaded data to {s3_prefix}")
    else:
        logger.error(f"Failed to upload data to {s3_prefix}")
