import logging
import os
import json
import random
import hashlib
import hmac
from datetime import timedelta
from urllib.parse import parse_qsl
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth import get_user_model
from django.db import transaction

from rest_framework import status, serializers, generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from urllib.parse import unquote
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
)

from .models import (
    User,
    Address,
    TelegramAccount,
    TelegramLinkCode,
)
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserVerifyOTPSerializer,
    UserLocationSerializer,
    AddressSerializer,
    AuthTokensResponseSerializer,
    LoginSerializer,
    TelegramBotRegisterSerializer,
    TelegramInitPendingSerializer,
    TelegramInitSerializer,   # ВАЖНО: используем из serializers.py
    TelegramLinkConfirmSerializer,
    TelegramRegisterSerializer,
    UserSerializer,
)
from .services import link_telegram_account, generate_token_pair
from .telegram import validate_telegram_payload

logger = logging.getLogger(__name__)

# ---------- вспомогательные сериализаторы для схемы ----------


class MessageResponseSerializer(serializers.Serializer):
    message = serializers.CharField()


class ErrorResponseSerializer(serializers.Serializer):
    error = serializers.CharField()


class TokenResponseSerializer(serializers.Serializer):
    token = serializers.CharField()


class TelegramChatIdRequestSerializer(serializers.Serializer):
    chat_id = serializers.CharField()
    phone_number = serializers.CharField(required=False)


# --------------------------------------------------------------
# Telegram bot / OTP
# --------------------------------------------------------------

MY_TELEGRAM_CHAT_ID = os.getenv("MY_TELEGRAM_CHAT_ID", "8375951877")

try:
    import telegram
except ImportError:
    telegram = None

TELEGRAM_BOT_TOKEN = getattr(settings, "TELEGRAM_BOT_TOKEN", None) or os.getenv(
    "TELEGRAM_BOT_TOKEN"
)

if telegram and TELEGRAM_BOT_TOKEN:
    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
else:
    bot = None


def build_auth_response(user: User, *, status_code=status.HTTP_200_OK) -> Response:
    """
    Вернуть пару JWT-токенов + сериализованного пользователя.
    """
    token_pair = generate_token_pair(user)
    payload = {
        **token_pair,
        "user": UserSerializer(user).data,
    }
    return Response(payload, status=status_code)


def send_telegram_otp(user: User, otp_code: str) -> bool:
    """
    Отправка OTP-кода в Telegram.
    Сначала пытаемся отправить на user.telegram_chat_id,
    если его нет — шлём на MY_TELEGRAM_CHAT_ID.
    """
    if not bot:
        print("Ошибка: Telegram Bot не настроен (нет токена или библиотеки telegram).")
        return False

    chat_id = getattr(user, "telegram_chat_id", None) or MY_TELEGRAM_CHAT_ID
    if not chat_id:
        print("Ошибка: не указан chat_id для отправки OTP.")
        return False

    message = f"Ваш код для подтверждения: {otp_code}"

    try:
        bot.send_message(chat_id=chat_id, text=message)
        print(f"Код {otp_code} успешно отправлен в Telegram (chat_id={chat_id}).")
        return True
    except Exception as e:
        print(f"Не удалось отправить сообщение в Telegram: {e}")
        return False


# --------------------------------------------------------------
# Валидация initData для Telegram WebApp
# --------------------------------------------------------------


def validate_telegram_init_data(init_data: str) -> dict:
    """
    Валидируем Telegram.WebApp.initData по оф. алгоритму:
    https://docs.telegram-mini-apps.com/platform/init-data#validating
    """
    if not init_data:
        raise ValidationError("Отсутствует Telegram initData.")

    if not TELEGRAM_BOT_TOKEN:
        raise ValidationError("TELEGRAM_BOT_TOKEN не настроен на сервере.")

    # 1. Декодируем всю строку один раз (как в доках)
    decoded = unquote(init_data)

    pairs = []
    hash_value = None

    for chunk in decoded.split("&"):
        if chunk.startswith("hash="):
            # сохраняем hash отдельно
            hash_value = chunk.split("=", 1)[1]
            continue
        if not chunk or "=" not in chunk:
            continue
        k, v = chunk.split("=", 1)
        pairs.append((k, v))

    if not hash_value:
        raise ValidationError("Отсутствует hash в initData.")

    # 2. Сортируем по ключу
    pairs.sort(key=lambda x: x[0])

    # 3. Собираем data_check_string в формате key=value\n...
    data_check_string = "\n".join(f"{k}={v}" for k, v in pairs)

    # 4. HMAC-SHA256("WebAppData", bot_token)
    secret_key = hmac.new(
        "WebAppData".encode("utf-8"),
        TELEGRAM_BOT_TOKEN.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    # 5. HMAC-SHA256(secret_key, data_check_string)
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, hash_value):
        raise ValidationError("Некорректная подпись Telegram (Invalid Telegram signature).")

    # Можно вернуть распарсенные данные для удобства
    data_dict = {k: v for k, v in pairs}
    data_dict["hash"] = hash_value
    return data_dict


