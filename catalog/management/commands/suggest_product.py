import json

from django.core.management.base import BaseCommand, CommandError

from catalog.services.ai_catalog import (
    AICatalogError,
    suggest_product,
)


class Command(BaseCommand):
    help = "Generate an AI catalogue suggestion from product notes"

    def add_arguments(self, parser):
        parser.add_argument(
            "product_notes",
            help="Basic description of the product",
        )

    def handle(self, *args, **options):
        product_notes = options["product_notes"]

        try:
            suggestion = suggest_product(product_notes)
        except AICatalogError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(
            json.dumps(
                suggestion,
                indent=2,
                ensure_ascii=False,
            )
        )
