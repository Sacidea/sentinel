# ADR-0013: Envelope teshisi offline; canli yok

- **Durum:** Kabul edildi
- **Tarih:** 2026-08-29
- **İlgili:** ADR-0012 (ham-rFFT kapanisi), ADR-0011 (ham-rFFT otopsi), ADR-0010 (kayit),
  ADR-0015 (belirginlik denendi ve kapandi; 0013 karari degismez)

## Baglam

ADR-0012 envelope'u sonraki deneme yapti: Hilbert / 2–10 kHz band-pass, sonra
ayni BPFO/BPFI/BSF kovalar ve AND kurali (`diagnose_fft_bands`, zorlanmayan
`uncertain`). Canli `fault_type` ancak Set 2 kalibrasyon **ve** Set 1 hold-out
4/4 tutarsa acilacakti.

## Karar

1. **Cikarim (domain, I/O yok):** `envelope_band_energy` — band-pass 2–10 kHz,
   FFT Hilbert genlik, `rfft_band_energy` kovalar. `extract_features` / snapshot
   borusu cagirmaz; `fft_band_energy` kaydi ADR-0010 aynen.
2. **Set 2 esikler** (`envelope.py`, `ims_set2_envelope_diagnosis.md`):
   `abs_z=12`, `dominance=3`, `companion_z=25`. Ham-FFT `companion_z=8`
   kopyalanmaz: C=8 envelope'de b2/b4 false BPFO. C=25, b4 max companion
   (~21.3) ustu; plato ~25–100. Bicak agrisi (FFT C=8 ~ b2 7.45 ile ayni tur).
3. **Set 2 4/4:** b1=`bpfo` (ilk index 959, 20 etiket); b2/3/4=`uncertain`.
   enerji-only b4'u 172 kez BPFO sayardi. Envelope spektrumu dis bilezik
   kontrastini ham-rFFT'den sertlestirdi (gec z_BPFO ~3015 vs ham ~107).
4. **Set 1 hold-out 4/4 tutmadi** (`ims_set1_envelope_diagnosis.md`). Esik kilit.
   b3 ic bilezik: max z_BPFI ~1257 ama E_BPFI ~ E_BPFO (hakimiyet 1x) → BPFI
   etiketi yok. b4 makara: C=25 ile **BPFO**; C=8'de BSF olurdu ama b2 false
   BPFO. Grid'de hicbir (C, abs_z) 4/4 yapmadi.
5. **Canli yok.** `fault_type`, schema, migration, Grafana teshis paneli yok.

## Alternatifler

- **Ham-FFT C=8'i envelope'a kopyalamak:** Set 2 4/4 bozulur (b2/b4). Elendi.
- **Set 1'e retune (C=8 b4=BSF):** b2 false BPFO, b3 hâlâ belirsiz. Elendi.
- **Envelope'u canli `extract_features`'a eklemek:** hold-out yokken CPU+sema.
  Elendi.
- **Teshisi kapatmak:** Set 2 dis bilezik vs kaplin envelope ile ayriliyor;
  karneler durur, canli yazilmaz. Bu ADR.

## Sonuclar

(+) Hilbert domain'de testli; Set 2 kaplin tuzaği (b4 enerji-orani) AND+C=25
    ile elenir; ham-rFFT otopsi silinmedi.
(−) Set 1 ic bilezik/makara hâlâ uc kovada hakimiyet uretmiyor. Canli teshis
    acilmaz.
(−) `companion_z=25` yine Set 2 bicak agrisi; baska sete tasinmaz.
