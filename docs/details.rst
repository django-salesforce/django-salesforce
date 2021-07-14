Settings
--------

``SF_ALT_PK``: A function used to generate an automatic uuid primary key for normal
databases used with SalesforceModel. The default is hexadecimal uuid.uuid4().

``SF_CAN_RUN_WITHOUT_DJANGO``: The database driver can run also without Django if the value is True,

``SF_LAZY_CONNECT``: The Salesforce database is connected as late as possible if the setting is True.
This is especially useful for test with normal databases used with SalesforceModel.
A default behaviour is similar to normal databases that a Django application will fail very fast
at startup if a connection is not possible or if authentications data are invalid.

``SF_PK``: The name of primary key which can be ``'id'`` (default) or ``'Id''``. It can be changed
only before the first migration is created. (A migration created with a different SF_PK is invalid.)

(All settings ``SF_EXAMPLE_*`` are not important and they are used only for tests with example.models.)
