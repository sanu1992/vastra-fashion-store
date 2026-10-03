import json
import time
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import DatabaseError, transaction
from django.utils.text import slugify

from catalog.models import Category, Product


SOURCE_CATEGORY_MAP = {
    "mens-shirts": {
        "parent": "Men Clothing",
        "subcategory": "Men's Shirts",
        "audience": Product.Audience.MEN,
    },
    "tops": {
        "parent": "Women Clothing",
        "subcategory": "Women's Tops",
        "audience": Product.Audience.WOMEN,
    },
    "womens-dresses": {
        "parent": "Women Clothing",
        "subcategory": "Women's Dresses",
        "audience": Product.Audience.WOMEN,
    },
    "womens-jewellery": {
        "parent": "Jewellery",
        "subcategory": "Women's Jewellery",
        "audience": Product.Audience.WOMEN,
    },
    "mens-shoes": {
        "parent": "Footwear",
        "subcategory": "Men's Footwear",
        "audience": Product.Audience.MEN,
    },
    "womens-shoes": {
        "parent": "Footwear",
        "subcategory": "Women's Footwear",
        "audience": Product.Audience.WOMEN,
    },
    "womens-bags": {
        "parent": "Accessories",
        "subcategory": "Women's Bags",
        "audience": Product.Audience.WOMEN,
    },
}


class DemoCatalogError(Exception):
    pass


