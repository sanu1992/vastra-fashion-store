from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def live(request):
    return JsonResponse(
        {"status": "alive"}
    )


def ready(request):
    return JsonResponse(
        {"status": "ready"}
    )


urlpatterns = [
    path(
        "admin/",
        admin.site.urls,
    ),
    path(
        "health/live/",
        live,
    ),
    path(
        "health/ready/",
        ready,
    ),
    path(
        "account/",
        include("accounts.urls"),
    ),
    path(
        "",
        include("catalog.urls"),
    ),
]
