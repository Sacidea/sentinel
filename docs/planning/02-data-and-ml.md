# 02 — Veri Kaynağı ve Makine Öğrenmesi Planı

## Veri Kaynağı: NASA IMS Bearing Dataset
- Gerçek, ham ivmeölçer (titreşim) sinyali — simülasyon değil
- 20 kHz örnekleme, dosya başına 20.480 nokta (~1 sn pencere)
- Her 10 dk'da bir 1 sn snapshot; run-to-failure

**Neden C-MAPSS değil:** C-MAPSS cycle bazlı, düşük çözünürlüklü, ham dalga formu yok.

### Etiket Durumu
| Görev | Etiket | Kaynak |
|---|---|---|
| Anlık anomali | Etiketsiz | Model bulacak |
| RUL | Etiketli (türetilebilir) | Son dosya = arıza anı |
| Arıza tipi | Test bazında etiketli | NASA README |

## ML Planı

### Çekirdek (3 hafta)
1. Ön İşleme — `RobustScaler` (outlier'a dayanıklı)
2. Anomali Tespiti — Isolation Forest (etiketsiz, yorumlanabilir)
3. Klasik Yöntem — PCA + Hotelling's T² / SPE
4. Online Öğrenme — River (HalfSpaceTrees)

### Opsiyonel
5. RUL — Random Forest / XGBoost
6. Autoencoder (PyTorch)
7. MLflow — deney takibi

### Neden LSTM/CNN çekirdek değil
- IMS'te ~12-16 sekans → overfit riski
- Isolation Forest/PCA yorumlanabilir, LSTM/CNN black-box
- LSTM hidden-state → event-driven'a ek karmaşıklık
- 3 haftalık ROI düşük

### Değerlendirme
- Anomali skorunun yükseldiği an işaretlenir
- **Lead time**: "arızadan X saat önce yakaladı"
- Yanlış pozitif oranı raporlanır

**Mimari not:** ML modeli `domain/detectors.py` içinde `AnomalyDetector` port'unu implemente eder. Offline eğitim ile online skorlama ayrı; artefakt `ml/models/`'dan yüklenir.
