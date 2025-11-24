from django.contrib import admin
from .models import (
    EventCategory,
    Event,
    SeatGroup,
    Seat,
    Registration,
    Ticket,
    CheckInLog,
)


@admin.register(EventCategory)
class EventCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "start_at", "venue_name", "is_active", "is_paid")
    list_filter = ("is_active", "is_paid", "visibility", "category")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(SeatGroup)
class SeatGroupAdmin(admin.ModelAdmin):
    list_display = ("event", "code", "name", "type", "base_price", "capacity")
    list_filter = ("event", "type")


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ("event", "group", "row", "seat_number", "price", "status")
    list_filter = ("event", "group", "status")


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ("event", "user", "status", "payment_status", "final_price")
    list_filter = ("status", "payment_status", "event")


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "registration", "seat", "is_used", "created_at")
    list_filter = ("is_used", "registration__event")


@admin.register(CheckInLog)
class CheckInLogAdmin(admin.ModelAdmin):
    list_display = ("ticket", "checked_by", "created_at")
