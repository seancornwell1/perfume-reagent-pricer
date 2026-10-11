"""Pick the best offer per reagent and the cheapest combination of vendors."""
import math
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, List, Optional, Tuple

from .models import Offer, Reagent, Vendor, coa_rank


@dataclass
class Pick:
    offer: Offer
    packs: int
    cost_usd: float  # packs x price, before shipping

    @property
    def grams(self) -> float:
        return self.packs * self.offer.pure_grams


def usable(o: Offer, reagent: Reagent) -> bool:
    """Has a price and a size, isn't known out of stock, and isn't a dilution (unless allowed)."""
    if o.price_usd is None or not o.pure_grams or o.available is False:
        return False
    if o.is_dilution and not reagent.allow_dilutions:
        return False
    return True


def pick_for_target(o: Offer, target_g: float) -> Pick:
    packs = max(1, math.ceil(target_g / o.pure_grams - 1e-9))
    return Pick(o, packs, packs * o.price_usd)


def best_pick(offers: List[Offer], target_g: float) -> Optional[Pick]:
    picks = [pick_for_target(o, target_g) for o in offers]
    if not picks:
        return None
    # cheapest way to reach the target; ties -> less waste, then better CoA
    return min(picks, key=lambda p: (round(p.cost_usd, 2), p.grams, -coa_rank(p.offer.coa_level)))


def best_by_reagent(offers: List[Offer], reagents: List[Reagent], target_g: float,
                    min_coa: str) -> Dict[str, Dict[str, Optional[Pick]]]:
    """For each reagent: 'coa' = best among CoA-qualified vendors, 'any' = best overall."""
    out = {}
    for r in reagents:
        mine = [o for o in offers if o.reagent == r.name and usable(o, r)]
        qualified = [o for o in mine if coa_rank(o.coa_level) >= coa_rank(min_coa)]
        tg = r.target_grams or target_g
        out[r.name] = {"coa": best_pick(qualified, tg), "any": best_pick(mine, tg)}
    return out


def shipping_for(vendor: Vendor, settings: dict) -> float:
    if vendor.shipping_usd is not None:
        return float(vendor.shipping_usd)
    if vendor.country.upper() == "US":
        return float(settings.get("default_shipping_usd_domestic", 10))
    return float(settings.get("default_shipping_usd_international", 25))


def cheapest_basket(offers: List[Offer], reagents: List[Reagent], vendors: List[Vendor],
                    target_g: float, min_coa: str, settings: dict,
                    max_vendors: int = 18) -> Optional[Tuple[List[Pick], Dict[str, float], List[str]]]:
    """Cover as many reagents as possible, then minimize total cost including one
    shipping charge per vendor used. Returns (picks, shipping per vendor, uncovered reagents)."""
    by_vendor = {v.name: v for v in vendors}
    table: Dict[str, Dict[str, Pick]] = {}
    for r in reagents:
        for o in offers:
            if o.reagent != r.name or not usable(o, r) or coa_rank(o.coa_level) < coa_rank(min_coa):
                continue
            p = pick_for_target(o, r.target_grams or target_g)
            cur = table.setdefault(o.vendor, {}).get(r.name)
            if cur is None or p.cost_usd < cur.cost_usd:
                table[o.vendor][r.name] = p
    if not table:
        return None

    # keep the vendors that are cheapest for at least one reagent, plus the broadest ones
    names = sorted(table, key=lambda n: (-len(table[n]), sum(p.cost_usd for p in table[n].values())))
    names = names[:max_vendors]

    best = None
    for k in range(1, min(len(names), len(reagents)) + 1):
        for combo in combinations(names, k):
            picks, ship = {}, {}
            for r in reagents:
                cands = [table[v][r.name] for v in combo if r.name in table[v]]
                if cands:
                    picks[r.name] = min(cands, key=lambda p: p.cost_usd)
            used = {p.offer.vendor for p in picks.values()}
            if len(used) < len(combo):
                continue  # a vendor in the combo isn't used; a smaller combo covers this
            for v in used:
                ship[v] = shipping_for(by_vendor[v], settings) if v in by_vendor else 0.0
            total = sum(p.cost_usd for p in picks.values()) + sum(ship.values())
            key = (-len(picks), total)
            if best is None or key < best[0]:
                best = (key, picks, ship)
    _, picks, ship = best
    uncovered = [r.name for r in reagents if r.name not in picks]
    return [picks[r.name] for r in reagents if r.name in picks], ship, uncovered
