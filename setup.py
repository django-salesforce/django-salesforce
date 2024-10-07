# minimal dynamic metadata are specified here. Static metadata are in "pyproject.toml".
import os
import setuptools

sf_development = os.path.isfile('.djsf_development')
setuptools.setup(
    install_requires=[
        'django>=2.1' + (',<5.2' if not sf_development else ''),
        'pytz>=2012c',
        'requests>=2.32.0',
    ],
)
