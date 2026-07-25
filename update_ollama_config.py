#!/usr/bin/env python3

import json
import pathlib
import sys
import urllib.error
import urllib.request


OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_TAGS_URL = f"{OLLAMA_BASE_URL}/api/tags"
CONFIG_PATH = pathlib.Path.home() / ".factory" / "config.json"


def fetch_model_names(url: str) -> list[str]:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        payload = json.load(response)
    models = payload.get("models", [])
    return [item.get("name") for item in models if item.get("name")]


def load_config(path: pathlib.Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError:
        return {}


def write_config(path: pathlib.Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def merge_custom_models(data: dict, model_names: list[str]) -> None:
    existing = data.get("custom_models")
    if not isinstance(existing, list):
        existing = []

    merged: list[dict] = []
    seen: set[str] = set()

    for item in existing:
        if not isinstance(item, dict):
            continue
        model_name = item.get("model")
        if not model_name or model_name in seen:
            continue
        if model_name in model_names:
            item = {
                "model": model_name,
                "base_url": OLLAMA_BASE_URL,
                "provider": "ollama",
            }
        merged.append(item)
        seen.add(model_name)

    for name in model_names:
        if name in seen:
            continue
        merged.append(
            {
                "model": name,
                "base_url": OLLAMA_BASE_URL,
                "provider": "ollama",
            }
        )
        seen.add(name)

    data["custom_models"] = merged


def main() -> int:
    try:
        model_names = fetch_model_names(OLLAMA_TAGS_URL)
    except urllib.error.URLError as error:
        print(f"Failed to reach Ollama at {OLLAMA_TAGS_URL}: {error}", file=sys.stderr)
        return 1
    update = load_config(CONFIG_PATH)
    merge_custom_models(update, model_names)
    update.pop("ollama_models", None)
    write_config(CONFIG_PATH, update)
    print(f"Stored {len(model_names)} models in {CONFIG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
