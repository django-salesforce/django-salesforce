DJANGO_VER=$(python -c "import django; print(django.get_version())")
echo "VER=$DJANGO_VER"
if [ $DJANGO_VER '<' 1.6 ]; then
	python manage.py test --settings=tests.test_lazy_connect.settings test_lazy_connect
else
	echo python manage.py test --settings=tests.test_lazy_connect.settings tests.test_lazy_connect
	python manage.py test --settings=tests.test_lazy_connect.settings tests.test_lazy_connect
fi
