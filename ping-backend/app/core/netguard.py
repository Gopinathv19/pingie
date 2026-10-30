"""Outbound requests to addresses an owner chose (crawled pages, alert
webhooks) must not reach Pingie's own network: localhost, private ranges, or
cloud metadata services (169.254.169.254).

`crawl_allow_private_hosts` turns the check off for local development.
"""

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import get_settings


def private_host_reason(url: str) -> str | None:
    """Why `url` must not be fetched, or None when it's a public address."""
    if get_settings().crawl_allow_private_hosts:
        return None
    host = urlparse(url).hostname or ""
    if not host:
        return "The URL has no host"
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return f"Could not resolve {host}"
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return f"{host} resolves to a private address"
    return None
