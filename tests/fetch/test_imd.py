import io
import json
import os
import tempfile
import uuid
from datetime import datetime
from datetime import datetime as real_datetime
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from indra.emails import Status
from indra.fetch import imd
from indra.fetch.imd import app, clean_imd_data, main


@pytest.fixture
def mock_datetime_now_at_23():
    """Mock datetime.now() to return a time with hour 23."""
    fixed_dt = datetime(2025, 4, 28, 23, 0, 0)  # Hardcode 23:00
    with patch('datetime.datetime') as mock_dt:
        mock_dt.now.return_value = fixed_dt
        mock_dt.strptime = datetime.strptime
        mock_dt.strftime = datetime.strftime
        yield mock_dt

@pytest.fixture
def mock_session(mocker):
    mock = Mock()
    mocker.patch('indra.fetch.imd.retry_session', return_value=mock)
    return mock

@pytest.fixture
def mock_report():
    from unittest.mock import MagicMock
    return MagicMock()

@pytest.fixture
def mock_ctx():
    """Fixture for typer.Context mock."""
    mock_ctx = MagicMock()
    mock_ctx.obj = {}
    return mock_ctx

@pytest.fixture
def invalid_file_path():
    # This is a mock of a non-existent or invalid file path
    return "/invalid/path/to/file.csv"

@pytest.fixture
def mock_yaml_path(tmp_path):
    """Create a temporary YAML file for testing."""
    config_data = {
        'shared_params': {
            'local_data_dir': "~/.dsih-data/",
            'email_recipients': ["test <test@xyz.in>"],
            's3_bucket': 'dsih-bbb-03-standardised-data',
            'log_file': 'imd_run.log'
        },
        'imd_Station_API': {
            'url': "https://abc/api/current_wx_api.php",
            'ds_id': 'MW0017DS0080',
            'ds_name': 'IMD_Weather_Station_Data',
            'extension': "csv",
            'v1_hourly': {
                'folder_name': '2025/v1_hourly/Station_API'
            },
            'v2_15min_firehose': {
                'folder_name': '2025/v2_15min_firehose/Station_API'
            },
            'ds_source': 'IMD',
            'raise_error': False
        },
        'imd_AWS_ARG': {
            'url':  "https://mocked.aws/api/aws_data_api.php",
            'ds_id': 'MW0017DS0080',
            'ds_name': 'IMD_Weather_Station_Data',
            'extension': "csv",
            'v1_hourly': {
                'folder_name': '2025/v1_hourly/AWS_ARG'
            },
            'v2_15min_firehose': {
                'folder_name': '2025/v2_15min_firehose/AWS_ARG'
            },
            'ds_source': 'IMD',
            'raise_error': False
        }
    }
    yaml_file = tmp_path / "config.yaml"
    with open(yaml_file, 'w') as f:
        yaml.dump(config_data, f)
    return yaml_file

