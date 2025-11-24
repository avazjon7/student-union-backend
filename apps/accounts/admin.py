from django.contrib import admin
from .models import University, UserProfile


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "city")
    search_fields = ("name", "short_name")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "telegram_id", "telegram_username", "phone", "role", "university")
    list_filter = ("role", "university")
    search_fields = ("full_name", "telegram_username", "phone")
