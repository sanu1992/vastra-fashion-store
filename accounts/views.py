import hashlib
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    get_user_model,
    login as django_login,
)
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.auth_forms import (
    SupabaseLoginForm,
    SupabaseRegistrationForm,
)
from accounts.forms import CustomerProfileForm
from accounts.models import CustomerProfile


LOGIN_RATE_WINDOW_SECONDS = 300
LOGIN_USER_IP_LIMIT = 5
LOGIN_IP_LIMIT = 10
SUPABASE_TIMEOUT_SECONDS = 15


class SupabaseRejected(Exception):
    pass


class SupabaseUnavailable(Exception):
    pass


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
    email = request.POST.get(
        "email",
        "",
    ).strip().casefold()

    client_ip = _client_ip(request)

    user_ip_identifier = f"{email}|{client_ip}"

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


def _supabase_configuration():
    supabase_url = getattr(
        settings,
        "SUPABASE_URL",
        "",
    ).strip().rstrip("/")

    publishable_key = getattr(
        settings,
        "SUPABASE_PUBLISHABLE_KEY",
        "",
    ).strip()

    if not supabase_url or not publishable_key:
        raise SupabaseUnavailable(
            "Customer authentication is not configured."
        )

    return supabase_url, publishable_key


def _supabase_error_message(error_body):
    try:
        payload = json.loads(error_body)
    except json.JSONDecodeError:
        return "Authentication request was rejected."

    return (
        payload.get("msg")
        or payload.get("message")
        or payload.get("error_description")
        or payload.get("error")
        or "Authentication request was rejected."
    )


