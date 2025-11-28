# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractUser):
    """
    Кастомная модель пользователя, использующая номер телефона вместо username.
    """
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    phone_number = models.CharField(
        max_length=15,
        unique=True,
        help_text="Номер телефона пользователя.",
        verbose_name='Номер телефона'
    )
    first_name = models.CharField(
        max_length=50,
        help_text="Имя пользователя.",
        verbose_name='Имя'
    )
    last_name = models.CharField(
        max_length=50,
        help_text="Фамилия пользователя.",
        verbose_name='Фамилия'
    )
    # Поля для SMS-кода
    otp_code = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        help_text="Одноразовый код для аутентификации."
    )
    otp_created_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Время создания OTP-кода."
    )
    telegram_chat_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text="Уникальный ID чата в Telegram для отправки уведомлений."
    )
    location_label = models.CharField(
        max_length=100,
        blank=True,
        help_text="Название сохраненной точки доставки (например, Дом)."
    )
    location_street = models.CharField(
        max_length=255,
        blank=True,
        help_text="Улица сохраненного адреса."
    )
    location_building = models.CharField(
        max_length=50,
        blank=True,
        help_text="Дом сохраненного адреса."
    )
    location_entrance = models.CharField(
        max_length=50,
        blank=True,
        help_text="Подъезд сохраненного адреса."
    )
    location_floor = models.CharField(
        max_length=50,
        blank=True,
        help_text="Этаж сохраненного адреса."
    )
    location_apartment = models.CharField(
        max_length=50,
        blank=True,
        help_text="Квартира сохраненного адреса."
    )
    location_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        help_text="Широта точки доставки."
    )
    location_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        help_text="Долгота точки доставки."
    )

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UserManager()

    def __str__(self):
        return self.phone_number

    @property
    def full_name(self):
        """
        Возвращает ФИО пользователя, собранное из полей first_name / last_name.
        """
        parts = [self.first_name or "", self.last_name or ""]
        full = " ".join(part for part in parts if part).strip()
        return full or ""

    def set_full_name(self, value: str):
        """
        Делит переданное ФИО на имя и фамилию для хранения в стандартных полях.
        """
        cleaned = (value or "").strip()
        if not cleaned:
            self.first_name = ""
            self.last_name = ""
            return

        parts = cleaned.split()
        self.first_name = parts[0]
        self.last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    def has_saved_location(self) -> bool:
        """Проверяет наличие сохраненного адреса."""
        required = [self.location_street, self.location_building, self.location_apartment]
        return all(required)

    def get_saved_location_payload(self) -> dict | None:
        """Возвращает данные сохраненного адреса."""
        if not self.has_saved_location():
            return None
        return {
            'address_street': self.location_street,
            'address_building': self.location_building,
            'address_entrance': self.location_entrance,
            'address_floor': self.location_floor,
            'address_apartment': self.location_apartment,
        }

    def update_saved_location(self, *, label: str | None = None, **address_fields) -> None:
        """Обновляет сохраненный адрес пользователя."""
        field_map = {
            'address_street': 'location_street',
            'address_building': 'location_building',
            'address_entrance': 'location_entrance',
            'address_floor': 'location_floor',
            'address_apartment': 'location_apartment',
        }
        update_fields = []
        if label is not None:
            self.location_label = label
            update_fields.append('location_label')
        for order_field, user_field in field_map.items():
            if order_field in address_fields:
                setattr(self, user_field, address_fields[order_field] or '')
                update_fields.append(user_field)
        if 'location_latitude' in address_fields:
            self.location_latitude = address_fields['location_latitude']
            update_fields.append('location_latitude')
        if 'location_longitude' in address_fields:
            self.location_longitude = address_fields['location_longitude']
            update_fields.append('location_longitude')
        if update_fields:
            self.save(update_fields=list(dict.fromkeys(update_fields)))


class TelegramAccount(models.Model):
    """Модель для хранения привязанных Telegram-аккаунтов."""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="telegram_account",
        verbose_name="Пользователь",
    )
    telegram_user_id = models.BigIntegerField(unique=True, verbose_name="Telegram user id")
    chat_id = models.BigIntegerField(null=True, blank=True, verbose_name="Chat ID")
    username = models.CharField(max_length=255, null=True, blank=True, verbose_name="Username")
    photo_url = models.URLField(null=True, blank=True, verbose_name="Ссылка на фото")
    linked_at = models.DateTimeField(default=timezone.now, verbose_name="Дата привязки")
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )

    class Meta:
        verbose_name = "Telegram аккаунт"
        verbose_name_plural = "Telegram аккаунты"
        ordering = ("-linked_at",)

    def __str__(self):
        return f"{self.username or self.telegram_user_id}"


class Address(models.Model):
    """Модель для хранения адресов доставки пользователей."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="addresses",
        verbose_name="Пользователь",
    )
    name = models.CharField(max_length=100, verbose_name="Название", help_text="Например: Дом, Офис")
    address = models.CharField(max_length=255, verbose_name="Адрес")
    longitude = models.CharField(max_length=64, verbose_name="Долгота")
    latitude = models.CharField(max_length=64, verbose_name="Широта")
    entrance = models.CharField(max_length=50, blank=True, verbose_name="Подъезд")
    intercom = models.CharField(max_length=50, blank=True, verbose_name="Домофон")
    floor = models.CharField(max_length=20, blank=True, verbose_name="Этаж")
    apartment = models.CharField(max_length=50, blank=True, verbose_name="Квартира")
    comment = models.TextField(blank=True, verbose_name="Комментарий для курьера")
    is_default = models.BooleanField(default=False, verbose_name="Адрес по умолчанию")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Адрес"
        verbose_name_plural = "Адреса"
        ordering = ("-is_default", "-updated_at")

    def __str__(self):
        return f"{self.name}: {self.address}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            Address.objects.filter(user=self.user).exclude(pk=self.pk).update(is_default=False)


class TelegramLinkCode(models.Model):
    """Модель для хранения кодов привязки Telegram-аккаунта."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="telegram_link_codes",
        verbose_name="Пользователь",
    )
    code = models.CharField(
        max_length=6,
        unique=True,
        verbose_name="Код привязки",
        help_text="6-значный код для привязки Telegram",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )
    expires_at = models.DateTimeField(
        verbose_name="Дата истечения",
        help_text="Время, до которого код действителен",
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата использования",
    )

    class Meta:
        verbose_name = "Код привязки Telegram"
        verbose_name_plural = "Коды привязки Telegram"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.code} ({self.user.phone_number})"

    def mark_used(self):
        """Помечает код как использованный."""
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

    @property
    def is_active(self):
        """Проверяет, активен ли код (не использован и не истёк)."""
        if self.used_at:
            return False
        return timezone.now() < self.expires_at
