from django.db import models


class University(models.Model):
    name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=255, blank=True)

    def __str__(self) -> str:
        return self.short_name or self.name


class UserRole(models.TextChoices):
    STUDENT = "student", "Student"
    ORGANIZER = "organizer", "Organizer"
    ADMIN = "admin", "Admin"


class UserProfile(models.Model):
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    telegram_username = models.CharField(max_length=255, blank=True)

    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, blank=True)

    university = models.ForeignKey(
        University, null=True, blank=True, on_delete=models.SET_NULL
    )
    role = models.CharField(
        max_length=20, choices=UserRole.choices, default=UserRole.STUDENT
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.full_name} ({self.role})"
