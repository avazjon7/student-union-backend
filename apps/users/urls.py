from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterAPIView,
    LoginAPIView,
    VerifyOTPAPIView,
    # UserLocationAPIView,
    GetTelegramChatIdAPIView,
    AddressDetailView,
    AddressListCreateView,
    LogoutAPIView,
    MeAPIView,
    TelegramAccountStatusView,
    TelegramBotRegisterOrLinkView,
    TelegramLinkCodeView,
    TelegramLinkConfirmView,
    TelegramWebAppInitView,
    TelegramWebAppRegisterView,  # Добавьте эту строку
)



urlpatterns = [

    path("register/", RegisterAPIView.as_view(), name="auth-register"),
    path("login/", LoginAPIView.as_view(), name="auth-login"),
    path("verify-otp/", VerifyOTPAPIView.as_view(), name="auth-verify-otp"),
    # path("location/", UserLocationAPIView.as_view(), name="user-location"),
    path("telegram/chat-id/", GetTelegramChatIdAPIView.as_view(), name="auth-telegram-chat-id"),
    path("telegram/webapp/init/", TelegramWebAppInitView.as_view(), name="telegram-webapp-init"),

    path("login/", LoginAPIView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
    path("me/", MeAPIView.as_view(), name="me"),
    path(
        "telegram/bot-register-or-link/",
        TelegramBotRegisterOrLinkView.as_view(),
        name="telegram_bot_register",
    ),
    path(
        "telegram/webapp/init/",
        TelegramWebAppInitView.as_view(),
        name="telegram_webapp_init",
    ),
    path(
        "telegram/webapp/register/",
        TelegramWebAppRegisterView.as_view(),
        name="telegram_webapp_register",
    ),
    path(
        "telegram/account/status/",
        TelegramAccountStatusView.as_view(),
        name="telegram_account_status",
    ),
    path(
        "telegram/link/code/",
        TelegramLinkCodeView.as_view(),
        name="telegram_link_code",
    ),
    path(
        "telegram/link/",
        TelegramLinkConfirmView.as_view(),
        name="telegram_link_confirm",
    ),
    path("addresses/", AddressListCreateView.as_view(), name="address_list_create"),
    path("addresses/<int:pk>/", AddressDetailView.as_view(), name="address_detail"),

]
