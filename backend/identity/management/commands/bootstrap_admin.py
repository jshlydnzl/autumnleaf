from getpass import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from identity.models import Account
from identity.views import USERNAME


class Command(BaseCommand):
    help = "Create a local AutumnLeaf Admin when there is no active Admin."

    @transaction.atomic
    def handle(self, *args, **options):
        if any(row.status == "active" for row in Account.objects.select_related("user").filter(role=Account.Role.ADMIN)):
            raise CommandError("An active Admin already exists. Use Accounts to add another.")

        username = input("Admin username: ").strip().lower()
        user_model = get_user_model()
        if not USERNAME.fullmatch(username):
            raise CommandError("Use 3–32 letters, numbers, dots, hyphens, or underscores.")
        if user_model.objects.filter(username=username).exists():
            raise CommandError("That username is already in use.")
        user = user_model(username=username)
        password = getpass("Password: ")
        if password != getpass("Confirm password: "):
            raise CommandError("Passwords did not match.")
        if len(password) > 128:
            raise CommandError("Password must be at most 128 characters.")
        try:
            validate_password(password, user)
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc

        user.set_password(password)
        user.save()
        Account.objects.create(user=user, role=Account.Role.ADMIN)
        self.stdout.write(self.style.SUCCESS(f"Created Admin account {username}."))
