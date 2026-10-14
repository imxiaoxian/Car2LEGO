"""Public web tools for the vehicle research skill, with machine-readable evidence."""
import argparse
import base64
import hashlib
import ipaddress
import json
import socket
from urllib.parse import parse_qs, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup


def check_url(url):
    parts = urlsplit(url)
    if parts.scheme not in {"https", "http"} or parts.username or parts.password or not parts.hostname:
        raise ValueError("Only public HTTP(S) pages are allowed.")
    if parts.port not in (None, 80, 443):
        raise ValueError("Only standard web ports are allowed.")
    addresses = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("Local and private network addresses are not allowed.")


def fetch_html(url, max_bytes=4_000_000):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"}
    with httpx.Client(timeout=20, headers=headers) as client:
        for _ in range(6):
            check_url(url)
            with client.stream("GET", url) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers["location"])
                    continue
                if not 200 <= response.status_code < 300:
                    raise httpx.HTTPStatusError(f"HTTP {response.status_code}", request=response.request, response=response)
                response.raise_for_status()
                if "html" not in response.headers.get("content-type", ""):
                    raise ValueError("This reader supports HTML pages; find an accessible HTML specification source.")
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > max_bytes:
                        raise ValueError(f"Page exceeds the {max_bytes // 1_000_000} MB limit.")
                return str(response.url), BeautifulSoup(bytes(data), "html.parser")
    raise ValueError("Too many redirects.")


def bing_link(url):
    if urlsplit(url).hostname in {"www.bing.com", "cn.bing.com"}:
        value = parse_qs(urlsplit(url).query).get("u", [""])[0]
        if value.startswith("a1"):
            try:
                return base64.urlsafe_b64decode(value[2:] + "=" * (-len(value[2:]) % 4)).decode()
            except (ValueError, UnicodeDecodeError):
                return ""
    return url


def search(query):
    url = str(httpx.URL("https://www.bing.com/search", params={"q": query, "count": "8", "ensearch": "1"}))
    final_url, page = fetch_html(url, max_bytes=1_000_000)
    results = []
    for row in page.select("li.b_algo"):
        link = row.select_one("h2 a")
        if not link:
            continue
        target = bing_link(urljoin(final_url, link.get("href", "")))
        if urlsplit(target).scheme in {"http", "https"}:
            results.append({"title": link.get_text(" ", strip=True), "url": target,
                            "snippet": row.get_text(" ", strip=True)[:1400]})
    return {"type": "vehicle_web_search", "query": query, "url": final_url,
            "success": bool(results), "results": results[:8]}


def open_page(url):
    final_url, page = fetch_html(url, max_bytes=2_000_000)
    if urlsplit(final_url).scheme != urlsplit(url).scheme:
        raise ValueError("A source may not redirect between HTTP and HTTPS.")
    title = page.title.get_text(" ", strip=True) if page.title else final_url
    for element in page.select("script, style, noscript, svg, nav, footer"):
        element.decompose()
    text = " ".join(page.stripped_strings)
    return {"type": "vehicle_web_open", "requested_url": url, "url": final_url, "title": title,
            "success": True, "text": text[:45000], "truncated": len(text) > 45000,
            "text_sha256": hashlib.sha256(text.encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("search").add_argument("--query", required=True)
    commands.add_parser("open").add_argument("--url", required=True)
    args = parser.parse_args()
    try:
        result = search(args.query) if args.action == "search" else open_page(args.url)
    except (ValueError, OSError, httpx.HTTPError) as error:
        result = {"type": f"vehicle_web_{args.action}", "success": False, "error": str(error)}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
