import statistics
import time

import requests

URL = "https://openrouter.ai/api/v1/models"
TIMEOUT_SECONDS = 30
ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5


class FetchError(Exception):
    pass


def parse_models(payload) -> dict[str, dict]:
    """Map model id -> model object; raise FetchError if the payload is malformed or empty."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise FetchError("unexpected response shape: missing 'data' list")
    models = {m["id"]: m for m in payload["data"] if isinstance(m, dict) and isinstance(m.get("id"), str)}
    if not models:
        raise FetchError("response contained no model ids")
    return models


def free_ids(all_ids) -> set[str]:
    return {i for i in all_ids if i.endswith(":free")}


def tool_calling_index(model: dict) -> int:
    """0 = no tool support, 1 = accepts `tools`, 2 = also accepts `tool_choice` (can force/forbid tool use)."""
    params = model.get("supported_parameters")
    params = params if isinstance(params, list) else []
    return int("tools" in params) + int("tools" in params and "tool_choice" in params)


def extract_details(model: dict) -> dict:
    """Pick the stored fields out of a /models entry. Missing values become None."""
    top = model.get("top_provider") or {}
    aa = (model.get("benchmarks") or {}).get("artificial_analysis") or {}
    return {
        "name": model.get("name"),
        "context_length": top.get("context_length") or model.get("context_length"),
        "max_completion_tokens": top.get("max_completion_tokens"),
        "intelligence_index": aa.get("intelligence_index"),
        "coding_index": aa.get("coding_index"),
        "agentic_index": aa.get("agentic_index"),
        "tool_calling_index": tool_calling_index(model),
        "latency_p50": None,
        "throughput_p50": None,
    }


def _p50(value):
    if isinstance(value, dict):
        value = value.get("p50")
    return value if isinstance(value, (int, float)) else None


def fetch_endpoint_stats(model_id: str, api_key: str) -> tuple[float | None, float | None]:
    """Median (across providers) p50 latency and throughput as reported by OpenRouter. Never raises."""
    try:
        resp = requests.get(
            f"https://openrouter.ai/api/v1/models/{model_id}/endpoints",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        resp.raise_for_status()
        endpoints = resp.json()["data"]["endpoints"]
        lat = [v for e in endpoints if (v := _p50(e.get("latency_last_30m"))) is not None]
        thr = [v for e in endpoints if (v := _p50(e.get("throughput_last_30m"))) is not None]
        return (statistics.median(lat) if lat else None, statistics.median(thr) if thr else None)
    except Exception:
        return None, None


def fetch_models() -> dict[str, dict]:
    last_error: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            resp = requests.get(URL, timeout=TIMEOUT_SECONDS)
            resp.raise_for_status()
            return parse_models(resp.json())
        except (requests.RequestException, ValueError, FetchError) as e:
            last_error = e
            if attempt < ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)
    raise FetchError(f"fetch failed after {ATTEMPTS} attempts: {last_error}")
