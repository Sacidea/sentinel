"""Set 1 IF otopsi: canli per-kanal same-domain vs offline Set 2 transfer.

Production'a girmez. Canli IF/esik degismez. Ham ozellik; z-norm yok.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from sklearn.preprocessing import RobustScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "stream-processor" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ims_domain_invariant_if import (  # noqa: E402
    BASELINE_WINDOW,
    BEARINGS,
    FAILED,
    FEATURE_KEYS,
    HEALTHY,
    NASA,
    SET1_CACHE,
    SET1_CHANNELS,
    _bearing_first,
    _earliest,
    _first_alarm,
    _first_status,
    _fmt,
    _gap_hours,
    _healthy_fp,
    _rank_cell,
    load_set1,
    load_set2,
    matrix_for,
    score_set1,
    train_set2,
)
from stream_processor.domain.detectors import DetectionStatus  # noqa: E402
from stream_processor.domain.features import SignalFeatures  # noqa: E402
from stream_processor.domain.ml_detectors import IsolationForestDetector  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
CRITICAL_Q = 0.999
Store = dict[str, dict[str, NDArray[np.float64]]]
StatusMap = dict[tuple[str, str], list[DetectionStatus]]
KindMap = dict[tuple[str, str], list[str]]


def _features_at(store: Store, key: str, index: int) -> SignalFeatures:
    return SignalFeatures(
        rms=float(store["rms"][key][index]),
        kurtosis=float(store["kurtosis"][key][index]),
        crest_factor=float(store["crest_factor"][key][index]),
        peak=float(store["peak"][key][index]),
    )


def replay_live(
    store: Store,
    *,
    use_extent: bool,
    random_state: int,
) -> tuple[StatusMap, KindMap]:
    n_files = len(next(iter(store["rms"].values())))
    statuses: StatusMap = {channel: [] for channel in SET1_CHANNELS}
    kinds: KindMap = {channel: [] for channel in SET1_CHANNELS}
    detector = IsolationForestDetector(
        baseline_window=BASELINE_WINDOW,
        random_state=random_state,
        warning_quantile=0.995,
        critical_quantile=CRITICAL_Q,
        use_extent=use_extent,
    )
    for index in range(n_files):
        for bearing, axis in SET1_CHANNELS:
            result = detector.observe(
                bearing,
                axis,
                _features_at(store, f"{bearing}_{axis}", index),
                dataset="set1",
            )
            statuses[(bearing, axis)].append(result.status)
            kinds[(bearing, axis)].append(result.score_kind or "")
    return statuses, kinds


def _critical_count(rows: list[DetectionStatus]) -> int:
    return sum(1 for value in rows if value is DetectionStatus.CRITICAL)


def _kind_counts(kinds: list[str], statuses: list[DetectionStatus]) -> str:
    extent = sum(
        1
        for kind, status in zip(kinds, statuses, strict=True)
        if status is DetectionStatus.CRITICAL and kind == "extent"
    )
    score = sum(
        1
        for kind, status in zip(kinds, statuses, strict=True)
        if status is DetectionStatus.CRITICAL and kind == "if_score"
    )
    return f"extent {extent} / if_score {score}"


def _iqr_row(matrix: NDArray[np.float64]) -> str:
    scaler = RobustScaler()
    scaler.fit(matrix[:BASELINE_WINDOW])
    scales = ", ".join(
        f"{key}={scale:.4g}" for key, scale in zip(FEATURE_KEYS, scaler.scale_, strict=True)
    )
    return scales


def summarize(
    live: StatusMap,
    live_kinds: KindMap,
    no_extent: StatusMap,
    transfer: StatusMap,
    set1_store: Store,
    set2_store: Store,
    n_files: int,
) -> str:
    live_failed = _earliest(live, FAILED)
    live_healthy = _earliest(live, HEALTHY)
    tr_failed = _earliest(transfer, FAILED)
    tr_healthy = _earliest(transfer, HEALTHY)
    live_fp = _healthy_fp(live, before=live_failed if live_failed is not None else n_files)
    tr_fp = _healthy_fp(transfer, before=tr_failed if tr_failed is not None else n_files)
    b2x = live[("bearing_2", "x")]
    pooled = np.vstack([matrix_for(set2_store, bearing)[:BASELINE_WINDOW] for bearing in BEARINGS])

    lines = [
        "# IMS IF Set 1: canli same-domain vs offline transfer otopsi",
        "",
        "Canli IF/esik/ADR-0008 degismez. Ham dosya cache; Kafka yok.",
        "Set 1 `vibration_features` 4312 satir = 2156 * 2 oynatma; ilk index ilk tur.",
        "",
        "## Protokol farki (esik/pencere ayni, model degil)",
        "",
        "| | Offline transfer (iyi gorunen) | Canli Set 1 (gurultulu) |",
        "|---|---|---|",
        "| Egitim | Set 2 havuz (4*200=800) | her kanal kendi 200 |",
        "| Test | ayni orman, Set 1 ham | ayni kanalin geri kalani |",
        "| RobustScaler | 800 noktalik genis bulut | 200 noktalik dar kanal bulutu |",
        "| random_state | 0 (kalibrasyon notebook) | 42 (detector default) |",
        "| BASELINE / Wq/Cq / zarf | 200 / 0.995/0.999 / acik | ayni |",
        "| IF RAM seed | - | Yok; yalniz Z-Score `load_baselines` |",
        "",
        "xy karismaz: anahtar `(dataset, machine_id, axis)`. Canli Z-Score ilk index",
        "offline `ims_set1_zscore.md` ile birebir (b3x W=755, b4x W=399, b2x W=2134).",
        "",
        "## Canli DB (set1, detector=isolation_forest)",
        "",
        "bearing_2 x: 970 critical, **ilk index 200** (ilk skorlanan snapshot).",
        "934/970 `score_kind=extent`. b2 y ilk W=200. b3 y ilk C=206. Saglikli,",
        "arizali ile ayni warmup-kenarinda; b2 x, b3'ten 6 dosya **once**.",
        "970 mutlak sayi: her critical snapshot kayda gider (debounce yalniz Telegram);",
        "iki tam oynatma sayiyi siser. Metrik ilk index'tir, count degil.",
        "",
        "## Offline tekrar: canli protokol (per-kanal, rs=42, zarf acik)",
        "",
        "| Kosul | b3 | b4 | b1 | b2 | siralama | bosluk | erken FP |",
        "|---|---:|---:|---:|---:|---|---|---:|",
        (
            f"| transfer (Set 2 ormani) | {_fmt(_bearing_first(transfer, 'bearing_3'))} | "
            f"{_fmt(_bearing_first(transfer, 'bearing_4'))} | "
            f"{_fmt(_bearing_first(transfer, 'bearing_1'))} | "
            f"{_fmt(_bearing_first(transfer, 'bearing_2'))} | "
            f"{_rank_cell(tr_failed, tr_healthy)} | {_gap_hours(tr_failed, tr_healthy)} | {tr_fp} |"
        ),
        (
            f"| same-domain per-kanal | {_fmt(_bearing_first(live, 'bearing_3'))} | "
            f"{_fmt(_bearing_first(live, 'bearing_4'))} | "
            f"{_fmt(_bearing_first(live, 'bearing_1'))} | "
            f"{_fmt(_bearing_first(live, 'bearing_2'))} | "
            f"{_rank_cell(live_failed, live_healthy)} | "
            f"{_gap_hours(live_failed, live_healthy)} | {live_fp} |"
        ),
        "",
        "| Rulman | eksen | NASA | ilk W | ilk C | critical sayisi | kazanan skor |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for bearing, axis in SET1_CHANNELS:
        rows = live[(bearing, axis)]
        lines.append(
            f"| {bearing} | {axis} | {NASA[bearing]} | "
            f"{_fmt(_first_status(rows, DetectionStatus.WARNING))} | "
            f"{_fmt(_first_status(rows, DetectionStatus.CRITICAL))} | "
            f"{_critical_count(rows)} | {_kind_counts(live_kinds[(bearing, axis)], rows)} |"
        )

    no_ext_b2 = _first_alarm(no_extent[("bearing_2", "x")])
    lines.extend(
        [
            "",
            f"Zarf kapali (ayni per-kanal, rs=42): b2/x ilk alarm {_fmt(no_ext_b2)}; "
            f"b2/x critical {_critical_count(no_extent[('bearing_2', 'x')])}.",
            "",
            "## Warmup darligi (RobustScaler IQR = scale_)",
            "",
            "Kucuk IQR tek basina suc degil (b2/x ~ Set 2 havuz). Fark: per-kanal",
            "0.999 extent niceligi 200 ornekte neredeyse max; bir sonraki snapshot asar.",
            "Havuzlu orman 800 cok-rulman noktasinda daha genis inlier; Set 1 saglikli",
            "mutlak RMS o bulutta kalir.",
            "",
            f"- Set 2 havuz warmup IQR: `{_iqr_row(pooled)}`",
            f"- Set 1 b2/x warmup IQR: `{_iqr_row(matrix_for(set1_store, 'bearing_2_x'))}`",
            f"- Set 1 b3/x warmup IQR: `{_iqr_row(matrix_for(set1_store, 'bearing_3_x'))}`",
            "",
            "## Kaynak (ne degil)",
            "",
            "- **Degil:** farkli BASELINE_WINDOW veya nicelik. Ikisi de 200 / 0.995/0.999.",
            "- **Degil:** x/y karisimi. Z-Score canli = offline karnesi.",
            "- **Degil:** ilk 200'un ariza ile kirlenmesi. NASA saglikli baslar; Z-Score",
            "  b2'yi 2134'e kadar sessiz tutar. IF b2 200'de calar cunku zarf, o kanalin",
            "  dar warmup max-norm'unu asmayi 'critical' sayar.",
            "- **Olan:** canli IF same-domain per-kanal + RobustScaler + extent.",
            "  Offline 'iyi' sonuc **baska model**: Set 2'nin genis mutlak-olcek ormani.",
            "  Same-domain'in cross-domain'den kotu gorunmesi ters degil: per-kanal",
            "  200 ornekte overfit; havuzlu Set 2 ormani saglikli Set 1'i tesadufen",
            "  inlier birakir.",
            f"- b2/x canli ilk critical {_fmt(_first_status(b2x, DetectionStatus.CRITICAL))} "
            f"(warmup bitisi). Tek tur critical={_critical_count(b2x)}; canli 970 ~ iki oynatma.",
            "- Canli IF'e tasinacak 'duzeltme' yok; bu otopsi. Esik retune yok.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    if not SET1_CACHE.is_file():
        raise SystemExit(f"Set 1 ML cache yok: {SET1_CACHE} (once ims_domain_invariant_if.py)")
    _set1_files, set1_store = load_set1()
    _set2_dir, _set2_files, set2_store = load_set2()
    live, live_kinds = replay_live(set1_store, use_extent=True, random_state=42)
    no_extent, _ = replay_live(set1_store, use_extent=False, random_state=42)
    transfer_model = train_set2(set2_store, normalize=False)
    transfer = score_set1(transfer_model, set1_store, normalize=False)
    n_files = len(next(iter(set1_store["rms"].values())))
    report = summarize(live, live_kinds, no_extent, transfer, set1_store, set2_store, n_files)
    out = OUT_DIR / "ims_if_set1_same_domain.md"
    out.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
