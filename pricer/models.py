from dataclasses import dataclass, field
from typing import List, Optional

COA_LEVELS = ["none", "unknown", "mentioned", "on_request", "with_order", "published"]


def coa_rank(level: str) -> int:
    return COA_LEVELS.index(level) if level in COA_LEVELS else COA_LEVELS.index("unknown")


@dataclass
class Reagent:
    name: str
    cas: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    density: Optional[float] = None
    allow_dilutions: bool = False
    target_grams: Optional[float] = None  # overrides the global target

    @property
    def search_terms(self) -> List[str]:
        terms = [self.name] + list(self.cas) + list(self.synonyms)
        seen, out = set(), []
        for t in terms:
            if t.lower() not in seen:
                seen.add(t.lower())
                out.append(t)
        return out


@dataclass
class Vendor:
    name: str
    url: str
    platform: str = "auto"
    country: str = "US"
    currency: str = "USD"
    coa_level: str = "unknown"
    coa_note: str = ""
    coa_source: str = ""
    search_url: str = ""
    product_link_pattern: str = ""
    shipping_usd: Optional[float] = None
    enabled: bool = True

    @property
    def base(self) -> str:
        return self.url.rstrip("/")


@dataclass
class Product:
    """A product page as returned by an adapter, before size/price analysis."""
    title: str
    url: str
    variants: List["Variant"]
    description: str = ""  # plain text or HTML, scanned for CoA mentions


@dataclass
class Variant:
    title: str
    price: Optional[float]  # in vendor currency, per pack (or per unit_size for per-gram pricing)
    available: Optional[bool] = None
    currency: Optional[str] = None


@dataclass
class Offer:
    reagent: str
    vendor: str
    product_title: str
    variant_title: str
    url: str
    price: Optional[float]
    currency: str
    price_usd: Optional[float]
    available: Optional[bool]
    pack_grams: Optional[float]       # grams of product in the pack
    concentration: Optional[float]    # 1.0 = neat; None = diluted, strength unknown
    pure_grams: Optional[float]       # grams of the actual material
    coa_level: str
    coa_evidence: str = ""
    flags: List[str] = field(default_factory=list)

    @property
    def usd_per_pure_gram(self) -> Optional[float]:
        if self.price_usd is None or not self.pure_grams:
            return None
        return self.price_usd / self.pure_grams

    @property
    def is_dilution(self) -> bool:
        return self.concentration is None or self.concentration < 1.0
