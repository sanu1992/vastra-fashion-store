from django.db import models
from django.db.models import F, Q


class Category(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
    )
    slug = models.SlugField(
        max_length=120,
        unique=True,
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )
    description = models.TextField(blank=True)

    ai_metadata = models.JSONField(
        default=dict,
        blank=True,
    )
    ai_generated = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"

        return self.name


class Product(models.Model):
    class Audience(models.TextChoices):
        MEN = "MEN", "Men"
        WOMEN = "WOMEN", "Women"
        UNISEX = "UNISEX", "Unisex"

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )

    # This remains the base product SKU during migration.
    # Purchasable SKUs will belong to ProductVariant.
    sku = models.CharField(
        max_length=40,
        unique=True,
    )

    name = models.CharField(max_length=200)

    slug = models.SlugField(
        max_length=220,
        unique=True,
    )

    description = models.TextField(blank=True)

    # These two fields remain temporarily so the current
    # storefront and importer continue working.
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    stock = models.PositiveIntegerField(default=0)

    audience = models.CharField(
        max_length=10,
        choices=Audience.choices,
        default=Audience.UNISEX,
    )

    image_url = models.URLField(
        blank=True,
        max_length=2000,
    )

    tags = models.JSONField(
        default=list,
        blank=True,
    )

    alt_text = models.CharField(
        max_length=255,
        blank=True,
    )

    ai_metadata = models.JSONField(
        default=dict,
        blank=True,
    )
    ai_generated = models.BooleanField(default=False)
    ai_model = models.CharField(
        max_length=100,
        blank=True,
    )

    # AI-imported products remain drafts until approved.
    is_active = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(
                fields=["is_active", "category"],
                name="product_active_category_idx",
            ),
            models.Index(
                fields=["audience"],
                name="product_audience_idx",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
    )

    sku = models.CharField(
        max_length=60,
        unique=True,
    )

    size = models.CharField(
        max_length=30,
        blank=True,
    )

    color = models.CharField(
        max_length=80,
        blank=True,
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    compare_at_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    attributes = models.JSONField(
        default=dict,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "product__name",
            "price",
            "sku",
        ]
        indexes = [
            models.Index(
                fields=["product", "is_active"],
                name="variant_product_active_idx",
            ),
            models.Index(
                fields=["size", "color"],
                name="variant_size_color_idx",
            ),
        ]

    def __str__(self):
        details = " / ".join(
            value
            for value in [self.color, self.size]
            if value
        )

        if not details:
            details = "Default"

        return f"{self.product.name} — {details} ({self.sku})"


class ProductMedia(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "IMAGE", "Image"
        VIDEO = "VIDEO", "Video"

    class Source(models.TextChoices):
        MERCHANT = "MERCHANT", "Merchant"
        SUPPLIER = "SUPPLIER", "Supplier"
        CUSTOMER = "CUSTOMER", "Customer"
        AI = "AI", "AI generated"

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="media",
    )

    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="media",
        null=True,
        blank=True,
    )

    media_type = models.CharField(
        max_length=10,
        choices=MediaType.choices,
        default=MediaType.IMAGE,
    )

    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.SUPPLIER,
    )

    url = models.URLField(max_length=2000)

    alt_text = models.CharField(
        max_length=255,
        blank=True,
    )

    position = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = [
            "position",
            "id",
        ]
        indexes = [
            models.Index(
                fields=["product", "position"],
                name="media_product_position_idx",
            ),
        ]
        verbose_name_plural = "product media"

    def __str__(self):
        return (
            f"{self.product.name} — "
            f"{self.get_media_type_display()}"
        )


class Warehouse(models.Model):
    code = models.CharField(
        max_length=30,
        unique=True,
    )

    name = models.CharField(max_length=150)

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

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Inventory(models.Model):
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="inventory_records",
    )

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="inventory_records",
    )

    quantity_on_hand = models.PositiveIntegerField(default=0)
    quantity_reserved = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "warehouse__name",
            "variant__sku",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "variant",
                    "warehouse",
                ],
                name="unique_variant_warehouse",
            ),
            models.CheckConstraint(
                condition=Q(
                    quantity_reserved__lte=F(
                        "quantity_on_hand"
                    )
                ),
                name="inventory_reserved_lte_on_hand",
            ),
        ]
        indexes = [
            models.Index(
                fields=["warehouse", "variant"],
                name="inventory_wh_variant_idx",
            ),
        ]
        verbose_name_plural = "inventory"

    @property
    def available_quantity(self):
        return (
            self.quantity_on_hand
            - self.quantity_reserved
        )

    def __str__(self):
        return (
            f"{self.variant.sku} at "
            f"{self.warehouse.code}: "
            f"{self.available_quantity} available"
        )
