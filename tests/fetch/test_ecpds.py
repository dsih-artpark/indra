from datetime import datetime, time, timedelta, timezone
from unittest.mock import Mock

import pytest

from indra.fetch.ecpds import last_date_of_ecpds_data


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
    mock.timezone = timezone
    mock.combine = datetime.combine

    return mock

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
