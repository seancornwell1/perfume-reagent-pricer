"""Run every vendor x reagent search and turn products into normalized Offers."""
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .adapters import make_adapter
from .http import FetchError, Http
from .models import Offer, Product, Reagent, Vendor, coa_rank
from .units import pack_grams, parse_concentration, parse_size

_COA_RE = re.compile(r"certificate\s+of\s+analysis|\bC\.?O\.?A\.?s?\b|\bGC[\s/-]?MS\b", re.I)


@dataclass
class RunResult:
    offers: List[Offer] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    manual: List[tuple] = field(default_factory=list)       # (vendor, reagent, url)
    not_found: List[tuple] = field(default_factory=list)    # (vendor, reagent)
    vendor_platform: Dict[str, str] = field(default_factory=dict)


def build_offers(product: Product, reagent: Reagent, vendor: Vendor,
                 usd_per: Dict[str, float]) -> List[Offer]:
    coa_level, coa_evidence = vendor.coa_level, ""
    if coa_rank(coa_level) < coa_rank("mentioned") and coa_level != "none":
        m = _COA_RE.search(re.sub(r"<[^>]+>", " ", product.description or ""))
        if m:
            coa_level, coa_evidence = "mentioned", f"product page mentions '{m.group(0)}'"

    offers = []
    for v in product.variants:
        flags = []
        vt = "" if v.title.strip().lower() in ("default title", "default") else v.title
        size = parse_size(vt) or parse_size(product.title)
        grams = None
        if size:
            grams, f = pack_grams(size, reagent.density)
            flags += f
        else:
            flags.append("pack size not found")
        conc, diluted = parse_concentration(f"{product.title} {vt}")
        if diluted:
            flags.append("dilution, strength unknown" if conc is None else f"dilution ({conc:.0%})")
        pure = grams * conc if (grams is not None and conc) else None

        currency = v.currency or vendor.currency
        usd = None
        if v.price is not None:
            rate = usd_per.get(currency)
            if rate is None:
                flags.append(f"no exchange rate for {currency}")
            else:
                usd = v.price * rate
        else:
            flags.append("price not found")
        if v.available is False:
            flags.append("out of stock")

        offers.append(Offer(
            reagent=reagent.name, vendor=vendor.name, product_title=product.title,
            variant_title=vt, url=product.url, price=v.price, currency=currency,
            price_usd=usd, available=v.available, pack_grams=grams, concentration=conc,
            pure_grams=pure, coa_level=coa_level, coa_evidence=coa_evidence, flags=flags,
        ))
    return offers


def run_search(vendors: List[Vendor], reagents: List[Reagent], http: Http,
               usd_per: Dict[str, float], log: Callable[[str], None] = print) -> RunResult:
    res = RunResult()
    for vendor in vendors:
        if not vendor.enabled:
            continue
        log(f"[{vendor.name}] connecting...")
        if vendor.platform == "manual":
            res.vendor_platform[vendor.name] = "manual"
            for r in reagents:
                res.manual.append((vendor, r, vendor.search_url.replace("{q}", r.name.replace(" ", "+"))))
            log(f"[{vendor.name}] manual check (links in report)")
            continue
        try:
            adapter = make_adapter(http, vendor)
        except FetchError as e:
            res.errors.append(f"{vendor.name}: {e}")
            log(f"[{vendor.name}] FAILED: {e}")
            continue
        res.vendor_platform[vendor.name] = adapter.platform
        for r in reagents:
            try:
                products = adapter.find(r)
            except FetchError as e:
                if e.unreachable:
                    res.errors.append(f"{vendor.name}: {e}; skipped the remaining reagents")
                    log(f"[{vendor.name}] FAILED: {e}; skipping this vendor")
                    break
                res.errors.append(f"{vendor.name} / {r.name}: {e}")
                log(f"[{vendor.name}] {r.name}: FAILED: {e}")
                continue
            except Exception as e:  # a parsing surprise on one site shouldn't kill the run
                res.errors.append(f"{vendor.name} / {r.name}: unexpected {e.__class__.__name__}: {e}")
                log(f"[{vendor.name}] {r.name}: ERROR: {e}")
                continue
            n = 0
            for p in products:
                new = build_offers(p, r, vendor, usd_per)
                res.offers.extend(new)
                n += len(new)
            if not products:
                res.not_found.append((vendor.name, r.name))
            if vendor.platform == "generic" and not products:
                res.manual.append((vendor, r, vendor.search_url.replace("{q}", r.name.replace(" ", "+"))))
            log(f"[{vendor.name}] {r.name}: {len(products)} product(s), {n} size option(s)")
    return res
