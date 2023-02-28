from functools import wraps


class Reporting:
    """Unifies logging and reporting to status API"""

    def __init__(self, logger, api=None):
        self.logger = logger
        self.api = api

    def ensure_failed_is_reported(self, fn):
        @wraps(fn)
        def _(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except SystemExit as error:
                if error.code != 0:
                    self.send(status="failed", message="Exit status different than 0")
                raise
            except BaseException as error:
                self.send(status="failed", message=str(error))
                raise

        return _

    def ensure_finished_is_reported(self, fn):
        @wraps(fn)
        def _(*args, **kwargs):
            fn(*args, **kwargs)
            self.send(
                "Begin configuration validation process",
                status="completed",
                progress=100,
            )

    def send(
        self,
        message,
        status="processing",
        progress=0,
        result=None,
        total=None,
        number=None,
    ):
        """Logs a message to the standard output on INFO level and calls inner
        report method to the worker authenticated.

        Args:
            message (str): The message of the log/report
            status (str): The status to report
            progress (int): The progress of the job
            result (dict): The result of the job
            total (int): The total elements of the job
            number (int): The number of actual elements completed
        """
        assert status is not None, "Status can't be set to None"
        self.logger.info(
            message,
            extra={"status": status, "progress": progress, "result": result},
        )

        self._report(
            self.api.auth.worker_uuid,
            set_status=str(status),
            message=message,
            progress=progress,
            result=result,
            total=total,
            number=number,
        )

    def _report(
        self,
        worker_uuid,
        set_status="processing",
        message=None,
        progress=0,
        result=None,
        total=None,
        number=None,
    ):
        """Creates a report based on the provided data and posts it through
        the given api instance.

        Args:
            worker_uuid (UUID): The uuid of the worker
            message (str): The message to report
            status (str): The status to report
            progress (int): The progress of the job
            result (dict): The result of the job
            total (int): The total elements of the job
            number (int): The number of actual elements completed

        Returns:
            the api response
        """
        status_url = f"/api/v1/jobs/{worker_uuid}/status"
        data = {
            "set_status": set_status,
            "progress": progress,
        }
        report = {}
        if message is not None:
            report["message"] = message
        if result is not None:
            report["result"] = result
        report["number"] = number
        report["total"] = total
        data["report"] = report
        response = self.api.post(status_url, data, retry=True)
        self.api.raise_for_status(response)
        return response
