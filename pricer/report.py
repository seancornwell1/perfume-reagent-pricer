import csv
import html
from datetime import datetime
from typing import Dict, List, Optional

from .analysis import Pick
from .models import Offer, Reagent, Vendor, coa_rank
from .search import RunResult

CSV_FIELDS = ["reagent", "vendor", "product", "size_option", "price", "currency", "price_usd",
              "in_stock", "pack_grams", "concentration", "pure_grams", "usd_per_gram",
              "coa_level", "coa_evidence", "flags", "url"]


def _fmt(x: Optional[float], nd=2) -> str:
    return "" if x is None else f"{x:.{nd}f}"


def write_csv(path: str, offers: List[Offer]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_FIELDS)
        for o in offers:
            w.writerow([o.reagent, o.vendor, o.product_title, o.variant_title, _fmt(o.price),
                        o.currency, _fmt(o.price_usd), {True: "yes", False: "no"}.get(o.available, "?"),
                        _fmt(o.pack_grams), _fmt(o.concentration), _fmt(o.pure_grams),
                        _fmt(o.usd_per_pure_gram, 3), o.coa_level, o.coa_evidence,
                        "; ".join(o.flags), o.url])


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _money(x: Optional[float]) -> str:
    return "—" if x is None else f"${x:,.2f}"


_COA_LABEL = {
    "published": "Lot CoA published", "with_order": "CoA with every order",
    "on_request": "CoA on request", "mentioned": "CoA mentioned (unverified)",
    "unknown": "CoA unknown", "none": "No CoA",
}


def _coa_badge(level: str) -> str:
    cls = "good" if coa_rank(level) >= coa_rank("on_request") else ("warn" if level == "mentioned" else "bad")
    return f'<span class="badge {cls}">{_e(_COA_LABEL.get(level, level))}</span>'


def _pick_cells(p: Optional[Pick]) -> str:
    if p is None:
        return '<td colspan="5" class="muted">no qualifying offer found</td>'
    o = p.offer
    size = o.variant_title or o.product_title
    qty = f"{p.packs} × " if p.packs > 1 else ""
    return (f'<td><a href="{_e(o.url)}" target="_blank" rel="noopener">{_e(o.vendor)}</a><br>'
            f'<span class="muted">{_e(o.product_title)}</span></td>'
            f"<td>{qty}{_e(size)}<br><span class=\"muted\">{_fmt(p.grams, 1)} g total</span></td>"
            f"<td class=\"num\"><b>{_money(p.cost_usd)}</b></td>"
            f"<td class=\"num\">{_money(o.usd_per_pure_gram)}/g</td>"
            f"<td>{_coa_badge(o.coa_level)}</td>")


