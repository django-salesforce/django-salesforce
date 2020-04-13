import debug_toolbar  # type: ignore[import] # noqa
from django.urls import include, path
from salesforce.testrunner.urls import urlpatterns
from .views import account_insert_delete

urlpatterns += [
    path('__debug__/', include(debug_toolbar.urls, namespace='djdt')),
    path('account_insert_delete/', account_insert_delete),
]
