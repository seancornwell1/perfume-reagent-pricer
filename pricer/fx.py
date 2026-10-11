from typing import Dict, Tuple

from .http import Http, FetchError


def load_rates(http: Http, fallback_usd_per: Dict[str, float]) -> Tuple[Dict[str, float], str]:
    """Return ({currency: USD per 1 unit}, source description)."""
    try:
        data = http.json("https://api.frankfurter.app/latest", params={"from": "USD"})
        rates = {"USD": 1.0}
        for cur, per_usd in data["rates"].items():
            rates[cur] = 1.0 / per_usd
        for cur, v in fallback_usd_per.items():
            rates.setdefault(cur, v)
        return rates, f"ECB rates via frankfurter.app ({data.get('date', 'today')})"
    except (FetchError, KeyError, TypeError, ValueError, ZeroDivisionError) as e:
        return dict(fallback_usd_per), f"fallback rates from vendors.yaml (live rates failed: {e})"
