from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('fu_web.salesforce.views',
	url(r'^$', 'list_accounts', name='sf_accounts'),
)
