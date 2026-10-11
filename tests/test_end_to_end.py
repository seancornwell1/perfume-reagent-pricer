"""Runs the full pipeline against canned responses for a Shopify, a WooCommerce and a
generic HTML store, so adapters, normalization, analysis and the report are all exercised."""
from urllib.parse import urlencode

import pytest

from pricer.analysis import best_by_reagent, cheapest_basket
from pricer.config import load_reagents
from pricer.http import FetchError
from pricer.models import Vendor
from pricer.report import write_csv, write_html
from pricer.search import run_search

_, REAGENTS = load_reagents("reagents.yaml")

SHOPIFY_CATALOG = {"products": [
    {"title": "Ionone Beta", "handle": "ionone-beta",
     "body_html": "<p>Certificate of Analysis available for each lot.</p>",
     "variants": [{"title": "5g", "price": "6.00", "available": True},
                  {"title": "25g", "price": "18.00", "available": True},
                  {"title": "100g", "price": "50.00", "available": False}]},
    {"title": "Ionone Beta 10% in DPG", "handle": "ionone-beta-10",
     "variants": [{"title": "10g", "price": "2.00", "available": True}]},
    {"title": "Alpha Ionone", "handle": "alpha-ionone",
     "variants": [{"title": "5g", "price": "1.00", "available": True}]},
    {"title": "Damascone Beta", "handle": "damascone-beta", "body_html": "",
     "variants": [{"title": "2g", "price": "4.00", "available": True},
                  {"title": "10g", "price": "15.00", "available": True}]},
]}

WOO_SEARCH = [
    {"id": 11, "name": "Delta Decalactone", "permalink": "https://woo.test/product/delta-decalactone/",
     "type": "variable", "prices": {"currency_code": "USD", "currency_minor_unit": 2, "price": "500"},
     "variations": [{"id": 12, "attributes": [{"name": "Size", "value": "5g"}]},
                    {"id": 13, "attributes": [{"name": "Size", "value": "25g"}]}],
     "description": "", "short_description": ""},
    {"id": 14, "name": "Gamma Decalactone", "permalink": "https://woo.test/product/gamma/",
     "type": "simple", "prices": {"price": "100", "currency_minor_unit": 2}},
]
WOO_VAR = {
    12: {"id": 12, "is_in_stock": True, "prices": {"price": "550", "currency_minor_unit": 2, "currency_code": "USD"}},
    13: {"id": 13, "is_in_stock": True, "prices": {"price": "1500", "currency_minor_unit": 2, "currency_code": "USD"}},
}

GENERIC_SEARCH = """<html><body>
<a href="/p-101-beta-ionone.aspx">Beta Ionone</a>
<a href="/p-102-alpha-ionone.aspx">Alpha Ionone</a>
<a href="/about">Beta Ionone guide</a></body></html>"""
GENERIC_PRODUCT = """<html><head><meta property="og:title" content="Beta Ionone"></head><body>
<select><option>Choose size</option><option>4 ml - $3.10</option><option>50 g - $19.00</option></select>
</body></html>"""


class FakeHttp:
    def __init__(self):
        self.calls = []

    def _key(self, url, params):
        return url + ("?" + urlencode(params) if params else "")

    def json(self, url, params=None):
        self.calls.append(self._key(url, params))
        if url == "https://shop.test/products.json":
            if params.get("page", 1) == 1:
                return SHOPIFY_CATALOG
            return {"products": []}
        if url == "https://woo.test/wp-json/wc/store/v1/products":
            if params.get("per_page") == 1:
                return WOO_SEARCH[:1]
            return WOO_SEARCH if "decalactone" in params.get("search", "").lower() else []
        if url.startswith("https://woo.test/wp-json/wc/store/v1/products/"):
            return WOO_VAR[int(url.rsplit("/", 1)[1])]
        raise FetchError(f"{url}: HTTP 404")

    def text(self, url, params=None):
        self.calls.append(self._key(url, params))
        if url.startswith("https://gen.test/search.aspx"):
            return GENERIC_SEARCH if "ionone" in url.lower() else "<html></html>"
        if url == "https://gen.test/p-101-beta-ionone.aspx":
            return GENERIC_PRODUCT
        raise FetchError(f"{url}: HTTP 404")


