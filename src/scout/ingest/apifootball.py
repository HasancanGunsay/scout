"""API-Football (api-sports.io) istemcisi - kota korumali, onbellekli.

Ucretsiz katman GUNDE 100 ISTEK. Bu yuzden istemci sunlari garanti eder:

1. ONBELLEK ONCE  - ayni endpoint+parametre kombinasyonu iki kez istenmez.
                    Yanitlar ham JSON olarak diske yazilir, kalici.
2. KOTA KORUMASI  - kalici gunluk sayac. Limit dolduysa istek ATILMAZ,
                    QuotaExhausted firlatilir (beklemez, sessizce basarisiz olmaz).
3. KURU CALISMA   - dry_run=True ile hicbir istek atmadan neyin cekilecegini gorursun.
4. SEFFAFLIK      - her istekten sonra kalan kota loglanir.

Onbellek dosyalari data/raw/apifootball/<endpoint>/<param-hash>.json
Sayac                data/raw/apifootball/_quota.json  (UTC gunune gore)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = ROOT / "data" / "raw" / "apifootball"
QUOTA_FILE = CACHE_DIR / "_quota.json"

BASE_URL = "https://v3.football.api-sports.io"


class QuotaExhausted(RuntimeError):
    """Gunluk istek kotasi doldu."""


class ApiError(RuntimeError):
    """API mantiksal hata dondurdu (HTTP 200 ama 'errors' dolu)."""


def _load_env() -> None:
    """.env dosyasini ortama yukle (python-dotenv bagimliligi olmadan)."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def _today() -> str:
    """Kota UTC gunune gore sifirlanir."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


class ApiFootball:
    def __init__(
        self,
        *,
        daily_limit: int | None = None,
        dry_run: bool = False,
        cache_dir: Path = CACHE_DIR,
        min_interval: float | None = None,
    ) -> None:
        _load_env()
        self.key = os.environ.get("API_FOOTBALL_KEY", "").strip()
        if not self.key and not dry_run:
            raise RuntimeError(
                "API_FOOTBALL_KEY bulunamadi. .env dosyasina ekle "
                "(ornek icin .env.example)."
            )
        self.daily_limit = daily_limit or int(
            os.environ.get("API_FOOTBALL_DAILY_LIMIT", "100")
        )
        self.dry_run = dry_run
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client: httpx.Client | None = None
        # Ucretsiz planda gunluk kotanin YANI SIRA dakikalik limit var (429).
        # Olculen guvenli aralik ~7sn (>=10 istek/dk siniri icin pay birakiyor).
        self.min_interval = (
            min_interval
            if min_interval is not None
            else float(os.environ.get("API_FOOTBALL_MIN_INTERVAL", "7"))
        )
        self._last_call: float = 0.0

    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    # ---------------------------------------------------------------- kota

    def _quota(self) -> dict:
        if QUOTA_FILE.exists():
            data = json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
            if data.get("date") == _today():
                return data
        return {"date": _today(), "used": 0}

    def _bump_quota(self) -> int:
        q = self._quota()
        q["used"] += 1
        QUOTA_FILE.write_text(json.dumps(q), encoding="utf-8")
        return q["used"]

    @property
    def used_today(self) -> int:
        return self._quota()["used"]

    @property
    def remaining(self) -> int:
        return max(0, self.daily_limit - self.used_today)

    # -------------------------------------------------------------- onbellek

    def _cache_path(self, endpoint: str, params: dict) -> Path:
        canon = json.dumps(params, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha1(canon.encode("utf-8")).hexdigest()[:16]
        stem = params_slug(params) or "all"
        return self.cache_dir / endpoint.strip("/") / f"{stem}_{digest}.json"

    # ---------------------------------------------------------------- istek

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        wait=wait_exponential(multiplier=4, min=8, max=120),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _http_get(self, endpoint: str, params: dict) -> dict:
        if self._client is None:
            self._client = httpx.Client(
                base_url=BASE_URL,
                headers={"x-apisports-key": self.key},
                timeout=45,
            )
        self._throttle()
        r = self._client.get(f"/{endpoint.strip('/')}", params=params)
        if r.status_code == 429:
            # Dakikalik limit - bir sonraki denemeden once daha uzun bekle
            log.warning("429 rate limit, geri cekiliyor...")
            time.sleep(30)
        r.raise_for_status()
        return r.json()

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        *,
        force: bool = False,
    ) -> dict:
        """Endpoint'i cek. Onbellekte varsa istek ATILMAZ.

        Raises
        ------
        QuotaExhausted : gunluk limit doldu ve yanit onbellekte yok
        ApiError       : API 'errors' alani dolu dondu
        """
        params = {k: v for k, v in (params or {}).items() if v is not None}
        path = self._cache_path(endpoint, params)

        if path.exists() and not force:
            log.debug("onbellek: %s", path.name)
            return json.loads(path.read_text(encoding="utf-8"))

        if self.dry_run:
            raise QuotaExhausted(
                f"[kuru calisma] istek atlandi: /{endpoint} {params}"
            )

        if self.remaining <= 0:
            raise QuotaExhausted(
                f"Gunluk kota doldu ({self.used_today}/{self.daily_limit}). "
                "00:00 UTC'de sifirlanir."
            )

        payload = self._http_get(endpoint, params)
        used = self._bump_quota()

        # API 200 dondurup iceride hata bildirebiliyor
        errors = payload.get("errors")
        if errors and errors not in ([], {}):
            raise ApiError(f"/{endpoint} {params} -> {errors}")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        log.info(
            "cekildi /%s %s -> %s sonuc | kota %s/%s",
            endpoint,
            params,
            payload.get("results"),
            used,
            self.daily_limit,
        )
        return payload

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "ApiFootball":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def params_slug(params: dict) -> str:
    """Onbellek dosya adi icin okunabilir on ek."""
    parts = [f"{k}-{v}" for k, v in sorted(params.items())]
    slug = "_".join(parts)[:60]
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in slug)
