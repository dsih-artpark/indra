from datetime import datetime, time, timedelta, timezone
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from indra.fetch.ecpds import construct_ecpds_urls, last_date_of_ecpds_data

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
    #Test when previous date is not in the dates list
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
