"""Test fixtures and controlled local HTTP server for Vexfox testing."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Generator

import pytest


class LocalTestServerHandler(BaseHTTPRequestHandler):
    """Deterministic local HTTP handler for testing."""

    # Track received requests to verify whether live network requests occurred
    request_history: list[dict[str, str]] = []

    def log_message(self, format: str, *args: object) -> None:
        # Suppress standard logging to keep test output clean
        pass

    def do_GET(self) -> None:
        LocalTestServerHandler.request_history.append({"method": "GET", "path": self.path})

        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "healthy"}')
        elif self.path.startswith("/users"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-Custom-Header", "VexfoxTest")
            self.end_headers()
            self.wfile.write(b'{"users": [{"id": 1, "name": "Ada Lovelace"}]}')
        elif self.path == "/binary":
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.end_headers()
            self.wfile.write(bytes([0x00, 0xFF, 0xFE, 0x12, 0x34]))
        elif self.path == "/empty":
            self.send_response(204)
            self.end_headers()
        elif self.path == "/not-found":
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "Resource not found"}')
        elif self.path == "/server-error":
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Internal Server Error")
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"Hello from {self.path}".encode("utf-8"))

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        LocalTestServerHandler.request_history.append(
            {"method": "POST", "path": self.path, "body": body.decode("utf-8", errors="replace")}
        )

        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"created": true, "id": 101}')


@pytest.fixture(scope="session")
def local_server() -> Generator[str, None, None]:
    """Runs a local HTTP server in a daemon thread on an ephemeral port."""
    server = HTTPServer(("127.0.0.1", 0), LocalTestServerHandler)
    # pyrefly: ignore[bad-unpacking]
    host, port = server.server_address
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    base_url = f"http://{host}:{port}"
    yield base_url

    server.shutdown()
    server.server_close()


@pytest.fixture(autouse=True)
def reset_request_history() -> Generator[None, None, None]:
    """Resets request history before and after each test."""
    LocalTestServerHandler.request_history.clear()
    yield
    LocalTestServerHandler.request_history.clear()


@pytest.fixture
def server_requests() -> list[dict[str, str]]:
    """Provides access to the request history tracked by the local HTTP server."""
    return LocalTestServerHandler.request_history
