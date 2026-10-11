# Perfume Reagent Pricer

Searches perfumery suppliers for the reagents you list, converts every pack size to a
price per gram of pure material, and tells you the cheapest way to get the amount you want.
It focuses on vendors that can supply a **Certificate of Analysis (CoA)**.

The output is a report in your browser plus a CSV of every size and price it found.

## Running it (Windows)

1. Install Python 3.9 or newer from <https://www.python.org/downloads/>.
   On the first installer screen, tick **"Add python.exe to PATH"**.
2. Download this repo: on GitHub, click **Code → Download ZIP** and unzip it, or `git clone` it.
3. Double-click **`run.bat`**.

The first run takes a minute while it installs its packages. A full search takes a few
minutes because it waits a second between requests to each site. The report opens in your
browser when it's done and is saved in the `results` folder.

On macOS/Linux, run `./run.sh` instead.

### Options

Add these after `run.bat` in a terminal (or after `python -m pricer`):

| Option | What it does |
|---|---|
| `--target 10` | Want 10 g of each instead of the value in `reagents.yaml` |
| `--min-coa mentioned` | Loosen the CoA requirement for recommendations (`published`, `with_order`, `on_request`, `mentioned`, `unknown`, `none`) |
| `--only-vendor "Pell Wall"` | Search just one vendor (repeatable) |
| `--only-reagent "Beta-ionone"` | Search just one reagent (repeatable) |
| `--no-open` | Don't open the browser |

## Reading the report

- **Best price per reagent**: the cheapest way to get your target amount from a vendor that
  meets the CoA requirement. "2 × 2 g" means buying two small packs beats one bigger one.
  Under it, a cheaper option from a vendor whose CoA isn't confirmed is shown when one exists.
- **Cheapest way to buy everything**: the vendor combination with the lowest total cost,
  including one estimated shipping charge per vendor. With 4 g orders, shipping usually
  costs more than the materials, so ordering everything from one or two vendors often wins.
- **All options found**: every product and size matched, with notes such as
  "converted from 4 ml at density 0.945" or "dilution (10%)".
- **Check by hand**: search links for sites that block scripts (Sigma-Aldrich, etc.).
- **Problems**: sites that couldn't be reached or read.

Diluted products ("10% in DPG") are listed but never recommended unless you set
`allow_dilutions: true` on that reagent. Out-of-stock sizes are listed but skipped.

## Certificates of Analysis

Each vendor in `vendors.yaml` has a `coa.level`. Recommendations only use vendors at or
above `settings.min_coa_level` (default `on_request`).

As of October 2026, from public sources:

| Vendor | Level | Basis |
|---|---|---|
| Sigma-Aldrich | published | Lot CoA lookup on their site |
| Molekula | with_order | States every batch ships with a CoA; batch lookup |
| PerfumersWorld | published | CoA PDFs per product, but organoleptic pass/fail, not GC assay |
| Bulkaroma | mentioned | Product pages have a COA section |
| Everyone else | unknown | Not confirmed; ask them |

Most small-pack perfumery shops don't advertise CoAs but will often send one if asked.
**When a vendor confirms**, change their `coa.level` to `on_request` (or `with_order`) and
they'll start counting. A short email works:

> Hi, I'm looking to buy small quantities (around 5 g) of beta-ionone, beta-damascone and
> delta-decalactone. Can you provide a lot-specific Certificate of Analysis (ideally with
> GC purity) with orders, either included or on request? Thanks!

For **essential oils** like nutmeg, ask for the **GC/MS report for the current lot**, not
just a spec sheet.

If a product page mentions "certificate of analysis", "COA" or "GC/MS", the report marks that
product as "CoA mentioned" even if the vendor is otherwise unknown.

## Adding reagents

Edit `reagents.yaml`. Only `name` is required, but matching is much better with CAS numbers,
synonyms, an `exclude` list for look-alike materials and a `density` for volume packs:

```yaml
  - name: Hedione
    cas: ["24851-98-7"]
    synonyms: ["methyl dihydrojasmonate", "hedione"]
    exclude: ["hc", "high cis"]
    density: 0.998
    target_grams: 10   # optional, overrides the global target_grams
```

## Adding vendors

Edit `vendors.yaml`. For most shops, `platform: auto` is enough: it detects Shopify and
WooCommerce stores, which most perfumery suppliers use, and reads their catalogs directly.
For other sites, use `platform: generic` with a `search_url` (put `{q}` where the search
text goes), or `platform: manual` to just get a link in the report.

```yaml
  - name: Some Shop
    url: https://someshop.com
    platform: auto
    country: US
    currency: USD
    shipping_usd: 8.50
    coa: {level: unknown}
```

Set `enabled: false` to skip a vendor without deleting it.

## Limits

- Prices exclude shipping and tax. Basket shipping figures are estimates you can set per
  vendor (`shipping_usd`).
- Matching is by name/CAS. It's tuned to avoid look-alikes (alpha vs beta, damascone vs
  damascenone, gamma vs delta lactones), but check the product before ordering.
- `generic` sites are read best-effort. If one shows no results, use its link under
  "Check by hand".
- Some sites may block automated requests. Those appear under "Problems".

## Development

```
pip install -r requirements.txt pytest
python -m pytest
```

Tests run the whole pipeline against canned Shopify, WooCommerce and HTML responses, so they
don't need internet access.
