import sys
from .config import config
from .oidc import OIDC, is_worker_username
from .api import API
from .reporting import Reporting
from .logger import logger
from functools import wraps
import time

auth = OIDC()
api = API(auth)
reporting = Reporting(api)


def login(**kwargs):
    global auth
    auth.do_login(**kwargs)
    return auth


def iterate_pagination(response, current=0):
    assert response.status_code == 200
    data = response.json()
    total = data.get("total")
    for item in data.get("results"):
        yield item
        current += 1
    if current < total:
        next_ = data.get("next")
        return iterate_pagination(api.get(next_), current=current)


USERNAME, PASSWORD, PROMPT = config.USERNAME, config.PASSWORD, config.PROMPT


def runs_authentified(func):
    """Decorator that authentifies and keeps token updated during execution."""

    @wraps(func)
    def wrapper(user, password, *args, **kwargs):
        global auth
        try:
            terms = dict(username=user, password=password, auto_update=True)
            is_worker = is_worker_username(user)
            authentified = auth.do_worker_login(**terms) if is_worker else auth.do_login(**terms)
            if not authentified:
                logger.error("Authentication failure, exiting")
                sys.exit(1)
            logger.info(f"Welcome, {auth.who}")
            return func(*args, **kwargs)
        finally:
            auth.stop()

    return wrapper


def may_insist_up_to(times, delay_in_secs=0):
    def will_retry_if_fails(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            failures = 0
            while failures < times:
                try:
                    return fn(*args, **kwargs)
                except Exception as error:
                    failures += 1
                    if failures > times:
                        raise error
                    else:
                        time.sleep(delay_in_secs)
            if failures > 0:
                logger.warning(f"The process tried: {failures} times")

        return wrapped

    return will_retry_if_fails
