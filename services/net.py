"""Public HTTP fetches that refuse private, loopback, and link-local targets."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import requests

from config import USER_AGENT


class UrlError(ValueError):
    """The address is missing, malformed, or not a public site."""


def public_http_url(url: str) -> str:
    raw = (url or "").strip()
    parsed = urlparse(raw)
    host = parsed.hostname
    if parsed.scheme not in {"http", "https"} or not host:
        raise UrlError("Use a public http or https address.")
    if host.lower() in {"localhost"} or host.lower().endswith(".local"):
        raise UrlError("That address is not a public site.")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UrlError("That address did not resolve.") from exc
    addresses = []
    for info in infos:
        try:
            addresses.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    if not addresses:
        raise UrlError("That address did not resolve.")
    for address in addresses:
        if not address.is_global:
            raise UrlError("That address is not a public site.")
    return raw


def fetch_public(url: str, *, timeout: float = 12, max_bytes: int = 1_500_000) -> dict:
    current = public_http_url(url)
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,image/*;q=0.9,*/*;q=0.8"}
    status = 0
    content = b""
    response_headers: dict[str, str] = {}
    for _ in range(4):
        response = requests.get(current, headers=headers, timeout=timeout, allow_redirects=False, stream=True)
        status = response.status_code
        response_headers = {key: value for key, value in response.headers.items()}
        if status in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise UrlError("The site returned a redirect without a destination.")
            current = public_http_url(urljoin(current, location))
            continue
        chunks = []
        size = 0
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            size += len(chunk)
            if size > max_bytes:
                response.close()
                raise UrlError("The response is larger than this desk will read.")
            chunks.append(chunk)
        response.close()
        content = b"".join(chunks)
        break
    return {
        "status": status,
        "url": current,
        "content": content,
        "headers": response_headers,
    }
