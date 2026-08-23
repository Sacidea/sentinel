# ADR-0002: Apache Kafka (Redis Streams Değil)

- **Durum:** Kabul edildi
- **Tarih:** 2025 (planlama)

## Bağlam
Sensör telemetrisi için bir akış omurgası gerekiyor. Redis Streams daha hafif ve kurulumu kolay; Kafka daha ağır ama endüstri standardı.

## Karar
Apache Kafka (KRaft mode, aiokafka istemcisi) seçildi.

## Alternatifler
- **Redis Streams:** Hafif, düşük operasyon maliyeti. Ancak partition bazlı yatay ölçeklenme, consumer group olgunluğu, uzun süreli kalıcılık ve replay konularında Kafka'nın gerisinde.

## Sonuçlar
(+) Endüstri standardı, replay, partition ölçeklenmesi, kalıcılık.
(−) Daha yüksek kurulum/kaynak maliyeti. KRaft mode ile Zookeeper bağımlılığı kaldırılarak hafifletildi.
