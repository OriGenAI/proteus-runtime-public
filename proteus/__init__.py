import sys
import time
from functools import wraps

from .api import API
from .config import Config
from .logger import initialize_logger
from .oidc import OIDC, is_worker_username
from .reporting import Reporting
from .runs import Runs
from .vault import Vault


class Proteus:
    def __init__(self, config: Config = None) -> None:
        self.config = config or Config()
        self.logger = initialize_logger(self.config.log_loc)
        self.auth = OIDC(self.config, self)
        self.api = API(self, self.auth, self.config, self.logger)
        self.reporting = Reporting(self.logger, self.api)
        self.runs = Runs(self)
        self.vault = Vault(self)

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

    def may_insist_up_to(self, times=None, delay_in_secs=None, logger=None):
        logger = logger or self.logger
        delay_in_secs = delay_in_secs if delay_in_secs is not None else self.config.default_retry_wait
        times = times if times is not None else self.config.default_retry_times
        times = times or 1

        def will_retry_if_fails(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                failures = 0
                while True:
                    try:
                        res = fn(*args, **kwargs)
                        if failures > 0:
                            logger.warning(
                                f'Call to function "{fn.__name__}" was successful '
                                f"after {failures} failed "
                                f"attemp{'' if failures == 1 else 's' }"
                            )
                        return res
                    except BaseException:
                        failures += 1
                        if failures < times:
                            time.sleep(delay_in_secs)
                        else:
                            raise

            return wrapped

        return will_retry_if_fails

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
