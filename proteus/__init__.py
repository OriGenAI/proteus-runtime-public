import sys
from functools import wraps

from .config import config
from .oidc import OIDC, is_worker_username
from .api import API
from .reporting import Reporting

from .logger import logger
from .decorators import may_insist_up_to


auth = OIDC()
api = API(auth)
reporting = Reporting(api)


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