class Command(BaseCommand):
    help = (
        "Import products with matching images "
        "from the DummyJSON demonstration catalogue"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--categories",
            default=(
                "mens-shirts,tops,womens-dresses,"
                "womens-jewellery,mens-shoes,womens-shoes"
            ),
            help="Comma-separated DummyJSON categories",
        )

        parser.add_argument(
            "--limit-per-category",
            type=int,
            default=3,
            help="Products to import from each category",
        )

        parser.add_argument(
            "--price-multiplier",
            type=Decimal,
            default=Decimal("80"),
            help=(
                "Demonstration multiplier applied "
                "to source prices"
            ),
        )

        parser.add_argument(
            "--activate",
            action="store_true",
            help="Publish imported products immediately",
        )

    def handle(self, *args, **options):
        source_categories = self._parse_categories(
            options["categories"]
        )

        limit_per_category = options[
            "limit_per_category"
        ]

        price_multiplier = options[
            "price_multiplier"
        ]

        activate = options["activate"]

        if limit_per_category < 1:
            raise CommandError(
                "--limit-per-category must be at least 1"
            )

        if limit_per_category > 30:
            raise CommandError(
                "--limit-per-category cannot exceed 30"
            )

        if price_multiplier <= 0:
            raise CommandError(
                "--price-multiplier must be positive"
            )

        created_count = 0
        skipped_count = 0
        failed_count = 0

        for source_category in source_categories:
            category_mapping = SOURCE_CATEGORY_MAP[
                source_category
            ]

            self.stdout.write("")
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"Importing: {source_category}"
                )
            )

            try:
                source_products = self._fetch_products(
                    source_category,
                    limit_per_category,
                )
            except DemoCatalogError as error:
                failed_count += 1

                self.stderr.write(
                    self.style.ERROR(
                        f"FAILED CATEGORY "
                        f"{source_category}: {error}"
                    )
                )
                continue

            parent_category = (
                self._get_or_create_category(
                    category_mapping["parent"]
                )
            )

            product_category = (
                self._get_or_create_category(
                    category_mapping["subcategory"],
                    parent=parent_category,
                )
            )

            for source_product in source_products:
                try:
                    source_id = int(
                        source_product["id"]
                    )

                    sku = f"DJ-{source_id:04d}"

                    if Product.objects.filter(
                        sku=sku
                    ).exists():
                        skipped_count += 1

                        self.stdout.write(
                            self.style.WARNING(
                                f"SKIPPED {sku}: "
                                f"already exists"
                            )
                        )
                        continue

                    title = str(
                        source_product["title"]
                    ).strip()

                    description = str(
                        source_product.get(
                            "description",
                            "",
                        )
                    ).strip()

                    if not title:
                        raise ValueError(
                            "Source product title is empty"
                        )

                    images = source_product.get(
                        "images",
                        [],
                    )

                    if not isinstance(images, list):
                        images = []

                    images = [
                        str(image).strip()
                        for image in images
                        if str(image).strip()
                    ]

                    thumbnail = str(
                        source_product.get(
                            "thumbnail",
                            "",
                        )
                    ).strip()

                    if images:
                        image_url = images[0]
                    else:
                        image_url = thumbnail

                    if not image_url:
                        raise ValueError(
                            "Source product has no image"
                        )

                    source_price = Decimal(
                        str(source_product["price"])
                    )

                    price = (
                        source_price
                        * price_multiplier
                    ).quantize(
                        Decimal("0.01")
                    )

                    stock = int(
                        source_product.get(
                            "stock",
                            0,
                        )
                    )

                    if stock < 0:
                        stock = 0

                    tags = source_product.get(
                        "tags",
                        [],
                    )

                    if not isinstance(tags, list):
                        tags = []

                    tags = [
                        str(tag).strip()
                        for tag in tags
                        if str(tag).strip()
                    ]

                    product_slug = slugify(
                        f"{title}-{sku}"
                    )[:220]

                    source_metadata = {
                        "source": "DummyJSON",
                        "source_product_id": source_id,
                        "source_category": source_category,
                        "source_sku": source_product.get(
                            "sku",
                            "",
                        ),
                        "brand": source_product.get(
                            "brand",
                            "",
                        ),
                        "original_price": str(
                            source_price
                        ),
                        "price_multiplier": str(
                            price_multiplier
                        ),
                        "thumbnail": thumbnail,
                        "images": images,
                    }

                    with transaction.atomic():
                        Product.objects.create(
                            category=product_category,
                            sku=sku,
                            name=title,
                            slug=product_slug,
                            description=description,
                            price=price,
                            stock=stock,
                            audience=category_mapping[
                                "audience"
                            ],
                            image_url=image_url,
                            tags=tags,
                            alt_text=title,
                            ai_metadata=source_metadata,
                            ai_generated=False,
                            ai_model="",
                            is_active=activate,
                        )

                    created_count += 1

                    status = (
                        "PUBLISHED"
                        if activate
                        else "DRAFT"
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"CREATED {sku}: "
                            f"{title} [{status}]"
                        )
                    )

                except (
                    DatabaseError,
                    InvalidOperation,
                    KeyError,
                    TypeError,
                    ValueError,
                ) as error:
                    failed_count += 1

                    source_reference = (
                        source_product.get("id")
                        or "unknown"
                    )

                    self.stderr.write(
                        self.style.ERROR(
                            f"FAILED SOURCE "
                            f"{source_reference}: {error}"
                        )
                    )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Demo catalogue import completed"
            )
        )
        self.stdout.write(
            f"Created: {created_count}"
        )
        self.stdout.write(
            f"Skipped: {skipped_count}"
        )
        self.stdout.write(
            f"Failed: {failed_count}"
        )

    def _parse_categories(self, raw_categories):
        categories = []
        seen = set()

        for category in raw_categories.split(","):
            category = category.strip()

            if not category:
                continue

            if category not in SOURCE_CATEGORY_MAP:
                supported = ", ".join(
                    sorted(SOURCE_CATEGORY_MAP)
                )

                raise CommandError(
                    f"Unsupported category: {category}. "
                    f"Supported categories: {supported}"
                )

            if category in seen:
                continue

            seen.add(category)
            categories.append(category)

        if not categories:
            raise CommandError(
                "At least one category is required"
            )

        return categories

    def _fetch_products(
        self,
        source_category,
        limit,
    ):
        query_parameters = urlencode(
            {
                "limit": limit,
                "select": (
                    "id,title,description,category,"
                    "price,stock,tags,brand,sku,"
                    "thumbnail,images"
                ),
            }
        )

        request = Request(
            url=(
                "https://dummyjson.com/products/"
                f"category/{source_category}?"
                f"{query_parameters}"
            ),
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "fashion-store-catalog/1.0"
                ),
            },
            method="GET",
        )

        maximum_attempts = 3

        for attempt in range(
            1,
            maximum_attempts + 1,
        ):
            try:
                with urlopen(
                    request,
                    timeout=30,
                ) as response:
                    response_data = json.loads(
                        response.read().decode(
                            "utf-8"
                        )
                    )

                products = response_data.get(
                    "products",
                    [],
                )

                if not isinstance(products, list):
                    raise DemoCatalogError(
                        "Source products value "
                        "was not a list"
                    )

                return products

            except HTTPError as error:
                error_body = error.read().decode(
                    "utf-8",
                    errors="replace",
                )

                if (
                    error.code >= 500
                    and attempt < maximum_attempts
                ):
                    time.sleep(
                        2 ** (attempt - 1)
                    )
                    continue

                raise DemoCatalogError(
                    f"Source returned HTTP "
                    f"{error.code}: {error_body}"
                ) from error

            except (URLError, TimeoutError) as error:
                if attempt < maximum_attempts:
                    time.sleep(
                        2 ** (attempt - 1)
                    )
                    continue

                raise DemoCatalogError(
                    f"Could not connect to source: "
                    f"{error}"
                ) from error

            except json.JSONDecodeError as error:
                raise DemoCatalogError(
                    "Source returned invalid JSON"
                ) from error

    def _get_or_create_category(
        self,
        name,
        parent=None,
    ):
        normalized_name = " ".join(
            str(name).split()
        ).title()

        category = Category.objects.filter(
            name__iexact=normalized_name
        ).first()

        if category:
            if (
                parent
                and category.parent_id
                and category.parent_id != parent.id
            ):
                raise ValueError(
                    f"Category {normalized_name} "
                    f"belongs to another parent"
                )

            if (
                parent
                and category.parent_id is None
            ):
                category.parent = parent
                category.save(
                    update_fields=["parent"]
                )

            return category

        base_slug = slugify(normalized_name)

        if parent:
            base_slug = (
                f"{parent.slug}-{base_slug}"
            )

        category_slug = base_slug
        suffix = 2

        while Category.objects.filter(
            slug=category_slug
        ).exists():
            category_slug = (
                f"{base_slug}-{suffix}"
            )
            suffix += 1

        return Category.objects.create(
            name=normalized_name,
            slug=category_slug,
            parent=parent,
            )
