# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

import os, os.path, subprocess

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
	
	We tag all our releases in Git, but we want to be able to distribute
	source packages without having to modify setup.py (and obviously without
	including an entire Git history).
	
	Since we're always creating the sdist from a checked-out Git repo, we
	let setup.py query Git and save it into a VERSION file. All subsequent
	runs of setup.py will read version info out of that file, and not
	attempt to read the current Git tag.
	
	It's therefore important that VERSION never gets checked into Git, and
	that you delete VERSION after creating a source package (or at least
	before making another one for a new version).
	"""
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
		
		version = stdoutdata.decode("utf-8").strip().lstrip('v')
		
		print("writing version file...")
		f = open(relative_path('VERSION'), 'w')
		f.write(version)
		f.close()
	
	print('package version: %s' % version)
	return version

def autosetup():
	from setuptools import setup, find_packages
	return setup(
		name			= "django-salesforce",
		version			= get_tagged_version(),
		
		zip_safe		= False,
		packages		= find_packages(),

		# setuptools won't auto-detect Git managed files without this
		setup_requires = [ "setuptools_git >= 0.4.2", ],
		
		entry_points	= {
			# Dependencies suck, but this is definitely preferable
			# to writing everything into MANIFEST.in by hand.
			'setuptools.file_finders'	: [
				'git = setuptools_git:gitlsfiles',
			],
		},
		
		# okay, so, normally install_requires is a list, right? Well, setuptools
		# really just iterates over it. As it happens, the pip requirements file
		# is in the same format, *and* file objects in python allow you to iterate
		# over them, getting back each line in turn. Why doesn't everyone do this?
		install_requires = open(relative_path('requirements.txt'), 'rU'),
		
		# metadata for upload to PyPI
		author			 = "Freelancers Union",
		author_email	 = "devs@freelancersunion.org",
		description		 = "a Salesforce backend for Django's ORM",
		license			 = "MIT",
		keywords		 = "django salesforce orm backend",
		url				 = "https://github.com/freelancersunion/django-salesforce",
	)

if(__name__ == '__main__'):
	dist = autosetup()
