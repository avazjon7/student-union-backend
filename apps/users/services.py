import secrets
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from .models import TelegramAccount, TelegramLinkCode, User


def generate_token_pair(user: User) -> dict:
    refresh = RefreshToken.for_user(user)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def link_telegram_account(
    *,
    user: User,
    telegram_user_id: int,
    chat_id: Optional[int] = None,
    username: Optional[str] = None,
    photo_url: Optional[str] = None,
) -> TelegramAccount:
    """
    Создаёт или обновляет связь пользователя с Telegram-аккаунтом.
    """

    with transaction.atomic():
        account, _ = TelegramAccount.objects.select_for_update().get_or_create(
            telegram_user_id=telegram_user_id,
            defaults={
                "user": user,
                "chat_id": chat_id,
                "username": username,
                "photo_url": photo_url,
            },
        )
        account.user = user
        if chat_id:
            account.chat_id = chat_id
        account.username = username or account.username
        if photo_url:
            account.photo_url = photo_url
        account.linked_at = timezone.now()
        account.save()

    return account


def create_link_code(user: User) -> TelegramLinkCode:
    ttl_minutes = getattr(settings, "TELEGRAM_LINK_CODE_TTL_MINUTES", 10)
    expires_at = timezone.now() + timedelta(minutes=ttl_minutes)

    # Убеждаемся, что предыдущие активные коды больше не действительны
    TelegramLinkCode.objects.filter(user=user, used_at__isnull=True, expires_at__gt=timezone.now()).update(
        expires_at=timezone.now()
    )

    while True:
        code = secrets.token_urlsafe(8)
        if not TelegramLinkCode.objects.filter(code=code).exists():
            break

    return TelegramLinkCode.objects.create(user=user, code=code, expires_at=expires_at)
