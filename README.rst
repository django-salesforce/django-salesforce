derived from django-salesforce
================================

.. image:: https://travis-ci.org/django-salesforce/django-salesforce.svg?branch=master
   :target: https://travis-ci.org/django-salesforce/django-salesforce

.. image:: https://badge.fury.io/py/django-salesforce.svg
   :target: https://pypi.python.org/pypi/django-salesforce

.. image:: https://img.shields.io/badge/python-3.5%20%7C%203.6%20%7C%203.7%20%7C%203.8%20%7C%203.9-blue
   :target: https://www.python.org/

.. image:: https://img.shields.io/badge/Django-2.0%2C%202.1%2C%202.2%2C%203.0%2C%203.1%20%7C%203.2-blue.svg
   :target: https://www.djangoproject.com/

This library allows you to load, edit and query the objects in any Salesforce instance
using Django models. The integration is fairly complete, and generally seamless
for most uses. It works by integrating with the Django ORM, allowing access to
the objects in your SFDC instance (Salesforce .com) as if they were in a
traditional database.

Python 3.5.3 to 3.9, Django 2.0 to 3.2.
(Tested also with Python 3.10.0a6)


The Patient Connections Platform
=================================

The Patient Connections Platform (PCP) is a totally custom SFDC application that we are connecting to. I've creatd a connected app called "integration engine" in order to authenticate myself inside of deldev3.
