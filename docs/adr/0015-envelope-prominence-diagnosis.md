# ADR-0015: Envelope tepe belirginligi teshisi kapandi; canli yok

- **Durum:** Kabul edildi (kapatildi; canli `fault_type` yok)
- **Tarih:** 2026-09-04
- **İlgili:** ADR-0013 (enerji kovasi envelope; karar degismez), ADR-0012
  (ham-rFFT kapanisi), ADR-0011 (otopsi izi), ADR-0010 (bant enerjisi kaydi)

## Baglam

ADR-0013 envelope enerji kovasi + AND kurali Set 2'de 4/4, Set 1 hold-out'ta
4/4 tutmadi: saglikli/bilye false BPFO, ic bilezik hakimiyet uretmedi.
Sonraki deneme enerji degil **tepe belirginligi** + yan bant + spektral ortalama;
teshis ayri katman, canli boruya baglanmaz. ADR-0011/0012 otopsi silinmez.

Kinematik (Rexnord ZA-2115, 2000 rpm, n=16, d=0.331 in, D=2.815 in,
alpha=15.17 deg, fr=33.333 Hz):

| | Formul | ADR-0010 kova |
|---|---:|---:|
| BPFO | 236.40 Hz | 236 |
| BPFI | 296.93 Hz | 297 |
| BSF | 139.92 Hz | — |
| 2xBSF | 279.83 Hz | **278** (`bsf`) |
| FTF | 14.78 Hz | — |

`CHARACTERISTIC_HZ['bsf']=278` **2xBSF** tir, temel BSF (~140 Hz) degil.
Kova degerleri degistirilmedi. Teshis `IMS_ZA2115` kullanir.
Karne: `ml/notebooks/ims_envelope_prominence_diagnosis.md`.

## Karar

1. **Deneme yapildi, yol kapandi.** Belirginlik + yan bant olcusu, enerji
   tabanli yaklasimlarin **yanlis etiket** sorununu cozdu (Set 1 orta pencere:
   0 yanlis; onceki kuralda b2/b4 false BPFO vardi). Ancak **teshis
   edilebilirlik** sorununu cozmedi: Set 1'de arizali kanallar orta pencerede
   %100 belirsiz.
2. **Alarm-capali pencere de bu ciftte calismaz.** Ek olcum, dogru etiketinin
   Z-Score tespit anindan **290–900 snapshot sonra** belirdigini gosterdi
   (b3/x W=755 vs BPFI 2023; b3/y W=1829 vs BPFI 2120). Set 2 b1'de warning
   (536) BPFO adasindan 8 dosya once; yalniz critical (554) ada icinde.
   Alarm anina pencere oturtmak bu veri ciftinde teshisi kurtarmaz.
3. **Teshis katmani canlida kapali; `fault_type` acilmadi.** Schema, migration,
   Grafana teshis paneli, snapshot_pipeline baglantisi yok. Esik gevsetilmedi,
   sinif birlestirilmedi, Set 1'e retune yok. ADR-0011/0012/0013 izi durur.
4. **Offline kod durur:** `domain/diagnosis.py` saf fonksiyon (I/O yok,
   detektor import yok). Esikler Set 2 orta: `min_score=20`, `bpfo_margin=2.0`,
   `inner_margin=1.3`. Canli cagri yok.

## Alternatifler

- **Set 1'e retune / min_score dusurmek:** hold-out overfitting. Elendi.
- **`bpfi_veya_bsf`'yi dogru saymak:** karne yalanlar. Elendi.
- **Kovadaki 278'i 140 yapmak:** canli enerji yolu kirilir. Elendi.
- **Z-Score alarmina capali teshis penceresi:** dogru etiket 290–900 snapshot
  gecikir; b4/x minmax W=399'u kapsa da o index `uncertain`. Elendi.
- **Canli `fault_type`:** teshis edilebilirlik yok. Elendi.

## Sonuclar

(+) Yanlis etiket (false BPFO) belirginlikle dustu; katman ayrimi korundu.
(−) Orta evrede ic bilezik/bilye etiketlenmiyor. Alarm-capali kural da bu
    Set 1/Set 2 ciftinde calismaz.
(−) Teshis canli degil. Yeni teshis denemesi ayri tur + yalniz Set 2 kalibrasyon
    + ayni hold-out citasi; 0011–0015 izi silinmez.
