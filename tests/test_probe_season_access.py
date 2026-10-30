"""Sezon erisim sondasi sonucunu dosyaya yazar ve gunluk modda tazeyse istek harcamaz.

30 Eki 2026'da bulundu: yazma satirlari `return 0`'in arkasinda kalmisti,
dosya hic guncellenmiyordu ve gunluk zincir her gun 2 istek yakiyordu.
"""
import datetime as dt
import json
import sys

import scripts.probe_season_access as ps


class _SahteApi:
    """Her sezonu reddeden, kac istek yapildigini sayan sahte istemci."""
    cagri = 0

    def __init__(self):
        self.used_today, self.daily_limit, self.remaining = 0, 100, 100

    def get(self, *_a, **_k):
        _SahteApi.cagri += 1
        return {"errors": {"plan": "Free plans do not have access"}, "response": []}


def _calistir(monkeypatch, tmp_path, argv):
    sonuc = tmp_path / "season_access.json"
    monkeypatch.setattr(ps, "SONUC", sonuc)
    monkeypatch.setattr(ps, "ApiFootball", _SahteApi)
    monkeypatch.setattr(sys, "argv", ["probe"] + argv)
    _SahteApi.cagri = 0
    assert ps.main() == 0
    return sonuc


def test_sonuc_dosyasi_yazilir(monkeypatch, tmp_path):
    sonuc = _calistir(monkeypatch, tmp_path, [])
    d = json.loads(sonuc.read_text(encoding="utf-8"))
    assert d["tarih"] == dt.date.today().isoformat()
    assert d["denenen"] == [2025, 2026] and d["acik"] == []
    assert _SahteApi.cagri == 2


def test_gunluk_modda_tazeyse_istek_yok(monkeypatch, tmp_path):
    sonuc = _calistir(monkeypatch, tmp_path, [])            # dosyayi bugunle yazar
    assert sonuc.exists()
    _calistir(monkeypatch, tmp_path, ["--gunluk"])
    assert _SahteApi.cagri == 0


def test_gunluk_modda_bayatsa_yeniden_sinar(monkeypatch, tmp_path):
    sonuc = tmp_path / "season_access.json"
    eski = (dt.date.today() - dt.timedelta(days=ps.TAZELIK_GUN + 1)).isoformat()
    sonuc.write_text(json.dumps({"tarih": eski, "denenen": [2025], "acik": []}),
                     encoding="utf-8")
    _calistir(monkeypatch, tmp_path, ["--gunluk"])
    assert _SahteApi.cagri == 2
    assert json.loads(sonuc.read_text(encoding="utf-8"))["tarih"] == dt.date.today().isoformat()
