# Gunluk otomatik calisma - Windows Gorev Zamanlayici bunu cagirir.
#
# 1) Kotanin izin verdigi kadar oyuncu verisi ceker (kaldigi yerden devam eder)
# 2) Tabloyu, ozellikleri, eslesmeleri ve skorlari yeniden uretir
#
# Tetikleyiciler: her gun 08:00 + oturum acildiginda (+3 dk).
# Kota 00:00 UTC'de (yerel 03:00) sifirlanir; gun icinde saat farketmez.
#
# DAYANIKLILIK (27 Tem 2026'da ogrenildi)
#   Ilk surum adimlarin cikis kodunu KONTROL ETMIYORDU. build_links.py
#   "Fatal Python error: PyEval_SaveThread ... GIL" ile coktu, script hic
#   sesini cikarmadan sonraki adima gecti ve build_scores hic calismadi.
#   Kimse fark etmedi. Simdi her adim kontrol ediliyor, hata bir kez
#   yeniden deneniyor ve loga BASARISIZ olarak yaziliyor.
#
#   Ayrica native kutuphane (numpy/scipy/sklearn) OpenMP cakismasini
#   azaltmak icin is parcaci sayisi 1'e sabitleniyor - bu veri boyutunda
#   hiz kaybi yok, kararlilik kazanci var.
#
# AG BEKLEME (1-2 Agu 2026'da ogrenildi)
#   Gorev internet yokken calisti, iki deneme sonrasi pes etti ve o gunun
#   100 istegi yandi. Artik once ag bekleniyor (en fazla 4 saat). Kota gun
#   icinde saat farketmeksizin gecerli oldugu icin beklemenin maliyeti yok.
#
# Log: data/raw/daily_log.txt (son 2000 satir tutulur)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$log = Join-Path $root "data\raw\daily_log.txt"

# Native kutuphane cakismasini azalt
$env:OMP_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"
$env:KMP_DUPLICATE_LIB_OK = "TRUE"
# Cikti kodlamasi: gorev zamanlayici altinda cp1254 oluyor ve Hirvat/Polonya
# isimleri tum zinciri UnicodeEncodeError ile kiriyordu (19 Agu 2026).
$env:PYTHONIOENCODING = "utf-8"

function Write-Log {
    param([string]$msg)
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg" |
        Out-File -FilePath $log -Append -Encoding utf8
}

function Invoke-Step {
    <#  Bir adimi calistir, cikis kodunu kontrol et, hata varsa bir kez tekrar dene.
        Doner: $true basarili, $false basarisiz. #>
    param([string]$script, [string[]]$ekArg = @())

    foreach ($attempt in 1, 2) {
        $tag = if ($attempt -eq 1) { $script } else { "$script (2. deneme)" }
        Write-Log "--- $tag $($ekArg -join ' ') ---"
        & $py (Join-Path $root "scripts\$script") @ekArg 2>&1 | ForEach-Object { Write-Log $_ }
        $code = $LASTEXITCODE
        if ($code -eq 0) {
            Write-Log "OK: $script"
            return $true
        }
        Write-Log "BASARISIZ: $script (cikis kodu $code)"
        if ($attempt -eq 1) { Start-Sleep -Seconds 10 }
    }
    return $false
}

function Test-Internet {
    <#  API sunucusunun adi cozulebiliyor mu?
        1 Agu 2026'daki hata tam olarak buydu: "getaddrinfo failed". #>
    try { return ([System.Net.Dns]::GetHostAddresses("v3.football.api-sports.io")).Count -gt 0 }
    catch { return $false }
}