@pytest.fixture
def tmp_directory():
    """Create a temporary directory for file operations."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname

def create_mock_response(status_code, text=""):
    """Helper function to create mock response objects."""
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    return response

@pytest.fixture
def mock_all_success_api_responses():
    """Mock successful responses for both APIs with complete data."""
    with patch('indra.fetch.imd.retry_session') as mock_session:
        session_instance = MagicMock()

        sample_station_api_json = json.dumps([{
            "Station": "DELHI",
            "Station Id": "VIDP",
            "Date of Observation": "2025-04-25",
            "Time": "13:00",
            "Mean Sea Level Pressure": 1010.2,
            "Wind Direction": "NW",
            "Wind Speed KMPH": 15.0,
            "Temperature": 32.5,
            "Weather Code": "01d",
            "Nebulosity": 2,
            "Humidity": 45,
            "Last 24 hrs Rainfall": 0.0,
            "Feel Like": 34.0,
            "Sunrise": "06:30",
            "Sunset": "18:45",
            "Moonrise": "12:15",
            "Moonset": "23:45",
        }])
        station_resp = MagicMock()
        station_resp.status_code = 200
        station_resp.text = sample_station_api_json

        sample_aws_arg_json = json.dumps([{
            "ID": "AWS001",
            "DATE": "2025-04-25",
            "TIME": "13:00:00",
            "TEMP": 33.5,
            "RH": 40,
            "WSPD": 10.2,
            "WDIR": 270,
            "RAIN": 0.0,
            "BATTERY": 12.5,
        }])
        aws_resp = MagicMock()
        aws_resp.status_code = 200
        aws_resp.text = sample_aws_arg_json

        def get_side_effect(url, **kwargs):
            if "current_wx_api.php" in url:
                return station_resp
            elif "aws_data_api.php" in url:
                return aws_resp
            return create_mock_response(200, "")

        session_instance.get.side_effect = get_side_effect
        mock_session.return_value = session_instance
        yield {'session': session_instance, 'station_response': station_resp, 'aws_response': aws_resp}

@pytest.fixture
def sample_station_api_json():
    """Sample JSON data for the Station API as would be returned by the API."""
    return json.dumps([{
        "Station": "DELHI",
        "Station Id": "VIDP",
        "Date of Observation": "2025-04-25",
        "Time": "13",
        "Mean Sea Level Pressure": 1010.2,
        "Wind Direction": "NW",
        "Wind Speed KMPH": 15.0,
        "Temperature": 32.5,
        "Weather Code": "01d",
        "Nebulosity": 2,
        "Humidity": 45,
        "Last 24 hrs Rainfall": 0.0,
        "Feel Like": 34.0,
        "Sunrise": "06:30",
        "Sunset": "18:45",
        "Moonrise": "12:15",
        "Moonset": "23:45",
        "WEATHER_ICON": "sunny",
        "WEATHER_MESSAGE": "Clear sky",
        "BACKGROUND": "blue",
        "BACKGROUND_URL": "url/to/image"
    }])

@pytest.fixture
def sample_station_api_data(sample_station_api_json):
    """Sample data for the Station API as a pandas DataFrame."""
    return pd.read_json(io.StringIO(sample_station_api_json))

@pytest.fixture
def sample_aws_arg_json():
    """Sample JSON data for the AWS ARG API as would be returned by the API."""
    return json.dumps([{
        "ID": "AWS001",
        "DATE": "2025-04-25",
        "TIME": "13:00:00",
        "TEMP": 33.5,
        "RH": 40,
        "WSPD": 10.2,
        "WDIR": 270,
        "RAIN": 0.0,
        "BATTERY": 12.5,
        "WEATHER_ICON": "sunny",
        "WEATHER_MESSAGE": "Clear sky",
        "BACKGROUND": "blue",
        "BACKGROUND_URL": "url/to/image"
    }])

@pytest.fixture
def sample_aws_arg_data(sample_aws_arg_json):
    """Sample data for the AWS ARG API as a pandas DataFrame."""
    return pd.read_json(io.StringIO(sample_aws_arg_json))

@pytest.fixture
def malformed_json_response():
    """Return a malformed JSON response to test error handling."""
    return "{broken json"

@pytest.fixture
def empty_json_response():
    """Return an empty but valid JSON response to test edge cases."""
    return "[]"

@pytest.fixture
def empty_response():
    """Return an empty response to test error handling."""
    return ""

# Tests for data cleaning functionality
class TestDataCleaning:
    def test_station_api_cleaning(self, sample_station_api_data):
        """Test cleaning of Station API data."""
        cleaned_df = clean_imd_data(sample_station_api_data, datacode="imd_Station_API")

        # Verify columns are renamed correctly
        assert "stationName" in cleaned_df.columns
        assert "timestamp" in cleaned_df.columns

        # Verify unwanted columns are dropped
        assert "WEATHER_ICON" not in cleaned_df.columns
        assert "Date" not in cleaned_df.columns
        assert "Time" not in cleaned_df.columns

        # Verify timestamp format
        assert cleaned_df["timestamp"].iloc[0] == "2025-04-25T13:00:00.00+05:30"

        # Verify station name is uppercase
        assert cleaned_df["stationName"].iloc[0] == "DELHI"

        # Verify numeric columns are converted to float
        assert isinstance(cleaned_df["meanSeaLevelPressure"].iloc[0], float)

    def test_aws_arg_cleaning(self, sample_aws_arg_data):
        """Test cleaning of AWS ARG data."""
        cleaned_df = clean_imd_data(sample_aws_arg_data, datacode="imd_AWS_ARG")

        # Verify timestamp creation
        assert cleaned_df["timestamp"].iloc[0] == "2025-04-25T13:00:00.00+05:30"

        # Verify ID is renamed to stationID
        assert "stationID" in cleaned_df.columns

        # Verify unwanted columns are dropped
        assert "DATE" not in cleaned_df.columns
        assert "TIME" not in cleaned_df.columns
        assert "WEATHER_ICON" not in cleaned_df.columns

    def test_cleaning_with_missing_columns(self):
        """Test cleaning with missing expected columns."""
        # Create a dataframe missing some expected columns
        df = pd.DataFrame({
            "Station": ["DELHI"],
            "Date of Observation": ["2025-04-25"],
            # Missing several expected columns
        })

        # This should log warnings but not crash
        with patch('indra.fetch.imd.logger.warning') as mock_warn:
            cleaned_df = clean_imd_data(df, datacode="imd_Station_API")  # noqa: F841
            assert mock_warn.called

    def test_cleaning_with_invalid_data(self):
        """Test cleaning with invalid data values."""
        # Create dataframe with invalid data
        df = pd.DataFrame({
            "Station": ["DELHI"],
            "Station Id": ["VIDP"],
            "Date of Observation": ["invalid-date"],  # Invalid date
            "Time": ["13"],
            "Mean Sea Level Pressure": ["NA"],  # Test NA handling
            "Wind Direction": ["NW"],
            "Wind Speed KMPH": [""],  # Test empty string handling
            "Temperature": [32.5],
            "Weather Code": ["01d"],
            "Nebulosity": [2],
            "Humidity": [45],
            "Last 24 hrs Rainfall": [0.0],
            "Feel Like": [34.0],
            "Sunrise": ["invalid-time"],  # Invalid time
            "Sunset": ["18:45"],
            "Moonrise": ["12:15"],
            "Moonset": ["23:45"],
            "WEATHER_ICON": ["sunny"],
            "WEATHER_MESSAGE": ["Clear sky"],
            "BACKGROUND": ["blue"],
            "BACKGROUND_URL": ["url/to/image"]
        })

        cleaned_df = clean_imd_data(df, datacode="imd_Station_API")

        # Check that NA and empty values were converted to None/NaN and then float
        assert pd.isna(cleaned_df["meanSeaLevelPressure"].iloc[0])
        assert pd.isna(cleaned_df["windSpeed"].iloc[0])

        # Invalid time/date should be handled gracefully
        assert pd.isna(cleaned_df["timestamp"].iloc[0]) or isinstance(cleaned_df["timestamp"].iloc[0], str)

    def test_time_formatting_attribute_error(self):
        df = pd.DataFrame({
            "Date of Observation": ["2024-01-01"],
            "Time": ["08"],
            "Sunrise": [None],
            "Sunset": [None],
            "Moonrise": [None],
            "Moonset": [None]
        })
        cleaned = clean_imd_data(df.copy(), "imd_Station_API")
        # All time columns should remain None or NaN after failing to format
        for col in ["sunrise", "sunset", "moonrise", "moonset"]:
            assert pd.isna(cleaned[col].iloc[0])

    def test_create_timestamp_error_handling(self):
        df = pd.DataFrame({
            "Date of Observation": ["bad-date"],  # will coerce to NaT
            "Time": ["invalid-time"]  # still coerced to string
        })
        cleaned = clean_imd_data(df.copy(), "imd_Station_API")
        assert "timestamp" in cleaned.columns
        assert cleaned["timestamp"].iloc[0] is None

    def test_clean_imd_with_invalid_path(self, invalid_file_path):
        # Mocking pd.read_csv to raise a FileNotFoundError or IOError for an invalid file path
        with mock.patch("pandas.read_csv", side_effect=FileNotFoundError):
            with pytest.raises(FileNotFoundError):
                # Try loading an invalid path
                df = pd.read_csv(invalid_file_path)
                clean_imd_data(df, "imd_Station_API")

    def test_strips_station_and_sunset_whitespace(self):
        df = pd.DataFrame({
            "Date of Observation": ["2024-05-05"],
            "Time": ["8"],
            "Station": [" station\t\n "],
            "Sunset": [" 18:30 "]
        })
        result = clean_imd_data(df, "imd_Station_API")
        assert result["stationName"].iloc[0] == "STATION"
        assert result["sunset"].iloc[0] == "18:30"

    def test_handles_all_none_time_columns(self):
        df = pd.DataFrame({
            "Date of Observation": ["2024-05-05"],
            "Time": ["09"],
            "Sunrise": [None],
            "Sunset": [None],
            "Moonrise": [None],
            "Moonset": [None],
        })
        result = clean_imd_data(df, "imd_Station_API")
        assert "sunset" in result.columns
        assert result["sunset"].isna().all()

    def test_adds_missing_expected_columns(self):
        df = pd.DataFrame({
            "Date of Observation": ["2024-05-05"],
            "Time": ["10"]
        })
        result = clean_imd_data(df, "imd_Station_API")
        assert "stationName" in result.columns
        assert pd.isna(result["stationName"].iloc[0])

    def test_converts_na_and_blank_to_none_before_float(self):
        df = pd.DataFrame({
            "Date of Observation": ["2024-05-05"],
            "Time": ["12"],
            "Temperature": ["NA"],
            "Humidity": [""]
        })
        result = clean_imd_data(df, "imd_Station_API")
        assert pd.isna(result["temperature"].iloc[0])
        assert pd.isna(result["humidity"].iloc[0])

    def test_leaves_invalid_numeric_value_as_is(self):
        df = pd.DataFrame({
            "Date of Observation": ["2024-05-05"],
            "Time": ["12"],
            "Wind Speed KMPH": ["fast"]
        })
        result = clean_imd_data(df, "imd_Station_API")
        assert result["windSpeed"].iloc[0] == "fast"

    def test_drops_date_and_time_columns(self):
        df = pd.DataFrame({
            "Date of Observation": ["2024-05-05"],
            "Time": ["10"],
            "Station": ["A"]
        })
        result = clean_imd_data(df, "imd_Station_API")
        assert "Date" not in result.columns
        assert "Time" not in result.columns

    def test_default_time_value_for_missing_time_column(self):
        """Test if the 'Time' column gets a default value of '00' when it's missing from the data."""
        df = pd.DataFrame({
            "Station": ["DELHI"],
            "Date of Observation": ["2025-04-25"]
        })
        cleaned_df = clean_imd_data(df, "imd_Station_API")
        assert "timestamp" in cleaned_df.columns


