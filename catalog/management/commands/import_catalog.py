import csv
import os
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from catalog.models import Category, Product
from catalog.services.ai_catalog import (
    AICatalogError,
    suggest_product,
)


class Command(BaseCommand):
    help = "Import and enrich products from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path",
            help="Path to the product CSV file",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Process only the first number of products",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=2.0,
            help="Seconds to wait between AI requests",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file_path"])
        limit = options["limit"]
        delay = options["delay"]

        if not file_path.is_file():
            raise CommandError(
                f"CSV file does not exist: {file_path}"
            )

        created_count = 0
        skipped_count = 0
        failed_count = 0

        with file_path.open(
            mode="r",
            encoding="utf-8-sig",
            newline="",
        ) as csv_file:
            reader = csv.DictReader(csv_file)

            required_columns = {
                "sku",
                "product_name",
                "price",
                "stock",
            }

            actual_columns = set(reader.fieldnames or [])
            missing_columns = required_columns - actual_columns

            if missing_columns:
                raise CommandError(
                    f"CSV is missing columns: "
                    f"{sorted(missing_columns)}"
                )

            for product_number, row in enumerate(
                reader,
                start=1,
            ):
                if limit and product_number > limit:
                    break

                sku = (row.get("sku") or "").strip()
                product_name = (
                    row.get("product_name") or ""
                ).strip()
                image_url = (
                    row.get("image_url") or ""
                ).strip()
                notes = (
                    row.get("notes")
                    or product_name
                ).strip()

                ai_request_made = False

                try:
                    self._validate_required_values(
                        sku,
                        product_name,
                    )

                    price = self._parse_price(row.get("price"))
                    stock = self._parse_stock(row.get("stock"))

                    if Product.objects.filter(sku=sku).exists():
                        skipped_count += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"SKIPPED {sku}: already exists"
                            )
                        )
                        continue

                    ai_request_made = True
                    suggestion = suggest_product(notes)

                    with transaction.atomic():
                        broad_category = (
                            self._get_or_create_category(
                                suggestion["category"]
                            )
                        )

                        product_category = broad_category

                        subcategory_name = (
                            suggestion.get("subcategory") or ""
                        ).strip()

                        if (
                            subcategory_name
                            and subcategory_name.lower()
                            != broad_category.name.lower()
                        ):
                            product_category = (
                                self._get_or_create_category(
                                    subcategory_name,
                                    parent=broad_category,
                                )
                            )

                        audience = (
                            suggestion.get(
                                "audience",
                                Product.Audience.UNISEX,
                            )
                            .strip()
                            .upper()
                        )

                        if audience not in Product.Audience.values:
                            audience = Product.Audience.UNISEX

                        tags = suggestion.get("tags", [])

                        if not isinstance(tags, list):
                            tags = []

                        suggested_slug = (
                            suggestion.get("slug")
                            or suggestion["name"]
                        )

                        product_slug = slugify(
                            f"{suggested_slug}-{sku}"
                        )[:220]

                        Product.objects.create(
                            category=product_category,
                            sku=sku,
                            name=suggestion["name"],
                            slug=product_slug,
                            description=suggestion["description"],
                            price=price,
                            stock=stock,
                            audience=audience,
                            image_url=image_url,
                            tags=tags,
                            alt_text=suggestion.get(
                                "alt_text",
                                "",
                            ),
                            ai_metadata=suggestion,
                            ai_generated=True,
                            ai_model=os.environ.get(
                                "AI_MODEL",
                                "",
                            ),
                            is_active=False,
                        )

                    created_count += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"CREATED {sku}: "
                            f"{suggestion['name']}"
                        )
                    )

                except (
                    ValueError,
                    InvalidOperation,
                    KeyError,
                    AICatalogError,
                ) as error:
                    failed_count += 1

                    self.stderr.write(
                        self.style.ERROR(
                            f"FAILED {sku or product_number}: "
                            f"{error}"
                        )
                    )

                finally:
                    if ai_request_made and delay > 0:
                        time.sleep(delay)

        self.stdout.write("")
        self.stdout.write("Import completed")
        self.stdout.write(f"Created: {created_count}")
        self.stdout.write(f"Skipped: {skipped_count}")
        self.stdout.write(f"Failed: {failed_count}")

    def _validate_required_values(
        self,
        sku,
        product_name,
    ):
        if not sku:
            raise ValueError("SKU is empty")

        if not product_name:
            raise ValueError("Product name is empty")

    def _parse_price(self, value):
        price = Decimal((value or "").strip())

        if price < 0:
            raise ValueError("Price cannot be negative")

        return price

    def _parse_stock(self, value):
        stock = int((value or "").strip())

        if stock < 0:
            raise ValueError("Stock cannot be negative")

        return stock

    def _get_or_create_category(
        self,
        name,
        parent=None,
    ):
        normalized_name = " ".join(name.split()).title()

        if not normalized_name:
            raise ValueError("AI returned an empty category")

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
