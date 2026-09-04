# ADR-0007: Katman 2 ML esikleri kalibre degil; FFT bantlari ertelendi

**Durum:** Kısmen yerini aldı [ADR-0008](0008-ml-quantiles-set2.md) (eğitim niceliği),
[ADR-0010](0010-fft-band-energy.md) (FFT bant çıkarımı; teşhis yok) ve
[ADR-0012](0012-raw-fft-diagnosis-closed-envelope-next.md) (ham-rFFT teşhis kapanır).
- **Tarih:** 2026-08-26

## Baglam

Hafta 2 Isolation Forest / PCA / River canli skorlamaya alindi. Birim testleri yesile cekilirken esik ve yedek-skor davranisi degisti. Bunlar sessizce "Set 2 de calisir" sayilmamali. Plan (14, 15, 08, README) FFT bant enerjisi icerir; canli cikarimda FFT yoktur. Kaldirilmis degil: hic yazilmadi, kapsam olarak ertelendi.

## Karar

1. `8.0 / 25 / 20 / 12` uretim esigi degildir. `test_ml_detectors.py` sentetik asiri vektordur (rms, kurtosis, crest, peak). Detector bu sayilari hardcode etmez. Canli warning/critical, her (machine_id, axis) icin warmup egitim skorlarindan turetilir (`_healthy_thresholds`).
2. Katman 2 Set 2 ye kalibre edilmedi. Lead time / FP taramasi yalniz Z-Score icindir (ADR-0006: 5.0/8.0, bearing_1 ilk warning index 536, lead 74.5 saat son dosyaya). ML gercek IMS dosyalari uzerinde ayni protokolle olculmedi. Yesil testler sentetik vektor + sahte port entegrasyonudur.
3. FFT bant enerjisi **cikarimi** ADR-0010 ile kapanir (teshis/alarm yok).
   Ham-rFFT teshis denendi ve kapandi (ADR-0011 otopsi, ADR-0012 envelope).
   Hafta 2'de ML vektoru hâlâ dort zaman-alani ozelligidir.
4. Yayilim payi ve IF yedek skoru sihirli sabittir, config degildir, Set 2 taramasindan gelmez. Amac: kucuk N de niceligin max a cokmesi ve Isolation Forest yol uzunlugunun doymasi. Uretim kalibrasyonu sayilmaz.

### Sihirli sabitler (`domain/ml_detectors.py`)

- `warning = peak + 0.5 * floor` — egitim max inin ustune pay; taranmadi
- `floor = max(spread, |peak|, 1e-3)` — sifir yayilimda payin yok olmamasi
- `critical = warning + max(spread, 0.25*|peak|, 1e-3)` — ikinci kademe; sezgi
- olceklenmis `max(|x|)` zarfi — IF decision_function uzakta doyunca yedek
- `predict == -1` en az WARNING — sklearn etiket yedegi
- `contamination=0.01`, `n_estimators=64` — hiperparametre, Set 2 degil

## Alternatifler

- ML i Set 2 de ADR-0006 protokoluyle taramak: dogru uretim kapisi; borc olarak durur.
- FFT yi Hafta 2 de eklemek: boru FFT siz zaten ucu uca akti; Z-Score zaman-alani ile kalibre edildi.
- 99/99.9 nicelik: kucuk N de max a coker; payli max buna tepki, yine kalibrasyon degil.

## Sonuclar

(+) Katman 2 port + freeze canlidir; `ML_LAYER_ENABLED=false` kapatir.
(+) Test vektoru ile esik karismaz; FFT cikarimi ADR-0010.
(-) Sentetik asiri vektor IMS lead/FP vermez.
(-) 0.5 / 0.25 / 1e-3 config te degil; test yesil kalip gercek veri bozulabilir.
(-) README / 08 FFT vaadini "yapildi" saymaz.