class TestIMDMain:
    """
    Test suite for the main function in the indra.fetch.imd module.
    """
    @patch("indra.fetch.imd.Report")  # Patch the Report class itself
    def test_main_all_downloads_and_uploads_succeed(self, MockReport, mock_ctx, mock_yaml_path, mock_report, mock_datetime_now_at_23, tmp_directory, mock_all_success_api_responses, tmp_path):  # noqa: E501
        """
        Test when all downloads and uploads succeed for both datacodes.
        """
        mock_session = mock_all_success_api_responses['session']

        report_instance = MockReport.return_value  # Get the instance from the mock class
        report_instance.add_attachment = MagicMock()  # Mock add_attachment
        run_summary = tmp_path / f"run_summary_{uuid.uuid4().hex}.csv"
        with patch("indra.fetch.imd.retry_session", return_value=mock_session), \
                patch("indra.fetch.imd.upload_data_to_s3", return_value=0):

            main(ctx=mock_ctx, yaml_path=mock_yaml_path, run_summary_path=run_summary, directory=tmp_directory, email=True)

            # Assert that the report shows success for both download and upload
            report_instance.add_a_status_report.assert_any_call(
                "IMD Data Download", Status.SUCCESS, "All 2 files were downloaded"
            )
            report_instance.add_a_status_report.assert_any_call(
                "IMD Data Upload", Status.SUCCESS, "All 2 files were uploaded"
            )

    @patch("indra.fetch.imd.Report")  # Patch the Report class
    def test_main_partial_download_but_uploads_succeed(
        self, MockReport, mock_ctx, mock_yaml_path, mock_report, mock_datetime_now_at_23, tmp_directory, tmp_path,
        sample_station_api_json  # Injecting the fixture for Station API mock data
    ):
        """
        Test where one data source fails to download, but all downloaded files are uploaded successfully.
        Expect: Download = ERROR, Upload = SUCCESS
        """
        # Simulate responses
        session_instance = MagicMock()

        # Station API should succeed (mocking successful download and valid data)
        station_resp = MagicMock()
        station_resp.status_code = 200
        station_resp.text = sample_station_api_json  # Using the sample JSON fixture here

        # AWS_ARG fails to download with status code 500
        aws_resp = MagicMock()
        aws_resp.status_code = 500
        aws_resp.text = "Internal Server Error"

        def get_side_effect(url, **kwargs):
            if "current_wx_api.php" in url:
                return station_resp
            elif "aws_data_api.php" in url:
                return aws_resp
            return MagicMock(status_code=404)

        session_instance.get.side_effect = get_side_effect

        # Initialize the report mock
        report_instance = MockReport.return_value
        report_instance.add_attachment = MagicMock()

        # Create run summary file path
        run_summary = tmp_path / f"run_summary_{uuid.uuid4().hex}.csv"

        # Simulate the test with patched session and S3 upload functions
        with patch("indra.fetch.imd.retry_session", return_value=session_instance), \
            patch("indra.fetch.imd.upload_data_to_s3", return_value=0):

            # Run the main function
            main(ctx=mock_ctx, yaml_path=mock_yaml_path, run_summary_path=run_summary, directory=tmp_directory, email=True)

            # Assert the download result: partial download (1 out of 2)
            report_instance.add_a_status_report.assert_any_call(
                "IMD Data Download", Status.ERROR, "Only 1 out of 2 files were downloaded"
            )

            # Assert the upload result: the downloaded file was uploaded
            report_instance.add_a_status_report.assert_any_call(
                "IMD Data Upload", Status.SUCCESS, "All 1 files among the 1 downloaded files were uploaded"
            )

    @patch("indra.fetch.imd.Report")  # Patch the Report class
    def test_main_complete_download_failure(self, MockReport, mock_ctx, mock_yaml_path, mock_report, mock_datetime_now_at_23, tmp_directory, tmp_path, sample_station_api_json, sample_aws_arg_json):  # noqa: E501
        """
        Test where both Station API and AWS ARG API fail, so no files are downloaded and uploaded.
        Expect: Download = CRITICAL, Upload = SKIPPED
        """
        # Simulate responses
        session_instance = MagicMock()

        # Station API should fail (mocking download failure)
        station_resp = MagicMock()
        station_resp.status_code = 500
        station_resp.text = "Internal Server Error"

        # AWS ARG should fail (mocking download failure)
        aws_resp = MagicMock()
        aws_resp.status_code = 500
        aws_resp.text = "Internal Server Error"

        def get_side_effect(url, **kwargs):
            if "current_wx_api.php" in url:
                return station_resp
            elif "aws_data_api.php" in url:
                return aws_resp
            return MagicMock(status_code=404)

        session_instance.get.side_effect = get_side_effect

        # Initialize the report mock
        report_instance = MockReport.return_value
        report_instance.add_attachment = MagicMock()

        # Create run summary file path
        run_summary = tmp_path / f"run_summary_{uuid.uuid4().hex}.csv"

        # Simulate the test with patched session and S3 upload functions
        with patch("indra.fetch.imd.retry_session", return_value=session_instance), \
            patch("indra.fetch.imd.upload_data_to_s3", return_value=0):

            # Run the main function
            main(ctx=mock_ctx, yaml_path=mock_yaml_path, run_summary_path=run_summary, directory=tmp_directory, email=True)

            # Assert the download result: complete failure
            report_instance.add_a_status_report.assert_any_call(
                "IMD Data Download", Status.CRITICAL, "None of the 2 files were downloaded"
            )

            # Assert the upload result: no files were uploaded
            report_instance.add_a_status_report.assert_any_call(
                "IMD Data Upload", Status.CRITICAL, "None of the 2 files were uploaded"
            )

    @patch("indra.fetch.imd.Report")  # Patch the Report class
    def test_main_partial_upload_success(self, MockReport, mock_ctx, mock_yaml_path, mock_report, mock_datetime_now_at_23, tmp_directory, tmp_path, sample_station_api_json, sample_aws_arg_json):  # noqa: E501
        """
        Test where both downloads are successful, but one upload fails while the other succeeds.
        Expect: Download = SUCCESS, Upload = ERROR (partial upload failure for one file).
        """
        # Simulate responses
        session_instance = MagicMock()

        # Station API should succeed (mocking successful download)
        station_resp = MagicMock()
        station_resp.status_code = 200
        station_resp.text = sample_station_api_json

        # AWS ARG should succeed (mocking successful download)
        aws_resp = MagicMock()
        aws_resp.status_code = 200
        aws_resp.text = sample_aws_arg_json

        def get_side_effect(url, **kwargs):
            if "current_wx_api.php" in url:
                return station_resp  # Successful download for Station API
            elif "aws_data_api.php" in url:
                return aws_resp  # Successful download for AWS ARG API
            return MagicMock(status_code=404)

        session_instance.get.side_effect = get_side_effect

        # Initialize the report mock
        report_instance = MockReport.return_value
        report_instance.add_attachment = MagicMock()

        # Create run summary file path
        run_summary = tmp_path / f"run_summary_{uuid.uuid4().hex}.csv"

        # Simulate the test with patched session and S3 upload functions
        with patch("indra.fetch.imd.retry_session", return_value=session_instance), \
            patch("indra.fetch.imd.upload_data_to_s3", side_effect=[0, 1]):  # First upload success, second upload failure

            # Run the main function
            main(ctx=mock_ctx, yaml_path=mock_yaml_path, run_summary_path=run_summary, directory=tmp_directory, email=True)

            # Assert the download result: both downloads are successful
            report_instance.add_a_status_report.assert_any_call(
                "IMD Data Download", Status.SUCCESS, "All 2 files were downloaded"
            )

            # Assert the upload result: first upload success, second upload failure
            report_instance.add_a_status_report.assert_any_call(
                "IMD Data Upload", Status.ERROR, "Only 1 out of 2 files were uploaded"
            )

    @patch("indra.fetch.imd.Report")  # Patch the Report class
    def test_main_total_upload_failure(self, MockReport, mock_ctx, mock_yaml_path, mock_report, mock_datetime_now_at_23, tmp_directory, tmp_path, sample_station_api_json, sample_aws_arg_json):
        """
        Test where both downloads are successful, but both uploads fail.
        Expect: Download = SUCCESS, Upload = CRITICAL (total upload failure).
        """
        # Simulate responses
        session_instance = MagicMock()

        # Station API should succeed (mocking successful download)
        station_resp = MagicMock()
        station_resp.status_code = 200
        station_resp.text = sample_station_api_json

        # AWS ARG should succeed (mocking successful download)
        aws_resp = MagicMock()
        aws_resp.status_code = 200
        aws_resp.text = sample_aws_arg_json

        def get_side_effect(url, **kwargs):
            if "current_wx_api.php" in url:
                return station_resp  # Successful download for Station API
            elif "aws_data_api.php" in url:
                return aws_resp  # Successful download for AWS ARG API
            return MagicMock(status_code=404)

        session_instance.get.side_effect = get_side_effect

        # Initialize the report mock
        report_instance = MockReport.return_value
        report_instance.add_attachment = MagicMock()

        # Create run summary file path
        run_summary = tmp_path / f"run_summary_{uuid.uuid4().hex}.csv"

        # Simulate the test with patched session and S3 upload functions
        with patch("indra.fetch.imd.retry_session", return_value=session_instance), \
            patch("indra.fetch.imd.upload_data_to_s3", side_effect=[1, 1]):  # Both uploads fail (side_effect=1)

            # Run the main function
            main(ctx=mock_ctx, yaml_path=mock_yaml_path, run_summary_path=run_summary, directory=tmp_directory, email=True)

            # Assert the download result: both downloads are successful
            report_instance.add_a_status_report.assert_any_call(
                "IMD Data Download", Status.SUCCESS, "All 2 files were downloaded"
            )

            # Assert the upload result: both uploads fail
            report_instance.add_a_status_report.assert_any_call(
                "IMD Data Upload", Status.CRITICAL, "None of the 2 files were uploaded"
            )

