import os
import time
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, transaction
from django.utils.text import slugify

from catalog.models import Category, Product
from catalog.services.ai_catalog import (
    AICatalogError,
    suggest_product,
)


class Command(BaseCommand):
    help = "Generate draft catalogue products using AI"

    def add_arguments(self, parser):
        parser.add_argument(
            "--categories",
            required=True,
            help="Comma-separated catalogue categories",
        )

        parser.add_argument(
            "--products-per-category",
            type=int,
            default=5,
            help="Number of products to generate per category",
        )

        parser.add_argument(
            "--price",
            type=Decimal,
            default=Decimal("999.00"),
            help="Default demonstration price",
        )

        parser.add_argument(
            "--stock",
            type=int,
            default=20,
            help="Default demonstration stock quantity",
        )

        parser.add_argument(
            "--delay",
            type=float,
            default=2.0,
            help="Seconds to wait between AI requests",
        )

    def handle(self, *args, **options):
        categories = self._parse_categories(
            options["categories"]
        )

        products_per_category = options[
            "products_per_category"
        ]
        price = options["price"]
        stock = options["stock"]
        delay = options["delay"]

        if products_per_category < 1:
            raise CommandError(
                "--products-per-category must be at least 1"
            )

        if price < 0:
            raise CommandError("--price cannot be negative")

        if stock < 0:
            raise CommandError("--stock cannot be negative")

        created_count = 0
        skipped_count = 0
        failed_count = 0

        for category_name in categories:
            parent_category = self._get_or_create_category(
                category_name
            )

            generated_names = []

            self.stdout.write("")
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"Generating category: {category_name}"
                )
            )

            for product_number in range(
                1,
                products_per_category + 1,
            ):
                sku = self._build_sku(
                    category_name,
                    product_number,
                )

                if Product.objects.filter(sku=sku).exists():
                    skipped_count += 1

                    self.stdout.write(
                        self.style.WARNING(
                            f"SKIPPED {sku}: already exists"
                        )
                    )
                    continue

                product_notes = self._build_product_notes(
                    category_name=category_name,
                    product_number=product_number,
                    products_per_category=products_per_category,
                    generated_names=generated_names,
                )

                ai_request_made = False

                try:
                    ai_request_made = True
                    suggestion = suggest_product(product_notes)

                    product_name = str(
                        suggestion["name"]
                    ).strip()

                    description = str(
                        suggestion["description"]
                    ).strip()

                    if not product_name:
                        raise ValueError(
                            "AI returned an empty product name"
                        )

                    if not description:
                        raise ValueError(
                            "AI returned an empty description"
                        )

                    subcategory_name = str(
                        suggestion.get("subcategory")
                        or suggestion.get("category")
                        or ""
                    ).strip()

                    product_category = parent_category

                    if (
                        subcategory_name
                        and subcategory_name.lower()
                        != parent_category.name.lower()
                    ):
                        product_category = (
                            self._get_or_create_category(
                                subcategory_name,
                                parent=parent_category,
                            )
                        )

                    audience = str(
                        suggestion.get(
                            "audience",
                            Product.Audience.UNISEX,
                        )
                    ).strip().upper()

                    if audience not in Product.Audience.values:
                        audience = Product.Audience.UNISEX

                    tags = suggestion.get("tags", [])

                    if not isinstance(tags, list):
                        tags = []

                    tags = [
                        str(tag).strip()
                        for tag in tags
                        if str(tag).strip()
                    ]

                    suggested_slug = (
                        suggestion.get("slug")
                        or product_name
                    )

                    product_slug = slugify(
                        f"{suggested_slug}-{sku}"
                    )[:220]

                    metadata = dict(suggestion)
                    metadata["generation_category"] = (
                        category_name
                    )
                    metadata["generation_number"] = (
                        product_number
                    )

                    with transaction.atomic():
                        Product.objects.create(
                            category=product_category,
                            sku=sku,
                            name=product_name,
                            slug=product_slug,
                            description=description,
                            price=price,
                            stock=stock,
                            audience=audience,
                            image_url="",
                            tags=tags,
                            alt_text=str(
                                suggestion.get(
                                    "alt_text",
                                    "",
                                )
                            ).strip(),
                            ai_metadata=metadata,
                            ai_generated=True,
                            ai_model=os.environ.get(
                                "AI_MODEL",
                                "",
                            ),
                            is_active=False,
                        )

                    generated_names.append(product_name)
                    created_count += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"CREATED {sku}: {product_name}"
                        )
                    )

                except (
                    AICatalogError,
                    DatabaseError,
                    KeyError,
                    TypeError,
                    ValueError,
                ) as error:
                    failed_count += 1

                    self.stderr.write(
                        self.style.ERROR(
                            f"FAILED {sku}: {error}"
                        )
                    )

                finally:
                    if ai_request_made and delay > 0:
                        time.sleep(delay)

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS("Generation completed")
        )
        self.stdout.write(f"Created: {created_count}")
        self.stdout.write(f"Skipped: {skipped_count}")
        self.stdout.write(f"Failed: {failed_count}")
        self.stdout.write(
            "Generated products are inactive drafts."
        )

    def _parse_categories(self, raw_categories):
        categories = []
        category_names_seen = set()

        for category_name in raw_categories.split(","):
            category_name = " ".join(
                category_name.split()
            ).title()

            if not category_name:
                continue

            normalized_name = category_name.casefold()

            if normalized_name in category_names_seen:
                continue

            category_names_seen.add(normalized_name)
            categories.append(category_name)

        if not categories:
            raise CommandError(
                "At least one category must be supplied"
            )

        return categories

    def _build_sku(self, category_name, product_number):
        category_code = slugify(
            category_name
        ).upper()[:28]

        return f"AI-{category_code}-{product_number:03d}"

    def _build_product_notes(
        self,
        category_name,
        product_number,
        products_per_category,
        generated_names,
    ):
        previous_names = ", ".join(generated_names)

        if not previous_names:
            previous_names = "none"

        return (
            f"Generate one realistic product for the "
            f"'{category_name}' collection in an Indian "
            f"fashion e-commerce store. "
            f"This is product {product_number} of "
            f"{products_per_category}. "
            f"Make it meaningfully different from the other "
            f"products. Previously generated product names: "
            f"{previous_names}. "
            f"Return a suitable category, subcategory, name, "
            f"description, audience, tags, slug and alt text."
        )

    def _get_or_create_category(
        self,
        name,
        parent=None,
    ):
        normalized_name = " ".join(
            str(name).split()
        ).title()

        if not normalized_name:
            raise ValueError("Category name is empty")

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
                    f"Category {normalized_name} already "
                    f"belongs to another parent"
                )

            if parent and category.parent_id is None:
                category.parent = parent
                category.save(update_fields=["parent"])

            return category

        base_slug = slugify(normalized_name)

        if parent:
            base_slug = f"{parent.slug}-{base_slug}"

        category_slug = base_slug
        suffix = 2

        while Category.objects.filter(
            slug=category_slug
        ).exists():
            category_slug = f"{base_slug}-{suffix}"
            suffix += 1

        return Category.objects.create(
            name=normalized_name,
            slug=category_slug,
            parent=parent,
        )
