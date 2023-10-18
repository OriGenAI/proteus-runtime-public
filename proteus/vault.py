import requests
from requests.exceptions import HTTPError


class Vault:
    def __init__(self, proteus):
        self.proteus = proteus
        self._vault_token = None

    def authenticate_with_jwt(self, auth):
        headers = {
            "Content-Type": "application/json",
        }
        url = f"v1/auth/jwt-{self.proteus.config.realm}/login"
        data = {"jwt": auth.access_token, "role": "worker"}
        response = requests.post(f"{self.proteus.config.vault_host}/{url}", headers=headers, json=data)
        self.proteus.api.raise_for_status(response)
        self.set_token(
            token=response.json().get("auth").get("client_token"),
            username=self.proteus.auth.who,
            user_type="proteus_jwt",
        )
        return self

    def authenticate_with_userpass(self, username, password):
        headers = {
            "Content-Type": "application/json",
        }
        url = f"v1/auth/userpass/login/{username}"
        data = {"password": password}
        response = requests.post(f"{self.proteus.config.vault_host}/{url}", headers=headers, json=data)
        self.proteus.api.raise_for_status(response)
        token = response.json().get("auth").get("client_token")
        return self.set_token(token, username=username, user_type="vault_user")

    def set_token(self, token, username=None, user_type=None):
        self._vault_user_type = user_type
        self._vault_user = username
        self._vault_token = token
        return self

    @property
    def is_logged_in(self):
        return bool(self._vault_token)

    def get_config(self, image_ref):
        assert self._vault_token is not None, "Run authenticate_with_jwt/authenticate_with_userpass before"
        headers = {
            "X-Vault-Token": self._vault_token,
            "Content-Type": "application/json",
        }
        url = f"v1/epyc-keys/data/{image_ref}"
        self.proteus.logger.info(f"requesting key {self.proteus.config.vault_host}/{url}")
        response = requests.get(f"{self.proteus.config.vault_host}/{url}", headers=headers)

        try:
            self.proteus.api.raise_for_status(response)
            response_json = response.json()
            data = response_json.get("data")
        except HTTPError as e:
            status_code = getattr(e.response, "status_code")
            if status_code == 403 and self._vault_user and self._vault_user_type:
                raise RuntimeError(
                    f'User "{self._vault_user}" of type "{self._vault_user_type}" is not allowed to access {image_ref}'
                ) from e

            if status_code != 404:
                raise

            self.proteus.logger.warn(
                f"Received status 404 when trying to retrieve vault key {image_ref}, the key doesn't exists"
            )
            data = None

        if data is not None and "data" in data:
            data = data.get("data")
        return data

    def save_config(self, image_ref, config):
        vault_token = self._vault_token
        headers = {
            "X-Vault-Token": vault_token,
            "Content-Type": "application/json",
        }
        url = f"v1/epyc-keys/data/{image_ref}"
        response = requests.post(f"{self.proteus.config.vault_host}/{url}", headers=headers, json=dict(data=config))
        self.proteus.api.raise_for_status(response)
        assert response.status_code in [
            200,
            201,
        ], "Cant confirm key assigment on vault"
        return response.json().get("data")
