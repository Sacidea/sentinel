# ADR-0012: Ham-rFFT teshis kapanir; sonraki adim envelope

- **Durum:** Kabul edildi
- **Tarih:** 2026-08-29
- **İlgili:** ADR-0011 (offline ham-FFT denemesi), ADR-0010 (bant enerjisi kaydi),
  ADR-0007 (FFT ertelemesi), ADR-0013 (envelope denemesi), ADR-0015 (belirginlik
  kapandi; 0012 karari degismez)

## Baglam

Ham spektrum (rFFT bant gucu + AND kurali) bilinerek denendi; sessizce envelope'a
atlanmadi. Set 2'de kaplin/bearing_4 tuzaği goruldu, kural ona gore kalibre
edildi, sonra Set 1 hold-out ayni esikle kosuldu. Bu iz silinmez: 0011 ve
`ml/notebooks/ims_set{1,2}_fft_diagnosis.md` otopsi olarak kalir.

Sinir:

- **Set 2:** enerji-orani bearing_4'u de BPFO yapardi (kaplin BPFO kovasini
  sisirir, tum bantlari esit kaldirmaz). Companion ile b1/b2/3/4 4/4 tutuldu;
  `companion_z=8` b2 tavaninin (7.45) bicak agrisi.
- **Set 1:** ayni kural 4/4 tutmadi. NASA ic bilezik (b3) ve makara (b4)
  yakalanmadi; NASA saglikli b2 yanlis BSF aldi. Esik grid'i kurtarmadi —
  uc kova rFFT, BPFI/BSF hakimiyeti uretmiyor.

## Karar

1. **Ham-rFFT teshis canliya yazilmaz.** `fault_type`, schema, migration,
   Grafana teshis paneli bu kurala baglanmaz. `diagnose_fft_bands` silinmez;
   kanit ve birim test olarak durur, snapshot_pipeline cagirmaz.
2. **ADR-0010 aynen:** `fft_band_energy` kayda gider, Z-Score/IF vektorune
   girmez, alarm uretmez.
3. **Sonraki teshis denemesi envelope** (Hilbert / genlik demodulasyonu, sonra
   ayni BPFO/BPFI/BSF kovalar). Uygulama ve karne ADR-0013. Tutmazsa canliya
   yazilmaz.

## Alternatifler

- **Ham-FFT'yi Set 1'e retune edip canliya almak:** grid 4/4 yapamadi; esik
  degil imza. Elendi.
- **Ham-FFT kodunu silmek:** otopsi kaybolur; "neden envelope" sorusu cevapsiz
  kalir. Elendi.
- **Envelope'siz teshisi kapatip birakmak:** kaplin vs dis bilezik sorusu
  acik kalir. Erteleme degil, yol degisikligi: envelope denenir.

## Sonuclar

(+) Deneme, sinir, kapanis ayni izde; olgunluk "hemen envelope" degil
    "ham-FFT yetmedi, sonra envelope".
(−) Teshis canli degil. Envelope Set 2 4/4, Set 1 hold-out tutmadi (ADR-0013).
