import sys
import time
from functools import wraps

from .api import API
from .bucket import Bucket
from .config import Config
from .logger import initialize_logger
from .oidc import OIDC, is_worker_username
from .reporting import Reporting
from .runs import Runs
from .safe import Safely
from .vault import Vault


class Proteus:
    def __init__(self, config: Config = None) -> None:
        self.config = config or Config()
        self.logger = initialize_logger(self.config.log_loc)
        self.auth = OIDC(self)
        self.api = API(self)
        self.reporting = Reporting(self)
        self.runs = Runs(self)
        self.vault = Vault(self)
        self.bucket = Bucket(self)
        self.safely = Safely(self)

    def runs_authentified(self, func=None, user=None, password=None):
        """Decorator that authentifies and keeps token updated during execution."""

        class RunsAuthentifiedContextManager:
            def __init__(self, runtime: Proteus, ctx_user, ctx_password):
                self.runtime = runtime
                self.ctx_user = ctx_user
                self.ctx_password = ctx_password

            def __enter__(self):
                terms = dict(username=self.ctx_user, password=self.ctx_password, auto_update=True)
                is_worker = is_worker_username(self.ctx_user)
                authentified = (
                    self.runtime.auth.do_worker_login(**terms) if is_worker else self.runtime.auth.do_login(**terms)
                )
                if not authentified:
                    self.runtime.logger.error("Authentication failure, exiting")
                    sys.exit(1)

                self.runtime.logger.info(f"Welcome, {self.runtime.auth.who}")

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.runtime.auth.stop()

        if not func:
            return RunsAuthentifiedContextManager(runtime=self, ctx_user=user, ctx_password=password)

        wrapped_user = user or self.config.username
        wrapped_password = password or self.config.password

        @wraps(func)
        def wrapper(user=wrapped_user, password=wrapped_password, *fn_args, **fn_kwargs):
            with RunsAuthentifiedContextManager(runtime=self, ctx_user=user, ctx_password=password):
                return func(*fn_args, **fn_kwargs)

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
