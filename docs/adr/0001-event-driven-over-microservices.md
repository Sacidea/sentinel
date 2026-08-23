# ADR-0001: Event-Driven Servis Mimarisi (Tam Mikroservis Değil)

- **Durum:** Kabul edildi
- **Tarih:** 2025 (planlama)

## Bağlam
Sistem birden fazla bağımsız işleme adımı içerir (simülasyon, işleme, bildirim, görselleştirme). Tam mikroservis mimarisinin maliyeti, tek kişilik/3 haftalık bir proje bağlamında değerlendirilmelidir.

## Karar
Event-driven, gevşek bağlı servis mimarisi benimsendi. Servisler ayrı process/container, Kafka üzerinden asenkron iletişim; ancak paylaşılan tek veritabanı (TimescaleDB), API gateway/service discovery yok.

## Alternatifler
- **Tam mikroservis (database-per-service, API gateway):** Bağımsız takım/deploy döngüsü olmadan fayda getirmeden operasyonel karmaşıklık ekliyor.
- **Monolit:** Streaming/asenkron doğaya ve "ayrı ölçeklenebilir işleyiciler" hedefine uymuyor.

## Sonuçlar
(+) Gevşek bağlılık, yeni consumer'la genişletilebilirlik, gerçekçi kapsam.
(−) "Mikroservis kullandım" denemez; doğru terim event-driven. Dağıtık transaction desenleri (Saga) uygulanamaz (zaten gerekmiyor).
