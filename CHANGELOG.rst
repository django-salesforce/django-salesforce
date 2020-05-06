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


[1.0] 2020-05-07
----------------
* Remove: Support for Django 1.10
* Remove: Support for Python 2.7, 3.4
* Add: Support for Python 3.9 (alpha 5)
* Add: Preliminary support for Django 3.1-dev (development snaphot 2020-04-21)
* Fix: Fixed all hidden deprecation warnings. (related removed old versions)
* Fix: .annotate() method can use GROUP BY if Django >= 2.1
       example queryset.order_by().values('account_id').annotate(cnt=Count('id'))
* Fix: DefaultedOnCreate() and DEFAULTED_ON_CREATE is now transparent for
       other code. It has a surrogate normal value and it is never saved #213
* Add: Warning if a value DEFAULTED_ON_CREATE is tried to be saved again without
       refreshing the real value.
* Fix: Support for Django Debug Toolbar - including EXPLAIN commend
* Fix: Consistent output of inspectdb with db_column on every field.
       The old behavior with ``custom=`` parameter and minimalistic db_column
       can be turn on by ``--concise-db-column`` option. #250
* Fix: Export attributes "verbose_name", "help_text" and "default=DEFAULTED_ON_CREATE"
       also for ForeignKey by inspectdb.
* Fix: Not to export DEFAULTED_ON_CREATE excessively for not createable fields.
* Fix: Error handling in bulk delete()
* Fix: SomeModel.objects.all().delete()
* Fix: Wildcard search with characters "_" and "%". #254
* Fix: Accept a manually added AutoField in models.
* Fix: Close correctly all SSL sockets before dropped. (minor)
* Fix: Lazy test helper fixed for Python >= 3.8 (lazy: exception can be tested later
       then the fail was detected. It uses two tracebacks.
       e.g. ``with lazy_assert_n_requests(n)``: check that the optimal number
       of requests was used if everything critical was OK and show the first
       suboptimal command-line.)
* Add: Bulk update limited to 200 objects: bulk_update_small()
* Add: Static typing by Mypy. Can validate user code that correspondd to the user data model.
        with SalesforceModel (requires also installed django-salesforce-stubs)
* Update: Salesforce 48.0 Spring '20 (no fix)
* Add: Raw cursor with fields dict: ``connection.cursor(name='dict')``
* Add: Internal module mocksf is used in tests/debugging for record or replay of
       raw Salesforce requests/responses.


[0.9] 2019-11-04
----------------

* Fixed: filter for objects with no children rows (missing test)

* Added: lookup ``.filter(...__not_in=subquery)``' and 'not_eq',
  because of unsupported ``.exclude(...__in=subquery)``.

* Added: command ``ping_connection`` that automatic called after every
  longer inactivity to minimize timeouts. Fixed #174

* Fixed: ``makemigrations`` works now also without db_table name e.g. for
  simple standard objects.

* Fixed: bug ``.using('salesforce')`` in ``default`` database queryset.

* Added: ``salesforce.models_extend`` module with SalesforceModel with
  varchar primary key that works also with ``default`` databases.
  Fixed methods for it: save() and ``bulk_create()`` to can create a new
  pk or to copy an object exactly. Fixed #231

* Fixed: test setUpClass to can run tests on an empty Salesforce database.

* Fixed: ``TimeField.save()`` regression on BusinessHours object. (Salesforce 47.0
  Winter '20 started to apply a default time shift by Organization time zone on
  TimeField.)

* Fixed inspectbd to ignore some new objects in Salesforce 47.0 Winter '20
  that are not a table.

* Updated for Django 3.0 beta 1.


[0.8.1] 2019-05-22
------------------
* Made custom exceptions importable from the top-level ``salesfrorce`` module.

* Created SalesforceAuthError custom exception to replace LookupError.

* Fixed #226: ``migrate`` command to ignore SalesforceModel migrations on the
  salesforce database.

* Fixed #234: select_related() when filtering by children objects.


[0.8] 2019-03-06
----------------

* Suports: Python 2.7.9+, 3.4 - 3.7, Django 1.10 - 2.2
  (Tested up to the newest 2.2 beta 1 at the release time.
  It works also with Django 2.2 unchanged.)

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

* New error reporting. Prepared also to a custom error handler to be possible
  to report more errors by block operations, if the would be supported also
  without AllOrNone transaction later.

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
  is now a warning, because it is important to easily clean all objects
  in tests finally without checking that they were succesfully created.
  This behavior is open to discussion.
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

* Removed: Many internal SOAP API methods (because they have been obsoleted for
  us by recent REST API methods). Only Lead conversion is still done by SOAP
  API (beatbox).

* (Discussion: A part of backward compatibility in raw queries could be
  reimplemented in the next version by a non default method if it will be
  required, but a current better compatibility with the standard Django
  is probably more important.)

* Experimental undocumented feature "dynamic models" (started in v0.6.9)
  can probably have some regressions. Its purpose is to use Django,
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
