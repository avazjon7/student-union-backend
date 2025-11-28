# apps/users/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User


class CustomUserCreationForm(UserCreationForm):
    # Добавляем поле username, чтобы Django не выдавал ошибку
    username = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            'phone_number',
            'first_name',
            'last_name',
            'location_label',
            'location_street',
            'location_building',
            'location_entrance',
            'location_floor',
            'location_apartment',
            'location_latitude',
            'location_longitude',
        )  # Убираем username отсюда

    def save(self, commit=True):
        # Автоматически генерируем уникальное имя пользователя
        user = super().save(commit=False)
        if not user.username:
            user.username = user.phone_number
        if commit:
            user.save()
        return user


class CustomUserChangeForm(UserChangeForm):
    # Добавляем поле username
    username = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = User
        fields = (
            'phone_number',
            'first_name',
            'last_name',
            'location_label',
            'location_street',
            'location_building',
            'location_entrance',
            'location_floor',
            'location_apartment',
            'location_latitude',
            'location_longitude',
        )