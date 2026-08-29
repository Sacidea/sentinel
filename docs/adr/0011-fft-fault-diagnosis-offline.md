# ADR-0011: FFT ariza teshisi offline; canli anomaly_events yok

- **Durum:** Kabul edildi (otopsi; teshis yolu [ADR-0012](0012-raw-fft-diagnosis-closed-envelope-next.md))
- **Tarih:** 2026-08-28
- **İlgili:** ADR-0010 (bant enerjisi cikarimi), ADR-0007 (FFT ertelemesi),
  ADR-0012 (ham-rFFT kapanir, envelope)

## Baglam

ADR-0010 BPFO/BPFI/BSF enerjisini hesaplar ve kaydeder; alarm/teshis uretmez.
Set 2 taramasi (`ims_set2_fft_bands.md`) etiketsiz kanallarda da gec BPFO
yukselisi gosterdi (kaplin). Ozellikle bearing_4: kucuk baseline yuzunden
gec/erken **orani** sisar; mutlak enerji b1 ile ayni mertebededir. Yalniz
"BPFO yukseldi" dis bilezik demek degildir.

Istenen kural iki kosulun AND'i:

- (a) Mutlak anlamli yukselis — aday bant, kendi saglikli baseline'ina gore
  yukselmis olmali (oran sismesini eker).
- (b) Goreli baskinlik — gercek dis bilezikte BPFO, ayni rulmanin BPFI/BSF'inden
  belirgin baskin olmali.

Teshis zorlanmaz: hicbir bant ikisini de gecmezse `uncertain`. Canli entegrasyon
(`fault_type`, schema, migration) bu turun disinda.

## Karar

1. **Saf kural** `domain/fft_diagnosis.py`: `diagnose_fft_bands` →
   `bpfo | bpfi | bsf | uncertain`. I/O yok; snapshot_pipeline/Kafka/DB
   cagirmaz.
2. **Set 2 esikleri** (sihirli sabit degil; `ims_set2_fft_diagnosis.md`):
   `abs_z=12`, `dominance=3`, `companion_z=8`. Baska sete tasinmaz.
3. **(b) operasyonellestirme:** Ham enerji orani yetmez. Set 2'de **butun**
   rulmanlarin gec BPFO'su BPFI/BSF'ten onlarca kat buyuk; kaplin tum bantlari
   birlikte kaldirmaz, **yalniz BPFO kovasini** sisirir. Bu yuzden (b) =
   enerji baskinligi **ve** en az bir diger karakteristigin z'si
   `companion_z` (gercek irk imzasinda BPFI de baseline'dan cikar; kaplin
   BPFI'yi yerinde birakir).
4. **Dogrulama (Set 2, kalibrasyon seti):** b1 → `bpfo`; b2/3/4 → `uncertain`.
   Karnesi `ml/notebooks/ims_set2_fft_diagnosis.md`.
5. **Hold-out (Set 1, esik kilit):** 4/4 tutmadi. NASA b3 ic bilezik / b4 makara
   yakalanmadi; NASA saglikli b2 yanlis `bsf` aldi. Grid'de hicbir (C, abs_z)
   4/4 yapmadi — esik kaydirmak kurtarmaz. Karne
   `ml/notebooks/ims_set1_fft_diagnosis.md`.
6. **Canli yok.** `anomaly_events.fault_type` bu kurala baglanmaz (ADR-0012).

## Alternatifler

- **Yalniz enerji baskinligi (E_bpfo / max(digerleri)):** b4'u de BPFO yapar;
  grid'de b1'i yakalayan hicbir (Z, D) cifti etiketsizleri sifirlamadi. Elendi.
- **Yalniz mutlak z_bpfo:** kaplin BPFO kovasini da kaldirir; b3/b4 false
  BPFO. Elendi.
- **Zorunlu teshis (en yuksek bant her zaman kazansin):** belirsizi yok eder;
  kaplini irk arizasi yazar. Elendi.
- **Canli `fault_type` bu turda:** dogrulama bitmeden sema kilitlenir. Ertele
  (kapanis ADR-0012).

## Sonuclar

(+) NASA dis bilezik (b1) ile kaplin (b4) Set 2'de ayrilir; teshis zorlanmaz.
(+) Deneme silinmedi: karneler ve bu ADR otopsi olarak durur.
(−) Set 1 hold-out ayni kurali dogrulamaz; rFFT uc kova BPFI/BSF hakimiyeti
    uretmez. Canli `fault_type` acilmaz — yol envelope (ADR-0012).
(−) `companion_z`, Set 2 kaplin duzeltmesidir; baska sete tasinmaz.
