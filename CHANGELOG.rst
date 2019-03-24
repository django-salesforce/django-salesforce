Changelog
=========
A nicer and more important final change log is
https://github.com/django-salesforce/django-salesforce/releases

This file CHANGELOG is more raw and especially useful if you want
to contribute.
It also is less complete and more oriented to details: in API,
maybe also internal changes that could have an unexpected effect or
some undocumented internal code that could yet have been used by
someone. Not related e.g. to examples and tests,
but a new feature can be referred by a test name if not documented yet.
Some items here can be marked as "internal": not ready enough or
experimental.


[0.8] 2019-03-06
----------------

* Suports: Python 2.7.9+, 3.4 - 3.7, Django 1.10 - 2.2
  (tested up to 2.2 beta 1)

* Implemented a big part of Python DB API 2.0.
  Standard DB API is emulated for all ``select`` commands, because it is
  finally easier and much more stable than to keep the old monkey patch
  style for new Django versions.

* Added: Linear rows cursor, that is expected by Django, like in other
  databases, not the cursor with rows like nested multi level dictionaries.

* Added: Bulk methods ``queryset.update()``, ``queryset.delete()``,
  ``SomeModel.objects.bulk_create([SomeModel(...),...])``.
  Currently only for 200 rows, in transactions with AllOrNone option.
  The queryset must contain a restriction. It can be overridden e.g.
  by ``.filter(pk__gt='')``, that is everytimes true.

* Added: Much better query compiler. Correctness of very complicated queries
  can be checked now by ``str(my_query_set.query)`` (recommended). A check
  of WHERE part is usually satisfactory.

* Removed: Extension method ``__len__`` has been removed from RawQuerySet.
  Consequnece: Function ``len(...)`` can not be applied on ``RawQuerySet``.
  (The current Django  doesn't cache the results objects of raw queryset.
  It had no advantage and on the contrary converting the raw query set
  by ``list(queryset)`` would require two full queries with all data,
  if ``__len__`` was not removed.)

* New error reporting. Prepared also to a custom error handler to can
  report more errors, if the block operations could be run without
  AllOrNone transaction later.

* Fixed: method ``QuerySet.select_related(...)`` (It never worked. Now
  it works completely.)

* Fixed: ``ManyToMany`` fields. (new, example in
  test_many2many_relationship_filter)

* Removed: custom method ``simple_select_related()`` (obsoleted by
  select_related)
  
* Changed: All custom error classes has been moved from
  ``salesforce.backend.driver`` to ``salesforce.dbapi.exceptions``.
  Very useful class is ``SalesforceError``.

* Changed: Two errors reported by SFDC REST API (ENTITY_IS_DELETED and
  INVALID_CROSS_REFERENCE_KEY) if a record that has been deleted yet, was
  tried to be updated or deleted again) were previously intentionally
  ignored to be compatible with normal SQL. Update is now an error, delete
  is now a warning, because it is important to easily to clean all objects
  in tests finally without checking that they were succesfully created.
  This behavious is open to discussion.
  (A warning can be easily silenced by configuration naturally.)

* Fixed introspection to work on text formula fields in Salesforce API
  version 45.0 Spring'19.

* Fixed: Command ``inspectdb`` detects unique firelds by ``unique=True``.

* Fixed: A default command ``inspectdb`` raised exception if ``salesforce``
  was not in ``INSTALLED_APPS``.

* Changed default ``Meta`` to ``managed=True``. Useful if simple Salesforce
  models are emulated by another database in fast tests, even without
  network connectivity. Fixed migrations. #190

* Added support for ``app_label`` config.

Internal:

* Removed: Many internal SOAP API methods (because obsoleted for us by
  recent REST API methods). Only Lead conversion is still done by SOAP
  API (beatbox).

* (Discussion: A part of backward compatibility in raw queries could be
  reimplemented in the next version by a non default method if it will be
  required, but a current better compatibility with the standard Django
  is probably more important.)

* Experimental undocumented feature "dynamic models" (started in v0.6.9)
  can probably have some regressions. Its purpose is to can use Django,
  mainly in development, if the model doesn't match exactly the SFDC
  structure with missing or added fields, especially with more databases.
  Migrations are not expected with it. (simple tests: test_dynamic_fields()
  and module tests.inspectdb.dependent_model.test)


[0.7.2] 2017-05-15
------------------
* Added: Support for two timeouts as a tuple (shorter time for connecting,
  a longer for data in a request)

* Fixed: Updated internal package versioning 0.7+ #184


[0.7] 2017-05-01
----------------
* Supports: Python 2.7.9+, 3.4 - 3.6, Django 1.8.4 - 1.11

* All SSL/TLS settings and tests has been removed, because TLS 1.0 has been
  disabled by Salesforce.com and systems with the tested vulnerabilies
  are unlikely now.

(... not complete)

[0.6.9] 2016-08-12
------------------
* Supports: Python 2.7.9+, 3.4 - 3.5, Django 1.7 - 1.10
