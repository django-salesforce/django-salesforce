"""
Dummy Salesforce driver that simulates some parts of DB API 2

used by the new Django >= 1.6b2
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
	# committed automatically and REST is stateles. They are
	# unconditionally required by Django 1.6+.

	# Simple transactions are emulated by Python in tests for faster testing.
	# That doesn't allow to modify values created:
	#   - before you call salesforce.test.setUpModule from your setUpModule
	#   - or outside test cases that are subclass of salesforce.test.TestCase
	#     (if you don't use setUpModule)
	# It is not possible to create the deleted object under the same Id, except
	# undelete.
	# We can not e.g. restore a deleted Contact if we can't know which objects
	# were also deleted automatically by Salesforce in the cascade, if
	# the contact has not been created inside the transaction.

	def __init__(self):
		self.transaction_stack = None

	def close(self):
		pass

	def commit(self):
		pass

	def rollback(self):
		log.info("Rollback is not implemented.")


def connect(**params):
	return Connection()


# --- internal

class TransactionStack(object):

	def __init__(self):
		self.current_status = None
		self.savepoints = None

	def set_autocommit(self, autocommit):
		if autocommit != self.get_autocommit():
			self.current_status = None if autocommit else {}
			self.savepoints = None if autocommit else []

	def get_autocommit(self):
		return current_status is None

	def _rollback(self):
		self._savepoint_rollback(self.savepoints[0].sid)
		self.savepoints = []

	def _commit(self):
		self.savepoints[SavePoint(None, self.current_status)]

	def _savepoint(self, sid):
		self.savepoints.append(SavePoint(sid, self.current_status))

	def _savepoint_rollback(self, sid):
		index = [i for i, x in enumerate(self.savepoints) if x.sid == sid][0]
		self.savepoints = self.savepoints[:index + 1]
		#...

	def _savepoint_commit(self, sid):
		index = [i for i, x in enumerate(self.savepoints) if x.sid == sid][0]
		self.savepoints = self.savepoints[:index]
		if not self.savepoints:
			self.current_status = {}

	def insert(self, oid, data):
		self.current_status[oid] = Record(oid, data)

	def update(self, oid, data):
		self.current_status[oid] = self.current_status[oid].updated(data)

	def delete(self, oid):
		del self.current_status[oid]

	def register_old_value(self, oid, data):
		"""
		This is very restricted to objects without children or children must be
		also registered after the parent.
		"""
		obj = Record(oid, data)
		obj.ordinal = - obj.ordinal
		self.current_status[oid] = obj
		for savepoint in self.savepoints:
			savepoint[oid] = obj

	# "udelete" is impossible to be emulated 


class SavePoint(object):
	def __init__(self, sid, records=None):
		self.sid = sid
		self.records = records.copy() if records else dict()

class Record(object):
	counter = 0

	def __init__(self, oid, data, ord_created=None):
		# the ordinal need not be thead safe (only unique inside the thread)
		Record.counter += 1
		self.ord_modified = Record.counter
		self.ord_created = ord_created or self.ord_modified
		self.oid = oid
		self.data = data

	def updated(self, data):
		cp = self.data.copy()
		cp.update(data)
		if cp == self.data:
			return self
		else:
			return Record(self.oid, cp, self.ord_created)

