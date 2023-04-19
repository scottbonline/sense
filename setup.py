from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

version = '{{VERSION_PLACEHOLDER}}'
setup(
    name = 'sense_energy',
    packages = ['sense_energy'], 
    install_requires=[
        'async_timeout>=3.0.1',
        'orjson',
        'requests',
        'websocket-client',
        'websockets;python_version>="3.5"',
        'aiohttp;python_version>="3.5"',
    ], 
    version = version,
    description = 'API for the Sense Energy Monitor',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author = 'scottbonline',
    author_email = 'scottbonline@gmail.com',
    url = 'https://github.com/scottbonline/sense',
    download_url = 'https://github.com/scottbonline/sense/archive/'+version+'.tar.gz',
    keywords = ['sense', 'energy', 'api'], 
    classifiers = [
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ],
)
