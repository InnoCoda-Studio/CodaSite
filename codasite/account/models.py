from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.


class User(AbstractUser):
    # We can add things like 'phone_number' or 'is_site_manager' later
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.username
