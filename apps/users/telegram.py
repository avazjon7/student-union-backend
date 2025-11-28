# apps/users/telegram.py

import json
import logging
import hmac
import hashlib
from urllib.parse import unquote
from typing import Optional, Dict, Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

logger = logging.getLogger("telegram")

BOT_TOKEN = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
MAX_AUTH_AGE_SECONDS = 60 * 60 * 24  # 24 часа


def _parse_init_data(init_data: str):
    """
    Разбираем initData в пары (key, value) и отдельно вытаскиваем hash.
    Делаем это по алгоритму из документации Telegram WebApp.
    """
    if not init_data:
        raise ValidationError("Отсутствует Telegram initData.")

    decoded = unquote(init_data)

    pairs = []
    hash_value = None

    for chunk in decoded.split("&"):
        if chunk.startswith("hash="):
            hash_value = chunk.split("=", 1)[1]
            continue
        if not chunk or "=" not in chunk:
            continue
        k, v = chunk.split("=", 1)
        pairs.append((k, v))

    if not hash_value:
        raise ValidationError("Отсутствует hash в initData.")

    return pairs, hash_value


def _check_hash(init_data: str) -> Dict[str, str]:
    """
    Проверяем подпись initData по официальному алгоритму Telegram WebApp.
    Возвращаем dict с данными (без hash).
    """
    if not BOT_TOKEN:
        raise ValidationError("TELEGRAM_BOT_TOKEN не настроен на сервере.")

    pairs, received_hash = _parse_init_data(init_data)

    # key=value\n, отсортированные по ключу
    pairs_sorted = sorted(pairs, key=lambda x: x[0])
    data_check_string = "\n".join(f"{k}={v}" for k, v in pairs_sorted)

    # secret_key = HMAC_SHA256("WebAppData", bot_token)
    secret_key = hmac.new(
        "WebAppData".encode("utf-8"),
        BOT_TOKEN.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    # expected_hash = HMAC_SHA256(secret_key, data_check_string)
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        logger.warning(
            "[telegram] signature mismatch",
            extra={
                "data": dict(pairs_sorted),
                "data_check": data_check_string,
                "expected": expected_hash,
                "received": received_hash,
                "init_data_present": True,
            },
        )
        raise ValidationError("Некорректная подпись Telegram (Invalid Telegram signature).")

    return dict(pairs_sorted)


def validate_telegram_payload(
    init_data: Optional[str],
    payload: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Основная функция, которую ты вызываешь из views.

    - Проверяет подпись initData (WebApp).
    - Проверяет, что auth_date не истёк.
    - Достаёт user.id / username / photo_url из initData.
    - Дополняет/переопределяет данными из payload (chat_id, phone, full_name и т.п.).

    Возвращает словарь:
      {
        "telegram_user_id": int,
        "username": str | None,
        "first_name": str | None,
        "last_name": str | None,
        "photo_url": str | None,
        "chat_id": int | str | None,
        "phone": str | None,       # если передан во фронтовом payload
        "full_name": str | None,   # если передан во фронтовом payload
      }
    """
    if not init_data:
        raise ValidationError("Telegram init data is required.")

    # 1. Проверяем подпись и разбираем данные
    data = _check_hash(init_data)

    # 2. Проверяем актуальность auth_date (TTL)
    auth_date_raw = data.get("auth_date")
    if auth_date_raw:
        try:
            auth_date_ts = int(auth_date_raw)
        except (TypeError, ValueError):
            raise ValidationError("Некорректный auth_date в initData.")

        now_ts = int(timezone.now().timestamp())
        if now_ts - auth_date_ts > MAX_AUTH_AGE_SECONDS:
            raise ValidationError("Telegram payload is expired.")

    # 3. Достаём user payload
    user_raw = data.get("user")
    if not user_raw:
        raise ValidationError("В initData отсутствует поле user.")

    try:
        user_info = json.loads(user_raw)
    except json.JSONDecodeError:
        raise ValidationError("Некорректный JSON в поле user initData.")

    if "id" not in user_info:
        raise ValidationError("Telegram user payload must include id.")

    telegram_user_id = int(user_info["id"])
    username = user_info.get("username")
    first_name = user_info.get("first_name")
    last_name = user_info.get("last_name")
    photo_url = user_info.get("photo_url")

    # 4. Базовый результат
    result: Dict[str, Any] = {
        "telegram_user_id": telegram_user_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "photo_url": photo_url,
        "chat_id": None,
    }

    # 5. Если фронт передал доп. payload — учитываем его
    if payload:
        # chat_id можно получить от бота или фронта
        if "chat_id" in payload:
            result["chat_id"] = payload["chat_id"]

        # username / photo_url можно обновить
        if payload.get("username"):
            result["username"] = payload["username"]
        if payload.get("photo_url"):
            result["photo_url"] = payload["photo_url"]

        # Прокидываем телефон и ФИО для регистрации
        if "phone" in payload:
            result["phone"] = payload["phone"]
        if "full_name" in payload:
            result["full_name"] = payload["full_name"]

    return result
