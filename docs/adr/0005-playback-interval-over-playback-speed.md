# ADR-0005: Oynatma Hızı `PLAYBACK_INTERVAL_SEC` ile İfade Edilir (`PLAYBACK_SPEED` Değil)

- **Durum:** Kabul edildi
- **Tarih:** 2026-08-24

## Bağlam

Simülatörün snapshot'ları hangi hızda yayınladığı iki farklı isimle ifade ediliyordu:

- Planlama dokümanları (`07-resilience.md`, `05-testing-observability.md`) ve ADR-0004'ün timeout
  bölümü **`PLAYBACK_SPEED`** çarpanını kullanıyordu: `max(FLOOR, (600 / PLAYBACK_SPEED) * FACTOR)`.
  Buradaki 600, IMS'in nominal snapshot aralığı (10 dk) idi.
- Implementasyon ise **`PLAYBACK_INTERVAL_SEC`** (snapshot'lar arası bekleme, saniye) okuyordu.

`.env` içindeki `SIM_PLAYBACK_SPEED` hiçbir kod tarafından okunmuyordu; `Settings`'in
`extra="ignore"` ayarı yüzünden hata da vermiyor, sessizce yok sayılıyordu. Yani oynatma hızı
pratikte hiç ayarlanamıyordu. Reassembly timeout'u bu değere dayandığı için (ADR-0004), iki ismin
hangisinin geçerli olduğu reassembly kodlanmadan önce netleşmek zorundaydı.

## Karar

Tek geçerli değişken **`PLAYBACK_INTERVAL_SEC`**'dir (snapshot'lar arası bekleme, saniye).
`PLAYBACK_SPEED` kavramı kullanımdan kaldırılmıştır.

Reassembly timeout formülü buna göre sadeleşir:

```
reassembly_timeout = max(REASSEMBLY_TIMEOUT_FLOOR, PLAYBACK_INTERVAL_SEC * REASSEMBLY_TIMEOUT_FACTOR)
```

Eski değerlerle karşılığı: `PLAYBACK_INTERVAL_SEC = 600 / PLAYBACK_SPEED`
(hız 1 → 600 sn; hız 6000 → 0,1 sn).

## Alternatifler

- **Dokümandaki `PLAYBACK_SPEED`'i esas alıp kodu değiştirmek:** Çarpan dolaylı bir ifade; her
  tüketicinin 600'e bölmesi gerekir. Daha kötüsü, "IMS 10 dakikada bir ölçüm alır" bilgisi (sihirli
  600 sabiti) stream-processor'a sızar — oysa o servisin veri setinin nominal aralığını bilmesi
  gerekmez. Ayrıca çalışan kodu değiştirmeyi gerektirirdi.
- **İkisini birlikte desteklemek:** İki kaynak, iki gerçek. Biri güncellenip diğeri unutulduğunda
  timeout sessizce yanlış hesaplanır — tam da bu ADR'nin önlemek istediği durum.

## Sonuçlar

(+) Tek kol, doğrudan gözlemlenebilir (servis açılışında config log'unda görünür).
(+) Sihirli 600 sabiti hiçbir servise sızmaz; timeout hesabı tek çarpmaya iner.
(+) Farklı nominal aralığa sahip bir veri setine geçilirse formül değişmez.

(−) `05` ve `07` ile ADR-0004'ün timeout bölümü eski ismi anıyordu; bu ADR ile birlikte
güncellendiler. Eski notlarda `PLAYBACK_SPEED` görülürse yukarıdaki dönüşümle okunmalıdır.
(−) "6000 kat hızlı oynat" gibi düşünmek artık doğrudan ifade edilemez; aralık cinsinden düşünülür.
