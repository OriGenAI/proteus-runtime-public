from functools import wraps
import time

from .logger import logger


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
