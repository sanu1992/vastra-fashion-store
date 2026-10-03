from django.contrib import admin

from .models import (
    DemandRequest,
    Retailer,
    RetailerOffer,
    StoreLocation,
)


class StoreLocationInline(admin.TabularInline):
    model = StoreLocation
    extra = 0

    fields = (
        "name",
        "city",
        "state",
        "postal_code",
        "is_demo",
        "is_active",
    )


@admin.register(Retailer)
class RetailerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "channel",
        "integration_level",
        "is_demo",
        "is_active",
        "updated_at",
    )

    list_filter = (
        "channel",
        "integration_level",
        "is_demo",
        "is_active",
    )

    search_fields = (
        "name",
        "slug",
        "website",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }

    filter_horizontal = (
        "supported_categories",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    inlines = (
        StoreLocationInline,
    )


@admin.register(StoreLocation)
class StoreLocationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "retailer",
        "city",
        "state",
        "postal_code",
        "is_demo",
        "is_active",
    )

    list_filter = (
        "retailer",
        "city",
        "state",
        "is_demo",
        "is_active",
    )

    search_fields = (
        "name",
        "retailer__name",
        "address",
        "city",
        "state",
        "postal_code",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(RetailerOffer)
class RetailerOfferAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "retailer",
        "category",
        "price",
        "availability",
        "fulfilment",
        "is_demo",
        "is_active",
        "updated_at",
    )

    list_filter = (
        "retailer",
        "category",
        "availability",
        "fulfilment",
        "is_demo",
        "is_active",
    )

    search_fields = (
        "title",
        "external_sku",
        "retailer__name",
        "product__name",
        "variant__sku",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    autocomplete_fields = (
        "retailer",
        "category",
        "product",
        "variant",
        "store_location",
    )


@admin.register(DemandRequest)
class DemandRequestAdmin(admin.ModelAdmin):
    list_display = (
        "short_query",
        "user",
        "status",
        "internal_match_count",
        "retailer_match_count",
        "created_at",
    )

    list_filter = (
        "status",
        "created_at",
    )

    search_fields = (
        "original_query",
        "user__username",
        "user__email",
        "session_key",
    )

    readonly_fields = (
        "user",
        "session_key",
        "original_query",
        "parsed_intent",
        "status",
        "internal_match_count",
        "retailer_match_count",
        "created_at",
    )

    ordering = (
        "-created_at",
    )

    @admin.display(description="Customer request")
    def short_query(self, obj):
        if len(obj.original_query) <= 70:
            return obj.original_query

        return f"{obj.original_query[:67]}..."
