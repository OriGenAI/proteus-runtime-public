import requests


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
        self._vault_token = response.json().get("auth").get("client_token")
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
        return self.set_token(token)

    def set_token(self, token):
        self._vault_token = token
        return self

    def get_config(self, image_ref):
        assert self._vault_token is not None, "Run authenticate_with_jwt/authenticate_with_userpass before"
        headers = {
            "X-Vault-Token": self._vault_token,
            "Content-Type": "application/json",
        }
        url = f"v1/epyc-keys/data/{image_ref}"
        print(f"requesting key {self.proteus.config.vault_host}/{url}")
        response = requests.get(f"{self.proteus.config.vault_host}/{url}", headers=headers)
        self.proteus.api.raise_for_status(response)
        response_json = response.json()
        print("got response", response)
        data = response_json.get("data")
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
