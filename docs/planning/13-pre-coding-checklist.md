# 13 — Koda Başlamadan Önce

Koda başlamadan önce yapılan işler, sonradan hata ayıklamaktan çok daha ucuzdur. Bu dosya, implementasyona geçmeden önce tamamlanacak/uygulanacak adımları toplar.

## 13.1 Walking Skeleton (Yürüyen İskelet) — Hafta 0.5'in Hedefi

**Amaç:** Tüm katmanları *en minimal* haliyle uçtan uca bağlamak. İş mantığı, ML, reassembly YOK — yalnızca bileşenlerin birbirine bağlandığını doğrulamak. İskelet çalıştıktan sonra her özellik bu yapının üstüne eklenir. Bu yaklaşım, entegrasyon sorunlarının proje sonuna birikmesini önler.

### İskeletin adımları (sırayla)
1. **Altyapı ayakta:** `docker compose up` ile Kafka (KRaft), TimescaleDB, Redis, Grafana kalkıyor. Health check'ler yeşil.
2. **Contracts paketi:** `libs/contracts` içinde en az `RawVibrationWindow` ve `AnomalyDetected` şemaları tanımlı (alanlar dondurulmuş).
3. **Simülatör (dummy):** Gerçek IMS verisi değil — sabit/rastgele tek bir mesajı belirli aralıkla `sensor.vibration.raw`'a yayınlar. Amaç: Kafka'ya yazma zincirini doğrulamak.
4. **Stream-processor (pass-through):** Mesajı tüketir, HİÇBİR işlem yapmadan (özellik çıkarımı yok) bir satır olarak TimescaleDB'ye yazar. Amaç: consume + DB write zinciri çalışıyor mu.
5. **DB → Grafana:** Grafana TimescaleDB'ye bağlanır, o satırları basit bir tabloda/grafikte gösterir. Amaç: veri uçtan uca görünüyor mu.
6. **Notifier (stub):** `anomaly.detected` topic'ini dinler; bir mesaj gelince gerçek Telegram yerine sadece log basar. Amaç: bildirim zinciri bağlı mı.

### İskelet "yürüdü" sayılır eğer:
- [ ] `docker compose up` tek komutla tüm stack'i kaldırıyor
- [ ] Dummy mesaj simülatörden çıkıp Grafana'da görünüyor
- [ ] Manuel yayınlanan bir `anomaly.detected` mesajı notifier log'unda beliriyor
- [ ] Bir servisi durdurup başlatınca sistem kaldığı yerden devam ediyor (Kafka tampon)

**Kural:** İskelet yürümeden hiçbir gerçek iş mantığı (özellik çıkarımı, ML, reassembly) yazılmaz.

## 13.2 Spike (Atılabilir Deneme)

**Amaç:** En riskli/belirsiz parçaları, tüm mimariyi kurmadan küçük denemelerle test etmek. Spike kodu ÖĞRENMEK içindir, sonra ATILIR — production'a girmez.

Bu projedeki iki kritik spike:
1. **Veri formatı spike'ı:** IMS dosyalarını bir script'le oku, gerçekten beklenen formatta mı (20.480 nokta, doğru kanal sayısı, timestamp isimlendirmesi) doğrula. Bir snapshot'ın RMS/kurtosis grafiğini çiz — bozulma örüntüsü görünüyor mu?
2. **Reassembly spike'ı:** Stateful reassembly (ADR-0004) doğrulaması. Tam pipeline olmadan, izole bir script'le chunk'lara bölme + yeniden birleştirme mantığı denenir. Çalışırsa `domain/`'e taşınır; aşırı karmaşıklaşırsa chunk'ların bağımsız işlendiği (reassembly'siz) alternatife geçilir.

## 13.3 Definition of Ready (Bir Göreve Başlamadan Önce)

Bir görev kodlanmaya başlanmadan önce şunlar hazır olmalı:
- [ ] İlgili event/veri şeması dondurulmuş (`libs/contracts`)
- [ ] Bağlı olduğu port arayüzleri tanımlı
- [ ] Test senaryoları listelenmiş (bkz. 05)
- [ ] Gereken config değişkenleri `.env.example`'da
- [ ] Belirsiz karar kalmadıysa (kaldıysa önce ADR)

## 13.4 Sıralama (Özet)
```
Walking Skeleton yürüsün
   → Contracts dondur
   → Spike ile riskli parçaları doğrula (veri formatı, reassembly)
   → Her özelliği iskeletin üstüne, test-önce ekle
   → Definition of Done ile kapat (bkz. 10)
```
