# 00 — Bağlam ve Hedef

**Problem:** Bir fabrikadaki kritik motorlardan/rulmanlardan gelen milisaniyelik titreşim verisini gerçek zamanlı işleyerek, makine arızalanmadan önce erken uyarı üretmek.

**Genel Hedef:** Canlı veri akışını yakalamak → asenkron yapılarla anlık işlemek/anomali tespit etmek → canlı bir panoda görselleştirmek.

**Kapsam içi:**
- IMS titreşim verisinin canlı akışa dönüştürülmesi
- Gerçek zamanlı özellik çıkarımı ve anomali tespiti
- Anomali durumunda Telegram bildirimi
- Grafana ile canlı görselleştirme

**Kapsam dışı (bilinçli tercih):**
- Gerçek PLC/SCADA donanım entegrasyonu
- Çoklu fabrika/bölge ölçeklenmesi
- Kullanıcı yönetimi / RBAC
- Yüksek erişilebilirlik (HA) kümeleme

Gerekçe: 3 haftalık, tek kişilik bir projenin amacı, uçtan uca bir veri mühendisliği + streaming ML sistemini doğru mühendislik pratikleriyle kurmaktır; production-grade ölçek hedeflenmez.
