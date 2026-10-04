from django.contrib.auth import views as auth_views
from django.urls import path

from accounts import views


app_name = "accounts"


urlpatterns = [
    path(
        "",
        views.profile,
        name="profile",
    ),
    path(
        "register/",
        views.register,
        name="register",
    ),
    path(
        "login/",
        views.RateLimitedLoginView.as_view(),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
]
