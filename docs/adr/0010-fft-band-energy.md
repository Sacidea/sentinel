# ADR-0010: FFT bant enerjisi cikarilir, tespite girmez

- **Durum:** Kabul edildi
- **Tarih:** 2026-08-28
- **İlgili:** ADR-0007 (FFT ertelemesi; cikarim kismi burada kapanir), ADR-0008 (IF nicelik)

## Baglam

Plan (14, README) `fft_band_energy` sozunu veriyordu; Hafta 2 borusu FFT'siz akti.
Z-Score/IF Set 2'de zaman-alani ile kalibre. Frekans-alani **teshis** (BPFO=dis
bilezik karari) ayri bir is (ADR-0011, offline); once enerjinin hesaplanip
saklanmasi gerekir.

## Karar

1. **Cikarim:** `extract_features` NumPy `rfft` ile her karakteristik frekansta
   temel + 2. + 3. harmonik, ±5 Hz bant gucunu toplar. Anahtarlar `bpfo` /
   `bpfi` / `bsf`. Merkezler Rexnord ZA-2115 / IMS Set 2:
   236 / 297 / 278 Hz, ornekleme 20.480 Hz —
   `domain/bearing_frequencies.py` (features.py icine gomulmez).
2. **Tespit yok.** Z-Score, IsolationForest, PCA, River ayni dort zaman-alani
   vektorunu kullanir. FFT esik/alarm/Telegram uretmez.
3. **Kalicilik:** `VibrationFeatures.fft_band_energy` ve
   `vibration_features.fft_band_energy` JSONB doldurulur. Sutun `001_init.sql`
   icinde zaten var; yeni migration yok. Doldurmak icin stream-processor rebuild.
4. **Dogrulama:** Set 2 taramasi `ml/notebooks/ims_set2_fft_bands.md` — bearing_1
   BPFO'nun run boyunca yukselmesi beklenir (NASA dis bilezik). Bu tarama lead/FP
   karnesi degildir.

## Alternatifler

- **FFT'yi IF vektorune eklemek:** Set 2 IF karnesini gecersiz kilar; elendi.
- **Ham spektrumu JSONB'ye yazmak:** 10k bin/satir; elendi.
- **Teshis esigi (BPFO > esik → dis bilezik):** ADR-0011 (offline; canli yok).

## Sonuclar

(+) Grafana/DB'de bant trendi gorulur; teshis kurali ADR-0011 (canli yazim yok).
(−) Merkezler yalniz ZA-2115 / Set 2. Baska rulman geometrisi sabitleri degistirir.
(−) ADR-0007'deki "FFT hic yok" ifadesi cikarim icin yerini alir; ML vektoru FFT'siz kalir.
