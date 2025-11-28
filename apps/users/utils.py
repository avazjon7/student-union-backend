import re


def normalize_phone(phone: str) -> str:
    """
    Нормализует номер телефона, удаляя все символы кроме цифр и плюса.

    Args:
        phone: Номер телефона в любом формате

    Returns:
        Нормализованный номер телефона

    Examples:
        >>> normalize_phone("+7 (123) 456-78-90")
        '+71234567890'
        >>> normalize_phone("8 123 456 78 90")
        '81234567890'
    """
    if not phone:
        return ""

    digits_only = re.sub(r'\D', '', phone)
    if not digits_only:
        return ""

    return f"+{digits_only}"
