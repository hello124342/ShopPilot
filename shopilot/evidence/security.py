from __future__ import annotations

import ipaddress
import re
import socket
from collections.abc import Callable, Iterable
from hashlib import sha256
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from .models import ExtractedDocument


class BrowserSecurityError(ValueError):
    pass


_INJECTION_PATTERNS = (
    re.compile(r"ignore (all |the )?(previous|system) instructions", re.I),
    re.compile(r"(reveal|print|return).{0,30}(secret|credential|api key|system prompt)", re.I),
    re.compile(r"忽略.{0,12}(指令|规则|要求)"),
    re.compile(r"(泄露|输出|返回).{0,12}(密钥|凭据|系统提示)"),
)


def default_resolver(host: str) -> list[str]:
    return sorted({item[4][0] for item in socket.getaddrinfo(host, None)})


class SafeBrowserExtractor:
    def __init__(
        self,
        *,
        allowed_domains: Iterable[str] = (),
        max_bytes: int = 2_000_000,
        max_redirects: int = 3,
        timeout_seconds: float = 10,
        resolver: Callable[[str], list[str]] = default_resolver,
        transport: httpx.BaseTransport | None = None,
    ):
        self.allowed_domains = frozenset(domain.lower().strip(".") for domain in allowed_domains)
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.timeout_seconds = timeout_seconds
        self.resolver = resolver
        self.transport = transport

    def _validate_url(self, url: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"}:
            raise BrowserSecurityError("url_scheme_not_allowed")
        if not parsed.hostname or parsed.username or parsed.password:
            raise BrowserSecurityError("url_authority_not_allowed")
        host = parsed.hostname.lower().strip(".")
        if self.allowed_domains and not any(
            host == domain or host.endswith(f".{domain}") for domain in self.allowed_domains
        ):
            raise BrowserSecurityError("domain_not_allowed")
        try:
            addresses = self.resolver(host)
        except (OSError, socket.gaierror) as exc:
            raise BrowserSecurityError("dns_resolution_failed") from exc
        if not addresses:
            raise BrowserSecurityError("dns_resolution_failed")
        for address in addresses:
            if not ipaddress.ip_address(address).is_global:
                raise BrowserSecurityError("private_network_target")

    @staticmethod
    def _sanitize_html(content: bytes, encoding: str | None) -> tuple[str, str]:
        text = content.decode(encoding or "utf-8", errors="replace")
        soup = BeautifulSoup(text, "lxml")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        for element in soup(["script", "style", "noscript", "template", "iframe", "object"]):
            element.decompose()
        return title, "\n".join(soup.stripped_strings)

    def extract(self, url: str) -> ExtractedDocument:
        current = url
        with httpx.Client(
            transport=self.transport,
            timeout=self.timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": "ShopPilotResearch/1.0"},
        ) as client:
            for redirect_count in range(self.max_redirects + 1):
                self._validate_url(current)
                try:
                    with client.stream("GET", current) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location:
                                raise BrowserSecurityError("redirect_location_missing")
                            if redirect_count >= self.max_redirects:
                                raise BrowserSecurityError("redirect_limit_exceeded")
                            current = urljoin(current, location)
                            continue
                        response.raise_for_status()
                        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                        if content_type not in {"text/html", "text/plain"}:
                            raise BrowserSecurityError("content_type_not_allowed")
                        declared_size = response.headers.get("content-length")
                        if declared_size and int(declared_size) > self.max_bytes:
                            raise BrowserSecurityError("response_too_large")
                        body = bytearray()
                        for chunk in response.iter_bytes():
                            body.extend(chunk)
                            if len(body) > self.max_bytes:
                                raise BrowserSecurityError("response_too_large")
                except httpx.TimeoutException as exc:
                    raise BrowserSecurityError("browser_timeout") from exc
                except httpx.HTTPStatusError as exc:
                    raise BrowserSecurityError(f"source_http_error:{exc.response.status_code}") from exc
                title, text = self._sanitize_html(bytes(body), response.encoding)
                return ExtractedDocument(
                    url=current,
                    title=title,
                    text=text,
                    content_type=content_type,
                    content_hash=sha256(bytes(body)).hexdigest(),
                    prompt_injection_suspected=any(pattern.search(text) for pattern in _INJECTION_PATTERNS),
                )
        raise BrowserSecurityError("redirect_limit_exceeded")
