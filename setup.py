# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

import os
import re
import subprocess

# disables creation of .DS_Store files inside tarballs on Mac OS X
os.environ['COPY_EXTENDED_ATTRIBUTES_DISABLE'] = 'true'
os.environ['COPYFILE_DISABLE'] = 'true'

def relative_path(path):
    """
    Return the given path relative to this file.
    """
    return os.path.join(os.path.dirname(__file__), path)

def get_tagged_version():
    """
    Determine the current version of this package.

    Precise long version numbers are used with Git, that contain Git tag,
    the commit serial and a short commit id,
    otherwise a short version number is used if installed from Pypi.
    """
    with_git = os.path.isdir(relative_path('.git'))
    if with_git:
        proc = subprocess.Popen(
            ['git', 'describe', '--tags'],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            cwd=os.path.dirname(__file__) or None
        )
        (stdoutdata, stderrdata) = proc.communicate()
        if proc.returncode == 0:
            version = stdoutdata.decode("utf-8").strip().lstrip('v')
            return version

    with open(relative_path('salesforce/__init__.py'), 'r') as fd:
        version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                            fd.read(), re.MULTILINE).group(1)
    return version

def autosetup():
    from setuptools import setup, find_packages

    with open(relative_path('requirements.txt'), 'rU') as f:
        requirements_txt = f.read().split("\n")

    # check if installed with git data (not via PyPi)
    with_git = os.path.isdir(relative_path('.git'))

    return setup(
        name="django-salesforce",
        version=get_tagged_version(),

        include_package_data=True,
        zip_safe=False,
        packages=find_packages(exclude=['tests', 'tests.*']),

        # setuptools won't auto-detect Git managed files without this
        setup_requires=["setuptools_git >= 0.4.2"] if with_git else [],

        install_requires=requirements_txt,

        # metadata for upload to PyPI
        author="Freelancers Union",
        author_email="devs@freelancersunion.org",
        maintainer="Phil Christensen",
        maintainer_email="phil@bubblehouse.org",
        description="a Salesforce backend for Django's ORM",
        license="MIT",
        keywords="django salesforce orm backend",
        url="https://github.com/django-salesforce/django-salesforce",
    )

if __name__ == '__main__':
    dist = autosetup()
