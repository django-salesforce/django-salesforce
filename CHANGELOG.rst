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

[5.1] 2024-10-08 ?
------------------
* Add: Support for Django 5.1
* Change: The cursor rollback() method log messages are silenced by default
  because they are mostly anoying in tests. They can be enabled again if
  ``settings.DATABASES['salesforce']['OPTIONS']['WARNING_ON_ROLLBACK'] == True``
* Changes where users will not know a difference:

  * Refactored the backend.query to use consistent data types internally.
  * Checked a development version of Django is really used by "tox -e djdev"
  * Fix introspection for Salesforce API 62.0 Winter '25 (skip introspection of ...Event object that is not a table)


[5.0.2] 2024-05-27
------------------
The main new features are in the improved query compiler

* Remove: the old Python 3.7
* Remove: the code for Django 2.0
* Fix: many issues in the query compiler in edge cases:

  - fix a query with offset, but without a limit (NotImplementedError)
  - fix a '__range' lookup on a field of custom foreign key object (SalesforceError)
  - fix a '=null' lookup.  It worked probably always correctly, but the old implementation was different from  standard lookups. It made it impossible to distinguish it from unsupported queries
* Add: The query compiler is now much more precise. Most of unsupported queries will
  write a warning before they are tried compiled. This is how users have
  discovered some functional queries in the past.
  No regression is known that a previously correct query would write a warning.
* Add: Support for date and datetime lookup by year, quarter, month, day, week_day, hour
  e.g. group this year by month:
  .filter(date__year=2024).value('date__month').annotate(total=Sum('amount'))
* Add: The method .sf(minimal_aliases=True) is not necessary
  for ContentDocumentLink .filter(...); #259
* Fix: Compile correctly: .filter(related_model__field__in=...) Fix #302
* Fix: Prepare tests for Salesforce API 61.0 Summer '24
* Add: Introspect Salesforce fields of type Formula to sf_formula="..." parameter


[5.0.1] 2024-03-04
------------------
* Add: Support for ``db_default`` field option in Django 5.0. It allows a seamless
  support of the ``defaultedOnCreate`` counterpart in Salesforce.
* Add: Support for Salesforce API 60.0 Spring '24.
* Change: Values of ``FloatField`` are now really float, not Decimal as previously.
* Fix: Compatibility with the current django-debug-toolbar #322
* Fix: Introspection ``inspectdb`` of custom editable name fields #308
* Add: FloatField is used by ``inspectdb`` for some metadata with negative decimal places
  that are new in API 60.0.
* Change: A license code is required also in the first half of lifetime of a LTS version
  unless the AGPL licence is accepted.
  Django 4.2 LTS will be unlocked together with unlocking 5.0 in August 2024
  in Django-salesforce 5.1 release.
* Change: License code validity may not transfer to the next django-salesforce version
  if sponsorship ended.


[5.0] 2023-12-07
----------------
* Add: Support for Django 5.0
* Add: Monitoring 'api_usage' from 'Sforce-Limit-Info' API response header #317


[4.2] 2023-07-04
----------------
* Add: Basic diagnostics after installation can be done by command
  ``python manage.py check --database=salesforce``
* Change: Use with Django 4.2 requires an enterprise license key.
* Add: Support for Django 4.2
* Use API 58.0 Summer '23
* Add: Support for Django Database caching #315
* Fix: Configurable max introspected pick-list size
  SF_MAX_INSPECTDB_PICKLIST_LENGTH #312
  Some people need to introspect huge picklists, some don't want.


[4.1] 2022-08-05
----------------
* Add: Support for Django 4.1
* Add: Command ``inspectdb`` can introspect actual default values
  of fields from a ``defaultValueFormula`` if it is a simple constant
  like a number or a string.
* Fix: A default value ``DefaultedOnCreate(value)`` is no longer created
  by ``inspectdb`` in favour of a simple ``value``. If a simple default value
  can not be known then a generic ``DEFAULTED_ON_CREATE`` is still used rarely
  for default values created by a complicated or unknown function only
  on Salesforce side. #280
* Fix: Optionally don't use redundant table names before field names
  if queried with ``.sf(minimal_aliases=True)``; important for some
  special system objects #302
* Fix: Tests with the newest Django, Salesforce, Python; including Python 3.11(beta)
* Fix: Extended SalesforceModel with PostgreSQL backend and Django >= 3.0 #299


[4.0] 2021-11-22
----------------
* Internal change: The default row type from salesforce Cursor is now a tuple,
  not a list
* Fix: Invalid primary key from bulk_create([one_object]) in Django 3.0 #298
* Add suport for Django 4.0 (rc 1) and declare support for Python 3.10,
  Salesforce API 53.0 Winter '22.