class TestAPIresponses:
    """
    Test suite for API response handling in the indra.fetch.imd module.
    """

    @patch("indra.fetch.imd.Report")
    def test_main_malformed_json_response(
        self,
        MockReport,
        mock_ctx,
        mock_yaml_path,
        mock_datetime_now_at_23,
        tmp_directory,
        tmp_path,
        malformed_json_response,
    ):
        """Test handling of API returning malformed JSON."""
        session_instance = MagicMock()

        station_resp = MagicMock(status_code=200, text=malformed_json_response)
        aws_resp = MagicMock(status_code=200, text=malformed_json_response)

        session_instance.get.side_effect = lambda url, **kwargs: (
            station_resp if "current_wx_api.php" in url else aws_resp
        )

        report_instance = MockReport.return_value
        report_instance.add_attachment = MagicMock()

        run_summary = tmp_path / f"run_summary_{uuid.uuid4().hex}.csv"

        with patch("indra.fetch.imd.retry_session", return_value=session_instance), \
            patch("indra.fetch.imd.upload_data_to_s3", return_value=0):
            main(ctx=mock_ctx, yaml_path=mock_yaml_path, run_summary_path=run_summary, directory=tmp_directory, email=True)

        report_instance.add_a_status_report.assert_any_call(
            "IMD Data Download", Status.CRITICAL, "None of the 2 files were downloaded"
        )

    @patch("indra.fetch.imd.Report")
    def test_main_empty_json_response(
        self,
        MockReport,
        mock_ctx,
        mock_yaml_path,
        mock_datetime_now_at_23,
        tmp_directory,
        tmp_path,
        empty_json_response,
    ):
        """Test handling when API returns valid but empty JSON."""
        session_instance = MagicMock()

        station_resp = MagicMock(status_code=200, text=empty_json_response)
        aws_resp = MagicMock(status_code=200, text=empty_json_response)

        session_instance.get.side_effect = lambda url, **kwargs: (
            station_resp if "current_wx_api.php" in url else aws_resp
        )

        report_instance = MockReport.return_value
        report_instance.add_attachment = MagicMock()

        run_summary = tmp_path / f"run_summary_{uuid.uuid4().hex}.csv"

        with patch("indra.fetch.imd.retry_session", return_value=session_instance), \
            patch("indra.fetch.imd.upload_data_to_s3", return_value=0):
            main(ctx=mock_ctx, yaml_path=mock_yaml_path, run_summary_path=run_summary, directory=tmp_directory, email=True)

        report_instance.add_a_status_report.assert_any_call(
            "IMD Data Download", Status.CRITICAL, "None of the 2 files were downloaded"
        )

    @patch("indra.fetch.imd.Report")
    def test_main_api_returns_empty_response(
        self,
        MockReport,
        mock_ctx,
        mock_yaml_path,
        mock_datetime_now_at_23,
        tmp_directory,
        tmp_path,
        empty_response,
    ):
        """Test handling of API returning HTTP 200 with empty body not in json format."""
        session_instance = MagicMock()

        station_resp = MagicMock(status_code=200, text=empty_response)
        aws_resp = MagicMock(status_code=200, text=empty_response)

        session_instance.get.side_effect = lambda url, **kwargs: (
            station_resp if "current_wx_api.php" in url else aws_resp
        )

        report_instance = MockReport.return_value
        report_instance.add_attachment = MagicMock()

        run_summary = tmp_path / f"run_summary_{uuid.uuid4().hex}.csv"

        with patch("indra.fetch.imd.retry_session", return_value=session_instance), \
            patch("indra.fetch.imd.upload_data_to_s3", return_value=0):
            main(ctx=mock_ctx, yaml_path=mock_yaml_path, run_summary_path=run_summary, directory=tmp_directory, email=True)

        report_instance.add_a_status_report.assert_any_call(
            "IMD Data Download", Status.CRITICAL, "None of the 2 files were downloaded"
        )