VENDORS = [
    Vendor(name="ShopCo", url="https://shop.test", platform="shopify", coa_level="unknown"),
    Vendor(name="WooCo", url="https://woo.test", platform="auto", coa_level="on_request"),
    Vendor(name="GenCo", url="https://gen.test", platform="generic", coa_level="published",
           search_url="https://gen.test/search.aspx?searchterm={q}", product_link_pattern=r"/p-\d+-"),
    Vendor(name="Sigma", url="https://sigma.test", platform="manual", coa_level="published",
           search_url="https://sigma.test/search?q={q}"),
    Vendor(name="DeadCo", url="https://dead.test", platform="auto"),
]


@pytest.fixture(scope="module")
def run():
    return run_search(VENDORS, REAGENTS, FakeHttp(), {"USD": 1.0}, log=lambda s: None)


def offers_for(res, vendor, reagent):
    return [o for o in res.offers if o.vendor == vendor and o.reagent == reagent]


def test_shopify_offers_and_coa_scan(run):
    ion = offers_for(run, "ShopCo", "Beta-ionone")
    titles = {(o.product_title, o.variant_title) for o in ion}
    assert ("Ionone Beta", "5g") in titles
    assert not any("Alpha" in t for t, _ in titles)
    neat = [o for o in ion if o.product_title == "Ionone Beta"]
    assert all(o.coa_level == "mentioned" for o in neat)  # body_html mentions CoA
    assert [o.available for o in neat] == [True, True, False]
    dil = [o for o in ion if "DPG" in o.product_title][0]
    assert dil.concentration == pytest.approx(0.1) and dil.pure_grams == pytest.approx(1.0)


def test_woo_auto_detect_and_variations(run):
    assert run.vendor_platform["WooCo"] == "woocommerce"
    dec = offers_for(run, "WooCo", "Delta-decalactone")
    assert sorted((o.variant_title, o.price) for o in dec) == [("25g", 15.0), ("5g", 5.5)]


def test_generic_select_options(run):
    ion = offers_for(run, "GenCo", "Beta-ionone")
    assert {(o.variant_title, o.price) for o in ion} == {("4 ml", 3.10), ("50 g", 19.00)}
    four_ml = [o for o in ion if o.variant_title == "4 ml"][0]
    assert four_ml.pure_grams == pytest.approx(4 * 0.945)


def test_manual_and_errors(run):
    assert any(v.name == "Sigma" for v, _, _ in run.manual)
    assert any(e.startswith("DeadCo") for e in run.errors)


def test_best_and_basket(run, tmp_path):
    best = best_by_reagent(run.offers, REAGENTS, 4.0, "on_request")
    # 4 ml generic pack is 3.78 g -> needs 2 packs ($6.20) vs. ShopCo 5 g ($6.00) unverified
    bi = best["Beta-ionone"]
    assert bi["coa"].offer.vendor == "GenCo" and bi["coa"].packs == 2
    assert bi["coa"].cost_usd == pytest.approx(6.20)
    assert bi["any"].offer.vendor == "ShopCo" and bi["any"].cost_usd == pytest.approx(6.00)
    # damascone: 2 x 2 g ($8) beats 10 g ($15)
    bd = best["Beta-damascone"]["any"]
    assert bd.packs == 2 and bd.cost_usd == pytest.approx(8.0)
    assert best["Beta-damascone"]["coa"] is None

    settings = {"default_shipping_usd_domestic": 10}
    picks, ship, uncovered = cheapest_basket(run.offers, REAGENTS, VENDORS, 4.0, "none", settings)
    covered = {p.offer.reagent for p in picks}
    assert covered == {"Beta-ionone", "Beta-damascone", "Delta-decalactone"}
    # ShopCo covers ionone + damascone, so it's cheaper than adding GenCo's shipping
    assert set(ship) == {"ShopCo", "WooCo"}
    assert "Nutmeg essential oil" in uncovered

    basket_coa = cheapest_basket(run.offers, REAGENTS, VENDORS, 4.0, "on_request", settings)
    write_csv(tmp_path / "o.csv", run.offers)
    write_html(str(tmp_path / "r.html"), reagents=REAGENTS, vendors=VENDORS, target_g=4.0,
               min_coa="on_request", result=run, best=best, basket_coa=basket_coa,
               basket_any=(picks, ship, uncovered), fx_source="test")
    page = (tmp_path / "r.html").read_text(encoding="utf-8")
    assert "GenCo" in page and "cheaper, CoA not confirmed" in page and "DeadCo" in page
