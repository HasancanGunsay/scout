"""Toplama tamamlanmışlık mantığı testleri.

NEDEN ONEMLI: toplama 34 gune yayiliyor, yani her gun en az bir lig YARIM.
Yarim ligde percentile hesaplamak yanilticidir - ustelik takim takim
topladigimiz icin ornek rastgele degil KUMELI (5/28 takim = 5 TAM takim),
yani sapma var. Sistem bunu kullaniciya soylemek zorunda.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest


def _state(tmp_path, leagues: dict) -> None:
    (tmp_path / "_ingest_state.json").write_text(
        json.dumps({"leagues": leagues}), encoding="utf-8"
    )


class TestCollectionStatus:
    def test_tam_ve_yarim_ayirt_edilir(self, tmp_path, monkeypatch):
        import scripts.build_db as bd

        _state(tmp_path, {
            "72:2024": {"complete": True, "team_ids": [1, 2, 3],
                        "teams": {"1": {"done": True}, "2": {"done": True},
                                  "3": {"done": True}}},
            "128:2024": {"complete": False, "team_ids": list(range(28)),
                         "teams": {str(i): {"done": True} for i in range(16)}},
        })
        monkeypatch.setattr(bd, "STATE", tmp_path / "_ingest_state.json")
        s = bd.collection_status().set_index("league_id")

        assert s.loc[72, "league_complete"] is True or s.loc[72, "league_complete"]
        assert not s.loc[128, "league_complete"]
        assert s.loc[128, "collection_pct"] == pytest.approx(57.1, abs=0.2)
        assert s.loc[128, "teams_done"] == 16
        assert s.loc[128, "teams_total"] == 28

    def test_durum_dosyasi_yoksa_bos_tablo(self, tmp_path, monkeypatch):
        import scripts.build_db as bd

        monkeypatch.setattr(bd, "STATE", tmp_path / "yok.json")
        s = bd.collection_status()
        assert s.empty
        assert "league_complete" in s.columns


class TestLatestTmDb:
    """30 Eki 2026'dan beri build_db, klasordeki EN YENI surumu degil
    config/kaynaklar.yaml'da SABITLENEN surumu kullanir (FAZ 9.1): en yeni
    secimi, yeni bir surum indirildigi gun zinciri iki surume bolerdi."""

    @staticmethod
    def _kur(tmp_path, monkeypatch, klasorler, sabit):
        import scout.kaynaklar as K

        base = tmp_path / "data" / "raw" / "transfermarkt"
        for d, dosyali in klasorler:
            (base / d).mkdir(parents=True)
            if dosyali:
                (base / d / "transfermarkt-datasets.duckdb").write_bytes(b"x")
        ayar = tmp_path / "kaynaklar.yaml"
        ayar.write_text("\n".join(["transfermarkt:", f'  anlik_goruntu: "{sabit}"', ""]),
                        encoding="utf-8")
        monkeypatch.setattr(K, "TM_DIZIN", base)
        monkeypatch.setattr(K, "AYAR", ayar)

    def test_sabitlenen_surum_secilir_daha_yenisi_degil(self, tmp_path, monkeypatch):
        import scripts.build_db as bd

        self._kur(tmp_path, monkeypatch, [("2026-06-01", True), ("2026-07-11", True),
                                          ("2026-08-02", True)], "2026-07-11")
        assert bd.latest_tm_db().parent.name == "2026-07-11"

    def test_dosyasiz_dizin_sayilmaz(self, tmp_path, monkeypatch):
        import scripts.build_db as bd

        self._kur(tmp_path, monkeypatch, [("2026-09-01", False), ("2026-07-11", True)],
                  "en_yeni")
        assert bd.latest_tm_db().parent.name == "2026-07-11"

    def test_sabit_surum_yoksa_none(self, tmp_path, monkeypatch):
        import scripts.build_db as bd

        self._kur(tmp_path, monkeypatch, [("2026-07-11", True)], "2026-09-05")
        assert bd.latest_tm_db() is None


class TestIncompleteFilter:
    def test_yarim_ligler_tespit_edilir(self):
        """Arayuz bu listeye gore ligleri gizler."""
        df = pd.DataFrame({
            "player_id": [1, 2, 3, 4],
            "league_id": [72, 72, 128, 128],
            "country": ["Brazil", "Brazil", "Argentina", "Argentina"],
            "league_name": ["Serie B", "Serie B", "Liga Prof", "Liga Prof"],
            "season": [2024] * 4,
            "league_complete": [True, True, False, False],
            "collection_pct": [100.0, 100.0, 57.0, 57.0],
            "teams_done": [20, 20, 16, 16],
            "teams_total": [20, 20, 28, 28],
        })
        complete_ids = set(df.loc[df.league_complete, "league_id"])
        assert complete_ids == {72}
        assert set(df[~df.league_id.isin(complete_ids)].league_id) == {128}