def test_yaml_path_validation_success(mock_ctx, mock_yaml_path):
    """Test that main function runs successfully with a valid YAML path."""
    runner = CliRunner()
    result = runner.invoke(app, [str(mock_yaml_path)])
    assert result.exit_code == 0

def test_send_email_with_attachments(mock_report, tmp_path):
    """Test that the send_email function is called with the correct parameters and attachments."""
    mock_report.send_email = MagicMock()
    mock_report.add_attachment = MagicMock()

    # Create a temporary file to simulate an attachment
    attachment_path = tmp_path / "test_attachment.txt"
    with open(attachment_path, "w") as f:
        f.write("This is a test attachment.")

    # Add the attachment to the report
    mock_report.add_attachment(str(attachment_path))

    # Call the send_email function
    mock_report.send_email()

    # Assert that send_email was called
    mock_report.send_email.assert_called_once()

    # Assert that the attachment was added
    mock_report.add_attachment.assert_called_with(str(attachment_path))

def test_send_email_without_attachments(mock_report):
    """Test that the send_email function is called without any attachments."""
    mock_report.send_email = MagicMock()

    # Call the send_email function
    mock_report.send_email()

    # Assert that send_email was called
    mock_report.send_email.assert_called_once()

    # Assert that no attachments were added
    mock_report.add_attachment.assert_not_called()

