from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import (
    login_required,
)
from django.db import transaction
from django.shortcuts import redirect, render

from accounts.forms import (
    CustomerProfileForm,
    CustomerRegistrationForm,
)
from accounts.models import CustomerProfile


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
