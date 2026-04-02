# from django.contrib.auth.models import User
# from django.contrib.auth.models import AbstractUser
# from django.db import models

# # Create your models here.


# class User(AbstractUser):
#     # We can add things like 'phone_number' or 'is_site_manager' later
#     is_verified = models.BooleanField(default=False)

#     def __str__(self):
#         return self.username


# class Company(models.Model):
#     name = models.CharField(max_length=255)
#     owner = models.OneToOneField(User, on_delete=models.CASCADE)
#     phone_number = models.CharField(max_length=20, blank=True, null=True)
#     office_address = models.TextField(blank=True, null=True)

#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return self.name

# account/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    is_verified = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.username


class Company(models.Model):
    name = models.CharField(max_length=255)
    # 🏗️ Using 'owner' because that's what your register_view is looking for
    owner = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='company')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    office_address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
