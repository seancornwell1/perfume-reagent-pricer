"""Best-effort HTML scraping for sites without a JSON API.

Search page -> product links whose text matches the reagent -> product page, where prices
come from (in order): size dropdown options, "$X / gram" unit prices, schema.org JSON-LD."""
import json
import re
from typing import List
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from ..http import Http
from ..matching import match
from ..models import Product, Reagent, Variant, Vendor
from ..units import parse_size

_CUR = {"$": "USD", "US$": "USD", "USD": "USD", "£": "GBP", "GBP": "GBP", "€": "EUR", "EUR": "EUR"}
_MONEY = r"(US\$|USD|\$|£|GBP|€|EUR)\s*([\d,]+(?:\.\d{1,2})?)"
_OPTION_PRICE = re.compile(_MONEY)
_UNIT_PRICE = re.compile(_MONEY + r"\s*(?:/|per)\s*(gram|gm|g|ml|kg|oz)\b", re.I)


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def parse_product_page(page_html: str, url: str) -> Product:
    soup = BeautifulSoup(page_html, "html.parser")
    title = ""
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        title = og["content"]
    elif soup.find("h1"):
        title = soup.find("h1").get_text(" ", strip=True)
    elif soup.title:
        title = soup.title.get_text(strip=True)

    variants: List[Variant] = []

    # 1. <select> options like "4 ml - $5.25" or "5g (+$3.00)"
    for opt in soup.find_all("option"):
        text = opt.get_text(" ", strip=True)
        m = _OPTION_PRICE.search(text)
        if m and parse_size(text) and "+" not in text[max(0, m.start() - 2):m.start()]:
            label = re.sub(r"[\s\-–:(]*" + _MONEY + r"\)?", "", text).strip(" -–:")
            variants.append(Variant(title=label or text, price=_num(m.group(2)), currency=_CUR[m.group(1)]))

    # 2. Unit prices like "US$ 0.73 /gram"
    if not variants:
        body_text = soup.get_text(" ", strip=True)
        m = _UNIT_PRICE.search(body_text)
        if m:
            variants.append(Variant(title=f"1 {m.group(3)} (unit price)", price=_num(m.group(2)),
                                    currency=_CUR[m.group(1)]))

    # 3. JSON-LD Product offers
    if not variants:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except ValueError:
                continue
            for node in data if isinstance(data, list) else data.get("@graph", [data]):
                if not isinstance(node, dict) or "Product" not in str(node.get("@type")):
                    continue
                offers = node.get("offers") or []
                if isinstance(offers, dict):
                    offers = offers.get("offers") or [offers]
                for off in offers:
                    price = off.get("price") or off.get("lowPrice")
                    if price is None:
                        continue
                    avail = off.get("availability")
                    variants.append(Variant(
                        title=off.get("name") or off.get("sku") or "",
                        price=float(price),
                        available=None if avail is None else "InStock" in str(avail),
                        currency=off.get("priceCurrency"),
                    ))
                title = title or node.get("name", "")

    text = soup.get_text(" ", strip=True)[:50000]
    return Product(title=title, url=url, variants=variants, description=text)


class GenericAdapter:
    platform = "generic"

    def __init__(self, http: Http, vendor: Vendor):
        self.http = http
        self.vendor = vendor

    def probe(self) -> bool:
        return True

    def find(self, reagent: Reagent) -> List[Product]:
        links = []
        pattern = re.compile(self.vendor.product_link_pattern) if self.vendor.product_link_pattern else None
        for term in reagent.search_terms[:3]:
            url = self.vendor.search_url.replace("{q}", quote_plus(term))
            soup = BeautifulSoup(self.http.text(url), "html.parser")
            for a in soup.find_all("a", href=True):
                href = urljoin(url, a["href"])
                if pattern and not pattern.search(href):
                    continue
                label = a.get_text(" ", strip=True) or a.get("title", "")
                if match(reagent, label) and href not in links:
                    links.append(href)
            if links:
                break
        products = []
        for href in links[:5]:
            p = parse_product_page(self.http.text(href), href)
            p.title = p.title or href
            products.append(p)
        return products
