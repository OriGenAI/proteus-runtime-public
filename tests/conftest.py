import jwt
import pytest
from requests.models import Response

from proteus.config import Config


@pytest.fixture
def session(requests_mock):
    config = Config()

    json = {
        "access_token": jwt.encode(payload={}, key="", algorithm="HS256"),
        "refresh_token": jwt.encode(payload={}, key="", algorithm="HS256"),
        "expires_in": 300,
        "refresh_expires_in": 1800,
    }
    return requests_mock.post(f"{config.auth_host}/auth/realms/origen/protocol/openid-connect/token", json=json)


@pytest.fixture
def access_token_mock(mocker):
    return mocker.patch(
        "proteus.oidc.OIDC.access_token",
        return_value=jwt.encode(payload={}, key="", algorithm="HS256"),
        new_callable=mocker.PropertyMock,
    )


@pytest.fixture
def mocked_api_get(mocker):
    mock = mocker.patch("requests.get", return_value=Response())
    mock.return_value.status_code = 200
    mock.return_value._content = b"Test content"
    return mock


@pytest.fixture
def mocked_api_post(mocker):
    mock = mocker.patch("requests.post", return_value=Response())
    mock.return_value.status_code = 200
    mock.return_value._content = b'{"file": {}}'
    return mock
