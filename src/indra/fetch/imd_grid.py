import logging
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Optional

import typer
from joblib import Parallel, delayed
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from indra.io import get_params, upload_data_to_s3

logger = logging.getLogger(__name__)
logging.captureWarnings(True)

app = typer.Typer()


def download_gridded_data(url, filename, element_clickID, css_selector_class, date, download_path,
                             page_timeout=100000, element_timeout=100000, download_timeout=100000):
    """Automates the download of temperature data for a specific date using Playwright."""
    try:
        with sync_playwright() as p:
            # Launch the browser in headless mode
            browser = p.webkit.launch(headless=True)

            # Create a new browser context that allows downloads
            context = browser.new_context(accept_downloads=True)

            # Open a new page within the context
            page = context.new_page()

            # Set page loading timeout (default: 30 seconds)
            page.set_default_navigation_timeout(page_timeout)

            # Navigate to the URL and wait for the page to be fully loaded with no active network connections
            try:
                page.goto(url, wait_until="networkidle", timeout=page_timeout)  # Wait until the network is idle
            except PlaywrightTimeoutError:
                logger.error(f"Timeout while loading page for {date} ({element_clickID})")
                return

            # Wait for the date field to be available and fill the date
            try:
                page.fill(f"#{element_clickID}", date, timeout=element_timeout)  # Timeout for filling the field
            except PlaywrightTimeoutError:
                logger.error(f"Timeout while filling date for {date} ({element_clickID})")
                return

            # Start waiting for the download
            try:
                with page.expect_download(timeout=download_timeout) as download_info:  # Timeout for download initiation
                    # Perform the action that initiates the download (click the download button)
                    page.click(css_selector_class, timeout=element_timeout)  # Timeout for clicking the button
            except PlaywrightTimeoutError:
                logger.error(f"Timeout while waiting for download to start for {date} ({element_clickID})")
                return
            # Get the download object
            download = download_info.value

            # Ensure the download folder exists
            os.makedirs(download_path, exist_ok=True)

            # Save the downloaded file to the specified location
            file_path = os.path.join(download_path, filename)
            download.save_as(file_path)  # Correct usage here
            logger.info(f"Downloaded file saved to {file_path}")
            logger.info(f"Downloaded data for {date} ({element_clickID}) and saved to {file_path}")

            # Check the file size to ensure it's not 0 bytes
            if os.path.getsize(file_path) == 0:
                logger.warning(f"Downloaded file for {date} ({element_clickID}) has 0 bytes. Deleting file...")
                os.remove(file_path)  # Delete the empty file
            else:
                logger.info(f"Download complete for {date} ({element_clickID}), file size: {os.path.getsize(file_path)} bytes")

            # Close the browser after completing the download
            browser.close()

    except Exception as e:
        logger.error(f"Error downloading data for {date} ({element_clickID}): {e}")

def download_data_for_dates(config, url, filename):
    """Download data for each date and configuration provided in the config dictionary."""
    logger.info(f"Starting download for {filename} from {url} for dates: {config['dates']}")
    Parallel(n_jobs=-1)(  # -1 means using all available CPU cores
        delayed(download_gridded_data)(url, filename, config['element_clickID'],
        config['css_selector_class'], date, config['download_path'])
        for date in config['dates']
    )


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
                directory = tempfile.TemporaryDirectory().name
                print(f"Temporary directory created at: {directory}")
    else:
                logger.info(f"Using the directory {directory} to store the data")

    params = get_params(yaml_path)
    shared_params = params["shared_params"]
    download_config = {
        "max": {
            "element_clickID": "max",  # Element ID for max temperature
            "css_selector_class": ".btn.btn-warning",  # CSS selector for max temperature button
            "dates": [(datetime.now()-timedelta(days=1)).strftime('%d%m%Y')],
            "download_path": os.path.join(directory, "maxtemp"),  # Replace with path to directory / max_temp
            "page_timeout": 100000,  # in milliseconds
            "element_timeout": 100000,  # in milliseconds
            "download_timeout": 100000  # in milliseconds
        },
        "min": {
            "element_clickID": "min",  # Element ID for min temperature
            "css_selector_class": ".btn.btn-info",  # CSS selector for min temperature button
            "dates": [(datetime.now()-timedelta(days=1)).strftime('%d%m%Y')],
            "download_path": os.path.join(directory, "mintemp"),  # Replace with your desired download directory
            "page_timeout": 100000,  # in milliseconds
            "element_timeout": 100000,  # in milliseconds
            "download_timeout": 100000  # in milliseconds
        },
        "rain": {
            "element_clickID": "rain",  # Element ID for rain data
            "css_selector_class": ".btn.btn-success",  # CSS selector for rain data button
            "dates": [(datetime.now()-timedelta(days=1)).strftime('%d%m%Y')],
            "download_path": os.path.join(directory, "rainfall"),  # Replace with the desired path for rain data downloads
            "page_timeout": 100000,  # in milliseconds
            "element_timeout": 100000,  # in milliseconds
            "download_timeout": 100000  # in milliseconds
        }
    }
    # Download the data for both max and min temperature configurations
    for temp_type, config in download_config.items():
        imd_grid_params = params[f'imd_gridded_{temp_type}']
        url = imd_grid_params["url"]
        logger.debug(f"Request URL: {url}")
        ddmmyyyy = config['dates'][0]
        now_str = ddmmyyyy[4:] + ddmmyyyy[2:4] + ddmmyyyy[0:2] # Use the first date from the config for the filename
        if temp_type == "max":
              filename =  f"2t_max_0p50_{now_str}.grd"
        elif temp_type == "min":
              filename =  f"2t_min_0p50_{now_str}.grd"
        elif temp_type == "rain":
              filename =  f"rain_0p50_{now_str}.grd"
        logger.info(f"attempting download {temp_type} data for {ddmmyyyy} to {filename}")
        try:
            download_data_for_dates(config, url, filename)
            logger.info(f"Downloaded {temp_type} data for {ddmmyyyy} to {filename}")
        except Exception as e:
            logger.error(f"Failed to download {temp_type} data for {ddmmyyyy}: {e}")
        # upload the data to S3
        s3_prefix = f"{imd_grid_params['ds_id']}-{imd_grid_params['ds_name']}/{imd_grid_params['folder_name']}"

        failed_uploads = upload_data_to_s3(
        upload_dir=config['download_path'],
        Bucket=shared_params["s3_bucket"],
        Prefix=s3_prefix,
        extension=imd_grid_params["extension"],
        raise_error=imd_grid_params["raise_error"],
    )
    if failed_uploads == 0:
        logger.info(f"Uploaded data to {s3_prefix}")
    else:
        logger.error(f"Failed to upload data to {s3_prefix}")
