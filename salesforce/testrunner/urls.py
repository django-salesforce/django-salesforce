from django.urls import include, path

from django.contrib import admin
admin.autodiscover()

urlpatterns = [
    path(r'', include('salesforce.testrunner.patient_connect.urls')),
    path(r'admin/doc/', include('django.contrib.admindocs.urls')),
    path(r'admin/', admin.site.urls),
]
