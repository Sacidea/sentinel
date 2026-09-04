"""IMS Set 1 Z-Score hold-out — Set 2 5.0/8.0 kilit; retune yok (ADR-0006).

Production'a girmez. Ham `data/ims_set1/1st_test` dosya index'i; wall-clock yok.
ML yok. x ve y ayri seri. Lead time NASA test sonuna (son dosya) gore.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "stream-processor" / "src"))

from stream_processor.domain.detectors import (  # noqa: E402
    DEFAULT_ZSCORE_CRITICAL,
    DEFAULT_ZSCORE_WARNING,
    DetectionStatus,
    ZScoreDetector,
)
from stream_processor.domain.features import SignalFeatures, extract_features  # noqa: E402

DATA_DIR = ROOT / "data" / "ims_set1" / "1st_test"
CACHE_PATH = ROOT / "data" / "ims_set1_zscore_features.npz"
OUT_DIR = Path(__file__).resolve().parent
BASELINE_WINDOW = 200
MA_WINDOW = 5
WARNING = DEFAULT_ZSCORE_WARNING
CRITICAL = DEFAULT_ZSCORE_CRITICAL
BEARINGS = ("bearing_1", "bearing_2", "bearing_3", "bearing_4")
AXES = ("x", "y")
CHANNELS = tuple((bearing, axis) for bearing in BEARINGS for axis in AXES)
FILE_NAME = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{2}$")
SNAPSHOT_INTERVAL_MIN = 10
FAILED = frozenset({"bearing_3", "bearing_4"})
HEALTHY = frozenset({"bearing_1", "bearing_2"})
NASA = {
    "bearing_1": "saglikli",
    "bearing_2": "saglikli",
    "bearing_3": "ic bilezik",
    "bearing_4": "makara",
}


def _files() -> list[Path]:
    if not DATA_DIR.is_dir():
        raise SystemExit(f"IMS Set 1 klasoru yok: {DATA_DIR}")
    files = sorted(
        path for path in DATA_DIR.iterdir() if path.is_file() and FILE_NAME.match(path.name)
    )
    if not files:
        raise SystemExit(f"Set 1 dosyasi yok: {DATA_DIR}")
    return files


def _channel_key(bearing: str, axis: str) -> str:
    return f"{bearing}_{axis}"


def load_features() -> dict[str, dict[str, np.ndarray]]:
    if CACHE_PATH.is_file():
        payload = np.load(CACHE_PATH)
        return {
            "rms": {key: payload[f"rms_{key}"] for key in (_channel_key(*ch) for ch in CHANNELS)},
            "kurtosis": {
                key: payload[f"kurt_{key}"] for key in (_channel_key(*ch) for ch in CHANNELS)
            },
        }

    files = _files()
    n_files = len(files)
    rms = {_channel_key(*ch): np.zeros(n_files) for ch in CHANNELS}
    kurtosis = {_channel_key(*ch): np.zeros(n_files) for ch in CHANNELS}
    for index, path in enumerate(files):
        samples = np.loadtxt(path, dtype=np.float64)
        if samples.ndim == 1:
            samples = samples.reshape(-1, 1)
        if samples.shape[1] < 8:
            raise SystemExit(f"Set 1 8 kanal beklenir, {samples.shape[1]}: {path.name}")
        for column, (bearing, axis) in enumerate(CHANNELS):
            features = extract_features(samples[:, column].tolist())
            key = _channel_key(bearing, axis)
            rms[key][index] = features.rms
            kurtosis[key][index] = features.kurtosis
    np.savez(
        CACHE_PATH,
        **{f"rms_{key}": rms[key] for key in rms},
        **{f"kurt_{key}": kurtosis[key] for key in kurtosis},
    )
    return {"rms": rms, "kurtosis": kurtosis}


def replay(
    features: dict[str, dict[str, np.ndarray]],
) -> dict[tuple[str, str], list[DetectionStatus]]:
    n_files = len(next(iter(features["rms"].values())))
    statuses: dict[tuple[str, str], list[DetectionStatus]] = {ch: [] for ch in CHANNELS}
    detectors = {
        channel: ZScoreDetector(
            baseline_window=BASELINE_WINDOW,
            ma_window=MA_WINDOW,
            warning_threshold=WARNING,
            critical_threshold=CRITICAL,
        )
        for channel in CHANNELS
    }
    for index in range(n_files):
        for bearing, axis in CHANNELS:
            key = _channel_key(bearing, axis)
            result = detectors[(bearing, axis)].observe(
                bearing,
                axis,
                SignalFeatures(
                    rms=float(features["rms"][key][index]),
                    kurtosis=float(features["kurtosis"][key][index]),
                    crest_factor=0.0,
                    peak=0.0,
                ),
                dataset="set1",
            )
            statuses[(bearing, axis)].append(result.status)
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


def _hours_before(index: int | None, failure_index: int) -> str:
    if index is None or index >= failure_index:
        return "-"
    minutes = (failure_index - index) * SNAPSHOT_INTERVAL_MIN
    return f"{minutes / 60:.1f} saat"


def _fmt(index: int | None) -> str:
    return str(index) if index is not None else "-"


def _count_alarms(rows: list[DetectionStatus], start: int, end: int) -> int:
    return sum(
        1
        for value in rows[start:end]
        if value in (DetectionStatus.WARNING, DetectionStatus.CRITICAL)
    )


def _earliest_failed_alarm(statuses: dict[tuple[str, str], list[DetectionStatus]]) -> int | None:
    indexes = [
        _first_alarm(statuses[(bearing, axis)]) for bearing, axis in CHANNELS if bearing in FAILED
    ]
    found = [index for index in indexes if index is not None]
    if not found:
        return None
    return min(found)


def _healthy_fp_before(
    statuses: dict[tuple[str, str], list[DetectionStatus]],
    *,
    before: int,
) -> dict[tuple[str, str], int]:
    return {
        (bearing, axis): _count_alarms(statuses[(bearing, axis)], BASELINE_WINDOW, before)
        for bearing, axis in CHANNELS
        if bearing in HEALTHY
    }


def summarize(
    files: list[Path],
    statuses: dict[tuple[str, str], list[DetectionStatus]],
) -> str:
    n_files = len(files)
    failure_index = n_files - 1
    first_name = files[0].name
    last_name = files[-1].name
    anchor = _earliest_failed_alarm(statuses)
    fp_end = anchor if anchor is not None else n_files
    healthy_fp = _healthy_fp_before(statuses, before=fp_end)
    fp_total = sum(healthy_fp.values())
    b3x = statuses[("bearing_3", "x")]
    b4x = statuses[("bearing_4", "x")]
    b3x_w = _first_status(b3x, DetectionStatus.WARNING)
    b3x_c = _first_status(b3x, DetectionStatus.CRITICAL)
    b4x_w = _first_status(b4x, DetectionStatus.WARNING)
    b4x_c = _first_status(b4x, DetectionStatus.CRITICAL)

    lines = [
        "# IMS Set 1 Z-Score hold-out (Set 2 5.0/8.0 kilit)",
        "",
        "Kaynak: NASA Ames PCoE / University of Cincinnati IMS, 1st_test README.",
        f"Kayit: `{first_name}` -> `{last_name}` ({n_files} dosya,",
        f"resmi aralik {SNAPSHOT_INTERVAL_MIN} dk; lead = dosya index farki,",
        "wall-clock degil — isim tarihleri arasinda bosluk olabilir).",
        "NASA: bearing_3 ic bilezik, bearing_4 makara (bilye); bearing_1/2 saglikli.",
        "Incipient timestamp yok — ariza capani **son dosya** (Set 2 ile ayni protokol).",
        f"Lead time = (son index - ilk critical) * {SNAPSHOT_INTERVAL_MIN} dk.",
        "Ilk warning ayri kolon; lead hesabina girmez (istek: ilk critical).",
        f"MA={MA_WINDOW}, BASELINE_WINDOW={BASELINE_WINDOW}.",
        f"Esik **kilit**: warning={WARNING:g} / critical={CRITICAL:g} (ADR-0006, yalniz Set 2",
        "kalibrasyonu). Set 1'e retune **yok**. ML yok.",
        "Ham dosya index'i; canli DB/Kafka/wall-clock yok. x ve y ayri seri.",
        "Birincil protokol **X** (Set 2 tek ivmeolcer analogu); Y ayri satir.",
        "",
        "FP: saglikli kanallar (bearing_1/2, her eksen) uzerinde, arizali grubun",
        "(bearing_3/4, herhangi bir eksen) **ilk uyarisindan** onceki alarm.",
        "",
        "## Set 2 karnesi formati (5.0/8.0 kilit, tarama yok)",
        "",
        "| W/C | b3x W | b3x C | lead C b3x | b4x W | b4x C | lead C b4x | saglikli FP |",
        "|---|---:|---:|---|---:|---:|---|---:|",
        (
            f"| {WARNING:g}/{CRITICAL:g} | {_fmt(b3x_w)} | {_fmt(b3x_c)} | "
            f"{_hours_before(b3x_c, failure_index)} | {_fmt(b4x_w)} | {_fmt(b4x_c)} | "
            f"{_hours_before(b4x_c, failure_index)} | {fp_total} |"
        ),
        "",
        "## 5.0 / 8.0 — kanal karnesi",
        "",
        "| Rulman | eksen | NASA | ilk W | ilk C | lead (ilk C, son dosya) |",
        "|---|---|---|---:|---:|---|",
    ]
    for bearing, axis in CHANNELS:
        rows = statuses[(bearing, axis)]
        first_w = _first_status(rows, DetectionStatus.WARNING)
        first_c = _first_status(rows, DetectionStatus.CRITICAL)
        lead = _hours_before(first_c, failure_index) if bearing in FAILED else "N/A (saglikli)"
        lines.append(
            f"| {bearing} | {axis} | {NASA[bearing]} | {_fmt(first_w)} | {_fmt(first_c)} | {lead} |"
        )

    lines.extend(
        [
            "",
            "## Erken FP (saglikli, arizalidan once)",
            "",
            f"Arizali grubun ilk uyarisi (b3/b4, min x/y): **{_fmt(anchor)}**",
            f"(index {BASELINE_WINDOW}..{fp_end} arasi sayilir; warmup haric).",
            f"Saglikli toplam erken alarm: **{fp_total}**.",
            "",
            "| Rulman | eksen | ilk alarm | erken FP sayisi | arizalidan once? |",
            "|---|---|---:|---:|---|",
        ]
    )
    for bearing, axis in CHANNELS:
        if bearing not in HEALTHY:
            continue
        first = _first_alarm(statuses[(bearing, axis)])
        count = healthy_fp[(bearing, axis)]
        early = "evet" if count > 0 else "hayir"
        lines.append(f"| {bearing} | {axis} | {_fmt(first)} | {count} | {early} |")

    failed_first = {
        (bearing, axis): _first_status(statuses[(bearing, axis)], DetectionStatus.WARNING)
        for bearing, axis in CHANNELS
        if bearing in FAILED
    }
    lines.extend(
        [
            "",
            "## Arizali kanallar — ilk uyari vs son dosya",
            "",
            f"Son dosya index: **{failure_index}** (`{last_name}`).",
            "",
            "| Rulman | eksen | ilk W | ilk C | lead W | lead C |",
            "|---|---|---:|---:|---|---|",
        ]
    )
    for bearing, axis in CHANNELS:
        if bearing not in FAILED:
            continue
        rows = statuses[(bearing, axis)]
        first_w = failed_first[(bearing, axis)]
        first_c = _first_status(rows, DetectionStatus.CRITICAL)
        lead_w = _hours_before(first_w, failure_index)
        lead_c = _hours_before(first_c, failure_index)
        lines.append(
            f"| {bearing} | {axis} | {_fmt(first_w)} | {_fmt(first_c)} | {lead_w} | {lead_c} |"
        )

    b3y_c = _first_status(statuses[("bearing_3", "y")], DetectionStatus.CRITICAL)
    lines.extend(
        [
            "",
            "## Hold-out yorumu (esik degismez)",
            "",
            "- Bu karne **secim tablosu degil**. 5.0/8.0 Set 2'de kaldi (ADR-0006);",
            "  Set 1'e uydurmak overfitting olur.",
            f"- Saglikli erken FP (b1/b2, arizali ilk uyaridan once): {fp_total}.",
            f"- b4/x ilk warning {_fmt(b4x_w)}; ilk critical {_fmt(b4x_c)}"
            f" ({_hours_before(b4x_c, failure_index)}).",
            "  Warning-critical boslugu buyuk olabilir; esik yine degistirilmedi.",
            f"- b3/x critical lead {_hours_before(b3x_c, failure_index)};"
            f" b3/y {_hours_before(b3y_c, failure_index)} (eksenler karismaz).",
            "- Lead time yalniz NASA'nin hasar duyurdugu rulmanlar (b3, b4) icin",
            "  son dosyaya gore raporlanir; sagliklida 'lead' anlamsizdir.",
            "- Canli esik, detector veya event semasi bu hold-out ile degismez.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    files = _files()
    features = load_features()
    statuses = replay(features)
    report = summarize(files, statuses)
    out = OUT_DIR / "ims_set1_zscore.md"
    out.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
