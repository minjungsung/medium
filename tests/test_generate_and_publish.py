"""End-to-end checks for src/generate_and_publish.py.

The tests run the real script as a subprocess against a local OpenAI-compatible stub, so the
request/response handling, the write-out of posts/site files, and the exit codes that the
daily workflow depends on are all exercised without touching any real provider.

Run:  python -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "src" / "generate_and_publish.py"

ARTICLE = """# Stub Article Title

*A subtitle for the stub article.*

## Failure modes & debugging

```python
print("hello")
```
"""


class _StubHandler(BaseHTTPRequestHandler):
    mode = "completion"

    def do_POST(self):  # noqa: N802 - http.server API
        length = int(self.headers.get("content-length") or 0)
        self.rfile.read(length)
        if _StubHandler.mode == "completion":
            body = json.dumps(
                {
                    "id": "stub-1",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "stub",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": ARTICLE},
                            "finish_reason": "stop",
                        }
                    ],
                }
            ).encode("utf-8")
            content_type = "application/json"
        else:
            # What the retired models.github.ai host answers: HTTP 200, text/plain, "OK".
            body = b"OK\r\n"
            content_type = "text/plain"
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep test output clean
        return


class GenerateAndPublishTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _run(self, args, env_extra, cwd):
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "PYTHONPATH": str(REPO),
            "PYTHONIOENCODING": "utf-8",
        }
        env.update(env_extra)
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )

    def _base_env(self):
        return {
            "LLM_PROVIDER": "openai",
            "LLM_API_KEY": "test-key",
            "LLM_BASE_URL": f"http://127.0.0.1:{self.port}/v1",
            "LLM_MODEL": "stub-model",
        }

    def test_generates_post_html_and_index(self):
        _StubHandler.mode = "completion"
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(
                ["--action", "generate", "--outdir", "posts", "--site_dir", "site"],
                self._base_env(),
                tmp,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            posts = list((Path(tmp) / "posts").glob("*.md"))
            self.assertEqual(len(posts), 1)
            self.assertIn("# Stub Article Title", posts[0].read_text(encoding="utf-8"))
            html_posts = list((Path(tmp) / "site" / "posts").glob("*.html"))
            self.assertEqual(len(html_posts), 1)
            self.assertIn("<h1>Stub Article Title</h1>", html_posts[0].read_text(encoding="utf-8"))
            self.assertTrue((Path(tmp) / "site" / "index.html").exists())

    def test_placeholder_ok_body_is_reported_as_retired_provider(self):
        _StubHandler.mode = "placeholder"
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(
                ["--action", "generate", "--outdir", "posts", "--site_dir", "site"],
                self._base_env(),
                tmp,
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            output = result.stdout + result.stderr
            self.assertIn("OK", output)
            self.assertIn("retired", output.lower())
            self.assertFalse((Path(tmp) / "posts").exists())

    def test_missing_credential_skips_with_allow_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self._base_env()
            env.pop("LLM_API_KEY")
            result = self._run(
                ["--action", "generate", "--allow-skip", "--outdir", "posts", "--site_dir", "site"],
                env,
                tmp,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Skipping today's post", result.stderr + result.stdout)
            self.assertFalse((Path(tmp) / "posts").exists())

    def test_missing_credential_fails_without_allow_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self._base_env()
            env.pop("LLM_API_KEY")
            result = self._run(
                ["--action", "generate", "--outdir", "posts", "--site_dir", "site"],
                env,
                tmp,
            )
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertIn("LLM_API_KEY", result.stderr)

    def test_github_models_provider_is_rejected_before_calling_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self._base_env()
            env["LLM_PROVIDER"] = "github_models"
            env["LLM_BASE_URL"] = "https://models.github.ai/inference"
            result = self._run(
                ["--action", "generate", "--outdir", "posts", "--site_dir", "site"],
                env,
                tmp,
            )
            self.assertEqual(result.returncode, 4, result.stderr)
            self.assertIn("2026-07-30", result.stderr)

    def test_retired_base_url_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self._base_env()
            env["LLM_BASE_URL"] = "https://models.github.ai/inference"
            result = self._run(["--check-provider"], env, tmp)
            self.assertEqual(result.returncode, 4, result.stdout + result.stderr)

    def test_check_provider_reports_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(["--check-provider"], self._base_env(), tmp)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("ready: True", result.stdout)
            self.assertIn("api_key: set", result.stdout)

    def test_check_provider_reports_missing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self._base_env()
            env.pop("LLM_API_KEY")
            result = self._run(["--check-provider"], env, tmp)
            self.assertEqual(result.returncode, 3, result.stdout)
            self.assertIn("api_key: missing", result.stdout)


if __name__ == "__main__":
    unittest.main()
