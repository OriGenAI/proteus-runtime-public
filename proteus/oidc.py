import base64
import json
import re
from threading import Timer, Lock
from urllib.parse import urlparse

import certifi
import requests
from black import contextmanager
from requests import HTTPError

from proteus.utils import get_random_string


class RepeatTimer(Timer):
    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)


WORKER_USERNAME_RE = re.compile(r"r-(?P<uuid>[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12})(@.*)?")


def is_worker_username(username):
    return WORKER_USERNAME_RE.match(username) is not None


class OIDC:
    def __init__(
        self,
        proteus,
    ):
        self.proteus = proteus

        self.set_config()

        self._access_token_locked = Lock()
        self._last_res = None
        self._refresh_timer = None
        self._when_login_callback = None
        self._when_refresh_callback = None
        self._update_credentials()
        self._i_am_robot = False

        # Register insists
        self.send_login_request = proteus.may_insist_up_to(3, delay_in_secs=1)(self.send_login_request)
        self.send_login_request = proteus.may_insist_up_to(5, delay_in_secs=1)(self.send_refresh_request)

        self.admin = OIDCAdmin(self)

    _username = None

    def set_config(
        self,
        host: str = None,
        realm: str = None,
        client_id: str = None,
        client_secret: str = None,
        username: str = None,
        password: str = None,
    ):
        self.host = host or self.proteus.config.auth_host
        self.realm = realm or self.proteus.config.realm

        self.client_id = client_id or self.proteus.config.client_id
        self.client_secret = client_secret or self.proteus.config.client_secret

        self.username = username or self.proteus.config.username
        self.password = password or self.proteus.config.password

        self.stop()

        self._i_am_robot = None

        self._oidc_config = None

        self._access_token = None
        self._refresh_token = None
        self._expires_in = None
        self._resfresh_expires_in = None

    @contextmanager
    def override_config(self, **kwargs):
        self.set_config(**kwargs)
        yield
        self.set_config()

    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, val):
        self._username = val

        if self._username:
            self._i_am_robot = is_worker_username(self._username)

    def _update_credentials(
        self,
        access_token=None,
        refresh_token=None,
        expires_in=None,
        refresh_expires_in=None,
        **_,
    ):
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._expires_in = expires_in
        self._resfresh_expires_in = refresh_expires_in

    @property
    def access_token(self):
        with self._access_token_locked:
            return self._access_token

    @property
    def access_token_parsed(self):
        _header, payload, _sig = self.access_token.split(".")
        payload = payload + "=" * divmod(len(payload), 4)[1]
        return json.loads(base64.urlsafe_b64decode(payload))

    @property
    def refresh_token(self):
        return self._refresh_token

    @property
    def host(self):
        return self._host

    @host.setter
    def host(self, host_or_url):
        self._host = urlparse(host_or_url).hostname or host_or_url

    @property
    def expires_in(self):
        return self._expires_in

    @property
    def refresh_expires_in(self):
        return self._resfresh_expires_in

    _oidc_config = None

    @property
    def oidc_config(self):
        if self._oidc_config is None:
            self._oidc_config = {"is_url_legacy": True}

            try:
                response = requests.get(self.url_oidc_config)
                self.proteus.api.raise_for_status(response)
            except HTTPError:
                self._oidc_config = {"is_url_legacy": False}

                response = requests.get(self.url_oidc_config)

            try:
                self.proteus.api.raise_for_status(response)
            except HTTPError:
                self._oidc_config = None
                raise

            real_is_url_legacy = self._oidc_config["is_url_legacy"]
            self._oidc_config = response.json()
            self._oidc_config["is_url_legacy"] = real_is_url_legacy

        return self._oidc_config

    @property
    def is_url_legacy(self):
        return self.oidc_config["is_url_legacy"]

    @property
    def base_url(self):
        return self.base_url_legacy if self.is_url_legacy else f"https://{self.host}"

    @property
    def base_url_legacy(self):
        return f"https://{self.host}/auth"

    @property
    def url_realm(self):
        return f"{self.base_url}/realms/{self.realm}"

    @property
    def url_realm_admin(self):
        return f"{self.base_url}/admin/realms/{self.realm}"

    @property
    def url_oidc_config(self):
        return self.url_realm + "/.well-known/openid-configuration"

    @property
    def url_token(self):
        return self.url_realm + "/protocol/openid-connect/token"

    @property
    def url_certs(self):
        return self.url_realm + "/protocol/openid-connect/certs"

    def when_login(self, callback):
        self._when_login_callback = callback

    def when_refresh(self, callback):
        self._when_refresh_callback = callback

    # @may_insist_up_to(3, delay_in_secs=1)
    def send_login_request(self, login):
        response = requests.post(
            self.url_token,
            data=login,
            verify=certifi.where(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code == 401:
            # No need to be blunt
            return None
        self.proteus.api.raise_for_status(response)
        return response

    def do_login(self, password=None, username=None, auto_update=True):

        self.username = self.username if username is None else username
        self.password = self.password if password is None else password

        login = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
            "client_id": self.client_id,
        }
        if self.client_secret is not None:
            login["client_secret"] = self.client_secret
        response = self.send_login_request(login)
        self.proteus.api.raise_for_status(response)

        credentials = response.json()
        assert "access_token" in credentials
        if self._when_login_callback is not None:
            self._when_login_callback()
        self._update_credentials(**credentials)
        if auto_update is True:
            self.prepare_refresh()
        return True

    def prepare_refresh(self):
        assert self.expires_in is not None

        def perform_refresh():
            self.do_refresh()

        self._refresh_timer = RepeatTimer(self.expires_in - self.proteus.config.refresh_gap, perform_refresh)
        self._refresh_timer.start()

    # @may_insist_up_to(5, delay_in_secs=1)
    def send_refresh_request(self, refresh):
        response = requests.post(
            self.url_token,
            data=refresh,
            verify=certifi.where(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.proteus.api.raise_for_status(response)
        return response

    def do_refresh(self):
        assert self.refresh_token is not None
        self._access_token_locked.acquire()
        refresh = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
        }
        if self.client_secret is not None:
            refresh["client_secret"] = self.client_secret
        try:
            response = self.send_refresh_request(refresh)
            credentials = response.json()
            assert credentials.get("access_token") is not None
            self._update_credentials(**credentials)
        except Exception:
            self.proteus.logger.error("Failed to refresh token, re-loging againg")
            return self.do_login(auto_update=False)
        finally:
            self._access_token_locked.release()
        if self._when_refresh_callback is not None:
            self._when_refresh_callback()

    def stop(self):
        if getattr(self, "_refresh_timer", None) is not None:
            self._refresh_timer.cancel()

    @property
    def am_i_robot(self):
        return self._i_am_robot

    @property
    def who(self):
        if self.access_token is None:
            return None
        parsed_token = self.access_token_parsed
        if self.am_i_robot:
            unit_name = parsed_token.get("preferred_username")
            return f"unit {unit_name}"
        return parsed_token.get("given_name")

    @property
    def worker_uuid(self):
        if self.proteus.config.worker_uuid:
            return self.proteus.config.worker_uuid
        if self.am_i_robot:
            username = self.access_token_parsed.get("preferred_username")
            robot_match = WORKER_USERNAME_RE.match(username)
            if robot_match is not None:
                return robot_match.groupdict().get("uuid")
        return None


class OIDCAdmin:
    def __init__(
        self,
        oidc: OIDC,
    ):
        self.auth = oidc

    def search_username_id(self, username):
        response = requests.get(
            f"{self.auth.url_realm_admin}/users",
            params={"username": username},
            verify=certifi.where(),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.auth.access_token),
            },
        )

        self.auth.proteus.api.raise_for_status(response)

        results = response.json()
        if len(results) == 0:
            raise RuntimeError(f"User {username} not found")

        if len(results) > 1:
            raise RuntimeError(f"More than one user with username {username}")

        return results[0].get("id")

    def change_password(self, username, password):
        assert self.auth is not None

        id_ = self.search_username_id(username)

        update = {"credentials": [{"type": "password", "temporary": False, "value": password}]}
        response = requests.put(
            f"{self.auth.url_realm_admin}/users/{id_}",
            json=update,
            verify=certifi.where(),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.auth.access_token),
            },
        )

        self.auth.proteus.api.raise_for_status(response)
        return username, password

    def create(self, username, email, /, roles=tuple(), password=None):
        assert self.auth is not None

        url = f"{self.auth.url_realm_admin}/users"
        password = get_random_string(32) if password is None else password

        creation = {
            "enabled": "true",
            "username": username,
            "credentials": [{"type": "password", "temporary": False, "value": password}],
            "realmRoles": list(roles),
            "groups": roles,
            "email": email,
        }

        response = requests.post(
            url,
            json=creation,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.auth.access_token),
            },
        )

        if response.status_code == 409:
            return self.change_password(username, password)

        self.auth.proteus.api.raise_for_status(response)

        if response.status_code != 201:
            raise RuntimeError(f"could not confirm user creation: {creation} " f"on {url}. {self.auth.access_token}")

        return username, password
