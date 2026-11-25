"""Populate the demo database with lots of related rows.

    python manage.py seed_demo                 # ~3000 books (default)
    python manage.py seed_demo --books 8000    # more
    python manage.py seed_demo --flush         # wipe demo data first

The data is generated from a fixed random seed, so it is reproducible. Volume
matters here: the per-branch breakdown is only interesting when individual
conditions match very different numbers of rows.
"""

import datetime
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from library.models import Author, Book, Country, Genre, Publisher


COUNTRIES = [
    ('Poland', 'PL'),
    ('United States', 'US'),
    ('United Kingdom', 'GB'),
    ('France', 'FR'),
    ('Germany', 'DE'),
    ('Japan', 'JP'),
    ('Italy', 'IT'),
    ('Spain', 'ES'),
    ('Canada', 'CA'),
    ('Brazil', 'BR'),
    ('India', 'IN'),
    ('Sweden', 'SE'),
    ('Australia', 'AU'),
    ('Argentina', 'AR'),
    ('Russia', 'RU'),
]

GENRES = [
    'Science Fiction',
    'Fantasy',
    'Mystery',
    'Thriller',
    'Romance',
    'Horror',
    'Historical',
    'Biography',
    'Poetry',
    'Drama',
    'Comics',
    'Non-fiction',
    'Adventure',
    'Crime',
    'Philosophy',
    'Travel',
    'Cookbook',
    'Children',
    'Young Adult',
    'Essay',
]

PUBLISHER_STEMS = [
    'Penguin',
    'Harper',
    'Vintage',
    'Orbit',
    'Tor',
    'Bloomsbury',
    'Macmillan',
    'Knopf',
    'Faber',
    'Norton',
    'Scholastic',
    'Gallimard',
    'Mondadori',
    'Czytelnik',
    'PWN',
    'Iskry',
    'Hachette',
    'Random House',
    'Simon',
    'Anchor',
]
PUBLISHER_SUFFIX = ['Press', 'Books', 'House', 'Publishing', '& Co']

FIRST_NAMES = [
    'Stanisław',
    'Olga',
    'Ursula',
    'George',
    'Isaac',
    'Agatha',
    'Haruki',
    'Italo',
    'Gabriel',
    'Jane',
    'Mary',
    'Philip',
    'Margaret',
    'Neil',
    'Toni',
    'Fyodor',
    'Jorge',
    'Chinua',
    'Octavia',
    'Ray',
    'Iain',
    'Ann',
]
LAST_NAMES = [
    'Lem',
    'Tokarczuk',
    'Le Guin',
    'Orwell',
    'Asimov',
    'Christie',
    'Murakami',
    'Calvino',
    'García Márquez',
    'Austen',
    'Shelley',
    'Dick',
    'Atwood',
    'Gaiman',
    'Morrison',
    'Dostoevsky',
    'Borges',
    'Achebe',
    'Butler',
    'Bradbury',
    'Banks',
    'Leckie',
]
TITLE_A = [
    'The',
    'A',
    'Last',
    'Silent',
    'Broken',
    'Hidden',
    'Burning',
    'Frozen',
    'Distant',
    'Crimson',
    'Hollow',
    'Endless',
    'Gilded',
    'Quiet',
    'Wild',
]
TITLE_B = [
    'Garden',
    'Empire',
    'Machine',
    'Ocean',
    'Shadow',
    'Mirror',
    'Forest',
    'City',
    'Star',
    'River',
    'Clock',
    'Door',
    'Storm',
    'Dream',
    'Engine',
]


class Command(BaseCommand):
    help = 'Seed the database with related demo data (countries..books).'

    def add_arguments(self, parser):
        parser.add_argument('--books', type=int, default=3000)
        parser.add_argument('--authors', type=int, default=600)
        parser.add_argument('--flush', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(1234)

        if options['flush']:
            Book.objects.all().delete()
            Author.objects.all().delete()
            Publisher.objects.all().delete()
            Genre.objects.all().delete()
            Country.objects.all().delete()
            self.stdout.write('Flushed existing demo data.')

        countries = [
            Country.objects.get_or_create(code=code, defaults={'name': name})[0]
            for name, code in COUNTRIES
        ]
        genres = [Genre.objects.get_or_create(name=name)[0] for name in GENRES]
        publishers = self._publishers(rng, countries)
        authors = self._authors(rng, countries, options['authors'])
        self._books(rng, authors, publishers, genres, options['books'])

        self.stdout.write(
            self.style.SUCCESS(
                'Seeded: {} countries, {} genres, {} publishers, {} authors, '
                '{} books.'.format(
                    len(countries),
                    len(genres),
                    len(publishers),
                    len(authors),
                    Book.objects.count(),
                )
            )
        )

    def _publishers(self, rng, countries):
        names = set()
        for stem in PUBLISHER_STEMS:
            names.add(f'{stem} {rng.choice(PUBLISHER_SUFFIX)}')
        objs = []
        for name in sorted(names):
            objs.append(
                Publisher.objects.get_or_create(
                    name=name,
                    defaults={
                        'country': rng.choice(countries),
                        'founded': rng.randint(1900, 2015),
                    },
                )[0]
            )
        return objs

    def _authors(self, rng, countries, count):
        existing = Author.objects.count()
        to_make = max(0, count - existing)
        objs = [
            Author(
                name='{} {}'.format(
                    rng.choice(FIRST_NAMES),
                    rng.choice(LAST_NAMES),
                ),
                country=rng.choice(countries),
                born=rng.randint(1900, 1995),
                alive=rng.random() < 0.6,
            )
            for _ in range(to_make)
        ]
        Author.objects.bulk_create(objs, batch_size=500)
        return list(Author.objects.all())

    def _books(self, rng, authors, publishers, genres, count):
        existing = Book.objects.count()
        to_make = max(0, count - existing)
        books = []
        for _ in range(to_make):
            year = rng.randint(1950, 2024)
            books.append(
                Book(
                    title='{} {}'.format(
                        rng.choice(TITLE_A),
                        rng.choice(TITLE_B),
                    ),
                    author=rng.choice(authors),
                    publisher=rng.choice(publishers),
                    year=year,
                    pages=rng.randint(80, 900),
                    rating=round(rng.uniform(1.0, 5.0), 1),
                    price=round(rng.uniform(5, 60), 2),
                    in_stock=rng.random() < 0.7,
                    published=datetime.date(year, rng.randint(1, 12), 1),
                )
            )
        Book.objects.bulk_create(books, batch_size=500)

        # Attach 1–3 genres to each new book via the M2M through table.
        through = Book.genres.through
        links = []
        for book in Book.objects.filter(genres__isnull=True):
            for genre in rng.sample(genres, rng.randint(1, 3)):
                links.append(through(book_id=book.id, genre_id=genre.id))
        through.objects.bulk_create(
            links,
            batch_size=1000,
            ignore_conflicts=True,
        )