function Wait-Internet {
    <#  Internet yoksa bekle.

        NEDEN (1-2 Agu 2026'da ogrenildi): gorev 07:26 ve 08:00'de calisti,
        ikisinde de internet yoktu, iki deneme sonrasi pes etti ve O GUNUN
        100 ISTEGI YANDI. Kota gun icinde saat farketmeksizin gecerli
        oldugu icin beklemek bedava - kaybedilen tek sey birkac saat.
        1 Agustos'un kotasi kalici olarak kayboldu, geri gelmiyor. #>
    param([int]$MaxDakika = 240, [int]$AralikSaniye = 600)

    if (Test-Internet) { return $true }
    Write-Log "AG YOK - internet bekleniyor (en fazla $MaxDakika dk, $($AralikSaniye/60) dk arayla)"
    $bitis = (Get-Date).AddMinutes($MaxDakika)
    while ((Get-Date) -lt $bitis) {
        Start-Sleep -Seconds $AralikSaniye
        if (Test-Internet) {
            $gecen = [int]((Get-Date) - $bitis.AddMinutes(-$MaxDakika)).TotalMinutes
            Write-Log "AG GELDI ($gecen dk sonra) - veri cekimine geciliyor"
            return $true
        }
    }
    Write-Log "AG YOK - $MaxDakika dk beklendi, veri cekimi atlaniyor"
    return $false
}

function Wait-KotaSifirlama {
    <#  Kota dolu ama sifirlanmasina az kaldiysa bekle.

        NEDEN (30 Agu 2026'da ogrenildi): gorev bilgisayar acilinca 02:59:13'te
        calisti. Kota 00:00 UTC'de (yerel 03:00) sifirlaniyor - yani 47 SANIYE
        sonra. Script "kota 100/100, kalan 0" gordu, sezon sondasini atladi,
        sifir istek cekti ve o gun bir daha calismadi. Bir gunluk toplama
        47 saniyeye kurban gitti.

        Kota gun icinde saat farketmeksizin gecerli oldugu icin beklemek
        bedava - Wait-Internet ile ayni mantik. #>
    param([int]$EnFazlaDakika = 45)

    $kf = Join-Path $root "data\raw\apifootball\_quota.json"
    if (-not (Test-Path $kf)) { return }
    try { $q = Get-Content $kf -Raw -Encoding utf8 | ConvertFrom-Json } catch { return }

    $limit = 100
    if ($env:API_FOOTBALL_DAILY_LIMIT) { $limit = [int]$env:API_FOOTBALL_DAILY_LIMIT }

    $simdiUtc = (Get-Date).ToUniversalTime()
    # Sayac baska bir UTC gunune aitse kota zaten tazedir.
    if ($q.date -ne $simdiUtc.ToString("yyyy-MM-dd")) { return }
    if ([int]$q.used -lt $limit) { return }

    $kalanDk = ($simdiUtc.Date.AddDays(1) - $simdiUtc).TotalMinutes
    if ($kalanDk -gt $EnFazlaDakika) { return }   # cok uzak, beklemeye degmez

    Write-Log ("KOTA DOLU ama sifirlanmasina {0:N1} dk kaldi - bekleniyor" -f $kalanDk)
    Start-Sleep -Seconds ([int]([Math]::Ceiling($kalanDk * 60)) + 30)
    Write-Log "kota sifirlandi - toplamaya devam"
}

Write-Log "=== gunluk calisma basladi ==="

# Kota sinirinda mi? (bkz. Wait-KotaSifirlama - 30 Agu 2026)
Wait-KotaSifirlama

if (-not (Test-Path $py)) {
    Write-Log "BASARISIZ: python bulunamadi: $py"
    exit 1
}

# 0) Yeni sezon acilmis mi? (2 istek, 30 gunde bir)
#    Ucretsiz plan penceresi "2022-2024" olarak olculmustu (26 Tem 2026,
#    API mesaji: "Free plans do not have access to this season"). Pencereler
#    takvim ilerledikce kayabilir - varsaymak yerine periyodik sinaniyor.
#    2025 acilirsa sistem GUNCEL sezonu gorebilir; bu niteliksel bir fark.
if (Wait-Internet) {
    & $py (Join-Path $root "scripts\probe_season_access.py") --gunluk 2>&1 |
        Where-Object { $_ -match "sezon|ACIK|REDDEDILDI|Kota" } |
        ForEach-Object { Write-Log "  $_" }
}

# 1) veri cek - basarisiz olsa bile build adimlari yine calissin
#    (onceki gunlerin verisi hala islenmemis olabilir)
if (Wait-Internet) {
    if (-not (Invoke-Step "ingest_players.py")) {
        Write-Log "UYARI: veri cekimi basarisiz, mevcut veriyle devam ediliyor"
    }
} else {
    Write-Log "UYARI: ag yok, veri cekimi hic denenmedi - mevcut veriyle devam"
}

# 2) build zinciri - SIRALI bagimlilik, biri coktuyse sonrakiler anlamsiz
$failed = $null
#    7.0 (1 Eki 2026): build_sonra + build_ranking eklendi. Onceden zincirde
#    yoktu - veri guncellenince Mevki Siralamasi SESSIZCE eski kaliyordu.
#    build_ranking player_tahmin'i (tek dogruluk kaynagi) da yazar; emsal ve
#    defter ondan okudugu icin ONLARDAN ONCE calisir.
foreach ($step in @("build_db.py", "build_features.py", "build_links.py",
                    "build_scores.py", "build_outcomes.py",
                    "build_sonra.py", "build_ranking.py --sessiz",
                    "build_emsal.py")) {
    $parca = $step -split ' '
    $ek = if ($parca.Count -gt 1) { $parca[1..($parca.Count - 1)] } else { @() }
    if (-not (Invoke-Step $parca[0] $ek)) { $failed = $step; break }
}

# 3) Hesap defteri - iddiayi KAYDET. Append-only; gecmis kayit
#    guncellenmiyor. Bir iddianin degeri geri alinamamasindan gelir.
if (-not $failed) {
    & $py (Join-Path $root "scripts\defter.py") --kaydet 2>&1 |
        Where-Object { $_ -match "kaydet" } | ForEach-Object { Write-Log "  $_" }
}

# Denetim de cokebiliyor (28 Agu 2026: import sirasinda yerel seviye cokme,
# daily_run basindaki GIL deseninin aynisi). Cokerse loga yuzlerce traceback
# satiri bosaliyordu. Artik bir kez yeniden deneniyor ve cikti anlamli
# satirlarla sinirli. Denetim tablolari DEGISTIRMEZ - cokmesi veri zincirini
# etkilemez, yalnizca o gunku dogrulama raporu kaybolur.
if (-not $failed) {
    $denetimOk = $false
    foreach ($deneme in 1, 2) {
        $cikti = & $py (Join-Path $root "scripts\audit.py") 2>&1
        $ozet = $cikti | Where-Object { $_ -match "KALDI|TOPLAM|^\s{2,}\S" }
        if ($ozet -match "TOPLAM") {
            $ozet | ForEach-Object { Write-Log "  denetim: $_" }
            $denetimOk = $true
            break
        }
        Write-Log "UYARI: denetim tamamlanmadi (deneme $deneme)"
        if ($deneme -eq 1) { Start-Sleep -Seconds 5 }
    }
    if (-not $denetimOk) {
        Write-Log "UYARI: denetim iki denemede de calismadi - VERI ZINCIRI ETKILENMEDI"
    }
}

if ($failed) {
    Write-Log "=== calisma BASARISIZ bitti - kirilan adim: $failed ==="
} else {
    Write-Log "=== calisma bitti (tum adimlar basarili) ==="
}

# log dosyasini sinirla
if (Test-Path $log) {
    $lines = Get-Content $log
    if ($lines.Count -gt 2000) {
        $lines | Select-Object -Last 2000 | Set-Content $log -Encoding utf8
    }
}

if ($failed) { exit 1 } else { exit 0 }
