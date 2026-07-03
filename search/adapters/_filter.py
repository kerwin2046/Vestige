from __future__ import annotations

import socket
from urllib.parse import urlparse


def resolve_hostname(hostname: str) -> tuple[list[str], list[str]]:
    addr_info = socket.getaddrinfo(hostname, None)
    ipv4 = [info[4][0] for info in addr_info if info[0] == socket.AF_INET]
    ipv6 = [info[4][0] for info in addr_info if info[0] == socket.AF_INET6]
    return ipv4, ipv6


def _host_allowed(hostnames: list[str], filter_list: list[str]) -> bool:
    """True if any hostname matches an allow-list entry (domain suffix match)."""
    for host in hostnames:
        host = host.lower()
        for entry in filter_list:
            entry = (entry or "").lower().strip()
            if not entry:
                continue
            if host == entry or host.endswith("." + entry):
                return True
    return False


def filter_by_domains(results: list[dict], filter_list: list[str] | None) -> list[dict]:
    """Keep only results whose URL host matches filter_list (optional)."""
    if not filter_list:
        return results

    filtered: list[dict] = []
    for result in results:
        url = result.get("url") or result.get("link") or result.get("href") or ""
        if not url.startswith(("http://", "https://")):
            continue
        domain = urlparse(url).hostname
        if not domain:
            continue
        hostnames = [domain]
        try:
            ipv4, ipv6 = resolve_hostname(domain)
            hostnames.extend(ipv4)
            hostnames.extend(ipv6)
        except OSError:
            pass
        if _host_allowed(hostnames, filter_list):
            filtered.append(result)
    return filtered
