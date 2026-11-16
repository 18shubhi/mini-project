"""Authentication URL routes."""
from django.urls import path

from .views import CurrentUserView, LoginView, RegistrationView, SafeTokenRefreshView


app_name = "accounts"

urlpatterns = [
    path("register/", RegistrationView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("token/refresh/", SafeTokenRefreshView.as_view(), name="token-refresh"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
]
