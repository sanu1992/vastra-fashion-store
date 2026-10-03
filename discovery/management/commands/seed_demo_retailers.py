from decimal import Decimal

from django.core.management.base import BaseCommand

from catalog.models import Category
from discovery.models import Retailer, RetailerOffer


CATEGORY_DATA = [
    {
        "name": "Men Clothing",
        "slug": "men-clothing",
        "description": "Clothing and fashion products for men.",
    },
    {
        "name": "Women Clothing",
        "slug": "women-clothing",
        "description": "Clothing and fashion products for women.",
    },
    {
        "name": "Jewellery",
        "slug": "jewellery",
        "description": "Fashion jewellery and accessories.",
    },
    {
        "name": "Footwear",
        "slug": "footwear",
        "description": "Footwear for different styles and occasions.",
    },
]


RETAILER_DATA = [
    {
        "name": "Vastra Demo Fashion Partner",
        "slug": "vastra-demo-fashion-partner",
        "channel": "BOTH",
        "integration_level": "DEMO",
        "notes": (
            "Fictional development retailer. Prices and availability "
            "must not be presented as live retailer data."
        ),
    },
    {
        "name": "Vastra Demo Footwear Partner",
        "slug": "vastra-demo-footwear-partner",
        "channel": "BOTH",
        "integration_level": "DEMO",
        "notes": (
            "Fictional development retailer used to test external "
            "footwear discovery."
        ),
    },
    {
        "name": "Vastra Demo Jewellery Partner",
        "slug": "vastra-demo-jewellery-partner",
        "channel": "ONLINE",
        "integration_level": "DEMO",
        "notes": (
            "Fictional development retailer used to test jewellery "
            "recommendations."
        ),
    },
]


OFFER_DATA = [
    {
        "retailer_slug": "vastra-demo-fashion-partner",
        "category_slug": "men-clothing",
        "external_sku": "DEMO-MEN-001",
        "title": "Blue Cotton Casual Office Shirt",
        "description": (
            "Demo blue cotton shirt suitable for casual office wear."
        ),
        "price": Decimal("1299.00"),
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["Blue"],
        "availability": "IN_STOCK",
        "fulfilment": "BOTH",
    },
    {
        "retailer_slug": "vastra-demo-fashion-partner",
        "category_slug": "men-clothing",
        "external_sku": "DEMO-MEN-002",
        "title": "Ivory Festive Nehru Jacket",
        "description": (
            "Demo Nehru jacket for weddings and festive occasions."
        ),
        "price": Decimal("2499.00"),
        "sizes": ["M", "L", "XL"],
        "colors": ["Ivory"],
        "availability": "CHECK_RETAILER",
        "fulfilment": "BOTH",
    },
    {
        "retailer_slug": "vastra-demo-fashion-partner",
        "category_slug": "women-clothing",
        "external_sku": "DEMO-WOMEN-001",
        "title": "Emerald Green Festive Kurta Set",
        "description": (
            "Demo embroidered kurta set suitable for festive wear."
        ),
        "price": Decimal("2199.00"),
        "sizes": ["S", "M", "L", "XL"],
        "colors": ["Emerald Green"],
        "availability": "IN_STOCK",
        "fulfilment": "ONLINE",
    },
    {
        "retailer_slug": "vastra-demo-fashion-partner",
        "category_slug": "women-clothing",
        "external_sku": "DEMO-WOMEN-002",
        "title": "Black Casual Maxi Dress",
        "description": (
            "Demo everyday maxi dress for casual outings."
        ),
        "price": Decimal("1799.00"),
        "sizes": ["S", "M", "L"],
        "colors": ["Black"],
        "availability": "CHECK_RETAILER",
        "fulfilment": "ONLINE",
    },
    {
        "retailer_slug": "vastra-demo-footwear-partner",
        "category_slug": "footwear",
        "external_sku": "DEMO-FOOT-001",
        "title": "Tan Leather Casual Sneakers",
        "description": (
            "Demo casual sneakers suitable for everyday use."
        ),
        "price": Decimal("1899.00"),
        "sizes": ["7", "8", "9", "10"],
        "colors": ["Tan"],
        "availability": "IN_STOCK",
        "fulfilment": "BOTH",
    },
    {
        "retailer_slug": "vastra-demo-footwear-partner",
        "category_slug": "footwear",
        "external_sku": "DEMO-FOOT-002",
        "title": "Gold Embellished Festive Juttis",
        "description": (
            "Demo embellished juttis for weddings and festivals."
        ),
        "price": Decimal("999.00"),
        "sizes": ["4", "5", "6", "7", "8"],
        "colors": ["Gold"],
        "availability": "CHECK_RETAILER",
        "fulfilment": "BOTH",
    },
    {
        "retailer_slug": "vastra-demo-jewellery-partner",
        "category_slug": "jewellery",
        "external_sku": "DEMO-JEWEL-001",
        "title": "Gold-Coloured Floral Necklace",
        "description": (
            "Demo floral necklace designed for festive outfits."
        ),
        "price": Decimal("1499.00"),
        "sizes": ["One Size"],
        "colors": ["Gold"],
        "availability": "IN_STOCK",
        "fulfilment": "ONLINE",
    },
    {
        "retailer_slug": "vastra-demo-jewellery-partner",
        "category_slug": "jewellery",
        "external_sku": "DEMO-JEWEL-002",
        "title": "Silver Oxidised Jhumka Earrings",
        "description": (
            "Demo oxidised earrings for traditional and casual outfits."
        ),
        "price": Decimal("699.00"),
        "sizes": ["One Size"],
        "colors": ["Silver"],
        "availability": "CHECK_RETAILER",
        "fulfilment": "ONLINE",
    },
]


