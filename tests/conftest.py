import os
import pytest
from dotenv import load_dotenv
from requests.models import Response
from proteus import login as api_login


@pytest.fixture
def session():
    load_dotenv(".testenv")
    user = os.getenv("PROTEUS_USERNAME", "user-not-configured")
    password = os.getenv("PROTEUS_PASSWORD", "password-not-configured")
    return api_login(username=user, password=password, auto_update=False)


@pytest.fixture
def mocked_api_get(mocker):
    mock = mocker.patch("proteus.api.get")
    mock.return_value = Response()
    mock.return_value.status_code = 200
    mock.return_value._content = b"Test content"
    return mock


@pytest.fixture
def mocked_api_post(mocker):
    mock = mocker.patch("proteus.api.post")
    mock.return_value = Response()
    return mock


@pytest.fixture
def mocked_response(mocker):
    mock = mocker.patch("requests.models.Response.raise_for_status")
    mock.return_value = None
    return mock
