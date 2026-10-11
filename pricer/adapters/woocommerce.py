"""WooCommerce Store API (public, no key needed on most stores)."""
import html
from typing import List, Optional

from ..http import FetchError, Http
from ..matching import match
from ..models import Product, Reagent, Variant, Vendor


def _price(prices: dict) -> Optional[float]:
    if not prices or prices.get("price") in (None, ""):
        return None
    minor = int(prices.get("currency_minor_unit", 2))
    return int(prices["price"]) / (10 ** minor)


class WooAdapter:
    platform = "woocommerce"
    PATHS = ("/wp-json/wc/store/v1/products", "/wp-json/wc/store/products")

    def __init__(self, http: Http, vendor: Vendor):
        self.http = http
        self.vendor = vendor
        self._path: Optional[str] = None

    def _api(self, suffix: str = "", params: Optional[dict] = None):
        paths = [self._path] if self._path else list(self.PATHS)
        last = None
        for path in paths:
            try:
                data = self.http.json(f"{self.vendor.base}{path}{suffix}", params=params)
                self._path = path
                return data
            except FetchError as e:
                last = e
        raise last

    def probe(self) -> bool:
        return isinstance(self._api(params={"per_page": 1}), list)

    def find(self, reagent: Reagent) -> List[Product]:
        found = {}
        for term in reagent.search_terms[:4]:
            for item in self._api(params={"search": term, "per_page": 20}) or []:
                if match(reagent, html.unescape(item.get("name", ""))):
                    found.setdefault(item["id"], item)
            if found:
                break
        return [self.to_product(item) for item in list(found.values())[:8]]

    def to_product(self, item: dict) -> Product:
        currency = (item.get("prices") or {}).get("currency_code")
        variants = []
        if item.get("type") == "variable" and item.get("variations"):
            for var in item["variations"][:12]:
                title = ", ".join(str(a.get("value", "")) for a in var.get("attributes") or [])
                try:
                    detail = self._api(f"/{var['id']}")
                except FetchError:
                    detail = {}
                variants.append(Variant(
                    title=title or html.unescape(detail.get("name", "")),
                    price=_price(detail.get("prices")),
                    available=detail.get("is_in_stock"),
                    currency=(detail.get("prices") or {}).get("currency_code") or currency,
                ))
        else:
            variants.append(Variant(title="", price=_price(item.get("prices")),
                                    available=item.get("is_in_stock"), currency=currency))
        desc = (item.get("description") or "") + " " + (item.get("short_description") or "")
        return Product(title=html.unescape(item.get("name", "")), url=item.get("permalink", ""),
                       variants=variants, description=desc)
