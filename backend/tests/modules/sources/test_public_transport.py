import socket
import ssl
from unittest.mock import patch

import httpx2
import pytest

from modules.sources.http import HttpxPageClient
from modules.sources.transport import PublicNetworkTransport


@pytest.mark.parametrize(
    "addresses",
    [
        ["127.0.0.1"],
        ["10.0.0.1"],
        ["169.254.169.254"],
        ["168.63.129.16"],
        ["93.184.216.34", "192.168.1.1"],
        ["::1"],
        ["fe80::1"],
        ["fec0::1"],
        ["64:ff9b::7f00:1"],
        ["::ffff:127.0.0.1"],
        [],
    ],
)
def test_transport_rejects_unsafe_dns_before_sending(
    addresses: list[str],
) -> None:
    sent: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return httpx2.Response(200)

    answers = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))
        for ip in addresses
    ]
    with (
        patch("socket.getaddrinfo", return_value=answers),
        patch(
            "httpx2.HTTPTransport",
            return_value=httpx2.MockTransport(respond),
        ),
        httpx2.Client(
            transport=PublicNetworkTransport(), trust_env=False
        ) as client,
        pytest.raises(ValueError, match="Unsafe source URL"),
    ):
        client.get("https://events.example/listings")
    assert sent == []


@pytest.mark.parametrize("address", ["93.184.216.34", "2606:4700::1111"])
def test_transport_pins_dns_but_preserves_host_and_tls(address: str) -> None:
    sent: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return httpx2.Response(200, text="events")

    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    answers = [(family, socket.SOCK_STREAM, 6, "", (address, 8443))]
    with (
        patch("socket.getaddrinfo", return_value=answers) as resolve,
        patch(
            "httpx2.HTTPTransport",
            side_effect=lambda **kwargs: httpx2.MockTransport(respond),
        ) as transport,
        httpx2.Client(
            transport=PublicNetworkTransport(), trust_env=False
        ) as client,
    ):
        response = client.get("https://events.example:8443/listings?q=1")

    assert response.text == "events"
    assert response.url == "https://events.example:8443/listings?q=1"
    assert len(sent) == 1
    assert sent[0].url.host == address
    assert sent[0].url.port == 8443
    assert sent[0].url.raw_path == b"/listings?q=1"
    assert sent[0].headers["host"] == "events.example:8443"
    assert sent[0].extensions["sni_hostname"] == "events.example"
    assert resolve.call_count == 1
    transport.assert_called_once_with(trust_env=False)


def test_default_page_client_rechecks_dns_on_same_host_redirect() -> None:
    sent: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return httpx2.Response(302, headers={"location": "/next"})

    answers = [
        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]
        for ip in ["93.184.216.34", "127.0.0.1"]
    ]
    with (
        patch("socket.getaddrinfo", side_effect=answers) as resolve,
        patch(
            "httpx2.HTTPTransport",
            side_effect=lambda **kwargs: httpx2.MockTransport(respond),
        ),
    ):
        client = HttpxPageClient(user_agent="BeeThere/test")
        try:
            with pytest.raises(ValueError, match="Unsafe source URL"):
                client.get_text("https://events.example/listings")
        finally:
            client.close()
    assert len(sent) == 1
    assert resolve.call_count == 2


def test_transport_closes_pool_when_connection_fails() -> None:
    def fail(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("Connection failed", request=request)

    transport = httpx2.MockTransport(fail)
    with (
        patch(
            "socket.getaddrinfo",
            return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
            ],
        ),
        patch("httpx2.HTTPTransport", return_value=transport),
        patch.object(transport, "close", wraps=transport.close) as close,
        httpx2.Client(
            transport=PublicNetworkTransport(), trust_env=False
        ) as client,
        pytest.raises(httpx2.ConnectError),
    ):
        client.get("https://events.example/event")
    close.assert_called_once()


class RecordingStream:
    """Fake the remote peer, but use the real HTTP and TLS setup code."""

    def __init__(self) -> None:
        self.tls_names: list[str | None] = []
        self.writes: list[bytes] = []
        self.closed = False

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        return (
            b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n"
            b"Content-Length: 5\r\n\r\nevent"
        )

    def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self.writes.append(bytes(buffer))

    def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ) -> RecordingStream:
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED
        assert ssl_context.check_hostname
        self.tls_names.append(server_hostname)
        return self

    def get_extra_info(self, info: str) -> None:
        return None

    def close(self) -> None:
        self.closed = True


def test_real_http_transport_uses_pinned_ip_and_verified_original_tls() -> None:
    stream = RecordingStream()
    answers = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
    ]
    with (
        patch("socket.getaddrinfo", return_value=answers),
        patch(
            "httpcore2.SyncBackend.connect_tcp", return_value=stream
        ) as connect,
        patch.dict("os.environ", {"HTTPS_PROXY": "http://127.0.0.1:9999"}),
    ):
        client = HttpxPageClient(user_agent="BeeThere/test")
        try:
            assert client.get_text("https://events.example/event") == "event"
        finally:
            client.close()
    assert connect.call_args.kwargs["host"] == "93.184.216.34"
    assert connect.call_args.kwargs["port"] == 443
    assert stream.tls_names == ["events.example"]
    assert b"Host: events.example\r\n" in b"".join(stream.writes)
    assert stream.closed
