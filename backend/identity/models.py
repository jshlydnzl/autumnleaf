import uuid

from django.conf import settings
from django.db import models


class Account(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=6, choices=Role, default=Role.MEMBER)
    session_revision = models.PositiveIntegerField(default=0)

    @property
    def status(self):
        if not self.user.is_active:
            return "disabled"
        return "active" if self.user.has_usable_password() else "pending"


class SetupLink(models.Model):
    account = models.OneToOneField(Account, on_delete=models.CASCADE)
    digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()


class AccountEvent(models.Model):
    actor = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="+")
    target = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
