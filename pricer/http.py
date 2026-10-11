import time
from typing import Dict, Optional
from urllib.parse import urlparse

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class FetchError(Exception):
    unreachable = False  # True when the site itself couldn't be reached (not just a 404)


class Http:
    """requests.Session with a per-host delay and small retry, so we stay polite."""

    def __init__(self, delay: float = 1.0, timeout: float = 25.0):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
        self.delay = delay
        self.timeout = timeout
        self._last: Dict[str, float] = {}

    def _wait(self, url: str):
        host = urlparse(url).netloc
        last = self._last.get(host)
        if last is not None:
            gap = time.monotonic() - last
            if gap < self.delay:
                time.sleep(self.delay - gap)
        self._last[host] = time.monotonic()

    def get(self, url: str, params: Optional[dict] = None, accept: str = "*/*") -> requests.Response:
        err = None
        for attempt in range(2):
            self._wait(url)
            try:
                r = self.s.get(url, params=params, timeout=self.timeout, headers={"Accept": accept})
            except (requests.ConnectionError, requests.Timeout) as e:
                kind = "timed out" if isinstance(e, requests.Timeout) else "could not connect"
                err = FetchError(f"{urlparse(url).netloc}: {kind} ({e.__class__.__name__})")
                err.unreachable = True
                continue
            except requests.RequestException as e:
                err = FetchError(f"{url}: {e.__class__.__name__}: {e}")
                continue
            if r.status_code == 429 or r.status_code >= 500:
                err = FetchError(f"{url}: HTTP {r.status_code}")
                time.sleep(3 * (attempt + 1))
                continue
            if r.status_code >= 400:
                raise FetchError(f"{r.url}: HTTP {r.status_code}")
            return r
        raise err

    def json(self, url: str, params: Optional[dict] = None):
        r = self.get(url, params=params, accept="application/json")
        try:
            return r.json()
        except ValueError:
            raise FetchError(f"{r.url}: expected JSON, got {r.headers.get('content-type', '?')}")

    def text(self, url: str, params: Optional[dict] = None) -> str:
        return self.get(url, params=params, accept="text/html,application/xhtml+xml").text
