from django.urls import path

from catalog import views


app_name = "catalog"


urlpatterns = [
    path(
        "",
        views.storefront,
        name="storefront",
    ),
    path(
        "products/<slug:slug>/",
        views.product_detail,
        name="product_detail",
    ),
]
