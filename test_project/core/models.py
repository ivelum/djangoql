from __future__ import unicode_literals

from django.db import models
from django.utils.timezone import now

from djangoql.queryset import DjangoQLQuerySet


class Book(models.Model):
    name = models.CharField(max_length=10)  # lol, we're minimalists
    author = models.ForeignKey('auth.User')
    written = models.DateTimeField(default=now)
    is_published = models.BooleanField(default=False)

    objects = DjangoQLQuerySet.as_manager()
