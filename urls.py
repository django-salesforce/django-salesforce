from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('fu_web.salesforce.views',
	url(r'^$', 'test', name='sf_test'),
)
