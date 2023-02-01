import base64
import json
import re
from copy import deepcopy
from threading import Timer, Lock

import certifi
import requests


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
        config,
        proteus,
    ):
        host = config.auth_host

        self.config = deepcopy(config)
        self.proteus = proteus
        self.username = config.username
        self.host = host if host.endswith("/auth") else host + "/auth"
        self.realm = config.realm
        self.client_id = config.client_id
        self.client_secret = config.client_secret
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
        self.do_refresh()
        self._access_token_locked.acquire()
        result = self._access_token
        self._access_token_locked.release()
        return result

    @property
    def access_token_parsed(self):
        _header, payload, _sig = self.access_token.split(".")
        payload = payload + "=" * divmod(len(payload), 4)[1]
        return json.loads(base64.urlsafe_b64decode(payload))

    @property
    def refresh_token(self):
        return self._refresh_token

    @property
    def expires_in(self):
        return self._expires_in

    @property
    def refresh_expires_in(self):
        return self._resfresh_expires_in

    @property
    def url(self):
        path = f"{self.host}/realms/{self.realm}" "/protocol/openid-connect/token"
        return path.format(self=self)

    def when_login(self, callback):
        self._when_login_callback = callback

    def when_refresh(self, callback):
        self._when_refresh_callback = callback

    # @may_insist_up_to(3, delay_in_secs=1)
    def send_login_request(self, login):
        response = requests.post(
            self.url,
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
        login = {
            "grant_type": "password",
            "username": self.username if username is None else username,
            "password": password or self.config.password,
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

    def do_worker_login(self, **terms):
        self.realm = self.realm
        self.client_id = self.client_id
        self.client_secret = self.client_secret
        self._i_am_robot = True
        return self.do_login(**terms)

    def prepare_refresh(self):
        assert self.expires_in is not None

        def perform_refresh():
            self.do_refresh()

        self._refresh_timer = RepeatTimer(self.expires_in - self.config.refresh_gap, perform_refresh)
        self._refresh_timer.start()

    # @may_insist_up_to(5, delay_in_secs=1)
    def send_refresh_request(self, refresh):
        response = requests.post(
            self.url,
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
            return self.do_login()
        finally:
            self._access_token_locked.release()
        if self._when_refresh_callback is not None:
            self._when_refresh_callback()

    def stop(self):
        if self._refresh_timer is not None:
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
        if self.am_i_robot:
            username = self.access_token_parsed.get("preferred_username")
            robot_match = WORKER_USERNAME_RE.match(username)
            if robot_match is not None:
                return robot_match.groupdict().get("uuid")
        return None
