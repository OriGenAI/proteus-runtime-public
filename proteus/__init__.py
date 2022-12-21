import sys
from functools import wraps

from .config import Config
from .oidc import OIDC, is_worker_username
from .api import API
from .reporting import Reporting

from .logger import initialize_logger
from .decorators import may_insist_up_to


class Proteus:
    def __init__(self, config: Config = None) -> None:
        self.config = config or Config()
        self.logger = initialize_logger(self.config.log_loc)
        self.auth = OIDC(self.config, self.logger)
        self.api = API(self.auth, self.config, self.logger)
        self.reporting = Reporting(self.logger, self.api)

    def runs_authentified(self, func):
        """Decorator that authentifies and keeps token updated during execution."""

        @wraps(func)
        def wrapper(user, password, *args, **kwargs):
            try:
                terms = dict(username=user, password=password, auto_update=True)
                is_worker = is_worker_username(user)
                authentified = self.auth.do_worker_login(**terms) if is_worker else self.auth.do_login(**terms)
                if not authentified:
                    self.logger.error("Authentication failure, exiting")
                    sys.exit(1)
                self.logger.info(f"Welcome, {self.auth.who}")
                return func(*args, **kwargs)
            finally:
                self.auth.stop()

        return wrapper

    def may_insist_up_to(self, times: int, delay_in_secs: int = 0):
        return may_insist_up_to(times, delay_in_secs, logger=self.logger)

    def login(self, **kwargs):
        self.auth.do_login(**kwargs)
        return self.auth

    def iterate_pagination(self, response, current=0):
        assert response.status_code == 200
        data = response.json()
        total = data.get("total")
        for item in data.get("results"):
            yield item
            current += 1
        if current < total:
            next_ = data.get("next")
            return self.iterate_pagination(self.api.get(next_), current=current)
