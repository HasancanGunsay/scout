"""Mevki siralama tablosu testleri (FAZ 6.3)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_ranking import guven_etiketi  # noqa: E402


def test_kaleci_her_zaman_dusuk_guven():
    """Kaleci n=210 (§60): ayri model yok, model ~ dakika+yas (+0,003)."""
    for v in (0, 1):
        for b in ("1 <0,5M", "3 2-5M", "4 >=5M"):
            assert guven_etiketi("Goalkeeper", v, b) == "dusuk"


def test_degerleme_yok_dogrulanmamis():
    """TM kor grup: 895 oyuncuda 12 olumlu (CV); tek pencere isareti (§45.3)."""
    assert guven_etiketi("Defender", 0, "0 yok") == "dogrulanmamis"


def test_ara_bant_zayif():
    """0,5-5M: model ~ dakika+yas (model-basit -0,001/+0,010; §45.2)."""
    for b in ("2 0,5-2M", "3 2-5M"):
        assert guven_etiketi("Midfielder", 1, b) == "zayif"


def test_en_ucuz_bant_artik_zayif():
    """§60: eslesme duzeltmesinden sonra <0,5M'de model - dakika+yas CV'de
    anlamli degil (+0,033 [-0,02, +0,10]; once +0,082*). Olcut ayni."""
    assert guven_etiketi("Attacker", 1, "1 <0,5M") == "zayif"


def test_pahali_bant_iyi():
    """>=5M: model - dakika+yas CV +0,056* / kayan +0,094* (§60)."""
    assert guven_etiketi("Attacker", 1, "4 >=5M") == "iyi"


def test_oncelik_en_kotumser_kazanir():
    """Kaleci + degerleme yok -> 'dusuk' (en kotumser)."""
    assert guven_etiketi("Goalkeeper", 0, "0 yok") == "dusuk"
    assert guven_etiketi("Defender", 0, "2 0,5-2M") == "dogrulanmamis"
