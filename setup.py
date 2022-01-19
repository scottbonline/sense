from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name = 'sense_energy',
    packages = ['sense_energy'], 
    install_requires=[
        'requests',
        'websocket-client',
        'websockets;python_version>="3.5"',
        'aiohttp;python_version>="3.5"',
    ], 
    version = '0.9.6',
    description = 'API for the Sense Energy Monitor',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author = 'scottbonline',
    author_email = 'scottbonline@gmail.com',
    url = 'https://github.com/scottbonline/sense',
    download_url = 'https://github.com/scottbonline/sense/archive/0.9.6.tar.gz',
    keywords = ['sense', 'energy', 'api', 'pytest'], 
    classifiers = [
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ],
)
