"""IMS Set 2 Z-Score eşik kalibrasyonu — atılabilir (bkz. planning/15, ADR-0006).

Production'a girmez. Lead time NASA README'deki arıza anına (test sonu, son dosya)
göre hesaplanır; RMS eğrisindeki göz kararı '~700' değerlendirme çapanı değildir.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "stream-processor" / "src"))

from stream_processor.domain.detectors import DetectionStatus, ZScoreDetector  # noqa: E402
from stream_processor.domain.features import SignalFeatures, extract_features  # noqa: E402

DATA_DIR = ROOT / "data" / "ims"
CACHE_PATH = ROOT / "data" / "ims_set2_features.npz"
OUT_DIR = Path(__file__).resolve().parent
BASELINE_WINDOW = 200
MA_WINDOW = 5
BEARINGS = ("bearing_1", "bearing_2", "bearing_3", "bearing_4")
FILE_NAME = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{2}$")
# NASA IMS Set 2 README: her 10 dakikada bir dosya; arıza testi sonunda duyurulur.
SNAPSHOT_INTERVAL_MIN = 10
LABELED_BEARING = "bearing_1"


def _files() -> list[Path]:
    return sorted(
        path for path in DATA_DIR.iterdir() if path.is_file() and FILE_NAME.match(path.name)
    )


def load_features() -> dict[str, dict[str, np.ndarray]]:
    if CACHE_PATH.is_file():
        payload = np.load(CACHE_PATH)
        return {
            "rms": {bearing: payload[f"rms_{bearing}"] for bearing in BEARINGS},
            "kurtosis": {bearing: payload[f"kurt_{bearing}"] for bearing in BEARINGS},
        }

    files = _files()
    n_files = len(files)
    rms = {bearing: np.zeros(n_files) for bearing in BEARINGS}
    kurtosis = {bearing: np.zeros(n_files) for bearing in BEARINGS}
    for index, path in enumerate(files):
        samples = np.loadtxt(path, dtype=np.float64)
        if samples.ndim == 1:
            samples = samples.reshape(-1, 1)
        for column, bearing in enumerate(BEARINGS):
            features = extract_features(samples[:, column].tolist())
            rms[bearing][index] = features.rms
            kurtosis[bearing][index] = features.kurtosis
    np.savez(
        CACHE_PATH,
        **{f"rms_{bearing}": rms[bearing] for bearing in BEARINGS},
        **{f"kurt_{bearing}": kurtosis[bearing] for bearing in BEARINGS},
    )
    return {"rms": rms, "kurtosis": kurtosis}


def replay(
    features: dict[str, dict[str, np.ndarray]],
    *,
    warning: float,
    critical: float,
) -> dict[str, list[DetectionStatus]]:
    n_files = len(next(iter(features["rms"].values())))
    statuses: dict[str, list[DetectionStatus]] = {bearing: [] for bearing in BEARINGS}
    detectors = {
        bearing: ZScoreDetector(
            baseline_window=BASELINE_WINDOW,
            ma_window=MA_WINDOW,
            warning_threshold=warning,
            critical_threshold=critical,
        )
        for bearing in BEARINGS
    }
    for index in range(n_files):
        for bearing in BEARINGS:
            result = detectors[bearing].observe(
                bearing,
                "x",
                SignalFeatures(
                    rms=float(features["rms"][bearing][index]),
                    kurtosis=float(features["kurtosis"][bearing][index]),
                    crest_factor=0.0,
                    peak=0.0,
                ),
            )
            statuses[bearing].append(result.status)
    return statuses


def _first_status(rows: list[DetectionStatus], status: DetectionStatus) -> int | None:
    for index, value in enumerate(rows):
        if value is status:
            return index
    return None


def _count_alarms(rows: list[DetectionStatus], start: int, end: int) -> int:
    return sum(
        1
        for value in rows[start:end]
        if value in (DetectionStatus.WARNING, DetectionStatus.CRITICAL)
    )


def _unlabeled_fp(
    statuses: dict[str, list[DetectionStatus]],
    *,
    before: int,
) -> int:
    """NASA'nın arıza duyurmadığı kanallarda, etiketli kanalın ilk uyarısından önceki alarm."""
    total = 0
    for bearing in BEARINGS:
        if bearing == LABELED_BEARING:
            continue
        total += _count_alarms(statuses[bearing], BASELINE_WINDOW, before)
    return total


def _hours_before(index: int | None, failure_index: int) -> str:
    if index is None or index >= failure_index:
        return "-"
    minutes = (failure_index - index) * SNAPSHOT_INTERVAL_MIN
    return f"{minutes / 60:.1f} saat"


def _first_alarm(rows: list[DetectionStatus]) -> int | None:
    warning = _first_status(rows, DetectionStatus.WARNING)
    critical = _first_status(rows, DetectionStatus.CRITICAL)
    candidates = [index for index in (warning, critical) if index is not None]
    if not candidates:
        return None
    return min(candidates)


