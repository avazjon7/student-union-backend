from django.db import models
from django.utils import timezone
from django.conf import settings
import uuid
import secrets

User = settings.AUTH_USER_MODEL


class University(models.Model):
    """
    Университет, к которому относится студент / событие.
    Можно расширить потом полями города, страны и т.п.
    """
    name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Университет"
        verbose_name_plural = "Университеты"

    def __str__(self) -> str:
        return self.short_name or self.name


class EventCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def __str__(self) -> str:
        return self.name


class EventVisibility(models.TextChoices):
    PUBLIC = "public", "Public"
    INTER_UNI = "inter_uni", "Inter-university"
    PRIVATE = "private", "Private"


class Event(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    category = models.ForeignKey(
        EventCategory, on_delete=models.SET_NULL, null=True, blank=True
    )

    start_at = models.DateTimeField()
    end_at = models.DateTimeField()

    venue_name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)

    visibility = models.CharField(
        max_length=20, choices=EventVisibility.choices, default=EventVisibility.PUBLIC
    )

    organizer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organized_events",
    )

    capacity = models.PositiveIntegerField(null=True, blank=True)
    confirmed_count = models.PositiveIntegerField(default=0)

    is_paid = models.BooleanField(default=False)
    base_price = models.PositiveIntegerField(
        null=True, blank=True, help_text="Базовая цена билета, если нет индивидуальных цен"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    allowed_universities = models.ManyToManyField(
        University,
        blank=True,
        help_text="Если visibility=inter_uni",
    )

    class Meta:
        verbose_name = "Событие"
        verbose_name_plural = "События"

    def __str__(self) -> str:
        return self.title


class SeatGroupType(models.TextChoices):
    TABLE = "table", "Table"
    SECTOR = "sector", "Sector"
    ZONE = "zone", "Zone"


class SeatGroup(models.Model):
    """
    Универсальная группа мест: стол (банкет), сектор (стадион), зона (фан-зона).
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="seat_groups")
    code = models.CharField(max_length=20)   # T1, T2, A203, FAN и т.п.
    name = models.CharField(max_length=100)  # "Стол 1", "Фан-зона"
    type = models.CharField(
        max_length=20, choices=SeatGroupType.choices, default=SeatGroupType.TABLE
    )

    base_price = models.PositiveIntegerField()
    capacity = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("event", "code")
        verbose_name = "Группа мест"
        verbose_name_plural = "Группы мест"

    def __str__(self) -> str:
        return f"{self.event.slug} {self.code}"


class SeatStatus(models.TextChoices):
    FREE = "free", "Free"
    RESERVED = "reserved", "Reserved"
    SOLD = "sold", "Sold"
    BLOCKED = "blocked", "Blocked"


class Seat(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="seats")
    group = models.ForeignKey(SeatGroup, on_delete=models.CASCADE, related_name="seats")

    row = models.CharField(max_length=10, blank=True)  # для столов можно не использовать
    seat_number = models.PositiveIntegerField(null=True, blank=True)

    price = models.PositiveIntegerField()

    status = models.CharField(
        max_length=16, choices=SeatStatus.choices, default=SeatStatus.FREE
    )

    reserved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reserved_seats",
    )
    reserved_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("event", "group", "row", "seat_number")
        verbose_name = "Место"
        verbose_name_plural = "Места"

    def __str__(self) -> str:
        return f"{self.event.slug} {self.group.code} #{self.seat_number or '-'}"


class RegistrationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"
    WAITLIST = "waitlist", "Waitlist"


class PaymentStatus(models.TextChoices):
    NONE = "none", "None"
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    FAILED = "failed", "Failed"
    REFUNDED = "refunded", "Refunded"


class Registration(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="registrations")
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="registrations",
    )

    status = models.CharField(
        max_length=20, choices=RegistrationStatus.choices, default=RegistrationStatus.PENDING
    )
    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.NONE
    )

    promo_code = models.CharField(max_length=50, blank=True)
    final_price = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("event", "user")
        verbose_name = "Регистрация"
        verbose_name_plural = "Регистрации"

    def __str__(self) -> str:
        return f"{self.user} -> {self.event} ({self.status})"


def generate_ticket_token() -> str:
    raw = uuid.uuid4().hex
    secret = secrets.token_hex(16)
    return f"{raw}{secret}"


class Ticket(models.Model):
    registration = models.OneToOneField(
        Registration, on_delete=models.CASCADE, related_name="ticket"
    )
    seat = models.ForeignKey(
        Seat, on_delete=models.PROTECT, null=True, blank=True, related_name="tickets"
    )

    token = models.CharField(max_length=128, unique=True, default=generate_ticket_token)
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Билет"
        verbose_name_plural = "Билеты"

    def mark_used(self):
        if not self.is_used:
            self.is_used = True
            self.used_at = timezone.now()
            self.save(update_fields=["is_used", "used_at"])

    def __str__(self) -> str:
        return f"Ticket #{self.id} for {self.registration.user} ({self.registration.event})"


class CheckInLog(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="checkins")
    checked_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="performed_checkins",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Чек-ин"
        verbose_name_plural = "Чек-ины"

    def __str__(self) -> str:
        return f"Check-in {self.ticket_id} at {self.created_at}"
