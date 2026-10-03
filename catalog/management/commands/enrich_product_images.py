import time

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import DatabaseError, transaction
from django.db.models import Q

from catalog.models import Product
from catalog.services.product_images import (
    ProductImageError,
    search_product_image,
)


class Command(BaseCommand):
    help = (
        "Find Unsplash images for catalogue products "
        "that do not have an image"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Process only this number of products",
        )

        parser.add_argument(
            "--delay",
            type=float,
            default=1.0,
            help="Seconds to wait between API requests",
        )

        parser.add_argument(
            "--sku",
            default=None,
            help="Process only one product SKU",
        )

        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace images already assigned to products",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        delay = options["delay"]
        sku = options["sku"]
        overwrite = options["overwrite"]

        if limit is not None and limit < 1:
            raise CommandError(
                "--limit must be at least 1"
            )

        if delay < 0:
            raise CommandError(
                "--delay cannot be negative"
            )

        products = (
            Product.objects
            .select_related("category")
            .order_by("id")
        )

        if sku:
            products = products.filter(sku=sku)

        if not overwrite:
            products = products.filter(
                Q(image_url="")
                | Q(image_url__isnull=True)
            )

        if limit:
            products = products[:limit]

        product_count = products.count()

        if product_count == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No products require image enrichment"
                )
            )
            return

        self.stdout.write(
            f"Products to process: {product_count}"
        )

        updated_count = 0
        no_result_count = 0
        failed_count = 0

        for product_number, product in enumerate(
            products,
            start=1,
        ):
            api_request_made = False

            try:
                api_request_made = True

                image_data = search_product_image(
                    product_name=product.name,
                    category_name=product.category.name,
                    tags=product.tags,
                    result_index=product_number - 1,
                )

                if image_data is None:
                    no_result_count += 1

                    self.stdout.write(
                        self.style.WARNING(
                            f"NO IMAGE {product.sku}: "
                            f"{product.name}"
                        )
                    )
                    continue

                metadata = product.ai_metadata

                if not isinstance(metadata, dict):
                    metadata = {}

                metadata = dict(metadata)

                metadata["image"] = {
                    "source": image_data["source"],
                    "unsplash_id": (
                        image_data["unsplash_id"]
                    ),
                    "photo_url": (
                        image_data["photo_url"]
                    ),
                    "photographer": (
                        image_data["photographer"]
                    ),
                    "photographer_url": (
                        image_data["photographer_url"]
                    ),
                    "download_location": (
                        image_data["download_location"]
                    ),
                    "search_query": (
                        image_data["search_query"]
                    ),
                }

                with transaction.atomic():
                    product.image_url = image_data[
                        "image_url"
                    ]

                    product.alt_text = image_data[
                        "alt_text"
                    ]

                    product.ai_metadata = metadata

                    product.save(
                        update_fields=[
                            "image_url",
                            "alt_text",
                            "ai_metadata",
                            "updated_at",
                        ]
                    )

                updated_count += 1

                remaining_requests = image_data.get(
                    "rate_limit_remaining",
                    "",
                )

                remaining_message = ""

                if remaining_requests:
                    remaining_message = (
                        f" | requests remaining: "
                        f"{remaining_requests}"
                    )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"UPDATED {product.sku}: "
                        f"{product.name}"
                        f"{remaining_message}"
                    )
                )

            except (
                ProductImageError,
                DatabaseError,
                KeyError,
                TypeError,
                ValueError,
            ) as error:
                failed_count += 1

                self.stderr.write(
                    self.style.ERROR(
                        f"FAILED {product.sku}: {error}"
                    )
                )

            finally:
                if api_request_made and delay > 0:
                    time.sleep(delay)

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Image enrichment completed"
            )
        )
        self.stdout.write(
            f"Updated: {updated_count}"
        )
        self.stdout.write(
            f"No image found: {no_result_count}"
        )
        self.stdout.write(
            f"Failed: {failed_count}"
        )
