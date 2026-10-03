from django.conf import settings
from django.db import models

from catalog.models import (
    Category,
    Product,
    ProductVariant,
)


class Retailer(models.Model):
    class Channel(models.TextChoices):
        ONLINE = "ONLINE", "Online"
        PHYSICAL = "PHYSICAL", "Physical stores"
        BOTH = "BOTH", "Online and physical"

    class IntegrationLevel(models.TextChoices):
        LINK_ONLY = "LINK_ONLY", "External link only"
        DEMO = "DEMO", "Development demo"
        MANUAL_FEED = "MANUAL_FEED", "Manual catalogue feed"
        AFFILIATE_FEED = (
            "AFFILIATE_FEED",
            "Affiliate catalogue feed",
        )
        LIVE_API = "LIVE_API", "Live retailer API"
        CHECKOUT_API = (
            "CHECKOUT_API",
            "Integrated checkout API",
        )

    name = models.CharField(
        max_length=150,
        unique=True,
    )

    slug = models.SlugField(
        max_length=170,
        unique=True,
    )

    website_url = models.URLField(
        max_length=1000,
    )

    search_url_template = models.CharField(
        max_length=1000,
        blank=True,
        help_text=(
            "Use {query} where the encoded customer "
            "search should be inserted."
        ),
    )

    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        default=Channel.ONLINE,
    )

    integration_level = models.CharField(
        max_length=30,
        choices=IntegrationLevel.choices,
        default=IntegrationLevel.LINK_ONLY,
    )

    supported_categories = models.ManyToManyField(
        Category,
        related_name="retailers",
        blank=True,
    )

    is_demo = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class StoreLocation(models.Model):
    retailer = models.ForeignKey(
        Retailer,
        on_delete=models.CASCADE,
        related_name="store_locations",
    )

    name = models.CharField(max_length=180)

    address = models.TextField(blank=True)
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

    map_url = models.URLField(
        max_length=1000,
        blank=True,
    )

    is_demo = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "retailer__name",
            "city",
            "name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "retailer",
                    "name",
                    "postal_code",
                ],
                name="uniq_store_name_pin",
            ),
        ]

    def __str__(self):
        location = self.city or self.postal_code

        if location:
            return (
                f"{self.retailer.name} — "
                f"{self.name}, {location}"
            )

        return f"{self.retailer.name} — {self.name}"


class RetailerOffer(models.Model):
    class Availability(models.TextChoices):
        IN_STOCK = "IN_STOCK", "In stock"
        OUT_OF_STOCK = "OUT_OF_STOCK", "Out of stock"
        CHECK_RETAILER = (
            "CHECK_RETAILER",
            "Check with retailer",
        )
        UNKNOWN = "UNKNOWN", "Unknown"

    class Fulfilment(models.TextChoices):
        ONLINE = "ONLINE", "Online"
        STORE = "STORE", "Physical store"
        BOTH = "BOTH", "Online or store"

    retailer = models.ForeignKey(
        Retailer,
        on_delete=models.CASCADE,
        related_name="offers",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="retailer_offers",
        null=True,
        blank=True,
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        related_name="retailer_offers",
        null=True,
        blank=True,
    )

    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        related_name="retailer_offers",
        null=True,
        blank=True,
    )

    store_location = models.ForeignKey(
        StoreLocation,
        on_delete=models.SET_NULL,
        related_name="offers",
        null=True,
        blank=True,
    )

    external_sku = models.CharField(
        max_length=100,
        blank=True,
    )

    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)

    product_url = models.URLField(
        max_length=2000,
    )

    image_url = models.URLField(
        max_length=2000,
        blank=True,
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    available_sizes = models.JSONField(
        default=list,
        blank=True,
    )

    colors = models.JSONField(
        default=list,
        blank=True,
    )

    availability = models.CharField(
        max_length=30,
        choices=Availability.choices,
        default=Availability.CHECK_RETAILER,
    )

    fulfilment = models.CharField(
        max_length=20,
        choices=Fulfilment.choices,
        default=Fulfilment.ONLINE,
    )

    is_demo = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    last_verified_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "price",
            "retailer__name",
            "title",
        ]
        indexes = [
            models.Index(
                fields=[
                    "retailer",
                    "is_active",
                ],
                name="offer_retailer_active_idx",
            ),
            models.Index(
                fields=[
                    "category",
                    "is_active",
                ],
                name="offer_category_active_idx",
            ),
        ]

    def __str__(self):
        return f"{self.title} — {self.retailer.name}"


class DemandRequest(models.Model):
    class Status(models.TextChoices):
        MATCHED = "MATCHED", "Exact match found"
        PARTIAL = "PARTIAL", "Partial match found"
        UNMATCHED = "UNMATCHED", "No match found"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="demand_requests",
        null=True,
        blank=True,
    )

    session_key = models.CharField(
        max_length=100,
        blank=True,
    )

    original_query = models.TextField()

    parsed_intent = models.JSONField(
        default=dict,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UNMATCHED,
    )

    internal_match_count = models.PositiveIntegerField(
        default=0,
    )

    retailer_match_count = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=[
                    "status",
                    "created_at",
                ],
                name="demand_status_created_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.get_status_display()} — "
            f"{self.original_query[:80]}"
        )
