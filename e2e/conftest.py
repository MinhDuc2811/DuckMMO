"""Real browser -> Streamlit -> FastAPI -> DB -> isolated worker.

Only the external AI provider is a controlled local fixture; no UI/API/worker mocks.
Each test uses its own database and ports, never the user's active workspace.
"""

import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import psutil
import pytest

ROOT = Path(__file__).resolve().parents[1]


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def stop_tree(process):
    if process and process.poll() is None:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for child in reversed(children):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        process.terminate()
        process.wait(timeout=10)
        psutil.wait_procs(children, timeout=5)


class Stack:
    def __init__(self, directory):
        self.directory = directory
        self.api_url = f"http://127.0.0.1:{port()}"
        self.ui_port = port()
        self.ui_url = f"http://127.0.0.1:{self.ui_port}"
        self.processes = []
        self.logs = []
        self.worker = None
        self.provider_started = threading.Event()
        self.provider_release = threading.Event()
        self.block_provider = False
        self.provider_requests = []
        stack = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                stack.provider_requests.append(json.loads(body))
                stack.provider_started.set()
                if stack.block_provider:
                    stack.provider_release.wait(timeout=90)
                payload = {
                    "summary": "Fixture summary",
                    "key_points": ["Fixture point"],
                    "video_content": "Kịch bản từ AI fixture để test luồng ứng dụng.",
                }
                body = json.dumps(
                    {"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]}
                ).encode()
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *_):
                pass

        self.provider = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.provider.daemon_threads = True
        self.provider_thread = threading.Thread(target=self.provider.serve_forever, daemon=True)
        self.provider_thread.start()
        self.env = {
            **os.environ,
            "STUDIO_DATABASE_URL": f"sqlite:///{directory / 'studio.db'}",
            "STUDIO_API_URL": self.api_url,
            "STUDIO_API_KEY": "",
            "STUDIO_ARTIFACT_DIR": str(directory / "artifacts"),
            "STUDIO_ANALYSIS_BASE_URL": f"http://127.0.0.1:{self.provider.server_port}/v1",
            "STUDIO_ANALYSIS_MODEL": "e2e-fixture-model",
            "STUDIO_ANALYSIS_API_KEY": "e2e-placeholder",
            "PYTHONUTF8": "1",
        }

    def spawn(self, name, arguments):
        log = (self.directory / f"{name}.log").open("w", encoding="utf-8")
        self.logs.append(log)
        process = subprocess.Popen(
            [sys.executable, *arguments],
            cwd=ROOT,
            env=self.env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.processes.append(process)
        return process

    def wait_http(self, url, process):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Server exited; logs: {self.directory}")
            try:
                if httpx.get(url, timeout=1).status_code == 200:
                    return
            except httpx.RequestError:
                pass
            time.sleep(0.1)
        raise RuntimeError(f"Server startup timed out: {url}; logs: {self.directory}")

    def start(self):
        migrated = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT,
            env=self.env,
            capture_output=True,
            text=True,
        )
        assert migrated.returncode == 0, migrated.stderr
        api = self.spawn(
            "api",
            [
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                self.api_url.rsplit(":", 1)[1],
            ],
        )
        self.wait_http(self.api_url + "/health", api)
        ui = self.spawn(
            "ui",
            [
                "-m",
                "streamlit",
                "run",
                "ui/studio.py",
                "--server.address",
                "127.0.0.1",
                "--server.port",
                str(self.ui_port),
                "--server.headless",
                "true",
                "--browser.gatherUsageStats",
                "false",
            ],
        )
        self.wait_http(self.ui_url + "/_stcore/health", ui)

    def start_worker(self):
        assert self.worker is None
        self.worker = self.spawn("worker", ["-m", "app.worker"])

    def create_job(self, title, with_source=False, content="Nội dung tự viết để test."):
        package = {
            "title": title,
            "branch": "novel",
            "language": "vi",
            "sources": [{"label": "Self-authored E2E fixture", "rights_note": "Test only"}],
            "scenes": [{"narration": content, "source_indices": [0]}],
        }
        if with_source:
            package["source_documents"] = [
                {
                    "title": title,
                    "source_url": "https://example.org",
                    "content": "Self-authored input snapshot for E2E.",
                }
            ]
        response = httpx.post(self.api_url + "/api/jobs", json={"package": package})
        response.raise_for_status()
        return response.json()

    def job(self, job_id):
        response = httpx.get(self.api_url + "/api/jobs/" + job_id)
        response.raise_for_status()
        return response.json()

    def wait_status(self, job_id, status):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            job = self.job(job_id)
            if job["status"] == status:
                return job
            time.sleep(0.1)
        raise AssertionError(f"Expected {status}; got {job}")

    def close(self):
        self.provider_release.set()
        for process in reversed(self.processes):
            stop_tree(process)
        self.provider.shutdown()
        self.provider.server_close()
        self.provider_thread.join(timeout=5)
        for log in self.logs:
            log.close()


@pytest.fixture
def studio(tmp_path, request):
    stack = Stack(tmp_path)
    try:
        stack.start()
        yield stack
    finally:
        stack.close()
        destination = ROOT / "artifacts" / "e2e" / request.node.name
        destination.mkdir(parents=True, exist_ok=True)
        for log in tmp_path.glob("*.log"):
            (destination / log.name).write_bytes(log.read_bytes())


@pytest.fixture(autouse=True)
def browser_evidence(page, studio, request):
    page.set_default_timeout(15000)
    yield
    destination = ROOT / "artifacts" / "e2e" / request.node.name
    destination.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=destination / "result.png", full_page=True)
