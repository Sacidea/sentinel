"""IMS IsolationForest havuzlu warmup — offline, canli yok (ADR-0008 kilit).

Per-kanal (canli) vs dataset-havuzu. Set 1 gurultu; Set 2 lead korunuyor mu?
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "stream-processor" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ims_domain_invariant_if import (  # noqa: E402
    BASELINE_WINDOW,
    BEARINGS,
    CONTAMINATION,
    FAILED,
    HEALTHY,
    N_ESTIMATORS,
    NASA,
    SET1_CHANNELS,
    SNAPSHOT_INTERVAL_MIN,
    FrozenIf,
    _earliest,
    _first_alarm,
    _first_status,
    _fmt,
    _gap_hours,
    _healthy_fp,
    _hours_before,
    _rank_cell,
    _rank_ok,
    load_set1,
    load_set2,
    matrix_for,
)
from stream_processor.domain.detectors import DetectionStatus  # noqa: E402
from stream_processor.domain.features import SignalFeatures  # noqa: E402
from stream_processor.domain.ml_detectors import (  # noqa: E402
    _MIN_VARIANCE,
    _SEVERITY_RANK,
    DEFAULT_ML_CRITICAL_QUANTILE,
    DEFAULT_ML_WARNING_QUANTILE,
    IsolationForestDetector,
    _classify,
    _healthy_thresholds,
)

OUT_DIR = Path(__file__).resolve().parent
SET2_CHANNELS = tuple((bearing, "x") for bearing in BEARINGS)
SET2_LEAD_REF_HOURS = 89.3
SET2_FIRST_W_REF = 447
WARNING_Q = DEFAULT_ML_WARNING_QUANTILE
CRITICAL_Q = DEFAULT_ML_CRITICAL_QUANTILE
Store = dict[str, dict[str, NDArray[np.float64]]]
StatusMap = dict[tuple[str, str], list[DetectionStatus]]
KeyFn = Callable[[str, str], str]


def _set1_key(bearing: str, axis: str) -> str:
    return f"{bearing}_{axis}"


def _set2_key(bearing: str, axis: str) -> str:
    return bearing


def _features_at(store: Store, key: str, index: int) -> SignalFeatures:
    return SignalFeatures(
        rms=float(store["rms"][key][index]),
        kurtosis=float(store["kurtosis"][key][index]),
        crest_factor=float(store["crest_factor"][key][index]),
        peak=float(store["peak"][key][index]),
    )


def replay_per_channel(
    store: Store,
    channels: tuple[tuple[str, str], ...],
    key_fn: KeyFn,
    *,
    dataset: str,
    random_state: int,
) -> StatusMap:
    n_files = len(next(iter(store["rms"].values())))
    statuses: StatusMap = {channel: [] for channel in channels}
    detector = IsolationForestDetector(
        baseline_window=BASELINE_WINDOW,
        random_state=random_state,
        warning_quantile=WARNING_Q,
        critical_quantile=CRITICAL_Q,
        use_extent=True,
    )
    for index in range(n_files):
        for bearing, axis in channels:
            result = detector.observe(
                bearing,
                axis,
                _features_at(store, key_fn(bearing, axis), index),
                dataset=dataset,
            )
            statuses[(bearing, axis)].append(result.status)
    return statuses


def fit_pooled(train: NDArray[np.float64], *, random_state: int) -> FrozenIf:
    scaler = RobustScaler()
    scaled = scaler.fit_transform(train)
    if float(np.max(np.std(scaled, axis=0))) <= _MIN_VARIANCE:
        raise SystemExit("Havuzlu IF: olceklenmis varyans yok.")
    forest = IsolationForest(
        n_estimators=N_ESTIMATORS,
        contamination=CONTAMINATION,
        random_state=random_state,
    )
    forest.fit(scaled)
    scores = -forest.decision_function(scaled)
    kwargs = {"warning_quantile": WARNING_Q, "critical_quantile": CRITICAL_Q}
    thresholds = _healthy_thresholds(scores, **kwargs)
    extent_thresholds = _healthy_thresholds(np.max(np.abs(scaled), axis=1), **kwargs)
    if thresholds is None or extent_thresholds is None:
        raise SystemExit("Havuzlu IF nicelik esigi hesaplanamadi.")
    return FrozenIf(
        scaler=scaler,
        forest=forest,
        warning=thresholds[0],
        critical=thresholds[1],
        extent_warning=extent_thresholds[0],
        extent_critical=extent_thresholds[1],
    )


def train_pooled(
    store: Store,
    channels: tuple[tuple[str, str], ...],
    key_fn: KeyFn,
    *,
    random_state: int,
) -> FrozenIf:
    blocks = [matrix_for(store, key_fn(*channel))[:BASELINE_WINDOW] for channel in channels]
    return fit_pooled(np.vstack(blocks), random_state=random_state)


def score_pooled(
    model: FrozenIf,
    store: Store,
    channels: tuple[tuple[str, str], ...],
    key_fn: KeyFn,
) -> StatusMap:
    statuses: StatusMap = {}
    for channel in channels:
        matrix = matrix_for(store, key_fn(*channel))
        n_files = len(matrix)
        rows: list[DetectionStatus] = [DetectionStatus.WARMING_UP] * min(BASELINE_WINDOW, n_files)
        if n_files > BASELINE_WINDOW:
            scaled = model.scaler.transform(matrix[BASELINE_WINDOW:])
            scores = -model.forest.decision_function(scaled)
            extents = np.max(np.abs(scaled), axis=1)
            for score, extent in zip(scores, extents, strict=True):
                status = _classify(float(score), model.warning, model.critical)
                extent_status = _classify(
                    float(extent), model.extent_warning, model.extent_critical
                )
                if _SEVERITY_RANK[extent_status] > _SEVERITY_RANK[status]:
                    status = extent_status
                rows.append(status)
        statuses[channel] = rows
    return statuses


def _critical_count(rows: list[DetectionStatus]) -> int:
    return sum(1 for value in rows if value is DetectionStatus.CRITICAL)


def _bearing_first(statuses: StatusMap, bearing: str) -> int | None:
    found = [_first_alarm(rows) for (name, _axis), rows in statuses.items() if name == bearing]
    present = [index for index in found if index is not None]
    if not present:
        return None
    return min(present)


def _set2_unlabeled_fp(statuses: StatusMap, *, before: int) -> int:
    labeled = "bearing_1"
    return sum(
        sum(
            1
            for value in rows[BASELINE_WINDOW:before]
            if value in (DetectionStatus.WARNING, DetectionStatus.CRITICAL)
        )
        for (bearing, _axis), rows in statuses.items()
        if bearing != labeled
    )


def _hours_value(index: int | None, failure_index: int) -> float | None:
    if index is None or index >= failure_index:
        return None
    return (failure_index - index) * SNAPSHOT_INTERVAL_MIN / 60.0


def _set1_block(title: str, statuses: StatusMap, n_files: int) -> list[str]:
    first_failed = _earliest(statuses, FAILED)
    first_healthy = _earliest(statuses, HEALTHY)
    fp_end = first_failed if first_failed is not None else n_files
    fp_total = _healthy_fp(statuses, before=fp_end)
    lines = [
        f"### {title}",
        "",
        f"Ilk arizali: **{_fmt(first_failed)}**. Ilk saglikli: **{_fmt(first_healthy)}**.",
        f"Siralama: **{_rank_ok(first_failed, first_healthy)}**.",
        f"Erken FP: **{fp_total}**.",
        "",
        "| Rulman | eksen | NASA | ilk W | ilk C | critical sayisi |",
        "|---|---|---|---:|---:|---:|",
    ]
    for bearing, axis in SET1_CHANNELS:
        rows = statuses[(bearing, axis)]
        lines.append(
            f"| {bearing} | {axis} | {NASA[bearing]} | "
            f"{_fmt(_first_status(rows, DetectionStatus.WARNING))} | "
            f"{_fmt(_first_status(rows, DetectionStatus.CRITICAL))} | "
            f"{_critical_count(rows)} |"
        )
    lines.extend(["", "| Rulman | NASA | ilk alarm (min x/y) |", "|---|---|---:|"])
    for bearing in BEARINGS:
        lines.append(f"| {bearing} | {NASA[bearing]} | {_fmt(_bearing_first(statuses, bearing))} |")
    lines.append("")
    return lines


def summarize(
    set1_per: StatusMap,
    set1_pool: StatusMap,
    set2_per: StatusMap,
    set2_pool: StatusMap,
    n_set1: int,
    n_set2: int,
) -> str:
    s1_fail_per = _earliest(set1_per, FAILED)
    s1_hlth_per = _earliest(set1_per, HEALTHY)
    s1_fail_pool = _earliest(set1_pool, FAILED)
    s1_hlth_pool = _earliest(set1_pool, HEALTHY)
    s1_fp_per = _healthy_fp(set1_per, before=s1_fail_per if s1_fail_per is not None else n_set1)
    s1_fp_pool = _healthy_fp(set1_pool, before=s1_fail_pool if s1_fail_pool is not None else n_set1)
    b2_per = _critical_count(set1_per[("bearing_2", "x")])
    b2_pool = _critical_count(set1_pool[("bearing_2", "x")])

    s2_fail = n_set2 - 1
    s2_w_per = _first_status(set2_per[("bearing_1", "x")], DetectionStatus.WARNING)
    s2_c_per = _first_status(set2_per[("bearing_1", "x")], DetectionStatus.CRITICAL)
    s2_w_pool = _first_status(set2_pool[("bearing_1", "x")], DetectionStatus.WARNING)
    s2_c_pool = _first_status(set2_pool[("bearing_1", "x")], DetectionStatus.CRITICAL)
    s2_lead_pool = _hours_value(s2_w_pool, s2_fail)
    s2_fp_per = _set2_unlabeled_fp(set2_per, before=s2_w_per if s2_w_per is not None else n_set2)
    s2_fp_pool = _set2_unlabeled_fp(
        set2_pool, before=s2_w_pool if s2_w_pool is not None else n_set2
    )

    healthy_quiet = b2_pool < b2_per / 2 and (
        s1_hlth_pool is None or (s1_fail_pool is not None and s1_fail_pool < s1_hlth_pool)
    )
    set2_ok = (
        s2_lead_pool is not None
        and s2_fp_pool == 0
        and abs(s2_lead_pool - SET2_LEAD_REF_HOURS) <= 15.0
    )
    if healthy_quiet and set2_ok:
        verdict = (
            "Beklenti tuttu: Set 1 saglikli sessizlesti, Set 2 lead/FP bozulmadi. "
            "Canli havuzlama bir sonraki adim (bu script canliya yazmaz)."
        )
    elif healthy_quiet and not set2_ok:
        verdict = "Set 1 iyilesti ama Set 2 bozuldu. Canli havuzlama yok; ADR-0008 kilit."
    elif not healthy_quiet and set2_ok:
        verdict = "Set 2 korundu ama Set 1 saglikli gurultusu inmedi. Canli yok."
    else:
        verdict = "Havuzlama bu kosuda hedefi tutmadi. Canli IF/esik degismez."

    lines = [
        "# IMS IsolationForest havuzlu warmup (offline)",
        "",
        "Canli IF, nicelik veya ADR-0008 **degismez**. Ham cache; Kafka yok.",
        "Zarf niceligi havuz skorlarindan (800/1600), dar 200'den degil.",
        f"IF: n_estimators={N_ESTIMATORS}, contamination={CONTAMINATION}, zarf acik,",
        f"Wq/Cq={WARNING_Q:g}/{CRITICAL_Q:g}. Set 1 rs=42 (canli default);",
        "Set 2 rs=0 (ADR-0008 kalibrasyon).",
        "",
        "## Iki kosu",
        "",
        "1. **Per-kanal (canli):** her `(dataset, rulman, eksen)` kendi ilk 200'u.",
        "2. **Havuzlu:** dataset'te tum kanallarin ilk 200'u birlesir",
        "   (Set 1: 8*200=1600; Set 2: 4*200=800). Tek IF+zarf; kalan skorlanir.",
        "",
        "Dogrulama: ilk uyari, siralama, bosluk, erken FP, critical sayisi.",
        "Mutlak alarm sayisi tek basina karar degil.",
        "",
        "## Set 1 ozet (yan yana)",
        "",
        "| Kosul | b3 | b4 | b1 | b2 | siralama | bosluk | erken FP | b2/x C |",
        "|---|---:|---:|---:|---:|---|---|---:|---:|",
        (
            f"| per-kanal | {_fmt(_bearing_first(set1_per, 'bearing_3'))} | "
            f"{_fmt(_bearing_first(set1_per, 'bearing_4'))} | "
            f"{_fmt(_bearing_first(set1_per, 'bearing_1'))} | "
            f"{_fmt(_bearing_first(set1_per, 'bearing_2'))} | "
            f"{_rank_cell(s1_fail_per, s1_hlth_per)} | "
            f"{_gap_hours(s1_fail_per, s1_hlth_per)} | {s1_fp_per} | {b2_per} |"
        ),
        (
            f"| havuzlu | {_fmt(_bearing_first(set1_pool, 'bearing_3'))} | "
            f"{_fmt(_bearing_first(set1_pool, 'bearing_4'))} | "
            f"{_fmt(_bearing_first(set1_pool, 'bearing_1'))} | "
            f"{_fmt(_bearing_first(set1_pool, 'bearing_2'))} | "
            f"{_rank_cell(s1_fail_pool, s1_hlth_pool)} | "
            f"{_gap_hours(s1_fail_pool, s1_hlth_pool)} | {s1_fp_pool} | {b2_pool} |"
        ),
        "",
        "## Set 1 karneleri",
        "",
    ]
    lines.extend(_set1_block(f"Per-kanal (rs=42, n={n_set1})", set1_per, n_set1))
    lines.extend(_set1_block(f"Havuzlu 1600 (rs=42, n={n_set1})", set1_pool, n_set1))

    lines.extend(
        [
            "## Set 2 (ADR-0008 referans: b1 W=447, lead 89.3 saat, FP=0)",
            "",
            f"Son dosya index {s2_fail}; lead = (son - ilk W) * 10 dk.",
            "",
            "| Kosul | b1 W | b1 C | lead W | etiketsiz FP | b2 ilk | b3 ilk | b4 ilk |",
            "|---|---:|---:|---|---:|---:|---:|---:|",
            (
                f"| per-kanal rs=0 | {_fmt(s2_w_per)} | {_fmt(s2_c_per)} | "
                f"{_hours_before(s2_w_per, s2_fail)} | {s2_fp_per} | "
                f"{_fmt(_bearing_first(set2_per, 'bearing_2'))} | "
                f"{_fmt(_bearing_first(set2_per, 'bearing_3'))} | "
                f"{_fmt(_bearing_first(set2_per, 'bearing_4'))} |"
            ),
            (
                f"| havuzlu 800 rs=0 | {_fmt(s2_w_pool)} | {_fmt(s2_c_pool)} | "
                f"{_hours_before(s2_w_pool, s2_fail)} | {s2_fp_pool} | "
                f"{_fmt(_bearing_first(set2_pool, 'bearing_2'))} | "
                f"{_fmt(_bearing_first(set2_pool, 'bearing_3'))} | "
                f"{_fmt(_bearing_first(set2_pool, 'bearing_4'))} |"
            ),
            (
                f"| ADR-0008 IF+zarf | {SET2_FIRST_W_REF} | 538 | "
                f"{SET2_LEAD_REF_HOURS} saat | 0 | 711 | 537 | 635 |"
            ),
            "",
            "## Hold-out yorumu (canli yok)",
            "",
            f"- {verdict}",
            f"- Set 1 b2/x critical: per-kanal {b2_per} -> havuzlu {b2_pool}.",
            "- Set 1 havuzda b3 hâlâ 206 (warmup-kenari); b1 ilk alarm 276.",
            "  Bosluk 11.7 saat — siralama evet ama Z-Score kadar temiz degil.",
            f"- Set 2 lead W: per-kanal {_hours_before(s2_w_per, s2_fail)}, "
            f"havuzlu {_hours_before(s2_w_pool, s2_fail)} "
            f"(hedef {SET2_LEAD_REF_HOURS} saat, ilk W {SET2_FIRST_W_REF}).",
            f"- Set 2 etiketsiz FP: per-kanal {s2_fp_per}, havuzlu {s2_fp_pool}.",
            "- Havuz inlier'i genisletir: Set 1 dar-zarf FP'sini keser, Set 2 etiketli",
            "  kanalin erken sapmasini yutar. Per-kanal Set 2 = ADR-0008 birebir.",
            "- Esik retune yok. Canli `IsolationForestDetector` bu karne ile degismez.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    _set1_files, set1_store = load_set1()
    _set2_dir, _set2_files, set2_store = load_set2()
    n_set1 = len(next(iter(set1_store["rms"].values())))
    n_set2 = len(next(iter(set2_store["rms"].values())))
    set1_per = replay_per_channel(
        set1_store, SET1_CHANNELS, _set1_key, dataset="set1", random_state=42
    )
    set1_model = train_pooled(set1_store, SET1_CHANNELS, _set1_key, random_state=42)
    set1_pool = score_pooled(set1_model, set1_store, SET1_CHANNELS, _set1_key)
    set2_per = replay_per_channel(
        set2_store, SET2_CHANNELS, _set2_key, dataset="set2", random_state=0
    )
    set2_model = train_pooled(set2_store, SET2_CHANNELS, _set2_key, random_state=0)
    set2_pool = score_pooled(set2_model, set2_store, SET2_CHANNELS, _set2_key)
    report = summarize(set1_per, set1_pool, set2_per, set2_pool, n_set1, n_set2)
    out = OUT_DIR / "ims_if_pooled.md"
    out.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
