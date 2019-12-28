from django.contrib import admin
from salesforce.backend import DJANGO_20_PLUS
if DJANGO_20_PLUS:
    from django.urls import path
else:
    from django.conf.urls import url as path

urlpatterns = [
    path('admin/', admin.site.urls),
]