def _supabase_request(
    path,
    *,
    payload=None,
    access_token=None,
):
    supabase_url, publishable_key = (
        _supabase_configuration()
    )

    headers = {
        "apikey": publishable_key,
        "Accept": "application/json",
    }

    if access_token:
        headers["Authorization"] = (
            f"Bearer {access_token}"
        )

    request_data = None
    method = "GET"

    if payload is not None:
        request_data = json.dumps(payload).encode(
            "utf-8"
        )
        headers["Content-Type"] = "application/json"
        method = "POST"

    request = Request(
        f"{supabase_url}{path}",
        data=request_data,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(
            request,
            timeout=SUPABASE_TIMEOUT_SECONDS,
        ) as response:
            response_body = response.read().decode(
                "utf-8"
            )

    except HTTPError as error:
        error_body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        raise SupabaseRejected(
            _supabase_error_message(error_body)
        ) from error

    except (URLError, TimeoutError) as error:
        raise SupabaseUnavailable(
            "The authentication service is temporarily "
            "unavailable. Please try again."
        ) from error

    if not response_body:
        return {}

    try:
        return json.loads(response_body)
    except json.JSONDecodeError as error:
        raise SupabaseUnavailable(
            "The authentication service returned "
            "an invalid response."
        ) from error


def _supabase_sign_in(email, password):
    session = _supabase_request(
        "/auth/v1/token?grant_type=password",
        payload={
            "email": email,
            "password": password,
        },
    )

    access_token = session.get("access_token")

    if not access_token:
        raise SupabaseRejected(
            "Invalid email or password."
        )

    return _supabase_request(
        "/auth/v1/user",
        access_token=access_token,
    )


def _supabase_sign_up(form):
    return _supabase_request(
        "/auth/v1/signup",
        payload={
            "email": form.cleaned_data["email"],
            "password": form.cleaned_data["password1"],
            "data": {
                "first_name": (
                    form.cleaned_data["first_name"]
                ),
                "last_name": (
                    form.cleaned_data["last_name"]
                ),
            },
        },
    )


def _shadow_username(supabase_user_id):
    return (
        "supabase_"
        f"{str(supabase_user_id).replace('-', '')}"
    )


@transaction.atomic
def _synchronise_django_user(supabase_user):
    User = get_user_model()

    supabase_user_id = supabase_user.get("id")
    email = (
        supabase_user.get("email")
        or ""
    ).strip().casefold()

    if not supabase_user_id or not email:
        raise SupabaseRejected(
            "Supabase did not return a valid user."
        )

    metadata = (
        supabase_user.get("user_metadata")
        or {}
    )

    profile = (
        CustomerProfile.objects
        .select_for_update()
        .select_related("user")
        .filter(
            supabase_user_id=supabase_user_id
        )
        .first()
    )

    if profile:
        user = profile.user
    else:
        user = (
            User.objects
            .filter(email__iexact=email)
            .order_by("id")
            .first()
        )

        if user is None:
            user = User(
                username=_shadow_username(
                    supabase_user_id
                ),
                email=email,
            )

            user.set_unusable_password()
            user.save()

        profile, unused = (
            CustomerProfile.objects
            .select_for_update()
            .get_or_create(user=user)
        )

        if (
            profile.supabase_user_id
            and str(profile.supabase_user_id)
            != str(supabase_user_id)
        ):
            raise SupabaseRejected(
                "This local account is already linked "
                "to another identity."
            )

        profile.supabase_user_id = (
            supabase_user_id
        )
        profile.save(
            update_fields=[
                "supabase_user_id",
                "updated_at",
            ]
        )

    changed_fields = []

    if user.email != email:
        user.email = email
        changed_fields.append("email")

    first_name = str(
        metadata.get("first_name") or ""
    ).strip()[:150]

    last_name = str(
        metadata.get("last_name") or ""
    ).strip()[:150]

    if first_name and user.first_name != first_name:
        user.first_name = first_name
        changed_fields.append("first_name")

    if last_name and user.last_name != last_name:
        user.last_name = last_name
        changed_fields.append("last_name")

    if user.has_usable_password():
        user.set_unusable_password()
        changed_fields.append("password")

    if changed_fields:
        user.save(update_fields=changed_fields)

    return user


def _safe_next_url(request):
    next_url = (
        request.POST.get("next")
        or request.GET.get("next")
        or ""
    )

    if url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url

    return reverse("accounts:profile")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")

    status_code = 200

    if request.method == "POST":
        form = SupabaseLoginForm(request.POST)
        rate_keys = _login_rate_keys(request)

        user_ip_key, ip_key = rate_keys

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
            form.add_error(
                None,
                (
                    "Too many failed login attempts. "
                    "Please wait five minutes and try again."
                ),
            )
            status_code = 429

        elif form.is_valid():
            try:
                supabase_user = _supabase_sign_in(
                    form.cleaned_data["email"],
                    form.cleaned_data["password"],
                )

                user = _synchronise_django_user(
                    supabase_user
                )

            except SupabaseRejected:
                for key in rate_keys:
                    _increment_rate_counter(key)

                form.add_error(
                    None,
                    "Invalid email or password.",
                )

            except SupabaseUnavailable as error:
                form.add_error(
                    None,
                    str(error),
                )
                status_code = 503

            else:
                cache.delete_many(rate_keys)

                django_login(
                    request,
                    user,
                    backend=(
                        "django.contrib.auth.backends."
                        "ModelBackend"
                    ),
                )

                request.session.set_expiry(3600)

                return redirect(
                    _safe_next_url(request)
                )
    else:
        form = SupabaseLoginForm()

    return render(
        request,
        "accounts/login.html",
        {
            "form": form,
            "next": request.GET.get("next", ""),
        },
        status=status_code,
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")

    status_code = 200

    if request.method == "POST":
        form = SupabaseRegistrationForm(
            request.POST
        )

        if form.is_valid():
            try:
                response = _supabase_sign_up(form)

                access_token = response.get(
                    "access_token"
                )

                if access_token:
                    supabase_user = (
                        _supabase_request(
                            "/auth/v1/user",
                            access_token=access_token,
                        )
                    )

                    user = (
                        _synchronise_django_user(
                            supabase_user
                        )
                    )

                    django_login(
                        request,
                        user,
                        backend=(
                            "django.contrib.auth.backends."
                            "ModelBackend"
                        ),
                    )

                    request.session.set_expiry(3600)

                    messages.success(
                        request,
                        "Your account has been created.",
                    )

                    return redirect(
                        "accounts:profile"
                    )

                messages.success(
                    request,
                    (
                        "Check your email to confirm your "
                        "account, then sign in."
                    ),
                )

                return redirect(
                    "accounts:login"
                )

            except SupabaseRejected as error:
                form.add_error(
                    None,
                    str(error),
                )

            except SupabaseUnavailable as error:
                form.add_error(
                    None,
                    str(error),
                )
                status_code = 503
    else:
        form = SupabaseRegistrationForm()

    return render(
        request,
        "accounts/register.html",
        {
            "form": form,
        },
        status=status_code,
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
