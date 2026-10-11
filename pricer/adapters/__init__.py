from ..http import FetchError, Http
from ..models import Vendor
from .generic import GenericAdapter
from .shopify import ShopifyAdapter
from .woocommerce import WooAdapter


class ManualAdapter:
    platform = "manual"

    def __init__(self, http, vendor):
        self.vendor = vendor

    def find(self, reagent):
        return []


def make_adapter(http: Http, vendor: Vendor):
    """Pick the adapter for a vendor. For 'auto', probe Shopify then WooCommerce."""
    if vendor.platform == "shopify":
        return ShopifyAdapter(http, vendor)
    if vendor.platform == "woocommerce":
        return WooAdapter(http, vendor)
    if vendor.platform == "generic":
        return GenericAdapter(http, vendor)
    if vendor.platform == "manual":
        return ManualAdapter(http, vendor)

    errors = []
    for cls in (ShopifyAdapter, WooAdapter):
        adapter = cls(http, vendor)
        try:
            if adapter.probe():
                return adapter
        except FetchError as e:
            errors.append(f"{cls.platform}: {e}")
    raise FetchError("could not detect a Shopify or WooCommerce store"
                     + (f" ({'; '.join(errors)})" if errors else "")
                     + ". Set platform: generic with a search_url, or manual.")
