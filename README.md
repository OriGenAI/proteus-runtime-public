## Install and setup

### 1. Clone the project into the desired directory.

```
git clone git@github.com:OriGenAI/proteus-runtime.git
```


### 2. Install and setup enviroment

```
poetry env use `which python3.8`
poetry shell
poetry install
```

### 3. Usage

#### Reporting

The Reporting class is created given an api instance:

```
reporting = Reporting(api_instance)
```

To report to the api usage, is mandatory to have an API instance and a logged worker.

Available methods:

- __send__:
    Logs a message to the standard output on INFO level and calls inner report method to the worker authenticated.

    Params:
    - message(str): The message of the log/report
    - status(str)="processing": The status to report
    - progress(int)=0: The progress of the job
    - result(dict)=None: The result of the job
    - total(int)=None: The total elements of the job
    - number(int)=None: The number of actual elements completed

    Usage:
    ```
    reporting.send("Msg to report", "completed", progress=100,result={"output": [...]}, total=20, number=20)
    ```

#### Logging

For the correct usage of the module, a logging.ini file should be placed on the root of the project that is using this package. This will allow the parametrization of the logging module within, including the log file generation, the format, the log level...

Usage:
```
logger.info("Info msg")   
logger.error("Error msg", exc_info=True, extra={"user_data": "vip-user"})
logger.debug("Debug msg")
logger.exception("Exception msg")
```

#### API

The API class has methods to interact with the proteus API, aswell as storing capabilities when handling file downloads.

Available methods:

- __get__:
    API get request.

    Params:
    - url(str): The url to request
    - headers(dict)=None: Headers of the request
    - stream(boolean)=False: If the get response will be streamed
    - **query_args: Additional arguments

    Usage:
    ```
    api.get("sampling/...", headers={"Content-Type": "application/json"}, stream=False)
    ```

- __post__:
    API post request.

    Params:
    - url(str): The url to request
    - data(dict): The data of the request
    - headers(dict)=None: Headers of the request

    Usage:
    ```
    api.post("sampling/...", data={"result": "Example data"}, headers={})
    ```

- __put__:
    API put request.

    Params:
    - url(str): The url to request
    - data(dict): The data of the request
    - headers(dict)=None: Headers of the request

    Usage:
    ```
    api.put("sampling/...", data={"result": "Example data"}, headers={})
    ```

- __post_file__:
    API post request for files.

    Params:
    - url(str): The url to request
    - filepath(str): The path of the file
    - content(binary)=None: Content of the file
    - modified(datetime)=None: Last file modified date

    Usage:
    ```
    api.post_file("sampling/...", filepath="/training/whatever", content=b"file content", modified=datetime())
    ```

- __download__:
    Download get request.

    Params:
    - url(str): The url to request
    - stream(boolean)=False: If the get response will be streamed
    - timeout(int)=None: Timeout for the get request

    Usage:
    ```
    api.download("sampling/...", timeout=60, stream=False)
    ```

- __store_download__:
    Method for downloading and storing a file in a local path.

    Params:
    - url(str): The url to request
    - localpath(str): The local path of the file
    - localname(str): The name of the file
    - stream(boolean)=True: If the get response will be streamed
    - timeout(int)=60: Timeout for the get request

    Usage:
    ```
    api.store_download("sampling/...", localpath="files/", localname="my-file.txt", stream=True, timeout=60)
    ```

#### OIDC

The OIDC class has methods to manage authentication on the API. Most of the module has inner methods that are not supposed to be used outside its own package. The ones that are convenient to use on other projects are described below.

Available methods:

- __may_insist_up_to__:
    Decorator to manage multiple tries on a function call.

    Params:
    - times(int): The number of tries
    - delay_in_secs(int)=0: The time to wait between tries

    Usage:
    ```
    @may_insist_up_to(5, delay_in_secs=60)
    def my_func(...):
        ...
    ```

### 4. Publishing

In order to publish a package to PyPi, the following steps must be followed:

- The project status that wants to be published needs to be on the private repository dev branch.
    - The project version on pyproject should be updated, or the following steps will not work.
- Push the dev branch to the dev-deploy branch
    - This will trigger a GitHub action that checks the new version, and creates an squashed commit.
    - The action will then push the squashed commit to the branch dev-release.
    - The action will also push to the dev branch on the public repository.
- On the public repository, on release creation, a new version of the repository will be pushed to PyPi.
    - The release creation will trigger a GitHub action that does this process automatically.

This process depends on having the following secrets on GitHub:
#### On the private repository:
- PUBLIC_REPO_TOKEN: Personal Access Token from GitHub. Necessary to publish to the public repository.
#### On the public repository:
- PYPI_API_TOKEN: PyPi token. Necessary to publish to PyPi.