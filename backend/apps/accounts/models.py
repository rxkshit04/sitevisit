from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        EXECUTIVE = "executive", "Sales executive"
        HEAD = "head", "Sales head"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EXECUTIVE)

    @property
    def is_head(self) -> bool:
        return self.role == self.Role.HEAD