def summarize(features: dict[str, dict[str, np.ndarray]], files: list[Path]) -> str:
    pairs = (
        (3.0, 5.0),
        (5.0, 8.0),
        (8.0, 12.0),
        (10.0, 15.0),
        (12.0, 20.0),
        (15.0, 25.0),
        (20.0, 30.0),
    )
    n_files = len(next(iter(features["rms"].values())))
    failure_index = n_files - 1
    first_name = files[0].name if files else "?"
    last_name = files[-1].name if files else "?"
    lines = [
        "# IMS Set 2 Z-Score esik kalibrasyonu",
        "",
        "Kaynak: NASA Ames PCoE / University of Cincinnati IMS, Set No. 2 README.",
        f"Kayit: `{first_name}` -> `{last_name}` ({n_files} dosya,",
        f"{SNAPSHOT_INTERVAL_MIN} dk aralik).",
        'Ariza ani: "At the end of the test-to-failure experiment, outer race',
        'failure occurred in bearing 1." — son dosya (index '
        f"{failure_index}); baslangic timestamp'i yok.",
        f"Lead time = (son index - ilk warning) * {SNAPSHOT_INTERVAL_MIN} dk.",
        "RMS egri gozlemi (~index 700) sadece nitel; bu hesaba girmez.",
        f"MA={MA_WINDOW}, BASELINE_WINDOW={BASELINE_WINDOW}.",
        "",
        "FP: NASA'nin hasar duyurmadigi kanallar (bearing_2/3/4) uzerinde,",
        "etiketli kanalin (bearing_1) ilk uyarisindan onceki alarm sayisi.",
        "",
        "## Esik taramasi",
        "",
        "| W / C | b1 ilk W | b1 ilk C | lead (son dosya) | etiketsiz FP |",
        "|---|---:|---:|---|---:|",
    ]
    chosen: dict[tuple[float, float], dict[str, list[DetectionStatus]]] = {}
    for warning, critical in pairs:
        statuses = replay(features, warning=warning, critical=critical)
        if (warning, critical) in ((3.0, 5.0), (5.0, 8.0)):
            chosen[(warning, critical)] = statuses
        b1 = statuses[LABELED_BEARING]
        first_w = _first_alarm(b1)
        first_c = _first_status(b1, DetectionStatus.CRITICAL)
        fp_end = first_w if first_w is not None else n_files
        lines.append(
            "| {w:g}/{c:g} | {fw} | {fc} | {lead} | {fp} |".format(
                w=warning,
                c=critical,
                fw=first_w if first_w is not None else "-",
                fc=first_c if first_c is not None else "-",
                lead=_hours_before(first_w, failure_index),
                fp=_unlabeled_fp(statuses, before=fp_end),
            )
        )

    lines.extend(
        [
            "",
            "## Ilk alarm index (3.0/5.0 vs 5.0/8.0)",
            "",
            "| Esik | bearing_1 | bearing_2 | bearing_3 | bearing_4 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for warning, critical in ((3.0, 5.0), (5.0, 8.0)):
        statuses = chosen[(warning, critical)]
        cells = [str(_first_alarm(statuses[bearing]) or "-") for bearing in BEARINGS]
        lines.append(f"| {warning:g}/{critical:g} | " + " | ".join(cells) + " |")

    selection: list[str] = [
        "",
        "## Secim: 5.0 / 8.0 (ADR-0006)",
        "",
    ]
    old = chosen[(3.0, 5.0)]
    new = chosen[(5.0, 8.0)]
    old_w = _first_alarm(old[LABELED_BEARING])
    new_w = _first_alarm(new[LABELED_BEARING])
    old_fp_end = old_w if old_w is not None else n_files
    new_fp_end = new_w if new_w is not None else n_files
    selection.extend(
        [
            f"- 3.0/5.0: etiketsiz FP={_unlabeled_fp(old, before=old_fp_end)}"
            f" (bearing_2 ilk alarm {_first_alarm(old['bearing_2'])});"
            f" lead {_hours_before(old_w, failure_index)}.",
            f"- 5.0/8.0: etiketsiz FP={_unlabeled_fp(new, before=new_fp_end)};"
            f" bearing_1 ilk warning {new_w};"
            f" lead {_hours_before(new_w, failure_index)}",
            f"  (index {new_w} -> {failure_index}).",
            "- Daha yuksek esikler FP'yi iyilestirmez, lead time'i kisaltir.",
            "- Bu sayilar yalniz Set 2 icindir; Set 1/3 veya baska veri setinde",
            "  esikler yeniden olculmelidir.",
            "",
        ]
    )
    lines.extend(selection)
    return "\n".join(lines) + "\n"


def main() -> None:
    if not DATA_DIR.is_dir() or not _files():
        raise SystemExit(f"IMS dosyası yok: {DATA_DIR}")
    files = _files()
    features = load_features()
    report = summarize(features, files)
    out = OUT_DIR / "ims_set2_zscore_calibration.md"
    out.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
