import debug_toolbar  # type: ignore[import] # noqa
from django.urls import include, path
from django.contrib import admin
admin.autodiscover()

urlpatterns = [
    path('__debug__/', include(debug_toolbar.urls, namespace='djdt')),
    path('admin/', admin.site.urls),
]
