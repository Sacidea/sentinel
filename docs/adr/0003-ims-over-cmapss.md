# ADR-0003: NASA IMS Bearing Veri Seti (C-MAPSS Değil)

- **Durum:** Kabul edildi
- **Tarih:** 2025 (planlama)

## Bağlam
Senaryo "milisaniyelik titreşim verisi" ve Z-Score/Moving Average ile sapma tespiti gerektiriyor. İki popüler PdM veri seti aday: NASA IMS Bearing ve C-MAPSS Turbofan.

## Karar
NASA IMS Bearing seçildi (gerçek 20 kHz ham ivmeölçer sinyali, run-to-failure).

## Alternatifler
- **C-MAPSS Turbofan:** Cycle bazlı, çok değişkenli ama düşük çözünürlüklü; ham dalga formu yok. RUL/trend için güçlü ama "titreşim sinyal işleme" senaryosuna uymuyor.
- **CWRU Bearing:** Temiz, farklı arıza tipleri; ancak run-to-failure (zamanla kötüleşme) senaryosu için IMS daha uygun.

## Sonuçlar
(+) Gerçek sinyal işleme (RMS/kurtosis/FFT), inandırıcı streaming simülasyonu, net bir arıza örüntüsü.
(−) Daha ham veri; pencereleme ve önişlemeyi kendimiz kuruyoruz (öğrenme açısından artı).
