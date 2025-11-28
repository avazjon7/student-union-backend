from rest_framework import serializers

from config import settings
from .models import (
    Event,
    EventCategory,
    SeatGroup,
    Seat,
    Registration,
    Ticket,
)
User = settings.AUTH_USER_MODEL


class EventCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EventCategory
        fields = ["id", "name", "slug"]


class EventSerializer(serializers.ModelSerializer):
    category = EventCategorySerializer(read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "category",
            "start_at",
            "end_at",
            "venue_name",
            "address",
            "visibility",
            "is_paid",
            "base_price",
        ]


class SeatGroupSerializer(serializers.ModelSerializer):
    free_seats = serializers.IntegerField(read_only=True)

    class Meta:
        model = SeatGroup
        fields = ["id", "code", "name", "type", "base_price", "capacity", "free_seats"]


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = ["id", "row", "seat_number", "price", "status", "group_id"]


class RegistrationSerializer(serializers.ModelSerializer):
    event = EventSerializer(read_only=True)

    class Meta:
        model = Registration
        fields = [
            "id",
            "event",
            "status",
            "payment_status",
            "promo_code",
            "final_price",
            "created_at",
        ]


class TicketSerializer(serializers.ModelSerializer):
    registration = RegistrationSerializer(read_only=True)
    seat = SeatSerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "token",
            "is_used",
            "used_at",
            "created_at",
            "registration",
            "seat",
        ]
