from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

ALPHABET = 'abcdefghijklmnopqrstuvwxyz'


class Command(BaseCommand):
    help = 'Generate fake users for testing value suggestion feature on username field'

    def handle(self, *args, **options):
        for letter in ALPHABET:
            for i in range(2, 150):
                user = User(username=letter * i)
                user.save()
