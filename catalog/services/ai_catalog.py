import json
import os
import random
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AICatalogError(Exception):
    pass


def suggest_product(product_notes):
    base_url = os.environ["AI_BASE_URL"].rstrip("/")
    api_key = os.environ["AI_API_KEY"]
    model = os.environ["AI_MODEL"]

    prompt = f"""
You are a catalogue assistant for an Indian fashion e-commerce store.

Analyse these product notes:

{product_notes}

Return only valid JSON using exactly these fields:

{{
  "category": "",
  "subcategory": "",
  "name": "",
  "description": "",
  "audience": "MEN, WOMEN, or UNISEX",
  "tags": [],
  "slug": "",
  "alt_text": ""
}}

Do not generate price, stock quantity, or SKU.
"""

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }

    request = Request(
        url=f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    retryable_statuses = {
        408,
        429,
        500,
        502,
        503,
        504,
    }

    maximum_attempts = 5

    for attempt in range(1, maximum_attempts + 1):
        try:
            with urlopen(request, timeout=60) as response:
                result = json.loads(
                    response.read().decode("utf-8")
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
                delay = (2 ** (attempt - 1)) + random.uniform(0, 1)
                time.sleep(delay)
                continue

            raise AICatalogError(
                f"AI endpoint returned HTTP {error.code}: "
                f"{error_body}"
            ) from error

        except (URLError, TimeoutError) as error:
            if attempt < maximum_attempts:
                delay = (2 ** (attempt - 1)) + random.uniform(0, 1)
                time.sleep(delay)
                continue

            raise AICatalogError(
                f"Could not connect to AI endpoint: {error}"
            ) from error

    content = result["choices"][0]["message"]["content"].strip()

    if content.startswith("```"):
        content = (
            content
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

    try:
        suggestion = json.loads(content)
    except json.JSONDecodeError as error:
        raise AICatalogError(
            f"AI response was not valid JSON: {content}"
        ) from error

    required_fields = {
        "category",
        "subcategory",
        "name",
        "description",
        "audience",
        "tags",
        "slug",
        "alt_text",
    }

    missing_fields = required_fields - suggestion.keys()

    if missing_fields:
        raise AICatalogError(
            f"AI response is missing fields: "
            f"{sorted(missing_fields)}"
        )

    return suggestion