def write_html(path: str, *, reagents: List[Reagent], vendors: List[Vendor], target_g: float,
               min_coa: str, result: RunResult, best: Dict[str, Dict[str, Optional[Pick]]],
               basket_coa, basket_any, fx_source: str):
    vend = {v.name: v for v in vendors}
    rows = []
    for r in reagents:
        b = best[r.name]
        cheaper = ""
        if b["any"] and (b["coa"] is None or b["any"].cost_usd < b["coa"].cost_usd - 0.005) \
                and (b["coa"] is None or b["any"].offer is not b["coa"].offer):
            cheaper = (f'<tr class="alt"><td class="muted">↳ cheaper, CoA not confirmed</td>'
                       f'{_pick_cells(b["any"])}</tr>')
        cls = ' class="has-alt"' if cheaper else ""
        rows.append(f"<tr{cls}><td><b>{_e(r.name)}</b></td>{_pick_cells(b['coa'])}</tr>{cheaper}")

    def basket_html(b, title):
        if not b:
            return f"<h3>{title}</h3><p class='muted'>No qualifying offers.</p>"
        picks, ship, uncovered = b
        items = "".join(
            f"<tr><td>{_e(p.offer.reagent)}</td><td>{_e(p.offer.vendor)}</td>"
            f"<td>{p.packs} × {_e(p.offer.variant_title or p.offer.product_title)}</td>"
            f"<td class='num'>{_money(p.cost_usd)}</td></tr>" for p in picks)
        ships = "".join(f"<tr class='muted'><td>Shipping (est.)</td><td>{_e(v)}</td><td></td>"
                        f"<td class='num'>{_money(c)}</td></tr>" for v, c in ship.items())
        total = sum(p.cost_usd for p in picks) + sum(ship.values())
        miss = f"<p class='bad-text'>Not covered: {_e(', '.join(uncovered))}</p>" if uncovered else ""
        return (f"<h3>{title}</h3><table><tr><th>Reagent</th><th>Vendor</th><th>Buy</th><th>Cost</th></tr>"
                f"{items}{ships}<tr><td colspan='3'><b>Total</b></td><td class='num'><b>{_money(total)}</b></td></tr>"
                f"</table>{miss}")

    detail = []
    for r in reagents:
        mine = sorted([o for o in result.offers if o.reagent == r.name],
                      key=lambda o: (o.usd_per_pure_gram is None, o.usd_per_pure_gram or 0))
        trs = "".join(
            f"<tr><td><a href='{_e(o.url)}' target='_blank' rel='noopener'>{_e(o.vendor)}</a></td>"
            f"<td>{_e(o.product_title)}</td><td>{_e(o.variant_title)}</td>"
            f"<td class='num'>{_e(_fmt(o.price))} {_e(o.currency)}</td><td class='num'>{_money(o.price_usd)}</td>"
            f"<td class='num'>{_fmt(o.pure_grams, 1)}</td><td class='num'>{_money(o.usd_per_pure_gram)}</td>"
            f"<td>{_coa_badge(o.coa_level)}</td><td class='muted'>{_e('; '.join(o.flags + ([o.coa_evidence] if o.coa_evidence else [])))}</td></tr>"
            for o in mine)
        detail.append(
            f"<details><summary>{_e(r.name)} — {len(mine)} option(s)</summary>"
            f"<table><tr><th>Vendor</th><th>Product</th><th>Size</th><th>Price</th><th>USD</th>"
            f"<th>Pure g</th><th>$/g</th><th>CoA</th><th>Notes</th></tr>{trs}</table></details>")

    manual = "".join(f"<li><b>{_e(v.name)}</b> ({_coa_badge(v.coa_level)}): "
                     f"<a href='{_e(u)}' target='_blank' rel='noopener'>{_e(r.name)}</a></li>"
                     for v, r, u in result.manual)
    errors = "".join(f"<li>{_e(e)}</li>" for e in result.errors)
    vendor_rows = "".join(
        f"<tr><td><a href='{_e(v.url)}' target='_blank' rel='noopener'>{_e(v.name)}</a></td><td>{_e(v.country)}</td>"
        f"<td>{_e(result.vendor_platform.get(v.name, 'not reached'))}</td><td>{_coa_badge(v.coa_level)}</td>"
        f"<td class='muted'>{_e(v.coa_note)}"
        + (f" <a href='{_e(v.coa_source)}' target='_blank' rel='noopener'>source</a>" if v.coa_source else "")
        + "</td></tr>" for v in vendors if v.enabled)

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Reagent Price Report</title>
<style>
:root{{--bg:#fbfaf8;--fg:#1d1b18;--muted:#6b665f;--line:#e4e0d9;--card:#fff;--good:#1f7a4a;--warn:#9a6a00;--bad:#9b2c2c;--link:#2c5d9b}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16150f;--fg:#ece8e1;--muted:#a39d93;--line:#34312b;--card:#1f1d18;--good:#5cc28d;--warn:#e0b04a;--bad:#e58585;--link:#8db7ec}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;margin:0;padding:24px 16px;}}
main{{max-width:1100px;margin:0 auto}} a{{color:var(--link)}} h1{{margin:0 0 4px}}
table{{border-collapse:collapse;width:100%;background:var(--card);margin:8px 0 20px}}
th,td{{border-bottom:1px solid var(--line);padding:7px 8px;text-align:left;vertical-align:top}}
th{{font-size:13px;color:var(--muted);font-weight:600}} .num{{text-align:right;white-space:nowrap}}
.muted{{color:var(--muted);font-size:13px}} tr.has-alt td{{border-bottom:none}} tr.alt td{{padding-top:0;opacity:.85}}
.badge{{font-size:12px;padding:2px 7px;border-radius:10px;border:1px solid currentColor;white-space:nowrap}}
.good{{color:var(--good)}} .warn{{color:var(--warn)}} .bad{{color:var(--bad)}} .bad-text{{color:var(--bad)}}
details{{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px 12px;margin:8px 0}}
summary{{cursor:pointer;font-weight:600}} .wrap{{overflow-x:auto}} li,p{{overflow-wrap:anywhere}}
.note{{background:var(--card);border-left:3px solid var(--warn);padding:8px 12px;margin:12px 0}}
</style></head><body><main>
<h1>Reagent price report</h1>
<p class="muted">{_e(datetime.now().strftime('%Y-%m-%d %H:%M'))} · target {target_g:g} g of pure material per reagent ·
recommendations require CoA level ≥ “{_e(_COA_LABEL.get(min_coa, min_coa))}” · {_e(fx_source)}</p>
<div class="note">Prices are product prices only. Shipping in the basket is an estimate from vendors.yaml.
Check the matched product before buying, especially grade, isomer and natural vs synthetic.</div>

<h2>Best price per reagent</h2>
<div class="wrap"><table><tr><th>Reagent</th><th>Vendor</th><th>Buy</th><th>Cost</th><th>$/g</th><th>CoA</th></tr>
{''.join(rows)}</table></div>

<h2>Cheapest way to buy everything</h2>
<p class="muted">Covers as many reagents as possible, then minimizes product + one shipping charge per vendor.</p>
<div class="wrap">{basket_html(basket_coa, "CoA-qualified vendors")}{basket_html(basket_any, "Any vendor (CoA not required)")}</div>

<h2>All options found</h2>
<div class="wrap">{''.join(detail)}</div>

<h2>Check by hand</h2>
<p class="muted">These sites block scripts or need a manual look.</p><ul>{manual or '<li class="muted">none</li>'}</ul>

<h2>Vendors</h2><div class="wrap"><table><tr><th>Vendor</th><th>Country</th><th>Read as</th><th>CoA</th><th>Notes</th></tr>{vendor_rows}</table></div>

<h2>Problems</h2><ul>{errors or '<li class="muted">none</li>'}</ul>
</main></body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
