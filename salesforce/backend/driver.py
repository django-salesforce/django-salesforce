"""
Dummy Salesforce driver that simulates some parts of DB API 2
"""
from django.utils.six import PY3

import logging
log = logging.getLogger(__name__)

# All error types described in DB API 2 are implemented the same way as in
# Django 1.6, otherwise some exceptions are not correctly reported in it.


class Error(Exception if PY3 else StandardError):
	pass


class InterfaceError(Error):
	pass


class DatabaseError(Error):
	pass


class DataError(DatabaseError):
	pass


class OperationalError(DatabaseError):
	pass


class IntegrityError(DatabaseError):
	pass


class InternalError(DatabaseError):
	pass


class ProgrammingError(DatabaseError):
	pass


class NotSupportedError(DatabaseError):
	pass


class Connection(object):
	# close and commit can be safely ignored because everything is
	# committed automatically and REST is stateles.
	def close(self):
		pass

	def commit(self):
		pass

	def rollback(self):
		log.info("Rollback is not implemented.")


def connect(**params):
	return Connection()
