"""A small but richly related schema, so DjangoQL queries can traverse
relations (``author.country``, ``publisher.name``, ``genres.name``) and the
per-branch breakdown has interesting numbers to show.

    Genre  ──< Book >──  Author ──< (born in) Country
                 │  └──────────── Publisher
                 └──< genres (M2M) >── Genre
"""

from django.db import models

from djangoql.queryset import DjangoQLQuerySet


class Country(models.Model):
    name = models.CharField(max_length=64, unique=True)
    code = models.CharField(max_length=2, unique=True)

    class Meta:
        verbose_name_plural = 'countries'
        ordering = ['name']

    def __str__(self):
        return self.name


class Genre(models.Model):
    name = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Publisher(models.Model):
    name = models.CharField(max_length=128, unique=True)
    country = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        related_name='publishers',
    )
    founded = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Author(models.Model):
    name = models.CharField(max_length=128)
    country = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        related_name='authors',
    )
    born = models.PositiveIntegerField(null=True, blank=True)
    alive = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(
        Author,
        on_delete=models.CASCADE,
        related_name='books',
    )
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.SET_NULL,
        null=True,
        related_name='books',
    )
    genres = models.ManyToManyField(Genre, related_name='books', blank=True)
    year = models.PositiveIntegerField()
    pages = models.PositiveIntegerField()
    rating = models.FloatField()
    price = models.DecimalField(max_digits=7, decimal_places=2)
    in_stock = models.BooleanField(default=True)
    published = models.DateField(null=True, blank=True)

    objects = DjangoQLQuerySet.as_manager()

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title