def get_or_create_user_from_telegram_userinfo(user_info: dict) -> User:
    """
    Старый helper (если понадобится привязка напрямую по Telegram user.id).
    Сейчас основной поток идёт через TelegramAccount, но оставим на будущее.
    """
    UserModel = get_user_model()

    telegram_id = user_info.get("id")
    if telegram_id is None:
        raise ValueError("Telegram user id is missing in initData.")

    model_fields = {f.name for f in UserModel._meta.get_fields()}

    lookup_kwargs = {}
    if "telegram_id" in model_fields:
        lookup_kwargs["telegram_id"] = telegram_id
    else:
        lookup_kwargs["username"] = f"tg_{telegram_id}"

    defaults = {}

    if "username" in model_fields and "username" not in lookup_kwargs:
        defaults["username"] = f"tg_{telegram_id}"

    if "first_name" in model_fields:
        defaults["first_name"] = user_info.get("first_name") or ""

    if "last_name" in model_fields:
        defaults["last_name"] = user_info.get("last_name") or ""

    if "is_active" in model_fields:
        defaults["is_active"] = True

    tg_username = user_info.get("username")
    if tg_username:
        if "telegram_username" in model_fields:
            defaults["telegram_username"] = tg_username
        elif "tg_username" in model_fields:
            defaults["tg_username"] = tg_username

    user, _ = UserModel.objects.get_or_create(
        defaults=defaults,
        **lookup_kwargs,
    )

    return user


# --------------------------------------------------------------
# OTP по номеру телефона
# --------------------------------------------------------------


class RegisterAPIView(APIView):
    """
    Регистрация нового пользователя по номеру телефона.
    Генерирует OTP и отправляет его в Telegram.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Регистрация пользователя",
        description="Регистрирует пользователя по номеру телефона и отправляет OTP-код в Telegram.",
        request=UserRegistrationSerializer,
        responses={
            201: OpenApiResponse(
                response=MessageResponseSerializer,
                description="Регистрация успешна. Код отправлен в Telegram.",
            ),
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Ошибка валидации данных.",
            ),
            409: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Пользователь с таким номером уже существует.",
            ),
        },
    )
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data["phone_number"]

        if User.objects.filter(phone_number=phone_number).exists():
            return Response(
                {"error": "Пользователь с таким номером уже существует."},
                status=status.HTTP_409_CONFLICT,
            )

        user = serializer.save()
        user.set_unusable_password()

        otp_code = f"{random.randint(0, 999999):06d}"
        user.otp_code = otp_code
        user.otp_created_at = timezone.now()
        user.save(update_fields=["password", "otp_code", "otp_created_at"])

        send_telegram_otp(user, otp_code)

        return Response(
            {"message": "Регистрация успешна. Код отправлен в Telegram."},
            status=status.HTTP_201_CREATED,
        )


class LoginAPIView(APIView):
    """
    Вход пользователя по номеру телефона.
    Генерирует и отправляет новый OTP в Telegram.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Отправка OTP для входа",
        description="Генерирует новый OTP-код для уже существующего пользователя и отправляет его в Telegram.",
        request=UserLoginSerializer,
        responses={
            200: OpenApiResponse(
                response=MessageResponseSerializer,
                description="Код для входа отправлен в Telegram.",
            ),
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Ошибка валидации данных.",
            ),
            404: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Пользователь с таким номером не найден.",
            ),
        },
    )
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data["phone_number"]

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response(
                {"error": "Пользователь с таким номером не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )

        otp_code = f"{random.randint(0, 999999):06d}"
        user.otp_code = otp_code
        user.otp_created_at = timezone.now()
        user.save(update_fields=["otp_code", "otp_created_at"])

        send_telegram_otp(user, otp_code)

        return Response(
            {"message": "Код для входа отправлен в Telegram."},
            status=status.HTTP_200_OK,
        )


class LogoutAPIView(APIView):
    """
    Выход из системы: удаление DRF Token.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            Token.objects.filter(user=request.user).delete()
            return Response(
                {"detail": "Успешный выход из системы."},
                status=status.HTTP_200_OK,
            )
        except Exception:
            return Response(
                {"detail": "Ошибка при выходе из системы."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class VerifyOTPAPIView(APIView):
    """
    Подтверждение OTP-кода.
    При успехе — выдаёт token (DRF TokenAuth).
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Подтверждение OTP",
        description="Проверяет OTP-код и выдаёт токен для аутентификации.",
        request=UserVerifyOTPSerializer,
        responses={
            200: OpenApiResponse(
                response=TokenResponseSerializer,
                description="Код подтверждён, возвращён токен.",
            ),
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Неверный или просроченный код / ошибка валидации.",
            ),
            404: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Пользователь не найден.",
            ),
        },
    )
    def post(self, request):
        serializer = UserVerifyOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data["phone_number"]
        otp_code = serializer.validated_data["otp_code"]

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response(
                {"error": "Пользователь не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if (
            user.otp_code == otp_code
            and user.otp_created_at
            and (timezone.now() - user.otp_created_at) < timedelta(minutes=5)
        ):
            user.otp_code = None
            user.otp_created_at = None
            user.save(update_fields=["otp_code", "otp_created_at"])

            token, _ = Token.objects.get_or_create(user=user)

            return Response(
                {"token": token.key},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"error": "Неверный или просроченный код."},
            status=status.HTTP_400_BAD_REQUEST,
        )


