from setuptools import setup
import project


with open("requirements/prod.txt") as f:
    requirements = f.read().splitlines()


setup(
    name=project.name,
    version=project.version,
    packages=["proteus"],
    install_requires=requirements,
)
