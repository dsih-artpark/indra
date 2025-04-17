from datetime import datetime, time, timedelta, timezone
from typing import ClassVar
from unittest.mock import MagicMock, Mock, patch

import pytest
import yaml
from typer.testing import CliRunner

from indra.emails import Report, Status
from indra.fetch.ecpds import app, construct_ecpds_urls, last_date_of_ecpds_data, main

runner = CliRunner()

@pytest.fixture
def mock_session(mocker):
    mock = Mock()
    mocker.patch('indra.fetch.ecpds.retry_session', return_value=mock)
    return mock

@pytest.fixture
def mock_datetime(mocker):
    """Fixture to mock datetime while preserving core functionality"""
    mock = mocker.patch('indra.fetch.ecpds.datetime')

    # Preserve real datetime functionality
    mock.strptime = datetime.strptime
    mock.datetime = datetime
    mock.timedelta = timedelta
    mock.time = time
    mock.date = datetime.date
    mock.timezone = timezone
    mock.combine = datetime.combine

    return mock

@pytest.fixture
def mock_config():
    return [
        {
            "reference_time": "20240315T000000",
            "model": "model_a",
            "resolution": "high",
            "stream": "stream_1",
            "step": "0h",
            "type": "fc",
            "format": ["netcdf", "grib"]
        },
        {
            "reference_time": "20240315T060000",
            "model": "model_b",
            "resolution": "low",
            "stream": "stream_2",
            "step": "6h",
            "type": "ef",
            "format": ["grib"]
        }
    ]

