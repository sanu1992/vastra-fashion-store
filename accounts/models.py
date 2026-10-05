from django.conf import settings
from django.db import models


class CustomerProfile(models.Model):
    class AudiencePreference(models.TextChoices):
        MEN = "MEN", "Men"
        WOMEN = "WOMEN", "Women"
        UNISEX = "UNISEX", "Unisex"
        ALL = "ALL", "Show everything"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )

    supabase_user_id = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )

    phone = models.CharField(
        max_length=20,
        blank=True,
    )

    preferred_audience = models.CharField(
        max_length=10,
        choices=AudiencePreference.choices,
        default=AudiencePreference.ALL,
    )

    city = models.CharField(
        max_length=100,
        blank=True,
    )

    state = models.CharField(
        max_length=100,
        blank=True,
    )

    postal_code = models.CharField(
        max_length=12,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.user.email or self.user.username
