import hashlib

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import (
    login_required,
)
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import redirect, render

from accounts.forms import (
    CustomerProfileForm,
    CustomerRegistrationForm,
)
from accounts.models import CustomerProfile


LOGIN_RATE_WINDOW_SECONDS = 300
LOGIN_USER_IP_LIMIT = 5
LOGIN_IP_LIMIT = 10


def _hash_rate_identifier(value):
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _client_ip(request):
    forwarded_for = request.META.get(
        "HTTP_X_FORWARDED_FOR",
        "",
    )

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.META.get(
        "REMOTE_ADDR",
        "unknown",
    )


def _login_rate_keys(request):
    username = request.POST.get(
        "username",
        "",
    ).strip().casefold()

    client_ip = _client_ip(request)

    user_ip_identifier = (
        f"{username}|{client_ip}"
    )

    return (
        (
            "login-rate:user-ip:"
            f"{_hash_rate_identifier(user_ip_identifier)}"
        ),
        (
            "login-rate:ip:"
            f"{_hash_rate_identifier(client_ip)}"
        ),
    )


def _increment_rate_counter(key):
    created = cache.add(
        key,
        1,
        timeout=LOGIN_RATE_WINDOW_SECONDS,
    )

    if created:
        return 1

    try:
        return cache.incr(key)
    except ValueError:
        cache.set(
            key,
            1,
            timeout=LOGIN_RATE_WINDOW_SECONDS,
        )

        return 1


class RateLimitedLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        self.rate_limit_keys = (
            _login_rate_keys(request)
        )

        user_ip_key, ip_key = (
            self.rate_limit_keys
        )

        user_ip_failures = cache.get(
            user_ip_key,
            0,
        )

        ip_failures = cache.get(
            ip_key,
            0,
        )

        if (
            user_ip_failures
            >= LOGIN_USER_IP_LIMIT
            or ip_failures >= LOGIN_IP_LIMIT
        ):
            form = self.get_form()

            form.add_error(
                None,
                (
                    "Too many failed login attempts. "
                    "Please wait five minutes "
                    "and try again."
                ),
            )

            response = self.form_invalid(form)
            response.status_code = 429

            return response

        return super().post(
            request,
            *args,
            **kwargs,
        )

    def form_invalid(self, form):
        for key in self.rate_limit_keys:
            _increment_rate_counter(key)

        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete_many(
            self.rate_limit_keys
        )

        return super().form_valid(form)


@transaction.atomic
def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")

    if request.method == "POST":
        form = CustomerRegistrationForm(
            request.POST
        )

        if form.is_valid():
            user = form.save()

            CustomerProfile.objects.create(
                user=user
            )

            login(request, user)

            messages.success(
                request,
                "Your account has been created.",
            )

            return redirect(
                "accounts:profile"
            )
    else:
        form = CustomerRegistrationForm()

    return render(
        request,
        "accounts/register.html",
        {
            "form": form,
        },
    )


@login_required
def profile(request):
    customer_profile, unused = (
        CustomerProfile.objects.get_or_create(
            user=request.user
        )
    )

    if request.method == "POST":
        form = CustomerProfileForm(
            request.POST,
            instance=customer_profile,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Your profile has been updated.",
            )

            return redirect(
                "accounts:profile"
            )
    else:
        form = CustomerProfileForm(
            instance=customer_profile
        )

    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
        },
    )
