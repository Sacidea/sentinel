"""IMS domain-invariant IsolationForest — Set 2 egitim, Set 1 test (offline).

Production'a girmez. Canli IF/esik/ADR-0008 degismez. Iki kosu: ham ozellik
transferi vs kanal-ici baseline z-norm (her set kendi warmup'i).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "stream-processor" / "src"))

from stream_processor.domain.detectors import DetectionStatus  # noqa: E402
from stream_processor.domain.features import extract_features  # noqa: E402
from stream_processor.domain.ml_detectors import (  # noqa: E402
    _MIN_VARIANCE,
    _SEVERITY_RANK,
    DEFAULT_ML_CRITICAL_QUANTILE,
    DEFAULT_ML_WARNING_QUANTILE,
    _classify,
    _healthy_thresholds,
)

SET2_FLAT = ROOT / "data" / "ims"
SET2_NESTED = ROOT / "data" / "ims" / "2nd_test"
SET1_DIR = ROOT / "data" / "ims_set1" / "1st_test"
SET2_CACHE = ROOT / "data" / "ims_set2_ml_features.npz"
SET1_CACHE = ROOT / "data" / "ims_set1_ml_features.npz"
OUT_DIR = Path(__file__).resolve().parent
BASELINE_WINDOW = 200
SNAPSHOT_INTERVAL_MIN = 10
FILE_NAME = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{2}$")
FEATURE_KEYS = ("rms", "kurtosis", "crest_factor", "peak")
BEARINGS = ("bearing_1", "bearing_2", "bearing_3", "bearing_4")
SET1_CHANNELS = tuple((bearing, axis) for bearing in BEARINGS for axis in ("x", "y"))
FAILED = frozenset({"bearing_3", "bearing_4"})
HEALTHY = frozenset({"bearing_1", "bearing_2"})
NASA = {
    "bearing_1": "saglikli",
    "bearing_2": "saglikli",
    "bearing_3": "ic bilezik",
    "bearing_4": "makara",
}
N_ESTIMATORS = 64
CONTAMINATION = 0.01
RANDOM_STATE = 0
WARNING_Q = DEFAULT_ML_WARNING_QUANTILE
CRITICAL_Q = DEFAULT_ML_CRITICAL_QUANTILE
MIN_STD = 1e-12
Store = dict[str, dict[str, NDArray[np.float64]]]
StatusMap = dict[tuple[str, str], list[DetectionStatus]]


def _timestamp_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        path for path in directory.iterdir() if path.is_file() and FILE_NAME.match(path.name)
    )


def _set2_dir() -> tuple[Path, list[Path]]:
    nested = _timestamp_files(SET2_NESTED)
    if nested:
        return SET2_NESTED, nested
    flat = _timestamp_files(SET2_FLAT)
    if flat:
        return SET2_FLAT, flat
    raise SystemExit(f"Set 2 dosyasi yok: {SET2_NESTED} veya {SET2_FLAT}")


def _channel_key(bearing: str, axis: str) -> str:
    return f"{bearing}_{axis}"


def _load_cached(path: Path, keys: tuple[str, ...]) -> Store | None:
    if not path.is_file():
        return None
    payload = np.load(path)
    return {feature: {key: payload[f"{feature}_{key}"] for key in keys} for feature in FEATURE_KEYS}


def load_set2() -> tuple[Path, list[Path], Store]:
    directory, files = _set2_dir()
    cached = _load_cached(SET2_CACHE, BEARINGS)
    if cached is not None:
        return directory, files, cached
    n_files = len(files)
    store: Store = {
        feature: {bearing: np.zeros(n_files) for bearing in BEARINGS} for feature in FEATURE_KEYS
    }
    for index, path in enumerate(files):
        samples = np.loadtxt(path, dtype=np.float64)
        if samples.ndim == 1:
            samples = samples.reshape(-1, 1)
        if samples.shape[1] < 4:
            raise SystemExit(f"Set 2 4 kanal beklenir, {samples.shape[1]}: {path.name}")
        for column, bearing in enumerate(BEARINGS):
            features = extract_features(samples[:, column].tolist())
            store["rms"][bearing][index] = features.rms
            store["kurtosis"][bearing][index] = features.kurtosis
            store["crest_factor"][bearing][index] = features.crest_factor
            store["peak"][bearing][index] = features.peak
    np.savez(
        SET2_CACHE,
        **{
            f"{feature}_{bearing}": store[feature][bearing]
            for feature in FEATURE_KEYS
            for bearing in BEARINGS
        },
    )
    return directory, files, store


def load_set1() -> tuple[list[Path], Store]:
    files = _timestamp_files(SET1_DIR)
    if not files:
        raise SystemExit(f"Set 1 dosyasi yok: {SET1_DIR}")
    keys = tuple(_channel_key(*channel) for channel in SET1_CHANNELS)
    cached = _load_cached(SET1_CACHE, keys)
    if cached is not None:
        return files, cached
    n_files = len(files)
    store: Store = {feature: {key: np.zeros(n_files) for key in keys} for feature in FEATURE_KEYS}
    for index, path in enumerate(files):
        samples = np.loadtxt(path, dtype=np.float64)
        if samples.ndim == 1:
            samples = samples.reshape(-1, 1)
        if samples.shape[1] < 8:
            raise SystemExit(f"Set 1 8 kanal beklenir, {samples.shape[1]}: {path.name}")
        for column, (bearing, axis) in enumerate(SET1_CHANNELS):
            features = extract_features(samples[:, column].tolist())
            key = _channel_key(bearing, axis)
            store["rms"][key][index] = features.rms
            store["kurtosis"][key][index] = features.kurtosis
            store["crest_factor"][key][index] = features.crest_factor
            store["peak"][key][index] = features.peak
    np.savez(
        SET1_CACHE,
        **{f"{feature}_{key}": store[feature][key] for feature in FEATURE_KEYS for key in keys},
    )
    return files, store


def matrix_for(store: Store, key: str) -> NDArray[np.float64]:
    return np.column_stack([store[feature][key] for feature in FEATURE_KEYS])


def z_normalize(matrix: NDArray[np.float64], window: int) -> NDArray[np.float64]:
    """Kanal-ici (deger - warmup_mean) / warmup_std. std~0 sutun 0 kalir."""
    warmup = matrix[:window]
    mean = warmup.mean(axis=0)
    std = warmup.std(axis=0)
    safe = np.where(std <= MIN_STD, 1.0, std)
    normalized = (matrix - mean) / safe
    normalized[:, std <= MIN_STD] = 0.0
    return normalized


@dataclass
class FrozenIf:
    scaler: RobustScaler
    forest: IsolationForest
    warning: float
    critical: float
    extent_warning: float
    extent_critical: float

    def classify(self, vector: NDArray[np.float64]) -> DetectionStatus:
        scaled = self.scaler.transform(vector.reshape(1, -1))
        score = float(-self.forest.decision_function(scaled)[0])
        status = _classify(score, self.warning, self.critical)
        extent = float(np.max(np.abs(scaled[0])))
        extent_status = _classify(extent, self.extent_warning, self.extent_critical)
        if _SEVERITY_RANK[extent_status] > _SEVERITY_RANK[status]:
            return extent_status
        return status


def fit_if(train: NDArray[np.float64]) -> FrozenIf:
    """IsolationForestDetector._freeze_forest ile ayni parametreler (zarf acik)."""
    scaler = RobustScaler()
    scaled = scaler.fit_transform(train)
    if float(np.max(np.std(scaled, axis=0))) <= _MIN_VARIANCE:
        raise SystemExit("IF egitimi: olceklenmis varyans yok.")
    forest = IsolationForest(
        n_estimators=N_ESTIMATORS,
        contamination=CONTAMINATION,
        random_state=RANDOM_STATE,
    )
    forest.fit(scaled)
    scores = -forest.decision_function(scaled)
    kwargs = {"warning_quantile": WARNING_Q, "critical_quantile": CRITICAL_Q}
    thresholds = _healthy_thresholds(scores, **kwargs)
    extent_thresholds = _healthy_thresholds(np.max(np.abs(scaled), axis=1), **kwargs)
    if thresholds is None or extent_thresholds is None:
        raise SystemExit("IF nicelik esigi hesaplanamadi.")
    return FrozenIf(
        scaler=scaler,
        forest=forest,
        warning=thresholds[0],
        critical=thresholds[1],
        extent_warning=extent_thresholds[0],
        extent_critical=extent_thresholds[1],
    )


def train_set2(store: Store, *, normalize: bool) -> FrozenIf:
    blocks: list[NDArray[np.float64]] = []
    for bearing in BEARINGS:
        matrix = matrix_for(store, bearing)
        if normalize:
            matrix = z_normalize(matrix, BASELINE_WINDOW)
        blocks.append(matrix[:BASELINE_WINDOW])
    return fit_if(np.vstack(blocks))


def score_set1(model: FrozenIf, store: Store, *, normalize: bool) -> StatusMap:
    statuses: StatusMap = {channel: [] for channel in SET1_CHANNELS}
    n_files = len(next(iter(store["rms"].values())))
    matrices = {channel: matrix_for(store, _channel_key(*channel)) for channel in SET1_CHANNELS}
    if normalize:
        matrices = {
            channel: z_normalize(matrix, BASELINE_WINDOW) for channel, matrix in matrices.items()
        }
    for index in range(n_files):
        for channel in SET1_CHANNELS:
            if index < BASELINE_WINDOW:
                statuses[channel].append(DetectionStatus.WARMING_UP)
                continue
            statuses[channel].append(model.classify(matrices[channel][index]))
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


def _fmt(index: int | None) -> str:
    return str(index) if index is not None else "-"


def _hours_before(index: int | None, failure_index: int) -> str:
    if index is None or index >= failure_index:
        return "-"
    minutes = (failure_index - index) * SNAPSHOT_INTERVAL_MIN
    return f"{minutes / 60:.1f} saat"


def _count_alarms(rows: list[DetectionStatus], start: int, end: int) -> int:
    return sum(
        1
        for value in rows[start:end]
        if value in (DetectionStatus.WARNING, DetectionStatus.CRITICAL)
    )


def _earliest(statuses: StatusMap, bearings: frozenset[str]) -> int | None:
    found = [
        _first_alarm(statuses[(bearing, axis)])
        for bearing, axis in SET1_CHANNELS
        if bearing in bearings
    ]
    present = [index for index in found if index is not None]
    if not present:
        return None
    return min(present)


def _healthy_fp(statuses: StatusMap, *, before: int) -> int:
    return sum(
        _count_alarms(statuses[(bearing, axis)], BASELINE_WINDOW, before)
        for bearing, axis in SET1_CHANNELS
        if bearing in HEALTHY
    )


def _bearing_first(statuses: StatusMap, bearing: str) -> int | None:
    found = [_first_alarm(statuses[(bearing, axis)]) for axis in ("x", "y")]
    present = [index for index in found if index is not None]
    if not present:
        return None
    return min(present)


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _rank_ok(first_failed: int | None, first_healthy: int | None) -> str:
    if first_failed is None:
        return "hayir (arizali sessiz)"
    if first_healthy is None:
        return "evet (saglikli sessiz)"
    if first_failed < first_healthy:
        gap = first_healthy - first_failed
        hours = gap * SNAPSHOT_INTERVAL_MIN / 60.0
        return f"evet ({gap} dosya / {hours:.1f} saat once)"
    return f"hayir (saglikli {first_healthy}, arizali {first_failed})"


def _rank_cell(first_failed: int | None, first_healthy: int | None) -> str:
    if first_failed is None:
        return "hayir"
    if first_healthy is None or first_failed < first_healthy:
        return "evet"
    return "hayir"


def _gap_hours(first_failed: int | None, first_healthy: int | None) -> str:
    if first_failed is None or first_healthy is None or first_failed >= first_healthy:
        return "-"
    return f"{(first_healthy - first_failed) * SNAPSHOT_INTERVAL_MIN / 60.0:.1f} saat"


def _run_block(
    title: str,
    statuses: StatusMap,
    failure_index: int,
) -> list[str]:
    first_failed = _earliest(statuses, FAILED)
    first_healthy = _earliest(statuses, HEALTHY)
    fp_end = first_failed if first_failed is not None else failure_index + 1
    fp_total = _healthy_fp(statuses, before=fp_end)
    lines = [
        f"### {title}",
        "",
        f"Ilk arizali alarm (b3/b4, min x/y): **{_fmt(first_failed)}**.",
        f"Ilk saglikli alarm (b1/b2, min x/y): **{_fmt(first_healthy)}**.",
        f"Siralama (arizali sagliklidan once mi): **{_rank_ok(first_failed, first_healthy)}**.",
        f"Erken FP (saglikli, arizali ilk uyaridan once, warmup haric): **{fp_total}**.",
        "",
        "| Rulman | eksen | NASA | ilk W | ilk C | lead C (son dosya) |",
        "|---|---|---|---:|---:|---|",
    ]
    for bearing, axis in SET1_CHANNELS:
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
            "| Rulman | NASA | ilk alarm (min x/y) |",
            "|---|---|---:|",
        ]
    )
    for bearing in BEARINGS:
        lines.append(f"| {bearing} | {NASA[bearing]} | {_fmt(_bearing_first(statuses, bearing))} |")
    lines.append("")
    return lines


def summarize(
    set2_files: list[Path],
    set1_files: list[Path],
    set2_dir: Path,
    raw: StatusMap,
    normalized: StatusMap,
) -> str:
    n_set1 = len(set1_files)
    failure_index = n_set1 - 1
    raw_failed = _earliest(raw, FAILED)
    raw_healthy = _earliest(raw, HEALTHY)
    raw_fp_end = raw_failed if raw_failed is not None else n_set1
    norm_failed = _earliest(normalized, FAILED)
    norm_healthy = _earliest(normalized, HEALTHY)
    norm_fp_end = norm_failed if norm_failed is not None else n_set1
    raw_fp = _healthy_fp(raw, before=raw_fp_end)
    norm_fp = _healthy_fp(normalized, before=norm_fp_end)

    lines = [
        "# IMS domain-invariant IsolationForest (Set 2 egitim -> Set 1 test)",
        "",
        "Offline hold-out. Canli Kafka/DB yok. Canli IF, nicelik veya ADR-0008 **degismez**.",
        "Referans: `ims_set2_ml_calibration.py` (IF+zarf, 0.995/0.999).",
        "",
        f"Set 2: `{_rel(set2_dir)}` (`{set2_files[0].name}` -> `{set2_files[-1].name}`,",
        f"{len(set2_files)} dosya, 4 kanal x). `data/ims/2nd_test` bossa `data/ims` kullanilir.",
        f"Set 1: `{_rel(SET1_DIR)}` (`{set1_files[0].name}` -> `{set1_files[-1].name}`,",
        f"{n_set1} dosya, 8 kanal x/y). NASA: b3 ic bilezik, b4 makara; b1/b2 saglikli.",
        "Dosya index'i; wall-clock degil. Lead = (son index - ilk C) * 10 dk.",
        "",
        "Ozellik: rms, kurtosis, crest, peak (`extract_features`). FFT IF vektorune girmez.",
        f"Egitim: Set 2 warmup (ilk {BASELINE_WINDOW} * 4 rulman = {BASELINE_WINDOW * 4} vektor).",
        "Tek orman + Set 2'den donmus nicelik esigi; Set 1'de yeniden egitim yok.",
        f"IF: n_estimators={N_ESTIMATORS}, contamination={CONTAMINATION},",
        f"random_state={RANDOM_STATE} (kalibrasyon notebook), RobustScaler, zarf acik,",
        f"Wq/Cq={WARNING_Q:g}/{CRITICAL_Q:g}. Set 1 skorlama index {BASELINE_WINDOW}'den.",
        "",
        "## Iki kosu",
        "",
        "1. **Ham:** Set 2 ham 4-vektorde egit, ayni modeli Set 1 ham 4-vektorde skorla.",
        "2. **Domain-invariant:** her (dataset, rulman, eksen) kendi ilk 200'unden",
        "   mean/std; `(x-mean)/std`. Set 2 kendi baseline'i, Set 1 kendi baseline'i.",
        "   IF normalize Set 2 warmup'ta egitilir, normalize Set 1'de test edilir.",
        "",
        "Dogrulama: mutlak alarm sayisi degil - ilk uyari index'i, siralama",
        "(arizali sagliklidan once mi), erken FP (arizali ilk uyaridan once saglikli).",
        "",
        "## Set 1 ozet (yan yana)",
        "",
        "| Kosul | b3 | b4 | b1 | b2 | siralama | bosluk | erken FP |",
        "|---|---:|---:|---:|---:|---|---|---:|",
        (
            f"| ham | {_fmt(_bearing_first(raw, 'bearing_3'))} | "
            f"{_fmt(_bearing_first(raw, 'bearing_4'))} | "
            f"{_fmt(_bearing_first(raw, 'bearing_1'))} | "
            f"{_fmt(_bearing_first(raw, 'bearing_2'))} | "
            f"{_rank_cell(raw_failed, raw_healthy)} | "
            f"{_gap_hours(raw_failed, raw_healthy)} | {raw_fp} |"
        ),
        (
            f"| normalize | {_fmt(_bearing_first(normalized, 'bearing_3'))} | "
            f"{_fmt(_bearing_first(normalized, 'bearing_4'))} | "
            f"{_fmt(_bearing_first(normalized, 'bearing_1'))} | "
            f"{_fmt(_bearing_first(normalized, 'bearing_2'))} | "
            f"{_rank_cell(norm_failed, norm_healthy)} | "
            f"{_gap_hours(norm_failed, norm_healthy)} | {norm_fp} |"
        ),
        "",
        "## Kanal karnesi (ham vs normalize, yan yana)",
        "",
        "| Rulman | eksen | NASA | ham W | ham C | norm W | norm C |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for bearing, axis in SET1_CHANNELS:
        ham = raw[(bearing, axis)]
        norm = normalized[(bearing, axis)]
        lines.append(
            f"| {bearing} | {axis} | {NASA[bearing]} | "
            f"{_fmt(_first_status(ham, DetectionStatus.WARNING))} | "
            f"{_fmt(_first_status(ham, DetectionStatus.CRITICAL))} | "
            f"{_fmt(_first_status(norm, DetectionStatus.WARNING))} | "
            f"{_fmt(_first_status(norm, DetectionStatus.CRITICAL))} |"
        )
    lines.extend(["", "## Set 1 karneleri (ayri)", ""])
    lines.extend(_run_block("Ham transfer", raw, failure_index))
    lines.extend(_run_block("Domain-invariant (z-norm)", normalized, failure_index))

    lines.extend(
        [
            "## Hold-out yorumu (esik degismez)",
            "",
            "- Beklenti (ham IF saglikli b2'yi erken/cok yakalar; z-norm arizaliyi ayirir)",
            "  **tutmadi**. Esik retune yok; asagisi gozlem.",
            f"- Ham: b1 sessiz, b2 yalniz {_fmt(raw_healthy)} (test sonu). Arizali ilk "
            f"{_fmt(raw_failed)} (b4). Siralama boslugu {_gap_hours(raw_failed, raw_healthy)}; "
            f"erken FP={raw_fp}.",
            f"- Normalize: b3={_fmt(_bearing_first(normalized, 'bearing_3'))}, "
            f"b4={_fmt(_bearing_first(normalized, 'bearing_4'))}, "
            f"b1={_fmt(_bearing_first(normalized, 'bearing_1'))}, "
            f"b2={_fmt(_bearing_first(normalized, 'bearing_2'))} "
            f"(hepsi warmup+kisa pencere). Siralama evet ama bosluk "
            f"{_gap_hours(norm_failed, norm_healthy)}. Erken FP={norm_fp} tanim icindir",
            "  (saglikli, arizalidan *sonra* calar; ayirim kucuk).",
            "- Normalize 'daha erken lead' warmup-kenari: ADR-0008'in eledigi 204-217",
            "  sahte erken ile ayni sinif. Mutlak olcek z-norm ile silinince her kanal",
            "  kucuk sapmada aykiri gorunur.",
            "- Ham kosuda mutlak RMS/peak Set 2 ormanina tasiyor; saglikli Set 1 bu",
            "  bulutta kaliyor, arizali (ozellikle b4/y) cikiyor. Bu, z-norm'un",
            "  cozmesi beklenen 'domain kaymasi'nin bu ciftte felaket olmadigini gosterir.",
            "- Bu karne secim tablosu degil. 0.995/0.999 Set 1'e uydurulmadi.",
            "- Per-kanal canli IF (her seri kendi warmup ormani) bu deney degil;",
            "  burada **tek** Set 2 ormani Set 1'e tasindi.",
            "- Canli detector, event semasi veya ADR-0008 bu hold-out ile degismez.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    set2_dir, set2_files, set2_store = load_set2()
    set1_files, set1_store = load_set1()
    raw_model = train_set2(set2_store, normalize=False)
    norm_model = train_set2(set2_store, normalize=True)
    raw = score_set1(raw_model, set1_store, normalize=False)
    normalized = score_set1(norm_model, set1_store, normalize=True)
    report = summarize(set2_files, set1_files, set2_dir, raw, normalized)
    out = OUT_DIR / "ims_domain_invariant_if.md"
    out.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
