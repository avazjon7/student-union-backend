# users/serializers.py
import json

from rest_framework import serializers
from .models import User


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,  # Теперь поле необязательно
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = [
            'phone_number',
            'first_name',
            'last_name',
            'password',
            'location_label',
            'location_street',
            'location_building',
            'location_entrance',
            'location_floor',
            'location_apartment',
            'location_latitude',
            'location_longitude',
        ]
        extra_kwargs = {
            'location_label': {'required': False},
            'location_street': {'required': False},
            'location_building': {'required': False},
            'location_entrance': {'required': False},
            'location_floor': {'required': False},
            'location_apartment': {'required': False},
            'location_latitude': {'required': False},
            'location_longitude': {'required': False},
        }

from .models import Address, TelegramAccount, User
from .utils import normalize_phone


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    telegram_linked = serializers.SerializerMethodField()
    telegram_username = serializers.SerializerMethodField()
    telegram_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "phone_number",
            "full_name",
            "telegram_linked",
            "telegram_username",
            "telegram_photo_url",
        )

    def create(self, validated_data):
        location_keys = {
            key: validated_data.pop(key, None)
            for key in [
                'location_label',
                'location_street',
                'location_building',
                'location_entrance',
                'location_floor',
                'location_apartment',
                'location_latitude',
                'location_longitude',
            ]
        }
        # Используем phone_number для создания пользователя
        user = User.objects.create_user(
            phone_number=validated_data['phone_number'],
            first_name=validated_data.get('first_name'),
            last_name=validated_data.get('last_name'),
            **{k: v for k, v in location_keys.items() if v is not None}
        )
        # Если пароль был предоставлен, устанавливаем его
        if 'password' in validated_data:
            user.set_password(validated_data['password'])
            user.save()
        else:
            # Если пароль не был предоставлен, делаем его непригодным
            user.set_unusable_password()
            user.save()

        return user

    def get_full_name(self, obj: User) -> str:
        return obj.full_name

    def get_telegram_linked(self, obj: User) -> bool:
        return hasattr(obj, "telegram_account") and obj.telegram_account is not None

    def get_telegram_username(self, obj: User) -> str | None:
        account = getattr(obj, "telegram_account", None)
        return getattr(account, "username", None)

    def get_telegram_photo_url(self, obj: User) -> str | None:
        account = getattr(obj, "telegram_account", None)
        return getattr(account, "photo_url", None)

class UserLoginSerializer(serializers.Serializer):
    """
    Сериализатор для входа по номеру телефона.
    """
    phone_number = serializers.CharField(max_length=15)


class PhoneValidationMixin:
    def validate_phone(self, value: str):
        normalized = normalize_phone(value)
        if not normalized:
            raise serializers.ValidationError("Введите корректный номер телефона в международном формате.")

        return normalized


class LoginSerializer(PhoneValidationMixin, serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True)


class TelegramBotRegisterSerializer(PhoneValidationMixin, serializers.Serializer):
    telegram_user_id = serializers.IntegerField()
    chat_id = serializers.IntegerField()
    full_name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=20)
    username = serializers.CharField(max_length=255, required=False, allow_blank=True)

class UserVerifyOTPSerializer(serializers.Serializer):
    """
    Сериализатор для подтверждения SMS-кода.
    """
    phone_number = serializers.CharField(max_length=15)
    otp_code = serializers.CharField(max_length=6)

class TelegramInitSerializer(serializers.Serializer):
    telegram_init_data = serializers.CharField()
    payload = serializers.JSONField(required=False)


class UserLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'location_label',
            'location_street',
            'location_building',
            'location_entrance',
            'location_floor',
            'location_apartment',
            'location_latitude',
            'location_longitude',
        ]


class TelegramRegisterSerializer(PhoneValidationMixin, TelegramInitSerializer):
    full_name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=20)


class TelegramLinkConfirmSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64)
    telegram_user_id = serializers.IntegerField()
    chat_id = serializers.IntegerField()
    username = serializers.CharField(max_length=255, required=False, allow_blank=True)


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            "id",
            "name",
            "address",
            "longitude",
            "latitude",
            "entrance",
            "intercom",
            "floor",
            "apartment",
            "comment",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "created_at", "updated_at")


class AuthTokensResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()


class TelegramInitPendingSerializer(serializers.Serializer):
    status = serializers.CharField(default="not_registered")

