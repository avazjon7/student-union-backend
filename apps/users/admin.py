# users/admin.py
from django.contrib.auth.admin import UserAdmin
from django.contrib import admin
from django.contrib.auth.models import Group
from .models import User
from .models import User, TelegramAccount, Address, TelegramLinkCode



class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ['phone_number', 'first_name', 'last_name', 'location_label', 'is_staff']
    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Delivery location', {
            'fields': (
                'location_label',
                'location_street',
                'location_building',
                'location_entrance',
                'location_floor',
                'location_apartment',
                'location_latitude',
                'location_longitude',
            )
        }),
        ('Permissions', {
            'fields': (
                'is_active', 'is_staff', 'is_superuser',
                'groups', 'user_permissions'
            )
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'phone_number',
                'first_name',
                'last_name',
                'location_label',
                'location_street',
                'location_building',
                'location_entrance',
                'location_floor',
                'location_apartment',
                'location_latitude',
                'location_longitude',
                'password1',
                'password2',
            ),
        }),
    )

    search_fields = ('phone_number',)
    ordering = ('phone_number',)


admin.site.register(User, CustomUserAdmin)
@admin.register(TelegramAccount)
class TelegramAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "telegram_user_id", "username", "linked_at")
    search_fields = ("user__phone", "telegram_user_id", "username")


@admin.register(TelegramLinkCode)
class TelegramLinkCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "user", "expires_at", "used_at")
    search_fields = ("code", "user__phone")
    readonly_fields = ("created_at", "used_at")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "address", "is_default", "updated_at")
    list_filter = ("is_default",)
    search_fields = ("name", "address", "user__phone")


admin.site.unregister(Group)
