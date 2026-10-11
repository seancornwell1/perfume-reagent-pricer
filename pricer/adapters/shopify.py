"""Shopify stores expose their catalog at /products.json, which is far more reliable than
scraping search pages. If that's disabled we fall back to /search/suggest.json."""
from typing import List, Optional

from ..http import FetchError, Http
from ..matching import match
from ..models import Product, Reagent, Variant, Vendor


class ShopifyAdapter:
    platform = "shopify"
    MAX_PAGES = 40  # 250 products per page

    def __init__(self, http: Http, vendor: Vendor):
        self.http = http
        self.vendor = vendor
        self._catalog: Optional[list] = None
        self._catalog_failed = False

    def probe(self) -> bool:
        data = self.http.json(f"{self.vendor.base}/products.json", params={"limit": 1})
        return isinstance(data, dict) and isinstance(data.get("products"), list)

    def _load_catalog(self) -> Optional[list]:
        if self._catalog is None and not self._catalog_failed:
            items = []
            try:
                for page in range(1, self.MAX_PAGES + 1):
                    data = self.http.json(f"{self.vendor.base}/products.json",
                                          params={"limit": 250, "page": page})
                    batch = data.get("products") or []
                    items.extend(batch)
                    if len(batch) < 250:
                        break
                self._catalog = items
            except FetchError:
                if items:
                    self._catalog = items  # partial catalog is still useful
                else:
                    self._catalog_failed = True
        return self._catalog

    def find(self, reagent: Reagent) -> List[Product]:
        catalog = self._load_catalog()
        if catalog is not None:
            return [self.from_catalog_item(p) for p in catalog
                    if match(reagent, p.get("title", ""))]
        return self._find_via_suggest(reagent)

    def from_catalog_item(self, p: dict) -> Product:
        variants = []
        for v in p.get("variants") or []:
            price = v.get("price")
            variants.append(Variant(
                title=v.get("title") or "",
                price=float(price) if price not in (None, "") else None,
                available=v.get("available"),
            ))
        return Product(title=p.get("title", ""), url=f"{self.vendor.base}/products/{p.get('handle')}",
                       variants=variants, description=p.get("body_html") or "")

    def _find_via_suggest(self, reagent: Reagent) -> List[Product]:
        handles = []
        for term in reagent.search_terms[:4]:
            data = self.http.json(f"{self.vendor.base}/search/suggest.json",
                                  params={"q": term, "resources[type]": "product",
                                          "resources[limit]": 10})
            for p in ((data.get("resources") or {}).get("results") or {}).get("products") or []:
                if match(reagent, p.get("title", "")) and p.get("handle") not in handles:
                    handles.append(p.get("handle"))
            if handles:
                break
        return [self.from_product_js(self.http.json(f"{self.vendor.base}/products/{h}.js"))
                for h in handles[:8]]

    def from_product_js(self, p: dict) -> Product:
        # /products/<handle>.js gives prices in cents
        variants = [Variant(title=v.get("title") or "",
                            price=(v["price"] / 100.0) if v.get("price") is not None else None,
                            available=v.get("available"))
                    for v in p.get("variants") or []]
        return Product(title=p.get("title", ""), url=f"{self.vendor.base}/products/{p.get('handle')}",
                       variants=variants, description=p.get("description") or "")
