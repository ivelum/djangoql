from __future__ import unicode_literals

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.timezone import now

from djangoql.queryset import DjangoQLQuerySet


class Book(models.Model):
    GENRES = {
        1: 'Drama',
        2: 'Comics',
        3: 'Other',
    }

    name = models.CharField(max_length=10)  # lol, we're minimalists
    author = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    genre = models.PositiveIntegerField(
        null=True,
        blank=True,
        choices=GENRES.items(),
    )
    written = models.DateTimeField(default=now)
    is_published = models.BooleanField(default=False)
    rating = models.FloatField(null=True)
    price = models.DecimalField(max_digits=7, decimal_places=2, null=True)
    content_type = models.ForeignKey(
        ContentType,
        null=True,
        on_delete=models.CASCADE,
        editable=False,
    )
    object_id = models.PositiveIntegerField(null=True, editable=False)
    content_object = GenericForeignKey('content_type', 'object_id')

    similar_books = models.ManyToManyField('Book', blank=True, related_name='+')

    objects = DjangoQLQuerySet.as_manager()

    def __str__(self):
        return self.name
