from __future__ import annotations

import importlib.util
import io
import os
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "skills" / "draw-image" / "scripts" / "probe_provider.py"


def _load_probe_module():
    spec = importlib.util.spec_from_file_location("probe_provider", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 probe_provider.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe_provider = _load_probe_module()


class DrawImageProbeProviderTests(unittest.TestCase):
    def test_normalize_roots_adds_v1_when_needed(self) -> None:
        self.assertEqual(
            probe_provider.normalize_roots("https://example.com"),
            ["https://example.com", "https://example.com/v1"],
        )
        self.assertEqual(
            probe_provider.normalize_roots("https://example.com/api/"),
            ["https://example.com/api", "https://example.com/api/v1"],
        )

    def test_normalize_roots_keeps_existing_v1(self) -> None:
        self.assertEqual(
            probe_provider.normalize_roots("https://example.com/v1/"),
            ["https://example.com/v1"],
        )

    def test_classify_status_keeps_auth_and_route_signals_separate(self) -> None:
        self.assertEqual(probe_provider.classify_status(401, "bad key"), "auth_or_permission_error")
        self.assertEqual(probe_provider.classify_status(403, "forbidden"), "auth_or_permission_error")
        self.assertEqual(probe_provider.classify_status(422, "missing prompt"), "route_likely_supported")
        self.assertEqual(probe_provider.classify_status(400, "unknown url"), "not_found")
        self.assertEqual(probe_provider.classify_status(404, "not found"), "not_found")

    def test_recommend_prefers_image_endpoints(self) -> None:
        endpoints = {
            "images_generations": {"classification": "route_likely_supported"},
            "images_edits": {"classification": "route_likely_supported"},
            "chat_completions": {"classification": "accepted"},
        }

        self.assertEqual(
            probe_provider.recommend(endpoints),
            {"generate": "images.generate", "edit": "images.edit"},
        )

    def test_main_fails_before_network_when_api_key_is_missing(self) -> None:
        stderr = io.StringIO()
        with patch.dict(os.environ, {}, clear=True):
            with redirect_stderr(stderr):
                result = probe_provider.main(
                    [
                        "--base-url",
                        "https://example.com/v1",
                        "--api-key-env",
                        "GPT_IMAGE_TEST_KEY",
                    ]
                )

        self.assertEqual(result, 2)
        self.assertIn("Missing API key env var", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
