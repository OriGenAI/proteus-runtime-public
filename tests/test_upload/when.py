from pytest_bdd import when

from proteus import Proteus
from .given import File


@when("a file is uploaded via .api.post_file")
def upload_a_file(proteus: Proteus, file: File, upload_file_url: str):
    proteus.api.post_file(upload_file_url, filepath=file.name, content=file.content)