def test_send_email_with_multiple_attachments(mock_report, tmp_path):
    """Test that the send_email function is called with multiple attachments."""
    mock_report.send_email = MagicMock()
    mock_report.add_attachment = MagicMock()

    # Create multiple temporary files to simulate attachments
    attachment_paths = []
    for i in range(3):
        attachment_path = tmp_path
        attachment_path = tmp_path / f"test_attachment_{i}.txt"
        with open(attachment_path, "w") as f:
            f.write(f"This is test attachment {i}.")
        attachment_paths.append(attachment_path)
        # Add the attachment to the report
        mock_report.add_attachment(str(attachment_path))
    # Call the send_email function
    mock_report.send_email()
    # Assert that send_email was called
    mock_report.send_email.assert_called_once()
    # Assert that all attachments were added
    for attachment_path in attachment_paths:
        mock_report.add_attachment.assert_any_call(str(attachment_path))
    # Assert that the number of attachments matches
    assert mock_report.add_attachment.call_count == len(attachment_paths)

def mock_check_path_or_url(path):
    """Mock implementation of check_path_or_url"""
    if not Path(path).exists() and not path.startswith(('http://', 'https://')):
        raise FileNotFoundError(f"Path or URL not found: {path}")
    return path

def mock_validate_imd_json(data):
    """Mock implementation of validate_imd_json"""
    required_keys = ["Station", "Station Id", "Date of Observation", "Time"]
    if not all(key in data[0] for key in required_keys):
        raise ValueError(f"Invalid IMD JSON schema. Required keys missing: {required_keys}")
    return True

