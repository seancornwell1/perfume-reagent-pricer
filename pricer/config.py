from typing import List, Tuple

import yaml

from .models import COA_LEVELS, Reagent, Vendor

PLATFORMS = {"auto", "shopify", "woocommerce", "generic", "manual"}


def load_reagents(path: str) -> Tuple[float, List[Reagent]]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    target = float(data.get("target_grams", 4))
    reagents = []
    for r in data.get("reagents") or []:
        if isinstance(r, str):
            r = {"name": r}
        reagents.append(Reagent(
            name=r["name"],
            cas=[str(c) for c in r.get("cas") or []],
            synonyms=[str(s) for s in r.get("synonyms") or []],
            exclude=[str(s) for s in r.get("exclude") or []],
            density=r.get("density"),
            allow_dilutions=bool(r.get("allow_dilutions", False)),
            target_grams=float(r["target_grams"]) if r.get("target_grams") else None,
        ))
    if not reagents:
        raise ValueError(f"{path}: no reagents listed")
    return target, reagents


def load_vendors(path: str) -> Tuple[dict, List[Vendor]]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    settings = data.get("settings") or {}
    vendors = []
    for v in data.get("vendors") or []:
        coa = v.get("coa") or {}
        level = coa.get("level", "unknown")
        if level not in COA_LEVELS:
            raise ValueError(f"{path}: vendor {v.get('name')}: unknown coa level '{level}' "
                             f"(use one of {', '.join(COA_LEVELS)})")
        platform = v.get("platform", "auto")
        if platform not in PLATFORMS:
            raise ValueError(f"{path}: vendor {v.get('name')}: unknown platform '{platform}'")
        if platform in ("generic", "manual") and not v.get("search_url"):
            raise ValueError(f"{path}: vendor {v.get('name')}: platform {platform} needs search_url")
        vendors.append(Vendor(
            name=v["name"], url=v["url"], platform=platform,
            country=v.get("country", "US"), currency=v.get("currency", "USD"),
            coa_level=level, coa_note=coa.get("note", ""), coa_source=coa.get("source", ""),
            search_url=v.get("search_url", ""), product_link_pattern=v.get("product_link_pattern", ""),
            shipping_usd=v.get("shipping_usd"), enabled=v.get("enabled", True),
        ))
    return settings, vendors
