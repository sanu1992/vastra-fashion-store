from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.shortcuts import (
    get_object_or_404,
    render,
)

from catalog.models import (
    Category,
    Inventory,
    Product,
    ProductMedia,
    ProductVariant,
)


PRODUCTS_PER_PAGE = 24


def catalog_product_queryset():
    inventory_queryset = (
        Inventory.objects
        .filter(warehouse__is_active=True)
        .select_related("warehouse")
    )

    variant_queryset = (
        ProductVariant.objects
        .filter(is_active=True)
        .prefetch_related(
            Prefetch(
                "inventory_records",
                queryset=inventory_queryset,
                to_attr="active_inventory",
            )
        )
    )

    media_queryset = (
        ProductMedia.objects
        .filter(
            media_type=ProductMedia.MediaType.IMAGE
        )
        .select_related("variant")
        .order_by(
            "-is_primary",
            "position",
            "id",
        )
    )

    return (
        Product.objects
        .select_related(
            "category",
            "category__parent",
        )
        .prefetch_related(
            Prefetch(
                "variants",
                queryset=variant_queryset,
                to_attr="active_variants",
            ),
            Prefetch(
                "media",
                queryset=media_queryset,
                to_attr="storefront_media",
            ),
        )
    )


def prepare_product(product):
    variants = list(
        getattr(
            product,
            "active_variants",
            [],
        )
    )

    for variant in variants:
        inventory_records = getattr(
            variant,
            "active_inventory",
            [],
        )

        variant.available_stock = sum(
            max(
                inventory.quantity_on_hand
                - inventory.quantity_reserved,
                0,
            )
            for inventory in inventory_records
        )

    variants.sort(
        key=lambda variant: (
            variant.available_stock == 0,
            variant.color.lower(),
            variant.size.lower(),
            variant.price,
        )
    )

    product.storefront_variants = variants

    product.selected_variant = next(
        (
            variant
            for variant in variants
            if variant.available_stock > 0
        ),
        variants[0] if variants else None,
    )

    variant_prices = [
        variant.price
        for variant in variants
    ]

    if variant_prices:
        product.storefront_price = min(
            variant_prices
        )
    else:
        product.storefront_price = product.price

    if variants:
        product.storefront_stock = sum(
            variant.available_stock
            for variant in variants
        )
    else:
        product.storefront_stock = product.stock

    image_urls = []

    for media in getattr(
        product,
        "storefront_media",
        [],
    ):
        if media.url and media.url not in image_urls:
            image_urls.append(media.url)

    if (
        product.image_url
        and product.image_url not in image_urls
    ):
        image_urls.append(product.image_url)

    if isinstance(product.ai_metadata, dict):
        for image_url in product.ai_metadata.get(
            "images",
            [],
        ):
            if (
                image_url
                and image_url not in image_urls
            ):
                image_urls.append(image_url)

    product.storefront_images = image_urls

    product.storefront_image_url = (
        image_urls[0]
        if image_urls
        else ""
    )

    return product


def storefront(request):
    products = (
        catalog_product_queryset()
        .filter(is_active=True)
        .order_by("-created_at")
    )

    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    category_slug = request.GET.get(
        "category",
        "",
    ).strip()

    selected_category = None

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(sku__icontains=search_query)
            | Q(variants__sku__icontains=search_query)
            | Q(variants__color__icontains=search_query)
            | Q(variants__size__icontains=search_query)
        ).distinct()

    if category_slug:
        selected_category = get_object_or_404(
            Category,
            slug=category_slug,
            is_active=True,
        )

        if selected_category.parent_id is None:
            products = products.filter(
                Q(category=selected_category)
                | Q(category__parent=selected_category)
            )
        else:
            products = products.filter(
                category=selected_category
            )

    paginator = Paginator(
        products,
        PRODUCTS_PER_PAGE,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    prepared_products = [
        prepare_product(product)
        for product in page_obj.object_list
    ]

    page_range = list(
        paginator.get_elided_page_range(
            page_obj.number,
            on_each_side=2,
            on_ends=1,
        )
    )

    pagination_parameters = request.GET.copy()
    pagination_parameters.pop("page", None)

    categories = (
        Category.objects
        .filter(
            parent__isnull=True,
            is_active=True,
        )
        .filter(
            Q(products__is_active=True)
            | Q(children__products__is_active=True)
        )
        .distinct()
        .order_by("name")
    )

    context = {
        "products": prepared_products,
        "page_obj": page_obj,
        "page_range": page_range,
        "pagination_ellipsis": paginator.ELLIPSIS,
        "pagination_query": (
            pagination_parameters.urlencode()
        ),
        "categories": categories,
        "selected_category": selected_category,
        "search_query": search_query,
    }

    return render(
        request,
        "catalog/storefront.html",
        context,
    )


def product_detail(request, slug):
    product = get_object_or_404(
        catalog_product_queryset(),
        slug=slug,
        is_active=True,
    )

    prepare_product(product)

    related_products = list(
        catalog_product_queryset()
        .filter(
            category=product.category,
            is_active=True,
        )
        .exclude(id=product.id)
        .order_by("-created_at")[:4]
    )

    related_products = [
        prepare_product(related)
        for related in related_products
    ]

    context = {
        "product": product,
        "selected_variant": product.selected_variant,
        "related_products": related_products,
    }

    return render(
        request,
        "catalog/product_detail.html",
        context,
    )
