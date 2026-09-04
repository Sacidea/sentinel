"""IMS Set 2 IsolationForest / PCA kalibrasyonu — atılabilir (ADR-0006 protokolü).

Production'a girmez. Lead time NASA README arıza anına (test sonu, son dosya) göredir.
Etiketsiz FP: bearing_2/3/4, bearing_1 ilk uyarısından önce.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "stream-processor" / "src"))

from stream_processor.domain.detectors import DetectionStatus  # noqa: E402
from stream_processor.domain.features import SignalFeatures, extract_features  # noqa: E402
from stream_processor.domain.ml_detectors import IsolationForestDetector, PcaDetector  # noqa: E402
from stream_processor.ports.detector import AnomalyDetector  # noqa: E402

DATA_DIR = ROOT / "data" / "ims"
CACHE_PATH = ROOT / "data" / "ims_set2_ml_features.npz"
OUT_DIR = Path(__file__).resolve().parent
BASELINE_WINDOW = 200
BEARINGS = ("bearing_1", "bearing_2", "bearing_3", "bearing_4")
FILE_NAME = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{2}$")
SNAPSHOT_INTERVAL_MIN = 10
LABELED_BEARING = "bearing_1"
ZSCORE_LEAD_HOURS = 74.5
ZSCORE_FP = 0
ZSCORE_FIRST_WARNING = 536

QUANTILE_PAIRS: tuple[tuple[float, float], ...] = (
    (0.90, 0.99),
    (0.95, 0.99),
    (0.99, 0.995),
    (0.99, 0.999),
    (0.995, 0.999),
    (0.999, 0.999),
)


def _files() -> list[Path]:
    return sorted(
        path for path in DATA_DIR.iterdir() if path.is_file() and FILE_NAME.match(path.name)
    )


def load_features() -> dict[str, dict[str, np.ndarray]]:
    if CACHE_PATH.is_file():
        payload = np.load(CACHE_PATH)
        return {
            key: {bearing: payload[f"{key}_{bearing}"] for bearing in BEARINGS}
            for key in ("rms", "kurtosis", "crest_factor", "peak")
        }

    files = _files()
    n_files = len(files)
    store = {
        key: {bearing: np.zeros(n_files) for bearing in BEARINGS}
        for key in ("rms", "kurtosis", "crest_factor", "peak")
    }
    for index, path in enumerate(files):
        samples = np.loadtxt(path, dtype=np.float64)
        if samples.ndim == 1:
            samples = samples.reshape(-1, 1)
        for column, bearing in enumerate(BEARINGS):
            features = extract_features(samples[:, column].tolist())
            store["rms"][bearing][index] = features.rms
            store["kurtosis"][bearing][index] = features.kurtosis
            store["crest_factor"][bearing][index] = features.crest_factor
            store["peak"][bearing][index] = features.peak
    np.savez(
        CACHE_PATH,
        **{f"{key}_{bearing}": store[key][bearing] for key in store for bearing in BEARINGS},
    )
    return store


def _features_at(
    store: dict[str, dict[str, np.ndarray]], bearing: str, index: int
) -> SignalFeatures:
    return SignalFeatures(
        rms=float(store["rms"][bearing][index]),
        kurtosis=float(store["kurtosis"][bearing][index]),
        crest_factor=float(store["crest_factor"][bearing][index]),
        peak=float(store["peak"][bearing][index]),
    )


def replay(
    store: dict[str, dict[str, np.ndarray]],
    factory: Callable[[], AnomalyDetector],
) -> dict[str, list[DetectionStatus]]:
    n_files = len(next(iter(store["rms"].values())))
    statuses: dict[str, list[DetectionStatus]] = {bearing: [] for bearing in BEARINGS}
    detectors = {bearing: factory() for bearing in BEARINGS}
    for index in range(n_files):
        for bearing in BEARINGS:
            result = detectors[bearing].observe(bearing, "x", _features_at(store, bearing, index))
            statuses[bearing].append(result.status)
    return statuses


def _first_status(rows: list[DetectionStatus], status: DetectionStatus) -> int | None:
    for index, value in enumerate(rows):
        if value is status:
            return index
    return None


def _first_alarm(rows: list[DetectionStatus]) -> int | None:
    warning = _first_status(rows, DetectionStatus.WARNING)
    critical = _first_status(rows, DetectionStatus.CRITICAL)
    candidates = [index for index in (warning, critical) if index is not None]
    if not candidates:
        return None
    return min(candidates)


def _count_alarms(rows: list[DetectionStatus], start: int, end: int) -> int:
    return sum(
        1
        for value in rows[start:end]
        if value in (DetectionStatus.WARNING, DetectionStatus.CRITICAL)
    )


def _unlabeled_fp(statuses: dict[str, list[DetectionStatus]], *, before: int) -> int:
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


def _hours_value(index: int | None, failure_index: int) -> float | None:
    if index is None or index >= failure_index:
        return None
    return (failure_index - index) * SNAPSHOT_INTERVAL_MIN / 60.0


def _scan_table(
    store: dict[str, dict[str, np.ndarray]],
    *,
    title: str,
    factory_for: Callable[[float, float], Callable[[], AnomalyDetector]],
) -> tuple[list[str], dict[tuple[float, float], dict[str, list[DetectionStatus]]]]:
    n_files = len(next(iter(store["rms"].values())))
    failure_index = n_files - 1
    lines = [
        f"## {title}",
        "",
        "| Wq / Cq | b1 ilk W | b1 ilk C | lead (son dosya) | etiketsiz FP |",
        "|---|---:|---:|---|---:|",
    ]
    chosen: dict[tuple[float, float], dict[str, list[DetectionStatus]]] = {}
    for warning_q, critical_q in QUANTILE_PAIRS:
        statuses = replay(store, factory_for(warning_q, critical_q))
        chosen[(warning_q, critical_q)] = statuses
        b1 = statuses[LABELED_BEARING]
        first_w = _first_alarm(b1)
        first_c = _first_status(b1, DetectionStatus.CRITICAL)
        fp_end = first_w if first_w is not None else n_files
        lines.append(
            "| {wq:g}/{cq:g} | {fw} | {fc} | {lead} | {fp} |".format(
                wq=warning_q,
                cq=critical_q,
                fw=first_w if first_w is not None else "-",
                fc=first_c if first_c is not None else "-",
                lead=_hours_before(first_w, failure_index),
                fp=_unlabeled_fp(statuses, before=fp_end),
            )
        )
    lines.append("")
    return lines, chosen


def summarize(store: dict[str, dict[str, np.ndarray]], files: list[Path]) -> str:
    n_files = len(next(iter(store["rms"].values())))
    failure_index = n_files - 1
    first_name = files[0].name if files else "?"
    last_name = files[-1].name if files else "?"
    lines = [
        "# IMS Set 2 IsolationForest / PCA kalibrasyonu",
        "",
        "Kaynak: NASA Ames PCoE / University of Cincinnati IMS, Set No. 2 README.",
        f"Kayit: `{first_name}` -> `{last_name}` ({n_files} dosya,",
        f"{SNAPSHOT_INTERVAL_MIN} dk aralik). Gercek Set 2 dosyalari; sentetik vektor yok.",
        'Ariza ani: "At the end of the test-to-failure experiment, outer race',
        'failure occurred in bearing 1." — son dosya (index '
        f"{failure_index}); baslangic timestamp'i yok.",
        f"Lead time = (son index - ilk warning) * {SNAPSHOT_INTERVAL_MIN} dk.",
        f"BASELINE_WINDOW={BASELINE_WINDOW}. Ozellikler: rms, kurtosis, crest, peak.",
        "Esik: egitim skorlarinin niceligi (carpan yok). `score > nicelik`.",
        "",
        "FP: NASA'nin hasar duyurmadigi kanallar (bearing_2/3/4) uzerinde,",
        "etiketli kanalin (bearing_1) ilk uyarisindan onceki alarm sayisi.",
        "",
        "Z-Score referansi (ADR-0006, 5.0/8.0): "
        f"lead {ZSCORE_LEAD_HOURS} saat (index {ZSCORE_FIRST_WARNING}), "
        f"etiketsiz FP={ZSCORE_FP}.",
        "",
    ]

    if_extent_lines, if_extent = _scan_table(
        store,
        title="IsolationForest (skor + olceklenmis max-norm zarf, nicelik)",
        factory_for=lambda wq, cq: (
            lambda: IsolationForestDetector(
                baseline_window=BASELINE_WINDOW,
                random_state=0,
                warning_quantile=wq,
                critical_quantile=cq,
                use_extent=True,
            )
        ),
    )
    if_score_lines, if_score = _scan_table(
        store,
        title="IsolationForest (yalniz decision_function niceligi, zarf yok)",
        factory_for=lambda wq, cq: (
            lambda: IsolationForestDetector(
                baseline_window=BASELINE_WINDOW,
                random_state=0,
                warning_quantile=wq,
                critical_quantile=cq,
                use_extent=False,
            )
        ),
    )
    pca_lines, pca = _scan_table(
        store,
        title="PCA Hotelling T2 / SPE (nicelik)",
        factory_for=lambda wq, cq: (
            lambda: PcaDetector(
                baseline_window=BASELINE_WINDOW,
                n_components=2,
                warning_quantile=wq,
                critical_quantile=cq,
            )
        ),
    )
    lines.extend(if_extent_lines)
    lines.extend(if_score_lines)
    lines.extend(pca_lines)

    default_pair = (0.995, 0.999)
    lines.extend(
        [
            "## Ilk alarm index (0.995 / 0.999)",
            "",
            "| Model | bearing_1 | bearing_2 | bearing_3 | bearing_4 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for name, chosen in (
        ("IF+zarf", if_extent),
        ("IF skor", if_score),
        ("PCA", pca),
    ):
        statuses = chosen[default_pair]
        cells = [str(_first_alarm(statuses[bearing]) or "-") for bearing in BEARINGS]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")

    def _row(name: str, statuses: dict[str, list[DetectionStatus]]) -> str:
        first = _first_alarm(statuses[LABELED_BEARING])
        fp_end = first if first is not None else n_files
        lead = _hours_value(first, failure_index)
        lead_s = f"{lead:.1f}" if lead is not None else "-"
        delta = ""
        if lead is not None:
            earlier = lead - ZSCORE_LEAD_HOURS
            delta = f" (Z-Score'a gore {earlier:+.1f} saat)"
        return (
            f"- {name}: b1 ilk alarm {first}; lead {lead_s} saat{delta}; "
            f"etiketsiz FP={_unlabeled_fp(statuses, before=fp_end)}."
        )

    lines.extend(
        [
            "",
            "## Z-Score ile karsilastirma (0.995 / 0.999)",
            "",
            f"- Z-Score 5.0/8.0: b1 ilk alarm {ZSCORE_FIRST_WARNING}; "
            f"lead {ZSCORE_LEAD_HOURS} saat; etiketsiz FP={ZSCORE_FP}.",
            _row("IF+zarf", if_extent[default_pair]),
            _row("IF skor", if_score[default_pair]),
            _row("PCA", pca[default_pair]),
            "",
            "Secim asagida taramaya gore doldurulur; bu script sonucu yazmadan",
            "'ML katmani bitti' denmez.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    if not DATA_DIR.is_dir() or not _files():
        raise SystemExit(f"IMS dosyasi yok: {DATA_DIR}")
    files = _files()
    store = load_features()
    report = summarize(store, files)
    out = OUT_DIR / "ims_set2_ml_calibration.md"
    out.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