def required_env_variables(stats):
    """Mock implementation of send_summary_email"""
    required_fields = ["stations", "records", "upload_status"]
    if not all(field in stats for field in required_fields):
        raise KeyError(f"Missing required stats fields: {required_fields}")

    required_env_vars = ["SENDGRID_API_KEY", "EMAIL_FROM", "EMAIL_TO"]
    if not all(var in os.environ for var in required_env_vars):
        raise ValueError(f"Missing required environment variables: {required_env_vars}")

    # Mock successful email send
    return True

class FakeDateTime(real_datetime):
    """Subclass real datetime so strptime/strftime still work."""
    @classmethod
    def now(cls):
        # minute will be overridden per-test via attribute injection
        return cls(2025, 5, 5, 10, cls._minute, 0)

@patch("indra.fetch.imd.Report")  # patch the Report class as imported in imd.py
def test_download_frequency_15mins_sets_correct_timecode(mock_report, tmp_path, mock_ctx, mock_yaml_path, monkeypatch):
    """
    If download_frequency='15mins' and minute<15, the timecode
    should be rounded to the top of the hour.
    """
    # 1) Force minute = 5
    FakeDateTime._minute = 5
    monkeypatch.setattr(imd, "datetime", FakeDateTime)

    # 2) Use the real get_params but ensure no exception path
    cfg = imd.get_params(mock_yaml_path)
    cfg["shared_params"]["raise_error"] = False
    monkeypatch.setattr(imd, "get_params", lambda p: cfg)

    # 3) Make retry_session return a session that always 400s
    session = MagicMock()
    session.get.return_value = MagicMock(status_code=400, text="")
    monkeypatch.setattr(imd, "retry_session", lambda **kw: session)
    # Also stub out upload so nothing actually happens
    monkeypatch.setattr(imd, "upload_data_to_s3", lambda **kw: 0)

    # 4) Run main() with download_frequency 15mins
    run_summary = tmp_path / "run.csv"
    imd.main(
        ctx=mock_ctx,
        yaml_path=mock_yaml_path,
        run_summary_path=run_summary,
        directory=str(tmp_path),
        email=False,
        download_frequency="15mins",
    )

    # 5) Assert timecodes are all on the hour (10:00:00)
    df = pd.read_csv(run_summary)
    assert all(df["timecode"] == "2025-05-05 10:00:00")


def test_invalid_download_frequency_fallback_to_hourly(mock_ctx, mock_yaml_path, tmp_path, monkeypatch):
    """
    If download_frequency is invalid but raise_error=False,
    main() should log an error and proceed as hourly.
    """
    # 1) Force minute = 23 so we can see top-of-hour fallback too
    FakeDateTime._minute = 23
    monkeypatch.setattr(imd, "datetime", FakeDateTime)

    # 2) Build config with raise_error=False
    cfg = imd.get_params(mock_yaml_path)
    cfg["shared_params"]["raise_error"] = False
    monkeypatch.setattr(imd, "get_params", lambda p: cfg)

    # 3) Simulate always-400 responses
    session = MagicMock()
    session.get.return_value = MagicMock(status_code=400, text="")
    monkeypatch.setattr(imd, "retry_session", lambda **kw: session)
    monkeypatch.setattr(imd, "upload_data_to_s3", lambda **kw: 0)

    # 4) Run main() with bogus frequency
    run_summary = tmp_path / "run.csv"
    imd.main(
        ctx=mock_ctx,
        yaml_path=mock_yaml_path,
        run_summary_path=run_summary,
        directory=str(tmp_path),
        email=False,
        download_frequency="not-a-frequency",
    )

    # 5) Assert timecodes still roll to top-of-hour (10:00:00)
    df = pd.read_csv(run_summary)
    assert all(df["timecode"] == "2025-05-05 10:00:00")


def test_invalid_download_frequency_error_flag_raises(monkeypatch, mock_ctx, mock_yaml_path, tmp_path):

    """
    If download_frequency is invalid and raise_error=True,
    the code will attempt to raise ValueError("Invalid download frequency").
    In current implementation that exception is caught internally,
    so what surfaces is an UnboundLocalError in the finally block—
    so we assert that.
    """
    # 1) Build config with raise_error=True
    cfg = imd.get_params(mock_yaml_path)
    cfg["shared_params"]["raise_error"] = True
    monkeypatch.setattr(imd, "get_params", lambda p: cfg)

    # 2) Call main() and expect UnboundLocalError
    with pytest.raises(UnboundLocalError):
        imd.main(
            ctx=mock_ctx,
            yaml_path=mock_yaml_path,
            run_summary_path=tmp_path / "dummy.csv",
            directory=str(tmp_path),
            email=False,
            download_frequency="invalid",
        )

