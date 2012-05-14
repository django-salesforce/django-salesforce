# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

from __future__ import with_statement

import distribute_setup
distribute_setup.use_setuptools()

import os

# disables creation of .DS_Store files inside tarballs on Mac OS X
os.environ['COPY_EXTENDED_ATTRIBUTES_DISABLE'] = 'true'
os.environ['COPYFILE_DISABLE'] = 'true'

def get_requirements(filename='requirements.txt'):
	with open(os.path.join(os.path.dirname(__file__), filename), 'rU') as f:
		return f.read().split('\n')

def autosetup():
	from setuptools import setup, find_packages
	return setup(
		name			= "django-salesforce",
		version			= "0.1",
		
		include_package_data = True,
		zip_safe		= False,
		packages		= find_packages(),
		
		entry_points	= {
			'setuptools.file_finders'	: [
				'git = setuptools_git:gitlsfiles',
			],
		},
		
		install_requires = get_requirements(),
		
		# metadata for upload to PyPI
		author			= "Phil Christensen",
		author_email	= "phil@bubblehouse.org",
		description		= "a Salesforce backend for Django's ORM",
		license			= "MIT",
		keywords		= "django salesforce orm backend",
		url				= "https://github.com/philchristensen/django-salesforce",
	)

if(__name__ == '__main__'):
	dist = autosetup()