@pytest.fixture
def mock_html_response(mock_session):
    """Fixture for successful HTML response"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = """
        <html>
            <a href="/forecasts/20240315/">20240315/</a>      15-03-2024 05:45             -             -
            <a href="/forecasts/20240314/">20240314/</a>      14-03-2024 05:45             -             -
        </html>
    """
    mock_session.get.return_value = mock_response
    return mock_response

@pytest.fixture
def mock_empty_html_response(mock_session):
    """Fixture for empty HTML response"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = """
    """
    mock_session.get.return_value = mock_response
    return mock_response

@pytest.fixture
def mock_no_dates_html_response(mock_session):
    """Fixture for HTML response with no dates"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = """
        <html>
            <a href="/forecasts/">20240315/</a>      15-03-2024 05:45             -             -
            <a href="/forecasts/">20240314/</a>      14-03-2024 05:45             -             -
        </html>
    """
    mock_session.get.return_value = mock_response
    return mock_response

@pytest.fixture
def mock_failed_http_request(mock_session):
    """Fixture for failed HTTP request"""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_session.get.return_value = mock_response
    return mock_response

@pytest.fixture
def mock_no_href_html_response(mock_session):
    """Fixture for HTML response with no href"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = """
    """
    mock_session.get.return_value = mock_response
    return mock_response

@pytest.fixture
def mock_previous_date_not_in_dates_list(mock_session):
    """Fixture for HTML response with previous date not in dates list"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = """
        <html>
            <a href="/forecasts/20240316/">20240316/</a>      16-03-2024 05:45             -             -
            <a href="/forecasts/20240314/">20240314/</a>      14-03-2024 05:45             -             -
        </html>
    """
    mock_session.get.return_value = mock_response
    return mock_response


@pytest.fixture
def mock_yaml_path(tmp_path):
    # Create a dummy YAML file for testing
    yaml_file = tmp_path / "config.yaml"
    config_data = {
        'shared_params': {
            'email_recipients': ["test@example.com"],
            's3_bucket': "test-bucket"
        },
        'ecpds': {
            'url': "https://data.ecmwf.int/forecasts/",
            'configs': [
                {
                    'reference_time': "00",
                    'model': "model1",
                    'resolution': "0.25",
                    'stream': "oper",
                    'step': "0h",
                    'type': "fc",
                    'format': ["grib"]
                }
            ],
            'raise_error': False,
            'ds_id': "dsid",
            'ds_name': "dsname",
            'ds_folder_name': "folder",
            'extensions': ["grib"]
        }
    }
    with open(yaml_file, 'w') as f:
        yaml.dump(config_data, f)
    return yaml_file

@pytest.fixture
def mock_ctx():
    class Ctx:
        obj: ClassVar[dict] = {"log_file": "test.log"}  # Simulate a context object
    return Ctx()

@pytest.fixture
def mock_report():
    mock = MagicMock()
    mock.add_a_status_report = MagicMock()
    mock.send_email = MagicMock()
    return mock

@pytest.fixture
def integration_setup(mock_yaml_path, tmp_path):
    # Setup for integration tests: create directories, a mock file, and return needed paths
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    test_file = test_dir / "test_file.grib"
    test_file.write_text("test content")
    return mock_yaml_path, test_dir, test_file

def test_failed_http_request(mock_session, mock_failed_http_request):
    """Test that HTTP errors are handled correctly"""
    mock_session.get.return_value = mock_failed_http_request

    result = last_date_of_ecpds_data()
    assert result is None

def test_successful_request_after_cutoff(mock_datetime, mock_html_response):
    """Test when current time is after 8:49 UTC"""
    mock_datetime.now.return_value = datetime(2024, 3, 15, 9, 0, tzinfo=timezone.utc)

    result = last_date_of_ecpds_data()
    assert result == datetime(2024, 3, 15)

def test_successful_request_before_cutoff(mock_datetime, mock_html_response):
    """Test when current time is before 8:49 UTC"""
    mock_datetime.now.return_value = datetime(2024, 3, 15, 8, 48, tzinfo=timezone.utc)

    result = last_date_of_ecpds_data()
    assert result == datetime(2024, 3, 14)

def test_successful_request_at_cutoff(mock_datetime, mock_html_response):
    """Test when current time is exactly at 8:49 UTC"""
    mock_datetime.now.return_value = datetime(2024, 3, 15, 8, 49, tzinfo=timezone.utc)

    result = last_date_of_ecpds_data()
    assert result == datetime(2024, 3, 14)

def test_empty_html_response(mock_session, mock_empty_html_response):
    """Test when HTML response is empty"""
    mock_session.get.return_value = mock_empty_html_response

    result = last_date_of_ecpds_data()
    assert result is None

def test_no_dates_html_response(mock_session, mock_no_dates_html_response):
    """Test when HTML response has no dates"""
    mock_session.get.return_value = mock_no_dates_html_response

    result = last_date_of_ecpds_data()
    assert result is None

def test_no_href_html_response(mock_session, mock_no_href_html_response):
    """Test when HTML response has no href"""
    mock_session.get.return_value = mock_no_href_html_response

    result = last_date_of_ecpds_data()
    assert result is None

def test_previous_date_not_in_dates_list(mock_datetime, mock_session, mock_previous_date_not_in_dates_list):
    """Test when previous date is not in the dates list"""
    mock_datetime.now.return_value = datetime(2024, 3, 15, 7, 0, tzinfo=timezone.utc)
    mock_session.get.return_value = mock_previous_date_not_in_dates_list

    result = last_date_of_ecpds_data()
    assert result is None

def test_different_base_url_values(mock_datetime, mock_config):
    """Test URL construction with different base_url values"""
    base_urls = [
        "https://ecpds.example.com/",  # With trailing slash
        "https://ecpds.example.com",   # Without trailing slash
        "http://ecpds.example.com",    # Different protocol
        "https://another-base-url.com/"  # Completely different URL
    ]
    date = datetime(2024, 3, 15, 5, 0, tzinfo=timezone.utc)
    mock_datetime.now.return_value = date
    expected_results = [
        "https://ecpds.example.com/20240315/20240315T000000z/model_a/high/stream_1/2024031520240315T0000000000-0h-stream_1-fc.netcdf",
        "https://ecpds.example.com/20240315/20240315T000000z/model_a/high/stream_1/2024031520240315T0000000000-0h-stream_1-fc.netcdf",
        "http://ecpds.example.com/20240315/20240315T000000z/model_a/high/stream_1/2024031520240315T0000000000-0h-stream_1-fc.netcdf",
        "https://another-base-url.com/20240315/20240315T000000z/model_a/high/stream_1/2024031520240315T0000000000-0h-stream_1-fc.netcdf"
    ]
    # Test each base_url
    for i, base_url in enumerate(base_urls):
        print(f"Testing base_url: {base_url}")
        result = construct_ecpds_urls(date=date, configs=mock_config, base_url=base_url)
        assert result[0] == expected_results[i]

def test_url_construction_multiple_formats(mock_datetime, mock_config):
    """Test URL construction when multiple formats are provided"""
    date = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)
    mock_datetime.now.return_value = date

    # Expected URLs for netcdf and grib formats
    expected_urls = [
        "https://data.ecmwf.int/forecasts/20240315/20240315T000000z/model_a/high/stream_1/2024031520240315T0000000000-0h-stream_1-fc.netcdf",
        "https://data.ecmwf.int/forecasts/20240315/20240315T000000z/model_a/high/stream_1/2024031520240315T0000000000-0h-stream_1-fc.grib",
        "https://data.ecmwf.int/forecasts/20240315/20240315T060000z/model_b/low/stream_2/2024031520240315T0600000000-6h-stream_2-ef.grib"
    ]

    # Call the function with the mock date and configuration
    result = construct_ecpds_urls(date=date, configs=mock_config)

    # Assert the result matches the expected URLs
    assert result == expected_urls

def test_empty_config(mock_datetime):
    """Test URL construction with an empty config"""
    date = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)
    mock_datetime.now.return_value = date

    # Call the function with an empty config
    result = construct_ecpds_urls(date=date, configs=[])

    # Assert the result is an empty list
    assert result == []

# List of required keys must match the keys defined inside construct_ecpds_urls.
REQUIRED_KEYS = ["reference_time", "model", "resolution", "stream", "step", "type", "format"]
@pytest.mark.parametrize("missing_key", REQUIRED_KEYS)
def test_construct_ecpds_urls_key_error_on_missing_config_keys(missing_key, mock_datetime, mock_config):
    test_date = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)
    mock_datetime.now.return_value = test_date

    broken_config = mock_config[0].copy()
    broken_config.pop(missing_key)

    with pytest.raises(KeyError):
        construct_ecpds_urls(date=test_date, configs=[broken_config])

def test_invalid_date_format(mock_config):
    invalid_date = "2024-03-15"  # String instead of datetime

    with pytest.raises(ValueError, match="Invalid date format"):
        construct_ecpds_urls(date=invalid_date, configs=mock_config)

def test_yaml_path_validation_success(mock_ctx, mock_yaml_path, mock_report):
    # Test that the main function runs successfully with a valid YAML path
    with patch('indra.fetch.ecpds.last_date_of_ecpds_data', return_value=datetime(2024, 1, 1)), \
         patch('indra.fetch.ecpds.construct_ecpds_urls', return_value=["test_url"]), \
         patch('indra.fetch.ecpds.download_from_url', return_value=True), \
         patch('indra.fetch.ecpds.upload_data_to_s3', return_value=0), \
         patch('indra.fetch.ecpds.tempfile.TemporaryDirectory') as mock_tempdir, \
         patch('indra.fetch.ecpds.Report') as MockReport:
        mock_tempdir.return_value.__enter__.return_value = "tempdir"
        MockReport.return_value = mock_report
        main(ctx=mock_ctx, yaml_path=mock_yaml_path, get_latest_date=True, custom_date=None, upload=True, directory=None)
        # Assert that the report methods were called
        MockReport.return_value.add_a_status_report.assert_called()

def test_get_latest_date_flag_true(mock_ctx, mock_yaml_path, mock_report):
    # If get_latest_date is True, last_date_of_ecpds_data should be called
    with patch('indra.fetch.ecpds.last_date_of_ecpds_data', return_value=datetime(2024, 1, 1)) as mock_last_date, \
         patch('indra.fetch.ecpds.construct_ecpds_urls', return_value=["test_url"]), \
         patch('indra.fetch.ecpds.download_from_url', return_value=True), \
         patch('indra.fetch.ecpds.upload_data_to_s3', return_value=0), \
         patch('indra.fetch.ecpds.tempfile.TemporaryDirectory') as mock_tempdir, \
         patch('indra.fetch.ecpds.Report') as MockReport:
        mock_tempdir.return_value.__enter__.return_value = "tempdir"
        MockReport.return_value = mock_report()

        main(ctx=mock_ctx, yaml_path=mock_yaml_path, get_latest_date=True, custom_date=None, upload=True, directory=None)
        mock_last_date.assert_called_once()

def test_get_latest_date_flag_false_logs_critical(mock_ctx, mock_yaml_path, mock_report):
    # If get_latest_date is False, a critical error should be logged and processing stopped
    with patch('indra.fetch.ecpds.construct_ecpds_urls', return_value=["test_url"]), \
         patch('indra.fetch.ecpds.download_from_url', return_value=True), \
         patch('indra.fetch.ecpds.upload_data_to_s3', return_value=0), \
         patch('indra.fetch.ecpds.tempfile.TemporaryDirectory') as mock_tempdir, \
         patch('indra.fetch.ecpds.Report') as MockReport:

        mock_tempdir.return_value.__enter__.return_value = "tempdir"
        MockReport.return_value = mock_report()
        main(ctx=mock_ctx, yaml_path=mock_yaml_path, get_latest_date=False, custom_date=None, upload=True, directory=None)
        # Report critical is logged
        MockReport.return_value.add_a_status_report.assert_called_with('ECPDS Data Retrieval', Status.CRITICAL,
                                                                        "Custom dates are not yet supported.")

def test_custom_date_option_not_supported(mock_ctx, mock_yaml_path, mock_report):
    # Custom date option should log a critical error as not yet implemented
    with patch('indra.fetch.ecpds.construct_ecpds_urls', return_value=["test_url"]), \
         patch('indra.fetch.ecpds.download_from_url', return_value=True), \
         patch('indra.fetch.ecpds.upload_data_to_s3', return_value=0), \
         patch('indra.fetch.ecpds.tempfile.TemporaryDirectory') as mock_tempdir, \
         patch('indra.fetch.ecpds.Report') as MockReport:

        mock_tempdir.return_value.__enter__.return_value = "tempdir"
        MockReport.return_value = mock_report()
        main(ctx=mock_ctx, yaml_path=mock_yaml_path, get_latest_date=False, custom_date="2025-04-15", upload=True, directory=None)
        MockReport.return_value.add_a_status_report.assert_called_with('ECPDS Data Retrieval', Status.CRITICAL,
                                                                        "Custom dates are not yet supported.")

def test_upload_flag_behavior(mock_ctx, mock_yaml_path, mock_report, tmp_path):
    # Test upload flag being True calls upload functions, being False skips the calls
    with patch('indra.fetch.ecpds.last_date_of_ecpds_data', return_value=datetime(2024, 1, 1)), \
         patch('indra.fetch.ecpds.construct_ecpds_urls', return_value=["test_url.grib"]), \
         patch('tempfile.TemporaryDirectory') as mock_tempdir, \
         patch('indra.fetch.ecpds.Report') as MockReport, \
         patch('os.path.exists', return_value=True):

        # Create a dummy file in the temporary directory
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        test_file = test_dir / "test_url.grib"
        test_file.write_text("test content")
        mock_tempdir.return_value.__enter__.return_value = str(test_dir)
        MockReport.return_value = mock_report

        # test upload True
        main(ctx=mock_ctx, yaml_path=mock_yaml_path, get_latest_date=True, custom_date=None, upload=True, directory=str(test_dir))

        # Test upload False
        main(ctx=mock_ctx, yaml_path=mock_yaml_path, get_latest_date=True, custom_date=None, upload=False, directory=str(test_dir))

def test_directory_option_usage(mock_ctx, mock_yaml_path, mock_report):
    # Test using a specified directory
    with patch('indra.fetch.ecpds.last_date_of_ecpds_data', return_value=datetime(2024, 1, 1)), \
         patch('indra.fetch.ecpds.construct_ecpds_urls', return_value=["test_url"]), \
         patch('indra.fetch.ecpds.download_from_url', return_value=True), \
         patch('indra.fetch.ecpds.upload_data_to_s3', return_value=0), \
         patch('indra.fetch.ecpds.os.makedirs') as mock_makedirs, \
         patch('indra.fetch.ecpds.tempfile.TemporaryDirectory') as mock_tempdir, \
         patch('indra.fetch.ecpds.Report') as MockReport:
        mock_tempdir.return_value.__enter__.return_value = "tempdir"
        MockReport.return_value = mock_report()
        directory = "custom_dir"
        main(ctx=mock_ctx, yaml_path=mock_yaml_path, get_latest_date=True, custom_date=None, upload=True, directory=directory)
        mock_makedirs.assert_called_with(directory, exist_ok=True)  # ensure os.makedirs is called

def test_invalid_yaml_path(mock_ctx):
    # Test that an invalid YAML path raises a FileNotFoundError
    invalid_yaml_path = "invalid_path.yaml"
    with pytest.raises(FileNotFoundError):
        main(ctx=mock_ctx, yaml_path=invalid_yaml_path, get_latest_date=True, custom_date=None, upload=True, directory=None)

def test_main_missing_required_yaml_path():
    """Test that the CLI fails if the required yaml_path argument is missing."""
    result = runner.invoke(app, [])

    # Should exit with a non-zero exit code
    assert result.exit_code != 0

    # Should mention the missing 'YAML_PATH' argument in the help/error
    assert "Missing argument 'YAML_PATH'" in result.output

def test_report_generation_success(mock_ctx, mock_yaml_path, mock_report):
    """Test that the report generation works as expected"""
    with patch('indra.fetch.ecpds.last_date_of_ecpds_data', return_value=datetime(2024, 1, 1)), \
         patch('indra.fetch.ecpds.construct_ecpds_urls', return_value=["test_url"]), \
         patch('indra.fetch.ecpds.download_from_url', return_value=True), \
         patch('indra.fetch.ecpds.upload_data_to_s3', return_value=0), \
         patch('indra.fetch.ecpds.tempfile.TemporaryDirectory') as mock_tempdir, \
         patch('indra.fetch.ecpds.Report') as MockReport:

        mock_tempdir.return_value.__enter__.return_value = "tempdir"
        MockReport.return_value = mock_report()
        main(ctx=mock_ctx, yaml_path=mock_yaml_path, get_latest_date=True, custom_date=None, upload=True, directory=None)
        MockReport.return_value.send_email.assert_called_once()

def test_report_generation_error(mock_ctx, mock_yaml_path, mock_report):
    """Test that the report generation works as expected"""
    with patch('indra.fetch.ecpds.last_date_of_ecpds_data', return_value=datetime(2024, 1, 1)), \
         patch('indra.fetch.ecpds.construct_ecpds_urls', return_value=["test_url"]), \
         patch('indra.fetch.ecpds.download_from_url', return_value=False), \
         patch('indra.fetch.ecpds.upload_data_to_s3', return_value=0), \
         patch('indra.fetch.ecpds.tempfile.TemporaryDirectory') as mock_tempdir, \
         patch('indra.fetch.ecpds.Report') as MockReport:

        mock_tempdir.return_value.__enter__.return_value = "tempdir"
        MockReport.return_value = mock_report()

        main(ctx=mock_ctx, yaml_path=mock_yaml_path, get_latest_date=True, custom_date=None, upload=True, directory=None)
        MockReport.return_value.send_email.assert_called_once()

def test_report_generation_critical_failure(mock_ctx, mock_yaml_path, mock_report):
    """Test that the report generation works as expected"""
    with patch('indra.fetch.ecpds.last_date_of_ecpds_data', return_value=None), \
         patch('indra.fetch.ecpds.construct_ecpds_urls', return_value=["test_url"]), \
         patch('indra.fetch.ecpds.download_from_url', return_value=True), \
         patch('indra.fetch.ecpds.upload_data_to_s3', return_value=0), \
         patch('indra.fetch.ecpds.tempfile.TemporaryDirectory') as mock_tempdir, \
         patch('indra.fetch.ecpds.Report') as MockReport:

        mock_tempdir.return_value.__enter__.return_value = "tempdir"
        MockReport.return_value = mock_report()

        main(ctx=mock_ctx, yaml_path=mock_yaml_path, get_latest_date=True, custom_date=None, upload=True, directory=None)
        MockReport.return_value.send_email.assert_called_once()

def test_email_attachment_logic(mock_ctx, mock_yaml_path, mock_report):
    """Test that the email attachment logic is triggered correctly"""
    with patch('indra.fetch.ecpds.last_date_of_ecpds_data', return_value=datetime(2024, 1, 1)), \
         patch('indra.fetch.ecpds.construct_ecpds_urls', return_value=["test_url"]), \
         patch('indra.fetch.ecpds.download_from_url', return_value=True), \
         patch('indra.fetch.ecpds.upload_data_to_s3', return_value=0), \
         patch('indra.fetch.ecpds.tempfile.TemporaryDirectory') as mock_tempdir, \
         patch('indra.fetch.ecpds.Report') as MockReport:

        mock_tempdir.return_value.__enter__.return_value = "tempdir"
        MockReport.return_value = mock_report()

        main(ctx=mock_ctx, yaml_path=mock_yaml_path, get_latest_date=True, custom_date=None, upload=True, directory=None)
        MockReport.return_value.add_attachment.assert_called_with("logs/test.log")  # Check for attachement of the log file

def test_report_creation_error(mock_ctx, mock_yaml_path):
    """Test that an exception in Report creation is handled gracefully"""
    with patch('indra.fetch.ecpds.last_date_of_ecpds_data', return_value=datetime(2024, 1, 1)), \
         patch('indra.fetch.ecpds.construct_ecpds_urls', return_value=["test_url"]), \
         patch('indra.fetch.ecpds.download_from_url', return_value=True), \
         patch('indra.fetch.ecpds.upload_data_to_s3', return_value=0), \
         patch('indra.fetch.ecpds.tempfile.TemporaryDirectory') as mock_tempdir, \
         patch('indra.fetch.ecpds.Report', side_effect=Exception("Report creation failed")):

        mock_tempdir.return_value.__enter__.return_value = "tempdir"

        with pytest.raises(Exception, match="Report creation failed"):
            main(ctx=mock_ctx, yaml_path=mock_yaml_path, get_latest_date=True, custom_date=None, upload=True, directory=None)

def test_temporary_directory_creation(mock_ctx, mock_yaml_path, mock_report):
    """Test that a temporary directory is created when no custom directory is given."""
    with patch('indra.fetch.ecpds.last_date_of_ecpds_data', return_value=datetime(2024, 1, 1)), \
         patch('indra.fetch.ecpds.construct_ecpds_urls', return_value=["test_url"]), \
         patch('indra.fetch.ecpds.download_from_url', return_value=True), \
         patch('indra.fetch.ecpds.upload_data_to_s3', return_value=0), \
         patch('indra.fetch.ecpds.tempfile.TemporaryDirectory') as mock_tempdir, \
         patch('indra.fetch.ecpds.Report') as MockReport:

        mock_tempdir.return_value.__enter__.return_value = "tempdir"
        MockReport.return_value = mock_report()

        main(ctx=mock_ctx, yaml_path=mock_yaml_path, get_latest_date=True,
             custom_date=None, upload=True, directory=None)

        mock_tempdir.assert_called_once()

def test_custom_directory_usage(mock_ctx, mock_yaml_path, mock_report):
    """Test that a custom directory path is used instead of a temp dir."""
    with patch('indra.fetch.ecpds.last_date_of_ecpds_data', return_value=datetime(2024, 1, 1)), \
         patch('indra.fetch.ecpds.construct_ecpds_urls', return_value=["test_url"]), \
         patch('indra.fetch.ecpds.download_from_url', return_value=True), \
         patch('indra.fetch.ecpds.upload_data_to_s3', return_value=0), \
         patch('indra.fetch.ecpds.os.makedirs') as mock_makedirs, \
         patch('indra.fetch.ecpds.Report') as MockReport:

        MockReport.return_value = mock_report()
        custom_directory = "custom_dir"

        main(ctx=mock_ctx, yaml_path=mock_yaml_path, get_latest_date=True,
             custom_date=None, upload=True, directory=custom_directory)

        mock_makedirs.assert_called()  # Optionally check for specific path logic

def test_file_download_verification(mock_ctx, mock_yaml_path, mock_report):
    """Test that downloaded files are verified for existence."""
    with patch('indra.fetch.ecpds.last_date_of_ecpds_data', return_value=datetime(2024, 1, 1)), \
         patch('indra.fetch.ecpds.construct_ecpds_urls', return_value=["test_url"]), \
         patch('indra.fetch.ecpds.download_from_url', return_value=True), \
         patch('indra.fetch.ecpds.upload_data_to_s3', return_value=0), \
         patch('indra.fetch.ecpds.tempfile.TemporaryDirectory') as mock_tempdir, \
         patch('indra.fetch.ecpds.os.path.exists', return_value=True) as mock_exists, \
         patch('indra.fetch.ecpds.Report') as MockReport:

        mock_tempdir.return_value.__enter__.return_value = "tempdir"
        MockReport.return_value = mock_report()

        main(ctx=mock_ctx, yaml_path=mock_yaml_path, get_latest_date=True,
             custom_date=None, upload=True, directory=None)

        mock_exists.assert_called()


@pytest.mark.integration
def test_email_reporting_integration(mock_ctx, integration_setup, mock_report):
    mock_yaml_path, test_dir, test_file = integration_setup

    with patch('indra.fetch.ecpds.last_date_of_ecpds_data', return_value=datetime(2024, 1, 1)), \
         patch('indra.fetch.ecpds.construct_ecpds_urls', return_value=[str(test_file)]), \
         patch('indra.fetch.ecpds.download_from_url', return_value=True), \
         patch('indra.fetch.ecpds.upload_data_to_s3', return_value=0), \
         patch('indra.fetch.ecpds.tempfile.TemporaryDirectory') as mock_tempdir, \
         patch('indra.fetch.ecpds.Report') as MockReport:

        mock_tempdir.return_value.__enter__.return_value = str(test_dir)
        mock_report.send_email = MagicMock()
        MockReport.return_value = mock_report

        main(ctx=mock_ctx, yaml_path=mock_yaml_path, get_latest_date=True, custom_date=None, upload=True, directory=str(test_dir))
        mock_report.send_email.assert_called_once()
