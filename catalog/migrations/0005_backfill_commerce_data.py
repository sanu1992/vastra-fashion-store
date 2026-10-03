from django.db import migrations


def backfill_commerce_data(apps, schema_editor):
    Product = apps.get_model(
        "catalog",
        "Product",
    )
    ProductVariant = apps.get_model(
        "catalog",
        "ProductVariant",
    )
    ProductMedia = apps.get_model(
        "catalog",
        "ProductMedia",
    )
    Warehouse = apps.get_model(
        "catalog",
        "Warehouse",
    )
    Inventory = apps.get_model(
        "catalog",
        "Inventory",
    )

    warehouse, unused = Warehouse.objects.get_or_create(
        code="MAIN",
        defaults={
            "name": "Primary Warehouse",
            "is_active": True,
        },
    )

    for product in Product.objects.all().iterator():
        variant, unused = ProductVariant.objects.get_or_create(
            sku=product.sku,
            defaults={
                "product_id": product.id,
                "size": "",
                "color": "",
                "price": product.price,
                "attributes": {
                    "backfilled_from_product": True,
                },
                "is_active": True,
            },
        )

        Inventory.objects.get_or_create(
            variant_id=variant.id,
            warehouse_id=warehouse.id,
            defaults={
                "quantity_on_hand": product.stock,
                "quantity_reserved": 0,
                "reorder_level": 0,
            },
        )

        if product.image_url:
            ProductMedia.objects.get_or_create(
                product_id=product.id,
                variant_id=variant.id,
                url=product.image_url,
                defaults={
                    "media_type": "IMAGE",
                    "source": "SUPPLIER",
                    "alt_text": product.alt_text,
                    "position": 0,
                    "is_primary": True,
                    "metadata": {
                        "backfilled_from_product": True,
                    },
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        (
            "catalog",
            "0004_commerce_foundation",
        ),
    ]

    operations = [
        migrations.RunPython(
            backfill_commerce_data,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
