"""Network transport for public ingestion sources."""

import ipaddress
import socket
from collections.abc import Iterator

import httpx2


def validate_source_url(url: httpx2.URL) -> None:
    """Reject unsupported URLs and non-public literal addresses."""
    if url.scheme not in {"http", "https"} or not url.host or url.userinfo:
        raise ValueError("Unsafe source URL")
    try:
        address = ipaddress.ip_address(url.host)
    except ValueError:
        return  # DNS names are checked by the transport before connection.
    if (
        not address.is_global
        or address.is_multicast
        or str(address) == "168.63.129.16"  # Azure platform virtual address.
        or (
            isinstance(address, ipaddress.IPv6Address)
            and (
                address.is_site_local
                or address in ipaddress.IPv6Network("64:ff9b::/96")
                or address.ipv4_mapped is not None
                or address.sixtofour is not None
                or address.teredo is not None
                or address.scope_id is not None
            )
        )
    ):
        raise ValueError("Unsafe source URL: non-public address")


class _ConnectionStream(httpx2.SyncByteStream):
    def __init__(
        self, response: httpx2.Response, transport: httpx2.HTTPTransport
    ) -> None:
        self._response = response
        self._transport = transport

    def __iter__(self) -> Iterator[bytes]:
        assert isinstance(self._response.stream, httpx2.SyncByteStream)
        yield from self._response.stream

    def close(self) -> None:
        try:
            self._response.close()
        finally:
            self._transport.close()


class PublicNetworkTransport(httpx2.BaseTransport):
    """Connect only to public IPs, with a separate pool for each request.

    Keep Host and TLS verification tied to the original hostname. A fresh
    transport prevents connection reuse across names sharing a pinned IP.
    Environment proxies are disabled so they cannot bypass address checks.
    """

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        pinned_request = self._pin_request_to_public_ip(request)
        transport = httpx2.HTTPTransport(trust_env=False)
        try:
            response = transport.handle_request(pinned_request)
        except BaseException:
            transport.close()
            raise
        return httpx2.Response(
            response.status_code,
            headers=response.headers,
            stream=_ConnectionStream(response, transport),
            extensions=response.extensions,
        )

    def _pin_request_to_public_ip(
        self, request: httpx2.Request
    ) -> httpx2.Request:
        validate_source_url(request.url)
        port = request.url.port or (
            443 if request.url.scheme == "https" else 80
        )
        answers = socket.getaddrinfo(
            request.url.host, port, type=socket.SOCK_STREAM
        )
        if not answers:
            raise ValueError("Unsafe source URL: no DNS addresses")

        addresses = [answer[4][0] for answer in answers]
        for address in addresses:
            validate_source_url(request.url.copy_with(host=address))

        return httpx2.Request(
            request.method,
            request.url.copy_with(host=addresses[0]),
            headers=request.headers,
            stream=request.stream,
            extensions={
                **request.extensions,
                "sni_hostname": request.url.host,
            },
        )
