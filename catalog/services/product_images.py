import json
import os
import random
import time
from urllib.error import HTTPError, URLError
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)
from urllib.request import Request, urlopen


class ProductImageError(Exception):
    pass


def search_product_image(
    product_name,
    category_name="",
    tags=None,
    result_index=0,
):
    access_key = os.environ.get(
        "UNSPLASH_ACCESS_KEY",
        "",
    ).strip()

    if not access_key:
        raise ProductImageError(
            "UNSPLASH_ACCESS_KEY is not configured"
        )

    product_name = str(product_name).strip()
    category_name = str(category_name).strip()

    if not product_name:
        raise ProductImageError(
            "Product name is required for image search"
        )

    if not isinstance(tags, list):
        tags = []

    clean_tags = [
        str(tag).strip()
        for tag in tags[:3]
        if str(tag).strip()
    ]

    query_parts = [
        product_name,
        category_name,
        *clean_tags,
        "fashion product photography",
    ]

    search_query = " ".join(
        part
        for part in query_parts
        if part
    )

    query_parameters = urlencode(
        {
            "query": search_query,
            "orientation": "portrait",
            "per_page": 12,
            "content_filter": "high",
        }
    )

    request = Request(
        url=(
            "https://api.unsplash.com/search/photos?"
            f"{query_parameters}"
        ),
        headers={
            "Authorization": (
                f"Client-ID {access_key}"
            ),
            "Accept-Version": "v1",
            "User-Agent": "fashion-store-catalog/1.0",
        },
        method="GET",
    )

    maximum_attempts = 3
    retryable_statuses = {
        408,
        429,
        500,
        502,
        503,
        504,
    }

    for attempt in range(1, maximum_attempts + 1):
        try:
            with urlopen(
                request,
                timeout=30,
            ) as response:
                response_data = json.loads(
                    response.read().decode("utf-8")
                )

                rate_limit_remaining = (
                    response.headers.get(
                        "X-Ratelimit-Remaining",
                        "",
                    )
                )

            break

        except HTTPError as error:
            error_body = error.read().decode(
                "utf-8",
                errors="replace",
            )

            should_retry = (
                error.code in retryable_statuses
                and attempt < maximum_attempts
            )

            if should_retry:
                delay = (
                    2 ** (attempt - 1)
                ) + random.uniform(0, 1)

                time.sleep(delay)
                continue

            raise ProductImageError(
                f"Unsplash returned HTTP "
                f"{error.code}: {error_body}"
            ) from error

        except (URLError, TimeoutError) as error:
            if attempt < maximum_attempts:
                delay = (
                    2 ** (attempt - 1)
                ) + random.uniform(0, 1)

                time.sleep(delay)
                continue

            raise ProductImageError(
                f"Could not connect to Unsplash: {error}"
            ) from error

        except json.JSONDecodeError as error:
            raise ProductImageError(
                "Unsplash returned invalid JSON"
            ) from error

    photos = response_data.get("results", [])

    if not photos:
        return None

    selected_index = result_index % len(photos)
    photo = photos[selected_index]

    image_urls = photo.get("urls", {})
    photo_links = photo.get("links", {})
    photographer = photo.get("user", {})
    photographer_links = photographer.get(
        "links",
        {},
    )

    image_url = (
        image_urls.get("regular")
        or image_urls.get("small")
    )

    if not image_url:
        raise ProductImageError(
            "Unsplash result did not contain an image URL"
        )

    photo_page_url = _add_attribution_parameters(
        photo_links.get("html", "")
    )

    photographer_url = _add_attribution_parameters(
        photographer_links.get("html", "")
    )

    alt_text = (
        photo.get("alt_description")
        or photo.get("description")
        or product_name
    )

    return {
        "image_url": image_url,
        "alt_text": str(alt_text).strip(),
        "source": "Unsplash",
        "unsplash_id": photo.get("id"),
        "photo_url": photo_page_url,
        "photographer": photographer.get(
            "name",
            "",
        ),
        "photographer_url": photographer_url,
        "download_location": photo_links.get(
            "download_location",
            "",
        ),
        "search_query": search_query,
        "rate_limit_remaining": (
            rate_limit_remaining
        ),
    }


def _add_attribution_parameters(url):
    if not url:
        return ""

    url_parts = urlsplit(url)

    query_parameters = dict(
        parse_qsl(
            url_parts.query,
            keep_blank_values=True,
        )
    )

    query_parameters.update(
        {
            "utm_source": "fashion_store",
            "utm_medium": "referral",
        }
    )

    return urlunsplit(
        (
            url_parts.scheme,
            url_parts.netloc,
            url_parts.path,
            urlencode(query_parameters),
            url_parts.fragment,
        )
    )