class Command(BaseCommand):
    help = "Create fictional retailers and offers for discovery testing"

    def handle(self, *args, **options):
        categories = {}
        retailers = {}

        for category_data in CATEGORY_DATA:
            category = self.find_or_create_category(category_data)
            categories[category_data["slug"]] = category

        for retailer_data in RETAILER_DATA:
            retailer, created = Retailer.objects.update_or_create(
                slug=retailer_data["slug"],
                defaults={
                    "name": retailer_data["name"],
                    "website_url": "",
                    "search_url_template": "",
                    "channel": retailer_data["channel"],
                    "integration_level": retailer_data[
                        "integration_level"
                    ],
                    "is_demo": True,
                    "is_active": True,
                    "notes": retailer_data["notes"],
                },
            )

            retailer.supported_categories.set(categories.values())
            retailers[retailer.slug] = retailer

            action = "CREATED" if created else "UPDATED"
            self.stdout.write(
                f"{action} RETAILER: {retailer.name}"
            )

        created_count = 0
        updated_count = 0

        for offer_data in OFFER_DATA:
            retailer = retailers[offer_data["retailer_slug"]]
            category = categories[offer_data["category_slug"]]

            offer, created = RetailerOffer.objects.update_or_create(
                retailer=retailer,
                external_sku=offer_data["external_sku"],
                defaults={
                    "category": category,
                    "title": offer_data["title"],
                    "description": offer_data["description"],
                    "product_url": "",
                    "image_url": "",
                    "price": offer_data["price"],
                    "available_sizes": offer_data["sizes"],
                    "colors": offer_data["colors"],
                    "availability": offer_data["availability"],
                    "fulfilment": offer_data["fulfilment"],
                    "is_demo": True,
                    "is_active": True,
                    "metadata": {
                        "source": "seed_demo_retailers",
                        "live_data": False,
                        "disclaimer": (
                            "Demonstration offer. Price and availability "
                            "are not live retailer data."
                        ),
                    },
                },
            )

            if created:
                created_count += 1
                action = "CREATED"
            else:
                updated_count += 1
                action = "UPDATED"

            self.stdout.write(
                f"{action} OFFER: {offer.external_sku} - {offer.title}"
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Demo retailer discovery data is ready"
            )
        )
        self.stdout.write(f"Offers created: {created_count}")
        self.stdout.write(f"Offers updated: {updated_count}")

    def find_or_create_category(self, category_data):
        category = Category.objects.filter(
            slug=category_data["slug"]
        ).first()

        if category is None:
            category = Category.objects.filter(
                name=category_data["name"]
            ).first()

        if category is None:
            category = Category.objects.create(
                name=category_data["name"],
                slug=category_data["slug"],
                description=category_data["description"],
                is_active=True,
            )

            self.stdout.write(
                f"CREATED CATEGORY: {category.name}"
            )

            return category

        changed_fields = []

        if not category.description:
            category.description = category_data["description"]
            changed_fields.append("description")

        if not category.is_active:
            category.is_active = True
            changed_fields.append("is_active")

        if changed_fields:
            category.save(update_fields=changed_fields)

        self.stdout.write(
            f"USING CATEGORY: {category.name}"
        )

        return category
