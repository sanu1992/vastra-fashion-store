from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from accounts.models import CustomerProfile


User = get_user_model()


class CustomerRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
        )

    def clean_email(self):
        email = self.cleaned_data[
            "email"
        ].strip().lower()

        if User.objects.filter(
            email__iexact=email
        ).exists():
            raise forms.ValidationError(
                "An account already uses this email."
            )

        return email

    def save(self, commit=True):
        user = super().save(
            commit=False
        )

        user.email = self.cleaned_data[
            "email"
        ].strip().lower()

        if commit:
            user.save()

        return user


class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = CustomerProfile
        fields = (
            "phone",
            "preferred_audience",
            "city",
            "state",
            "postal_code",
        )
