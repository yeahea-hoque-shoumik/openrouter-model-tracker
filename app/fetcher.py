import time

import requests

URL = "https://openrouter.ai/api/v1/models"
TIMEOUT_SECONDS = 30
ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5


class FetchError(Exception):
    pass


def parse_model_ids(payload) -> set[str]:
    """Extract all model ids from an API payload; raise FetchError if malformed or empty."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise FetchError("unexpected response shape: missing 'data' list")
    ids = {m["id"] for m in payload["data"] if isinstance(m, dict) and isinstance(m.get("id"), str)}
    if not ids:
        raise FetchError("response contained no model ids")
    return ids


def free_ids(all_ids: set[str]) -> set[str]:
    return {i for i in all_ids if i.endswith(":free")}


def fetch_model_ids() -> set[str]:
    last_error: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            resp = requests.get(URL, timeout=TIMEOUT_SECONDS)
            resp.raise_for_status()
            return parse_model_ids(resp.json())
        except (requests.RequestException, ValueError, FetchError) as e:
            last_error = e
            if attempt < ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)
    raise FetchError(f"fetch failed after {ATTEMPTS} attempts: {last_error}")