# --------------------------------------------------------------
# Профиль, локация, Telegram chat_id
# --------------------------------------------------------------


# class UserLocationAPIView(APIView):
#     permission_classes = [IsAuthenticated]
#
#     @extend_schema(
#         summary="Получить сохраненную локацию пользователя",
#         responses={200: UserLocationSerializer},
#     )
#     def get(self, request):
#         serializer = UserLocationSerializer(request.user)
#         return Response(serializer.data, status=status.HTTP_200_OK)
#
#     @extend_schema(
#         summary="Обновить сохраненную локацию пользователя",
#         request=UserLocationSerializer,
#         responses={200: UserLocationSerializer},
#     )
#     def put(self, request):
#         serializer = UserLocationSerializer(request.user, data=request.data)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#         return Response(serializer.data, status=status.HTTP_200_OK)
#
#     @extend_schema(
#         summary="Частично обновить сохраненную локацию пользователя",
#         request=UserLocationSerializer,
#         responses={200: UserLocationSerializer},
#     )
#     def patch(self, request):
#         serializer = UserLocationSerializer(
#             request.user,
#             data=request.data,
#             partial=True,
#         )
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#         return Response(serializer.data, status=status.HTTP_200_OK)
#

class GetTelegramChatIdAPIView(APIView):
    """
    Привязка Telegram chat_id к пользователю.
    Ожидает:
      - chat_id (обязателен)
      - phone_number (опционально; если нет — берём request.user)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Привязать Telegram chat_id",
        description="Сохраняет chat_id Telegram для пользователя.",
        request=TelegramChatIdRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=MessageResponseSerializer,
                description="Telegram-аккаунт успешно привязан.",
            ),
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Ошибка валидации или другая ошибка.",
            ),
            404: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Пользователь не найден.",
            ),
        },
    )
    def post(self, request):
        chat_id = request.data.get("chat_id")
        phone_number = request.data.get("phone_number")

        if not chat_id:
            return Response(
                {"error": "chat_id обязателен."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            if phone_number:
                user = User.objects.get(phone_number=phone_number)
            else:
                user = request.user

            user.telegram_chat_id = chat_id
            user.save(update_fields=["telegram_chat_id"])

            return Response(
                {"message": "Telegram-аккаунт успешно привязан."},
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            return Response(
                {"error": "Пользователь не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


# --------------------------------------------------------------
# Telegram Bot: регистрация/линк
# --------------------------------------------------------------


class TelegramBotRegisterOrLinkView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=TelegramBotRegisterSerializer,
        responses={
            200: OpenApiResponse(AuthTokensResponseSerializer, description="Пользователь найден, Telegram привязан"),
            201: OpenApiResponse(AuthTokensResponseSerializer, description="Новый пользователь создан и привязан"),
            400: OpenApiResponse(description="Некорректные данные"),
        },
    )
    def post(self, request):
        serializer = TelegramBotRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        phone_number = data["phone"]
        user, created = User.objects.get_or_create(
            phone_number=phone_number,
            defaults={"username": phone_number},
        )

        if created:
            user.set_unusable_password()

        if not user.username:
            user.username = phone_number

        user.set_full_name(data["full_name"])
        user.save(update_fields=["first_name", "last_name", "username"])

        link_telegram_account(
            user=user,
            telegram_user_id=data["telegram_user_id"],
            chat_id=data["chat_id"],
            username=data.get("username"),
            photo_url=None,
        )

        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return build_auth_response(user, status_code=response_status)


# --------------------------------------------------------------
# Telegram WebApp: авторизация и регистрация
# --------------------------------------------------------------


@extend_schema(
    request=TelegramInitSerializer,
    responses={
        200: OpenApiResponse(AuthTokensResponseSerializer, description="Успешная авторизация"),
        202: OpenApiResponse(
            TelegramInitPendingSerializer,
            description="Пользователь ещё не завершил регистрацию",
            examples=[
                OpenApiExample(
                    "Not registered",
                    value={"status": "not_registered"},
                )
            ],
        ),
        400: OpenApiResponse(description="Некорректные данные Telegram"),
    },
)
class TelegramWebAppInitView(APIView):
    """
    Авторизация через Telegram Mini App.
    Принимает Telegram.WebApp.initData, валидирует подпись и
    логинит/создаёт пользователя, возвращая JWT-токены.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Авторизация через Telegram WebApp",
        description=(
            "Принимает строку Telegram.WebApp.initData, валидирует подпись по алгоритму "
            "HMAC-SHA256 и создаёт/находит пользователя. Обновляет TelegramAccount и "
            "возвращает пару токенов + данные пользователя."
        ),
        request=TelegramInitSerializer,
        responses={
            200: OpenApiResponse(
                response=AuthTokensResponseSerializer,
                description="Успешная авторизация, возвращены токены.",
            ),
            202: OpenApiResponse(
                response=TelegramInitPendingSerializer,
                description="Пользователь ещё не зарегистрирован в системе.",
            ),
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Неверная подпись или некорректные данные.",
            ),
        },
    )
    def post(self, request):
        logger.info("WEBAPP_INIT request.data = %s", request.data)

        serializer = TelegramInitSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("WEBAPP_INIT serializer errors = %s", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        init_data = serializer.validated_data["telegram_init_data"]
        payload = serializer.validated_data.get("payload") or {}

        # 1) Валидируем initData (подпись Telegram)
        try:
            _data = validate_telegram_init_data(init_data)
        except DjangoValidationError as e:
            logger.warning("WEBAPP_INIT validate_telegram_init_data error = %s", e)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # 2) Валидируем payload через ваш validate_telegram_payload
        try:
            payload = validate_telegram_payload(
                init_data,
                payload,
            )
        except DjangoValidationError as exc:
            logger.warning("WEBAPP_INIT validate_telegram_payload error = %s", exc)
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        logger.info("WEBAPP_INIT payload after validation = %s", payload)

        user = (
            User.objects.select_related("telegram_account")
            .filter(telegram_account__telegram_user_id=payload["telegram_user_id"])
            .first()
        )

        if not user or not getattr(user, "telegram_account", None):
            logger.info(
                "WEBAPP_INIT: user not registered for telegram_user_id=%s",
                payload.get("telegram_user_id"),
            )
            return Response(
                {"status": "not_registered"},
                status=status.HTTP_202_ACCEPTED,
            )

        # 3) Обновляем данные Telegram-аккаунта
        with transaction.atomic():
            telegram_account = user.telegram_account
            updated_fields = []

            if payload.get("username") and payload.get("username") != telegram_account.username:
                telegram_account.username = payload["username"]
                updated_fields.append("username")

            if payload.get("chat_id") and payload.get("chat_id") != telegram_account.chat_id:
                telegram_account.chat_id = payload["chat_id"]
                updated_fields.append("chat_id")

            if payload.get("photo_url") and payload.get("photo_url") != telegram_account.photo_url:
                telegram_account.photo_url = payload["photo_url"]
                updated_fields.append("photo_url")

            telegram_account.linked_at = timezone.now()
            updated_fields.append("linked_at")
            telegram_account.save(update_fields=updated_fields)

        logger.info(
            "WEBAPP_INIT success for user_id=%s, telegram_user_id=%s",
            user.id,
            payload.get("telegram_user_id"),
        )

        return build_auth_response(user)


@extend_schema(
    request=TelegramRegisterSerializer,
    responses={
        200: OpenApiResponse(
            AuthTokensResponseSerializer,
            description="Telegram-аккаунт уже был привязан",
        ),
        201: OpenApiResponse(
            AuthTokensResponseSerializer,
            description="Новый пользователь зарегистрирован",
        ),
        400: OpenApiResponse(description="Некорректные данные Telegram"),
    },
)
class TelegramWebAppRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TelegramRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            payload = validate_telegram_payload(
                data.get("telegram_init_data"),
                data.get("payload"),
            )
        except DjangoValidationError as exc:
            return Response({"error": exc.message}, status=status.HTTP_400_BAD_REQUEST)

        phone_number = data["phone"]
        defaults = {
            "username": phone_number,
        }
        user, created = User.objects.get_or_create(
            phone_number=phone_number,
            defaults=defaults,
        )

        if created:
            user.set_unusable_password()

        if not user.username:
            user.username = phone_number

        user.set_full_name(data["full_name"])
        user.save(update_fields=["first_name", "last_name", "username"])

        existing = User.objects.filter(
            telegram_account__telegram_user_id=payload["telegram_user_id"]
        ).exclude(pk=user.pk)

        if existing.exists():
            return Response(
                {"error": "Этот Telegram уже привязан к другому аккаунту."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_raw = data.get("user")
        if not user_raw:
            link_telegram_account(
                user=user,
                telegram_user_id=payload["telegram_user_id"],
                chat_id=payload.get("chat_id"),
                username=payload.get("username"),
                photo_url=payload.get("photo_url"),
            )

        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return build_auth_response(user, status_code=response_status)


class TelegramAccountStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        telegram_user_id = request.query_params.get("telegram_user_id")
        if not telegram_user_id:
            return Response(
                {"error": "telegram_user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            account = TelegramAccount.objects.select_related("user").get(
                telegram_user_id=telegram_user_id
            )
        except TelegramAccount.DoesNotExist:
            return Response({"status": "not_registered"}, status=status.HTTP_200_OK)

        user = account.user
        return Response(
            {
                "status": "linked",
                "user": {
                    "id": user.id,
                    "phone_number": user.phone_number,
                    "full_name": user.full_name,
                },
            },
            status=status.HTTP_200_OK,
        )


# --------------------------------------------------------------
# Адреса пользователя
# --------------------------------------------------------------


class AddressListCreateView(generics.ListCreateAPIView):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user).order_by(
            "-is_default", "-updated_at"
        )

    @extend_schema(
        summary="Список адресов пользователя",
        responses={200: AddressSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Создать адрес пользователя",
        description="Создаёт новый адрес, привязанный к текущему пользователю.",
        request=AddressSerializer,
        responses={
            201: OpenApiResponse(
                response=AddressSerializer,
                description="Адрес успешно создан.",
            ),
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Ошибка валидации.",
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)


# --------------------------------------------------------------
# Link-коды для привязки Telegram
# --------------------------------------------------------------


class TelegramLinkCodeView(APIView):
    """
    API для генерации кода привязки Telegram-аккаунта.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        code = "".join(random.choices("0123456789", k=6))
        expires_at = timezone.now() + timedelta(minutes=10)

        link_code = TelegramLinkCode.objects.create(
            user=user,
            code=code,
            expires_at=expires_at,
        )

        return Response(
            {
                "code": link_code.code,
                "expires_at": link_code.expires_at,
            },
            status=status.HTTP_201_CREATED,
        )


class TelegramLinkConfirmView(APIView):
    """
    API для подтверждения привязки Telegram-аккаунта по коду.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TelegramLinkConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            link_code = TelegramLinkCode.objects.get(code=data["code"])
        except TelegramLinkCode.DoesNotExist:
            return Response(
                {"detail": "Неверный код."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not link_code.is_active:
            return Response(
                {"detail": "Код истёк или уже использован."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        telegram_user_id = data["telegram_user_id"]
        existing = User.objects.filter(
            telegram_account__telegram_user_id=telegram_user_id
        ).exclude(pk=link_code.user.pk)

        if existing.exists():
            return Response(
                {"detail": "Этот Telegram-аккаунт уже привязан к другому пользователю."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        link_telegram_account(
            user=link_code.user,
            telegram_user_id=telegram_user_id,
            chat_id=data.get("chat_id"),
            username=data.get("username"),
        )
        link_code.mark_used()

        return build_auth_response(link_code.user)
