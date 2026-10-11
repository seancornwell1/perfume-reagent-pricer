import argparse
import os
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from .analysis import best_by_reagent, cheapest_basket
from .config import load_reagents, load_vendors
from .fx import load_rates
from .http import Http
from .models import COA_LEVELS
from .report import write_csv, write_html
from .search import run_search


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pricer", description="Find the best price for perfume reagents.")
    ap.add_argument("--reagents", default="reagents.yaml")
    ap.add_argument("--vendors", default="vendors.yaml")
    ap.add_argument("--target", type=float, help="grams of pure material wanted (overrides reagents.yaml)")
    ap.add_argument("--min-coa", choices=COA_LEVELS, help="minimum CoA level for recommendations")
    ap.add_argument("--only-vendor", action="append", default=[], help="search only this vendor (repeatable)")
    ap.add_argument("--only-reagent", action="append", default=[], help="search only this reagent (repeatable)")
    ap.add_argument("--out", default="results", help="output folder")
    ap.add_argument("--no-open", action="store_true", help="don't open the report in a browser")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # Windows consoles can't print every character

    target, reagents = load_reagents(args.reagents)
    settings, vendors = load_vendors(args.vendors)
    target = args.target or target
    min_coa = args.min_coa or settings.get("min_coa_level", "on_request")

    if args.only_vendor:
        wanted = {n.lower() for n in args.only_vendor}
        vendors = [v for v in vendors if v.name.lower() in wanted]
    if args.only_reagent:
        wanted = {n.lower() for n in args.only_reagent}
        reagents = [r for r in reagents if r.name.lower() in wanted]
    if not vendors or not reagents:
        print("Nothing to search (check --only-vendor / --only-reagent spelling).", file=sys.stderr)
        return 2

    http = Http(delay=float(settings.get("request_delay_seconds", 1.0)))
    rates, fx_source = load_rates(http, settings.get("fallback_usd_per") or {"USD": 1.0})
    print(f"Exchange rates: {fx_source}")
    print(f"Searching {len(vendors)} vendor(s) for {len(reagents)} reagent(s), target {target:g} g each...\n")

    result = run_search(vendors, reagents, http, rates)
    best = best_by_reagent(result.offers, reagents, target, min_coa)
    basket_coa = cheapest_basket(result.offers, reagents, vendors, target, min_coa, settings)
    basket_any = cheapest_basket(result.offers, reagents, vendors, target, "none", settings)

    os.makedirs(args.out, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    csv_path = os.path.join(args.out, f"offers_{stamp}.csv")
    html_path = os.path.join(args.out, f"report_{stamp}.html")
    write_csv(csv_path, result.offers)
    write_html(html_path, reagents=reagents, vendors=vendors, target_g=target, min_coa=min_coa,
               result=result, best=best, basket_coa=basket_coa, basket_any=basket_any, fx_source=fx_source)

    print("\nBest price per reagent (CoA-qualified):")
    for r in reagents:
        p = best[r.name]["coa"]
        if p:
            o = p.offer
            print(f"  {r.name:<24} ${p.cost_usd:>8.2f}  {o.vendor} - {p.packs} x {o.variant_title or o.product_title}")
        else:
            print(f"  {r.name:<24} {'—':>9}  none found (see report for unverified vendors)")
    print(f"\n{len(result.offers)} size options found; {len(result.errors)} problem(s).")
    print(f"Report: {os.path.abspath(html_path)}")
    print(f"CSV:    {os.path.abspath(csv_path)}")
    if not args.no_open:
        webbrowser.open(Path(html_path).resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
