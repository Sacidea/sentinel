# ML Notebooks

Kesifsel analiz bu dizindedir. Kalibrasyon karneleri silinmez; esik “sessizce
dogru cikti” sayilmaz.

## Teshis izi (ham-rFFT → envelope)

Sira silinmez (ADR-0011 otopsi, ADR-0012 kapanis, ADR-0013 envelope).

1. Bant enerjisi kayda gider, tespite girmez — `ims_set2_fft_bands.md` (ADR-0010).
2. Ham-rFFT teshis Set 2'de 4/4; bearing_4 enerji-orani tuzaği — `ims_set2_fft_diagnosis.md`.
3. Ayni esik Set 1 hold-out 4/4 tutmadi — `ims_set1_fft_diagnosis.md`.
4. Envelope (Hilbert 2–10 kHz): Set 2 4/4 (`companion_z=25`); Set 1 hold-out
   yine 4/4 tutmadi — `ims_set2_envelope_diagnosis.md`, `ims_set1_envelope_diagnosis.md`.
   Canli `fault_type` yok.

## Diger karneler

- `ims_set2_spike.py` / `ims_set2_spike.md` — NASA IMS Set 2 format + baseline dogrulamasi (planning/13.2).
- `ims_set2_zscore_calibration.py` / `ims_set2_zscore_calibration.md` — Z-Score esik taramasi; lead time NASA test sonuna gore (ADR-0006, 5.0/8.0, yalniz Set 2).
- `ims_set1_zscore.py` / `ims_set1_zscore.md` — Z-Score Set 1 hold-out. Ayni 5.0/8.0 kilit, retune yok; x/y ayri. ML yok.
- `ims_set2_ml_calibration.py` / `ims_set2_ml_calibration.md` — IsolationForest / PCA nicelik taramasi (ADR-0008, 0.995/0.999 IF+zarf). Gercek 984 Set 2 dosyasi.
- `ims_set2_fft_bands.py` / `ims_set2_fft_bands.md` — FFT bant enerjisi (BPFO/BPFI/BSF); teshis yok (ADR-0010).
- `ims_set2_fft_diagnosis.py` / `ims_set2_fft_diagnosis.md` — ham-rFFT teshis, Set 2 kalibrasyon (ADR-0011). Canli yok.
- `ims_set1_fft_diagnosis.py` / `ims_set1_fft_diagnosis.md` — ham-rFFT Set 1 hold-out. 4/4 tutmadi.
- `ims_set2_envelope_diagnosis.py` / `ims_set2_envelope_diagnosis.md` — envelope Set 2 (ADR-0013, C=25).
- `ims_set1_envelope_diagnosis.py` / `ims_set1_envelope_diagnosis.md` — envelope Set 1 hold-out. 4/4 tutmadi.