* Add: Support timestamps with "auto_now_add=True" and "auto_now=True".
* Fix: Fix tests for Salesforce API 52.0 Summer '21 that broke syntax of
  filters on a primary key or foreign keys: can not be compared to empty string
  and allowed only =, !=, IN, NOT IN.
  A filter ``.filter(field__gt='')`` must be replaced e.g. by ``.exlude(field=None)``.
* Fix: Works also with obsoleted USE_TZ=False #221
* Fix: Support also alternative clones of Beatbox #172
* Add: Implement queryset.bulk_update() method #236
* Fix: SOQL command in queryset.raw() is supported case insensitive
* Fix: ManyToMany relationships compiled also with GROUP BY, HAVING, ORDER BY. #264
* Fix: Lookup IsNull() in 'queryset.filter(...=None).update(...)' #283
* Fix: DefaultedOnCreate() to work with new sqlite3 and new Django
* Fix: Command inspectdb with --table-filter=regex_pattern
* Fix: Count('*') and Count(... distinct=True)
* Add: Simple authentication by auth.SimpleSfPasswordAuth(). #282
* Add: Higher 'threadsafety=2' level of the driver. Every thread can use its
  own database connections with the same alias, but checked that the same
  thread can not open more connections with the same alias.
* Add: Test for big SOQL queries of length almost 100000 bytes
* Add: Strict typing of SalesforceModel and all ``salesforce/*.py`` code.
  All dependent user code can use also strict typing now.
* Add: Method .explain(...)
* Fix: Low level EXPLAIN command
* Add: Decorator 'PatchedSfConnection(... use_debug_info ...)' to can check
  the executed SOQL in tests e.g. for aggregate() method.
* Add: Verbose error message in authentication.
* Add: Support offline tests with playback by MockTestCase,
  also for tests of database error handling.
* Fix: Example models can now create a migration
* Fix: Check pylint, increase code coverage (91%)
* Fix: Tests updated for Salesforce API 52.0 Summer '21
* Remove: Unused code, mostly residues from old Django versions
* Add: Prepare for DynamicWebAuth; Configurable username in RefreshTokenAuth
  Still requires a low level user code in middlewawe. (therefore considered as
  undocumented alpha code.)


[3.2] 2021-04-06
----------------
* Add: Support for Django 3.2
* Remove: Django 1.11
* Update: to use Salesforce 51.0 Spring '21 API
* Add: Fields `OneToOneField` are detected by `inspectdb` in Django >= 3.0
  (and as ForeignKey unchanged in old Django)
* Fix: Fixed all hidden deprecation warnings
* Fix: Backward compatibility with old migrations. #275
* Fix: Simplify output of inspectdb if a choice is too huge
  or if tables are restricted by table filter. #279


[3.1] 2020-08-05
----------------
* Fix: Enable support for Django 3.1 final.
* Change: Package versions will be synchronized with Django "release version" from now on.


[1.1] 2020-07-09
----------------
* Add: Optional Refresh Token Authentication by ``RefreshTokenAuth`` with
  cryptographic code_challenge / code_verifier.
* Add: Tag `[django-salesforce]
  <https://stackoverflow.com/questions/tagged/django-salesforce>`_
  for questions on Stackoverflow.com.
* Fix: Allow SOQL query up to 100000 characters, fixed #164
* Add: Support for custom authentication modules configurable by
  ``settings.DATABASES['salesforce']['AUTH']``
* Add: Authentication by Salesforce CLI SFDX application for developers, e.g.
  'salesforce.auth.SfdxOrgWebAuth'
* Fix: Easier dynamic authentication. It requires an explicit setting now:
  ``"salesforce": {... "AUTH": "salesforce.auth.DynamicAuth" ...}``
* Add: Configurable API_VERSION by settings.DATABASES['salesforce']['API_VERSION']
* Add: A method .sf() on querysets and managers to can pass additional parameter
  e.g. all_or_none=True or edge_updates=True to bulk_create() and update() methods.
* Fix: Fixed long delay in application after unstable nework connection #267
* Fix: Old fix for timeouts #174 was inappropriate for unstable connections.
* Fix: Queryset with empty slice e.g. queryset[100:100]
* Fix: Fix "max_length" in inspectdb for Choice Fields, because it is ignored
  by SFDC, but important for Django.


[1.0] 2020-05-08
----------------
* Remove: Support for Django 1.10
* Remove: Support for Python 2.7, 3.4
* Add: Support for Python 3.9 (alpha 5)
* Add: Preliminary support for Django 3.1-dev (development snaphot 2020-04-21)
* Fix: Fixed all hidden deprecation warnings. (related removed old versions)
* Fix: ``.annotate()`` method can use GROUP BY if Django >= 2.1
  example queryset.order_by().values('account_id').annotate(cnt=Count('id'))
* Fix: ``DefaultedOnCreate()`` and DEFAULTED_ON_CREATE is now transparent for
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


[0.9] 2019-11-05
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


[0.7.2] 2017-05-16
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
