# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

from __future__ import with_statement

import distribute_setup
distribute_setup.use_setuptools()

import os, os.path, subprocess

# disables creation of .DS_Store files inside tarballs on Mac OS X
os.environ['COPY_EXTENDED_ATTRIBUTES_DISABLE'] = 'true'
os.environ['COPYFILE_DISABLE'] = 'true'

def relative_path(path):
	return os.path.join(os.path.dirname(__file__), path)

def get_tagged_version():
	if(os.path.exists(relative_path('VERSION'))):
		with open(relative_path('VERSION'), 'rU') as f:
			version = f.read().strip()
	else:
		proc = subprocess.Popen(['git', 'describe', '--tags'],
			stderr	= subprocess.PIPE,
			stdout	= subprocess.PIPE,
			cwd		= os.path.dirname(__file__) or None
		)
		(stdoutdata, stderrdata) = proc.communicate()
		if(proc.returncode):
			raise RuntimeError(stderrdata)
		version = stdoutdata.strip().lstrip('v')
		
		print "writing version file..."
		with open(relative_path('VERSION'), 'w') as f:
			f.write(version)
	print 'package version: %s' % version
	return version

def autosetup():
	from setuptools import setup, find_packages
	return setup(
		name			= "django-salesforce",
		version			= get_tagged_version(),
		
		include_package_data = True,
		zip_safe		= False,
		packages		= find_packages(),
		
		entry_points	= {
			'setuptools.file_finders'	: [
				'git = setuptools_git:gitlsfiles',
			],
		},
		
		install_requires = open(relative_path('requirements.txt'), 'rU'),
		
		# metadata for upload to PyPI
		author			 = "Freelancers Union",
		author_email	 = "devs@freelancersunion.org",
		maintainer		 = "Phil Christensen",
		maintainer_email = "phil@bubblehouse.org",
		description		 = "a Salesforce backend for Django's ORM",
		license			 = "MIT",
		keywords		 = "django salesforce orm backend",
		url				 = "https://github.com/freelancersunion/django-salesforce",
	)

if(__name__ == '__main__'):
	dist = autosetup()
