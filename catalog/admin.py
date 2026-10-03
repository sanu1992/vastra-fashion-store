import json

from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Category,
    Inventory,
    Product,
    ProductMedia,
    ProductVariant,
    Warehouse,
)


admin.site.site_header = "Fashion Store Administration"
admin.site.site_title = "Fashion Store Admin"
admin.site.index_title = "Store Management"


class ProductAdminForm(forms.ModelForm):
    tags_text = forms.CharField(
        label="Tags",
        required=False,
        help_text="Enter tags separated by commas.",
        widget=forms.TextInput(
            attrs={
                "placeholder": (
                    "silver bracelet, jewellery, daily wear"
                ),
            }
        ),
    )

    class Meta:
        model = Product
        exclude = ["tags"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance:
            self.fields["tags_text"].initial = ", ".join(
                self.instance.tags or []
            )

    def save(self, commit=True):
        product = super().save(commit=False)

        tags_text = self.cleaned_data.get(
            "tags_text",
            "",
        )

        product.tags = [
            tag.strip()
            for tag in tags_text.split(",")
            if tag.strip()
        ]

        if commit:
            product.save()
            self.save_m2m()

        return product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "parent",
        "slug",
        "is_active",
        "ai_generated",
    ]

    list_filter = [
        "parent",
        "is_active",
        "ai_generated",
    ]

    search_fields = [
        "name",
        "parent__name",
        "description",
    ]

    prepopulated_fields = {
        "slug": ("name",),
    }


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    show_change_link = True

    fields = [
        "sku",
        "color",
        "size",
        "price",
        "compare_at_price",
        "is_active",
    ]


class ProductMediaInline(admin.TabularInline):
    model = ProductMedia
    extra = 0
    show_change_link = True

    fields = [
        "variant",
        "media_type",
        "source",
        "url",
        "position",
        "is_primary",
    ]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm

    inlines = [
        ProductVariantInline,
        ProductMediaInline,
    ]

    list_display = [
        "name",
        "sku",
        "category",
        "price",
        "stock",
        "audience",
        "ai_generated",
        "is_active",
    ]

    list_filter = [
        "is_active",
        "ai_generated",
        "audience",
        "category",
        "ai_model",
    ]

    search_fields = [
        "name",
        "sku",
        "description",
        "category__name",
    ]

    list_select_related = [
        "category",
        "category__parent",
    ]

    autocomplete_fields = ["category"]

    prepopulated_fields = {
        "slug": ("name",),
    }

    readonly_fields = [
        "image_preview",
        "ai_generated",
        "ai_model",
        "formatted_ai_metadata",
        "created_at",
        "updated_at",
    ]

    actions = [
        "publish_selected_products",
        "unpublish_selected_products",
    ]

    save_on_top = True

    fieldsets = [
        (
            "Product information",
            {
                "fields": [
                    "sku",
                    "name",
                    "slug",
                    "category",
                    "description",
                ]
            },
        ),
        (
            "Commercial information",
            {
                "fields": [
                    "price",
                    "stock",
                    "audience",
                    "image_url",
                    "image_preview",
                ]
            },
        ),
        (
            "AI catalogue suggestion",
            {
                "classes": ["collapse"],
                "fields": [
                    "tags_text",
                    "alt_text",
                    "ai_generated",
                    "ai_model",
                    "formatted_ai_metadata",
                ],
            },
        ),
        (
            "Publishing",
            {
                "fields": [
                    "is_active",
                ]
            },
        ),
        (
            "Audit information",
            {
                "classes": ["collapse"],
                "fields": [
                    "created_at",
                    "updated_at",
                ],
            },
        ),
    ]

    @admin.display(description="Image preview")
    def image_preview(self, product):
        if not product.image_url:
            return "No image provided"

        return format_html(
            '<img src="{}" alt="" '
            'style="max-width: 240px; max-height: 240px; '
            'object-fit: contain; border-radius: 8px;">',
            product.image_url,
        )

    @admin.display(description="AI metadata")
    def formatted_ai_metadata(self, product):
        if not product.ai_metadata:
            return "No AI metadata"

        formatted_metadata = json.dumps(
            product.ai_metadata,
            indent=2,
            ensure_ascii=False,
        )

        return format_html(
            '<pre style="white-space: pre-wrap; '
            'max-width: 800px;">{}</pre>',
            formatted_metadata,
        )

    @admin.action(
        description="Publish selected products"
    )
    def publish_selected_products(
        self,
        request,
        queryset,
    ):
        updated = queryset.update(is_active=True)

        self.message_user(
            request,
            f"Published {updated} product(s).",
        )

    @admin.action(
        description="Return selected products to draft"
    )
    def unpublish_selected_products(
        self,
        request,
        queryset,
    ):
        updated = queryset.update(is_active=False)

        self.message_user(
            request,
            f"Returned {updated} product(s) to draft.",
        )


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = [
        "sku",
        "product",
        "color",
        "size",
        "price",
        "is_active",
    ]

    list_filter = [
        "is_active",
        "size",
        "color",
    ]

    search_fields = [
        "sku",
        "product__name",
        "product__sku",
        "color",
        "size",
    ]

    list_select_related = ["product"]

    autocomplete_fields = ["product"]

    readonly_fields = [
        "created_at",
        "updated_at",
    ]


@admin.register(ProductMedia)
class ProductMediaAdmin(admin.ModelAdmin):
    list_display = [
        "product",
        "variant",
        "media_type",
        "source",
        "position",
        "is_primary",
    ]

    list_filter = [
        "media_type",
        "source",
        "is_primary",
    ]

    search_fields = [
        "product__name",
        "product__sku",
        "variant__sku",
        "alt_text",
    ]

    list_select_related = [
        "product",
        "variant",
    ]

    autocomplete_fields = [
        "product",
        "variant",
    ]

    readonly_fields = ["created_at"]


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "name",
        "city",
        "state",
        "postal_code",
        "is_active",
    ]

    list_filter = [
        "is_active",
        "state",
        "city",
    ]

    search_fields = [
        "code",
        "name",
        "city",
        "state",
        "postal_code",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
    ]


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = [
        "variant",
        "warehouse",
        "quantity_on_hand",
        "quantity_reserved",
        "available_stock",
        "reorder_level",
        "updated_at",
    ]

    list_filter = [
        "warehouse",
    ]

    search_fields = [
        "variant__sku",
        "variant__product__name",
        "warehouse__code",
        "warehouse__name",
    ]

    list_select_related = [
        "variant",
        "variant__product",
        "warehouse",
    ]

    autocomplete_fields = [
        "variant",
        "warehouse",
    ]

    readonly_fields = [
        "available_stock",
        "updated_at",
    ]

    @admin.display(
        description="Available",
        ordering="quantity_on_hand",
    )
    def available_stock(self, inventory):
        return inventory.available_quantity