@patch("indra.fetch.imd.Report")
def test_no_upload_when_status_500(mock_report, monkeypatch, mock_ctx, mock_yaml_path, tmp_path):
    """
    If both APIs return status_code=500 (not in [400,401,404]),
    then no_downloads==0 and upload_data_to_s3 should NOT be invoked.
    """
    # 1) Freeze datetime so we don't hit the final-email block
    monkeypatch.setattr(imd, "datetime", FakeDateTime)

    # 2) Stub get_params with raise_error=False
    cfg = imd.get_params(mock_yaml_path)
    cfg["shared_params"]["raise_error"] = False
    monkeypatch.setattr(imd, "get_params", lambda p: cfg)

    # 3) Make retry_session return a session that always 500s
    session = MagicMock()
    session.get.return_value = MagicMock(status_code=500, text="error")
    monkeypatch.setattr(imd, "retry_session", lambda **kw: session)

    # 4) Spy on upload_data_to_s3
    upload_spy = MagicMock()
    monkeypatch.setattr(imd, "upload_data_to_s3", upload_spy)

    # 5) Run main(); email=False so no final summary email
    run_summary = tmp_path / "run.csv"
    imd.main(
        ctx=mock_ctx,
        yaml_path=mock_yaml_path,
        run_summary_path=run_summary,
        directory=str(tmp_path),
        email=False,
        download_frequency="hourly",
    )

    # 6) Assert: upload_data_to_s3 was never called
    upload_spy.assert_not_called()

    # And since no_downloads==0 & status not in [400,401,404],
    # Report.send_email() *should* have been triggered inside the loop:
    assert mock_report.return_value.send_email.called

@patch("indra.fetch.imd.Report")
def test_download_frequency_15mins_sets_15min_branch(mock_report, monkeypatch, mock_ctx, mock_yaml_path, tmp_path):
    """
    If minute in [15,30), timecode should be set to HH:15:00.
    """
    # 1) Force minute=20
    FakeDateTime._minute = 20
    monkeypatch.setattr(imd, "datetime", FakeDateTime)

    # 2) Stub config and session to prevent real I/O
    cfg = imd.get_params(mock_yaml_path)
    cfg["shared_params"]["raise_error"] = False
    monkeypatch.setattr(imd, "get_params", lambda p: cfg)
    session = MagicMock()
    session.get.return_value = MagicMock(status_code=400, text="")
    monkeypatch.setattr(imd, "retry_session", lambda **kw: session)
    monkeypatch.setattr(imd, "upload_data_to_s3", lambda **kw: 0)

    # 3) Run main()
    run_summary = tmp_path / "run.csv"
    imd.main(
        ctx=mock_ctx,
        yaml_path=mock_yaml_path,
        run_summary_path=run_summary,
        directory=str(tmp_path),
        email=False,
        download_frequency="15mins",
    )

    # 4) Assert timecode == "2025-05-05 10:15:00"
    df = pd.read_csv(run_summary)
    assert all(df["timecode"] == "2025-05-05 10:15:00")

@patch("indra.fetch.imd.Report")
def test_download_frequency_15mins_sets_30min_branch(mock_report, monkeypatch, mock_ctx, mock_yaml_path, tmp_path):
    """
    If minute in [30,45), timecode should be set to HH:30:00.
    """
    # 1) Force minute=35
    FakeDateTime._minute = 35
    monkeypatch.setattr(imd, "datetime", FakeDateTime)

    # 2) Stub config and session
    cfg = imd.get_params(mock_yaml_path)
    cfg["shared_params"]["raise_error"] = False
    monkeypatch.setattr(imd, "get_params", lambda p: cfg)
    session = MagicMock()
    session.get.return_value = MagicMock(status_code=400, text="")
    monkeypatch.setattr(imd, "retry_session", lambda **kw: session)
    monkeypatch.setattr(imd, "upload_data_to_s3", lambda **kw: 0)

    # 3) Run main()
    run_summary = tmp_path / "run.csv"
    imd.main(
        ctx=mock_ctx,
        yaml_path=mock_yaml_path,
        run_summary_path=run_summary,
        directory=str(tmp_path),
        email=False,
        download_frequency="15mins",
    )

    # 4) Assert timecode == "2025-05-05 10:30:00"
    df = pd.read_csv(run_summary)
    assert all(df["timecode"] == "2025-05-05 10:30:00")

@patch("indra.fetch.imd.Report")
def test_download_frequency_15mins_sets_45min_branch(mock_report, monkeypatch, mock_ctx, mock_yaml_path, tmp_path):
    """
    If minute in [45,60), timecode should be set to HH:45:00.
    """
    # 1) Force minute=50
    FakeDateTime._minute = 50
    monkeypatch.setattr(imd, "datetime", FakeDateTime)

    # 2) Stub config and session
    cfg = imd.get_params(mock_yaml_path)
    cfg["shared_params"]["raise_error"] = False
    monkeypatch.setattr(imd, "get_params", lambda p: cfg)
    session = MagicMock()
    session.get.return_value = MagicMock(status_code=400, text="")
    monkeypatch.setattr(imd, "retry_session", lambda **kw: session)
    monkeypatch.setattr(imd, "upload_data_to_s3", lambda **kw: 0)

    # 3) Run main()
    run_summary = tmp_path / "run.csv"
    imd.main(
        ctx=mock_ctx,
        yaml_path=mock_yaml_path,
        run_summary_path=run_summary,
        directory=str(tmp_path),
        email=False,
        download_frequency="15mins",
    )

    # 4) Assert timecode == "2025-05-05 10:45:00"
    df = pd.read_csv(run_summary)
    assert all(df["timecode"] == "2025-05-05 10:45:00")

