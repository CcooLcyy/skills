#!/usr/bin/env python3
"""Probe GPT Image provider endpoints without generating an image."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_MODEL = "gpt-image-2"
DEFAULT_BASE_URL_ENV = "GPT_IMAGE_BASE_URL"
DEFAULT_API_KEY_ENV = "GPT_IMAGE_API_KEY"

ENDPOINTS = [
    {
        "name": "images_generations",
        "path": "/images/generations",
        "payload": lambda model: {"model": model},
        "usable_for": ["generate"],
    },
    {
        "name": "images_edits",
        "path": "/images/edits",
        "payload": lambda model: {"model": model},
        "usable_for": ["edit"],
    },
    {
        "name": "chat_completions",
        "path": "/chat/completions",
        "payload": lambda model: {"model": model},
        "usable_for": ["generate", "edit_probe_only"],
    },
]


def normalize_roots(base_url: str) -> list[str]:
    text = base_url.strip().rstrip("/")
    if not text:
        raise ValueError("base_url is empty")

    parsed = urllib.parse.urlparse(text)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("base_url must include scheme and host, such as https://example.com/v1")

    roots = [text]
    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts or path_parts[-1] != "v1":
        roots.append(f"{text}/v1")
    return roots


def redact_error_body(body: str) -> str:
    compact = " ".join(body.strip().split())
    if len(compact) > 600:
        compact = compact[:600] + "..."
    return compact


def classify_status(status: int, body: str) -> str:
    lowered = body.lower()
    if status in {200, 201}:
        return "accepted"
    if status in {400, 415, 422}:
        if "not found" in lowered or "no route" in lowered or "unknown url" in lowered:
            return "not_found"
        return "route_likely_supported"
    if status in {401, 403}:
        return "auth_or_permission_error"
    if status == 404:
        return "not_found"
    if status == 405:
        return "method_not_allowed_or_unsupported"
    if status == 429:
        return "rate_limited"
    if 500 <= status <= 599:
        return "server_error_or_route_problem"
    return "unknown"


def post_json(url: str, api_key: str, payload: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            status = response.getcode()
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        return {
            "status": None,
            "classification": "network_error",
            "detail": str(exc.reason),
        }

    return {
        "status": status,
        "classification": classify_status(status, body),
        "detail": redact_error_body(body),
    }


def choose_root(probe_results: list[dict]) -> str | None:
    priority = {
        "accepted": 0,
        "route_likely_supported": 1,
        "auth_or_permission_error": 2,
        "rate_limited": 3,
    }
    best = None
    best_score = 999
    for root_result in probe_results:
        for endpoint in root_result["endpoints"].values():
            score = priority.get(endpoint["classification"], 999)
            if score < best_score:
                best_score = score
                best = root_result["root"]
    return best


def recommend(endpoints: dict) -> dict:
    def is_supported(name: str) -> bool:
        return endpoints.get(name, {}).get("classification") in {
            "accepted",
            "route_likely_supported",
            "rate_limited",
        }

    generation = None
    if is_supported("images_generations"):
        generation = "images.generate"
    elif is_supported("chat_completions"):
        generation = "chat.completions"

    edit = None
    if is_supported("images_edits"):
        edit = "images.edit"
    elif is_supported("chat_completions"):
        edit = "chat.completions_probe_required"

    return {
        "generate": generation,
        "edit": edit,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe GPT Image compatible provider endpoints without generating images."
    )
    parser.add_argument("--base-url", default=os.environ.get(DEFAULT_BASE_URL_ENV, ""))
    parser.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args(argv)

    api_key = os.environ.get(args.api_key_env, "")
    if not args.base_url:
        print(
            json.dumps(
                {"error": f"Missing --base-url or {DEFAULT_BASE_URL_ENV}"},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    if not api_key:
        print(
            json.dumps(
                {"error": f"Missing API key env var: {args.api_key_env}"},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    try:
        roots = normalize_roots(args.base_url)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    probe_results = []
    for root in roots:
        endpoint_results = {}
        for endpoint in ENDPOINTS:
            url = f"{root}{endpoint['path']}"
            endpoint_results[endpoint["name"]] = {
                "url": url,
                "usable_for": endpoint["usable_for"],
                **post_json(url, api_key, endpoint["payload"](args.model), args.timeout),
            }
        probe_results.append({"root": root, "endpoints": endpoint_results})

    selected_root = choose_root(probe_results)
    selected_endpoints = {}
    if selected_root:
        for item in probe_results:
            if item["root"] == selected_root:
                selected_endpoints = item["endpoints"]
                break

    output = {
        "model": args.model,
        "selected_base_url": selected_root,
        "recommendation": recommend(selected_endpoints) if selected_endpoints else {},
        "probes": probe_results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
