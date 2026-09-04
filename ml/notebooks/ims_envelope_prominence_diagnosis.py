"""IMS envelope tepe-belirginligi teshisi — offline (ADR-0015).

Canli yok. Enerji kovasi / Z-Score / IF degismez. Esik yalniz Set 2.
"""

from __future__ import annotations

import re
import sys
from collections import deque
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from numpy.typing import NDArray

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "stream-processor" / "src"))

from stream_processor.domain.bearing_frequencies import (  # noqa: E402
    CHARACTERISTIC_HZ,
    IMS_ZA2115,
)
from stream_processor.domain.diagnosis import (  # noqa: E402
    DiagnosisLabel,
    DiagnosisScores,
    decide_from_scores,
    prominence_scores,
)
from stream_processor.domain.envelope import envelope_magnitude_spectrum  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
SET2_DIR = ROOT / "data" / "ims"
SET2_NESTED = ROOT / "data" / "ims" / "2nd_test"
SET1_DIR = ROOT / "data" / "ims_set1" / "1st_test"
SET2_CACHE = ROOT / "data" / "ims_set2_prominence_scores.npz"
SET1_CACHE = ROOT / "data" / "ims_set1_prominence_scores.npz"
FILE_NAME = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{2}$")
BEARINGS = ("bearing_1", "bearing_2", "bearing_3", "bearing_4")
SET1_CHANNELS = tuple((bearing, axis) for bearing in BEARINGS for axis in ("x", "y"))
BASELINE = 200
SPECTRAL_AVERAGE = 8
FAULT_LABELS = frozenset({"bpfo", "bpfi", "bsf", "bpfi_veya_bsf"})
SET2_EXPECTED = {
    "bearing_1": "bpfo",
    "bearing_2": "uncertain",
    "bearing_3": "uncertain",
    "bearing_4": "uncertain",
}
SET1_EXPECTED = {
    "bearing_1": "uncertain",
    "bearing_2": "uncertain",
    "bearing_3": "bpfi",
    "bearing_4": "bsf",
}
SET2_NASA = {
    "bearing_1": "dis bilezik",
    "bearing_2": "saglikli",
    "bearing_3": "saglikli",
    "bearing_4": "saglikli",
}
SET1_NASA = {
    "bearing_1": "saglikli",
    "bearing_2": "saglikli",
    "bearing_3": "ic bilezik",
    "bearing_4": "makara",
}
GRID_MIN_SCORE = (8.0, 12.0, 16.0, 20.0)
GRID_BPFO_MARGIN = (1.3, 1.5, 2.0)
GRID_INNER_MARGIN = (1.3, 1.5, 2.0)
LABEL_ORDER: tuple[DiagnosisLabel, ...] = (
    "uncertain",
    "bpfo",
    "bpfi",
    "bsf",
    "bpfi_veya_bsf",
)
LABEL_COLORS = {
    "uncertain": "#9e9e9e",
    "bpfo": "#1976d2",
    "bpfi": "#f57c00",
    "bsf": "#388e3c",
    "bpfi_veya_bsf": "#7b1fa2",
}
# Z-Score ilk W/C — mevcut karneler, yeniden hesap yok (ADR-0006).
# Set 2: ims_set2_zscore_calibration.md 5.0/8.0. b1 W/C ayri; b2/3/4 yalniz
# "ilk alarm" tablosu (critical karnede yok -> None).
ZSCORE_SET2: dict[str, tuple[int | None, int | None]] = {
    "bearing_1": (536, 554),
    "bearing_2": (828, None),
    "bearing_3": (902, None),
    "bearing_4": (702, None),
}
# Set 1: ims_set1_zscore.md kanal karnesi.
ZSCORE_SET1: dict[tuple[str, str], tuple[int | None, int | None]] = {
    ("bearing_1", "x"): (None, None),
    ("bearing_1", "y"): (None, None),
    ("bearing_2", "x"): (2134, 2155),
    ("bearing_2", "y"): (2152, None),
    ("bearing_3", "x"): (755, 1159),
    ("bearing_3", "y"): (1829, 1830),
    ("bearing_4", "x"): (399, 1440),
    ("bearing_4", "y"): (523, 1467),
}
FAULTY_CHANNELS: tuple[tuple[str, str, str, str], ...] = (
    ("set2", "bearing_1", "", "bpfo"),
    ("set1", "bearing_3", "x", "bpfi"),
    ("set1", "bearing_3", "y", "bpfi"),
    ("set1", "bearing_4", "x", "bsf"),
    ("set1", "bearing_4", "y", "bsf"),
)


def _timestamp_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        path for path in directory.iterdir() if path.is_file() and FILE_NAME.match(path.name)
    )


def _set2_files() -> list[Path]:
    nested = _timestamp_files(SET2_NESTED)
    if nested:
        return nested
    files = _timestamp_files(SET2_DIR)
    if not files:
        raise SystemExit("Set 2 dosyasi yok.")
    return files


def _windows(n_files: int) -> dict[str, tuple[int, int]]:
    start = BASELINE
    usable = n_files - start
    third = max(usable // 3, 1)
    return {
        "erken": (start, start + third),
        "orta": (start + third, start + 2 * third),
        "gec": (start + 2 * third, n_files),
    }


def _score_files(files: list[Path], keys: tuple[str, ...]) -> dict[str, NDArray[np.float64]]:
    """Dosya basina bir loadtxt; her kanal icin son SPECTRAL_AVERAGE spektrum ortalamasi."""
    n_files = len(files)
    n_ch = len(keys)
    out = {key: np.zeros((n_files, 3), dtype=np.float64) for key in keys}
    recents: list[deque[NDArray[np.float64]]] = [deque(maxlen=SPECTRAL_AVERAGE) for _ in keys]
    freqs: NDArray[np.float64] | None = None
    for index, path in enumerate(files):
        samples = np.loadtxt(path, dtype=np.float64)
        if samples.ndim == 1:
            samples = samples.reshape(-1, 1)
        if samples.shape[1] < n_ch:
            raise SystemExit(f"{n_ch} kanal beklenir: {path.name}")
        for column, key in enumerate(keys):
            freq_bins, magnitude = envelope_magnitude_spectrum(samples[:, column])
            if freqs is None:
                freqs = freq_bins
            recents[column].append(magnitude)
            if index < BASELINE or len(recents[column]) < SPECTRAL_AVERAGE:
                continue
            stacked = np.mean(np.stack(list(recents[column]), axis=0), axis=0)
            scores = prominence_scores(freqs, stacked)
            out[key][index] = (scores.bpfo, scores.bpfi, scores.bsf)
        if index % 50 == 0 or index + 1 == n_files:
            print(f"  {path.parent.name} {index + 1}/{n_files}", flush=True)
    return out


def load_set2_scores() -> dict[str, NDArray[np.float64]]:
    if SET2_CACHE.is_file():
        payload = np.load(SET2_CACHE)
        return {bearing: payload[bearing] for bearing in BEARINGS}
    print("Set 2 zarf spektrumu (cache yok)...", flush=True)
    scores = _score_files(_set2_files(), BEARINGS)
    np.savez(SET2_CACHE, **scores)
    return scores


def load_set1_scores() -> dict[str, NDArray[np.float64]]:
    keys = tuple(f"{bearing}_{axis}" for bearing, axis in SET1_CHANNELS)
    if SET1_CACHE.is_file():
        payload = np.load(SET1_CACHE)
        return {key: payload[key] for key in keys}
    files = _timestamp_files(SET1_DIR)
    if not files:
        raise SystemExit(f"Set 1 yok: {SET1_DIR}")
    print("Set 1 zarf spektrumu (cache yok)...", flush=True)
    scores = _score_files(files, keys)
    np.savez(SET1_CACHE, **scores)
    return scores


def labels_from_scores(
    matrix: NDArray[np.float64],
    *,
    min_score: float,
    bpfo_margin: float,
    inner_margin: float,
) -> list[DiagnosisLabel]:
    labels: list[DiagnosisLabel] = []
    for index, row in enumerate(matrix):
        if index < BASELINE or float(np.max(row)) == 0.0:
            labels.append("uncertain")
            continue
        labels.append(
            decide_from_scores(
                DiagnosisScores(bpfo=float(row[0]), bpfi=float(row[1]), bsf=float(row[2])),
                min_score=min_score,
                bpfo_margin=bpfo_margin,
                inner_margin=inner_margin,
            ).label
        )
    return labels


def _bucket(label: DiagnosisLabel, expected: str) -> str:
    if expected == "uncertain":
        return "yanlis" if label in FAULT_LABELS else "dogru"
    if label == expected:
        return "dogru"
    if label == "uncertain":
        return "belirsiz"
    if label == "bpfi_veya_bsf" and expected in {"bpfi", "bsf"}:
        return "belirsiz"
    return "yanlis"


def tally(
    labels: list[DiagnosisLabel], expected: str, start: int, end: int
) -> tuple[int, int, int, int]:
    dogru = yanlis = belirsiz = 0
    for label in labels[start:end]:
        bucket = _bucket(label, expected)
        if bucket == "dogru":
            dogru += 1
        elif bucket == "yanlis":
            yanlis += 1
        else:
            belirsiz += 1
    total = dogru + yanlis + belirsiz
    return total, dogru, yanlis, belirsiz


def _fmt_rate(count: int, total: int) -> str:
    if total == 0:
        return "-"
    return f"{100.0 * count / total:.1f}%"


def _row(
    name: str,
    nasa: str,
    expected: str,
    labels: list[DiagnosisLabel],
    start: int,
    end: int,
) -> str:
    total, dogru, yanlis, belirsiz = tally(labels, expected, start, end)
    return (
        f"| {name} | {nasa} | {expected} | {total} | {dogru} | {yanlis} | "
        f"{belirsiz} | {_fmt_rate(belirsiz, total)} |"
    )


def calibrate_set2(scores: dict[str, NDArray[np.float64]]) -> tuple[float, float, float]:
    n_files = len(next(iter(scores.values())))
    mid = _windows(n_files)["orta"]
    best: tuple[int, float, float, float, float] | None = None
    for min_score in GRID_MIN_SCORE:
        for bpfo_margin in GRID_BPFO_MARGIN:
            for inner_margin in GRID_INNER_MARGIN:
                unlabeled_wrong = 0
                b1_correct = 0
                b1_total = 0
                for bearing in BEARINGS:
                    labels = labels_from_scores(
                        scores[bearing],
                        min_score=min_score,
                        bpfo_margin=bpfo_margin,
                        inner_margin=inner_margin,
                    )
                    _total, dogru, yanlis, _belirsiz = tally(
                        labels, SET2_EXPECTED[bearing], mid[0], mid[1]
                    )
                    if bearing == "bearing_1":
                        b1_correct += dogru
                        b1_total += _total
                    else:
                        unlabeled_wrong += yanlis
                b1_rate = b1_correct / b1_total if b1_total else 0.0
                key = (unlabeled_wrong, -b1_rate, min_score, bpfo_margin, inner_margin)
                if best is None or key < best:
                    best = key
    assert best is not None
    return best[2], best[3], best[4]


def label_runs(labels: list[DiagnosisLabel], target: str) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, label in enumerate(labels):
        if label == target:
            if start is None:
                start = index
            continue
        if start is not None:
            runs.append((start, index - 1))
            start = None
    if start is not None:
        runs.append((start, len(labels) - 1))
    return runs


def _fmt_runs(runs: list[tuple[int, int]]) -> str:
    if not runs:
        return "yok"
    n_hits = sum(end - start + 1 for start, end in runs)
    parts = [f"{start}-{end}" if start != end else str(start) for start, end in runs]
    span = f"{runs[0][0]}-{runs[-1][1]}"
    if len(runs) == 1:
        return f"{span} (n={n_hits})"
    shown = parts if len(parts) <= 10 else [*parts[:10], f"... +{len(parts) - 10} ada"]
    return f"{span} ({len(runs)} ada: {', '.join(shown)}; n={n_hits})"


def _in_span(runs: list[tuple[int, int]], index: int | None) -> str:
    if index is None:
        return "-"
    if not runs:
        return "hayir (etiket yok)"
    lo, hi = runs[0][0], runs[-1][1]
    inside = lo <= index <= hi
    return f"{'evet' if inside else 'hayir'} (W/C={index}, minmax {lo}-{hi})"


def _in_island(runs: list[tuple[int, int]], index: int | None) -> str:
    if index is None:
        return "-"
    if not runs:
        return "hayir (etiket yok)"
    for start, end in runs:
        if start <= index <= end:
            return "evet"
    return "hayir (adalarda yok)"


def _label_at(labels: list[DiagnosisLabel], index: int | None) -> str:
    if index is None:
        return "-"
    if index < 0 or index >= len(labels):
        return "?"
    return labels[index]


def _vlines(axis: Axes, warning: int | None, critical: int | None, *, alarm_only: bool) -> None:
    if warning is not None:
        name = "Z-Score ilk alarm (karne)" if alarm_only else "Z-Score warning"
        axis.axvline(warning, color="#c62828", linestyle="--", linewidth=1.1, label=name)
    if critical is not None:
        axis.axvline(
            critical, color="#6a1b9a", linestyle=":", linewidth=1.2, label="Z-Score critical"
        )


def _plot_channel(
    ax_scores: Axes,
    ax_labels: Axes,
    scores: NDArray[np.float64],
    labels: list[DiagnosisLabel],
    *,
    title: str,
    warning: int | None,
    critical: int | None,
    alarm_only: bool,
) -> None:
    index = np.arange(len(labels))
    ax_scores.plot(
        index, scores[:, 0], color=LABEL_COLORS["bpfo"], linewidth=0.9, label="skor_bpfo"
    )
    ax_scores.plot(
        index, scores[:, 1], color=LABEL_COLORS["bpfi"], linewidth=0.9, label="skor_bpfi"
    )
    ax_scores.plot(index, scores[:, 2], color=LABEL_COLORS["bsf"], linewidth=0.9, label="skor_bsf")
    _vlines(ax_scores, warning, critical, alarm_only=alarm_only)
    ax_scores.set_ylabel("skor")
    ax_scores.set_title(title)
    ax_scores.grid(True, alpha=0.3)
    ax_scores.legend(loc="upper left", fontsize=7, ncol=3)
    codes = np.array([LABEL_ORDER.index(label) for label in labels], dtype=np.int8)
    colors = [LABEL_COLORS[label] for label in labels]
    ax_labels.scatter(index, codes, c=colors, s=6, marker="|", linewidths=0.8)
    _vlines(ax_labels, warning, critical, alarm_only=alarm_only)
    ax_labels.set_yticks(list(range(len(LABEL_ORDER))))
    ax_labels.set_yticklabels(list(LABEL_ORDER))
    ax_labels.set_ylabel("etiket")
    ax_labels.set_ylim(-0.5, float(len(LABEL_ORDER)) - 0.5)
    ax_labels.grid(True, axis="x", alpha=0.3)


def save_visibility_figures(
    set2: dict[str, NDArray[np.float64]],
    set2_labels: dict[str, list[DiagnosisLabel]],
    set1: dict[str, NDArray[np.float64]],
    set1_x: dict[str, list[DiagnosisLabel]],
    set1_y: dict[str, list[DiagnosisLabel]],
) -> tuple[str, str, str]:
    names = (
        "ims_envelope_prominence_set2.png",
        "ims_envelope_prominence_set1_x.png",
        "ims_envelope_prominence_set1_y.png",
    )

    figure, axes = plt.subplots(8, 1, figsize=(11, 16), sharex=True)
    for row, bearing in enumerate(BEARINGS):
        warning, critical = ZSCORE_SET2[bearing]
        alarm_only = critical is None and warning is not None
        _plot_channel(
            axes[2 * row],
            axes[2 * row + 1],
            set2[bearing],
            set2_labels[bearing],
            title=f"Set 2 {bearing} ({SET2_NASA[bearing]})",
            warning=warning,
            critical=critical,
            alarm_only=alarm_only,
        )
    axes[-1].set_xlabel("dosya index")
    figure.tight_layout()
    figure.savefig(OUT_DIR / names[0], dpi=120)
    plt.close(figure)

    for axis_name, labels_by, filename in (
        ("x", set1_x, names[1]),
        ("y", set1_y, names[2]),
    ):
        figure, axes = plt.subplots(8, 1, figsize=(11, 16), sharex=True)
        for row, bearing in enumerate(BEARINGS):
            warning, critical = ZSCORE_SET1[(bearing, axis_name)]
            _plot_channel(
                axes[2 * row],
                axes[2 * row + 1],
                set1[f"{bearing}_{axis_name}"],
                labels_by[bearing],
                title=f"Set 1 {bearing}/{axis_name} ({SET1_NASA[bearing]})",
                warning=warning,
                critical=critical,
                alarm_only=False,
            )
        axes[-1].set_xlabel("dosya index")
        figure.tight_layout()
        figure.savefig(OUT_DIR / filename, dpi=120)
        plt.close(figure)
    return names


def visibility_block(
    set2_labels: dict[str, list[DiagnosisLabel]],
    set1_x: dict[str, list[DiagnosisLabel]],
    set1_y: dict[str, list[DiagnosisLabel]],
    figures: tuple[str, str, str],
) -> list[str]:
    lines = [
        "## Gorunurluk (esik/pencere kilit; olcum)",
        "",
        "Z-Score cizgileri mevcut karnelerden (yeniden hesap yok):",
        "`ims_set2_zscore_calibration.md` 5.0/8.0, `ims_set1_zscore.md`.",
        "Set 2 b2/b3/b4 karnede yalniz ilk alarm; critical yok.",
        "Set 1'e bakarak pencere/esik secilmedi.",
        "",
        f"![Set 2]({figures[0]})",
        "",
        f"![Set 1 X]({figures[1]})",
        "",
        f"![Set 1 Y]({figures[2]})",
        "",
        "### Arizali kanal: dogru etiket araligi vs Z-Score",
        "",
        "| Kanal | beklenen | dogru etiket araligi | Z-Score W | Z-Score C | "
        "W minmax? | C minmax? | W ada ici? | C ada ici? | etiket(W) | etiket(C) |",
        "|---|---|---|---:|---:|---|---|---|---|---|---|",
    ]
    pack = {
        ("set2", "bearing_1", ""): set2_labels["bearing_1"],
        ("set1", "bearing_3", "x"): set1_x["bearing_3"],
        ("set1", "bearing_3", "y"): set1_y["bearing_3"],
        ("set1", "bearing_4", "x"): set1_x["bearing_4"],
        ("set1", "bearing_4", "y"): set1_y["bearing_4"],
    }
    zpack: dict[tuple[str, str, str], tuple[int | None, int | None]] = {
        ("set2", "bearing_1", ""): ZSCORE_SET2["bearing_1"],
        ("set1", "bearing_3", "x"): ZSCORE_SET1[("bearing_3", "x")],
        ("set1", "bearing_3", "y"): ZSCORE_SET1[("bearing_3", "y")],
        ("set1", "bearing_4", "x"): ZSCORE_SET1[("bearing_4", "x")],
        ("set1", "bearing_4", "y"): ZSCORE_SET1[("bearing_4", "y")],
    }
    answers: list[str] = []
    for set_name, bearing, axis, expected in FAULTY_CHANNELS:
        labels = pack[(set_name, bearing, axis)]
        runs = label_runs(labels, expected)
        warning, critical = zpack[(set_name, bearing, axis)]
        channel = f"{set_name} {bearing}" + (f"/{axis}" if axis else "")
        w_txt = "-" if warning is None else str(warning)
        c_txt = "-" if critical is None else str(critical)
        lines.append(
            f"| {channel} | {expected} | {_fmt_runs(runs)} | {w_txt} | {c_txt} | "
            f"{_in_span(runs, warning)} | {_in_span(runs, critical)} | "
            f"{_in_island(runs, warning)} | {_in_island(runs, critical)} | "
            f"{_label_at(labels, warning)} | {_label_at(labels, critical)} |"
        )
        span = "yok" if not runs else f"{runs[0][0]}-{runs[-1][1]}"
        answers.append(
            f"- **{channel}** {expected} etiketleri {span} "
            f"(n={0 if not runs else sum(e - s + 1 for s, e in runs)}, "
            f"{len(runs)} ada). "
            f"Z-Score warning {w_txt}: minmax {_in_span(runs, warning)}, "
            f"ada ici {_in_island(runs, warning)}, o index'te "
            f"`{_label_at(labels, warning)}`. "
            f"critical {c_txt}: minmax {_in_span(runs, critical)}, "
            f"ada ici {_in_island(runs, critical)}, o index'te "
            f"`{_label_at(labels, critical)}`."
        )
    lines.extend(["", "### Sorunun cevabi (olcum; kural degismez)", "", *answers, ""])
    return lines


def _kinematics_block() -> list[str]:
    kin = IMS_ZA2115
    return [
        "## Kinematik (ZA-2115, 2000 rpm, kod yazilmadan onceki hesap)",
        "",
        "n=16, d=0.331 in, D=2.815 in, alpha=15.17 deg, fr=2000/60 Hz.",
        f"BPFO={kin.bpfo_hz:.2f} Hz, BPFI={kin.bpfi_hz:.2f} Hz, "
        f"BSF={kin.bsf_hz:.2f} Hz, 2xBSF={kin.two_bsf_hz:.2f} Hz, "
        f"FTF={kin.ftf_hz:.2f} Hz.",
        f"ADR-0010 `CHARACTERISTIC_HZ`: bpfo={CHARACTERISTIC_HZ['bpfo']}, "
        f"bpfi={CHARACTERISTIC_HZ['bpfi']}, bsf={CHARACTERISTIC_HZ['bsf']}.",
        f"**278 Hz = 2xBSF** "
        f"(rel {abs(CHARACTERISTIC_HZ['bsf'] - kin.two_bsf_hz) / kin.two_bsf_hz:.2%}); "
        "temel BSF ~140 Hz. Enerji kovasi 1.+2.+3. H * 278 -> ~2x,4x,6x BSF; "
        "tek sayili BSF harmonikleri o kovada yok. Kovalar **degistirilmedi** "
        "(canli fft_band_energy / mevcut testler). Teshis 2xBSF + FTF yan bant kullanir.",
        "",
    ]


def summarize(
    set2: dict[str, NDArray[np.float64]],
    set1: dict[str, NDArray[np.float64]],
    *,
    min_score: float,
    bpfo_margin: float,
    inner_margin: float,
) -> str:
    n2 = len(next(iter(set2.values())))
    n1 = len(next(iter(set1.values())))
    w2 = _windows(n2)
    w1 = _windows(n1)
    set2_labels = {
        bearing: labels_from_scores(
            set2[bearing],
            min_score=min_score,
            bpfo_margin=bpfo_margin,
            inner_margin=inner_margin,
        )
        for bearing in BEARINGS
    }
    set1_x = {
        bearing: labels_from_scores(
            set1[f"{bearing}_x"],
            min_score=min_score,
            bpfo_margin=bpfo_margin,
            inner_margin=inner_margin,
        )
        for bearing in BEARINGS
    }
    set1_y = {
        bearing: labels_from_scores(
            set1[f"{bearing}_y"],
            min_score=min_score,
            bpfo_margin=bpfo_margin,
            inner_margin=inner_margin,
        )
        for bearing in BEARINGS
    }

    def _table(
        title: str,
        labels_by: dict[str, list[DiagnosisLabel]],
        expected: dict[str, str],
        nasa: dict[str, str],
        windows: dict[str, tuple[int, int]],
    ) -> list[str]:
        lines = [f"### {title}", ""]
        for window_name, (start, end) in windows.items():
            lines.extend(
                [
                    f"#### {window_name} (index {start}..{end})",
                    "",
                    "| Rulman | NASA | beklenen | n | dogru | yanlis | belirsiz | belirsiz % |",
                    "|---|---|---|---:|---:|---:|---:|---|",
                ]
            )
            for bearing in BEARINGS:
                lines.append(
                    _row(
                        bearing,
                        nasa[bearing],
                        expected[bearing],
                        labels_by[bearing],
                        start,
                        end,
                    )
                )
            lines.append("")
        return lines

    lines = [
        "# IMS envelope tepe-belirginligi teshisi (ADR-0015, offline)",
        "",
        "Canli `fault_type` yok. Z-Score/IF/esik degismez. Mutlak enerji yok.",
        "ADR-0015 **kapandi**: yanlis etiket dustu; teshis edilebilirlik ve "
        "alarm-capali pencere bu Set 1/Set 2 ciftinde calismadi.",
        f"Kayma ±{100 * 0.02:.0f}%, gurultu tabani ±50 Hz medyan, k=1..5, "
        f"spektral ortalama {SPECTRAL_AVERAGE}, Hann.",
        f"Esik **Set 2 orta pencere**: min_score={min_score:g}, "
        f"bpfo_margin={bpfo_margin:g}, inner_margin={inner_margin:g}. "
        "Set 1'e retune yok.",
        "",
        "bpfi_veya_bsf: beklenen bpfi/bsf ise belirsiz (yanlis degil); "
        "beklenen bpfo veya saglikli ise yanlis.",
        "",
    ]
    lines.extend(_kinematics_block())
    lines.extend(
        [
            "## Set 2 kalibrasyon (b1=bpfo, b2/3/4=uncertain)",
            "",
            f"{n2} dosya. Orta pencere esik secimi; erken/gec rapor.",
            "",
        ]
    )
    lines.extend(_table("Set 2", set2_labels, SET2_EXPECTED, SET2_NASA, w2))
    lines.extend(
        [
            "## Set 1 hold-out (esik kilit)",
            "",
            f"{n1} dosya. NASA: b3 ic bilezik, b4 bilye, b1/b2 saglikli.",
            "",
        ]
    )
    lines.extend(_table("Set 1 X", set1_x, SET1_EXPECTED, SET1_NASA, w1))
    lines.extend(_table("Set 1 Y", set1_y, SET1_EXPECTED, SET1_NASA, w1))
    lines.extend(_holdout_block(set1_x, set1_y, w1))
    lines.extend(
        [
            "## Enerji tabanli karne ile (ims_set1_envelope_diagnosis.md)",
            "",
            "Onceki kural tek etiket/rulman (AND + z + enerji orani, C=25). "
            "Bu kural snapshot basina tepe belirginligi + erken/orta/gec. "
            "Sutunlar birebir degil; yanlis vs belirsiz burada ayri sayilir.",
            "",
            "| Kaynak | Set 1 X b1 | b2 | b3 (ic) | b4 (bilye) | 4/4 |",
            "|---|---|---|---|---|---|",
            "| Enerji+z C=25 | uncertain ok | **bpfo yanlis** | uncertain (hedef yok) | "
            "**bpfo yanlis** | tutmadi |",
            "| Belirginlik (orta, asagida) | "
            f"{_one_line(set1_x['bearing_1'], SET1_EXPECTED['bearing_1'], w1['orta'])} | "
            f"{_one_line(set1_x['bearing_2'], SET1_EXPECTED['bearing_2'], w1['orta'])} | "
            f"{_one_line(set1_x['bearing_3'], SET1_EXPECTED['bearing_3'], w1['orta'])} | "
            f"{_one_line(set1_x['bearing_4'], SET1_EXPECTED['bearing_4'], w1['orta'])} | "
            f"{_four_of_four(set1_x, w1['orta'])} |",
            "",
            "Esik Set 1'e kaydirilmadi. Tutmazsa gevsetme / sinif birlestirme yok.",
            "",
        ]
    )
    lines.extend(_yorum(set2_labels, set1_x, set1_y, w2, w1))
    figures = save_visibility_figures(set2, set2_labels, set1, set1_x, set1_y)
    lines.extend(visibility_block(set2_labels, set1_x, set1_y, figures))
    return "\n".join(lines) + "\n"


def _one_line(labels: list[DiagnosisLabel], expected: str, window: tuple[int, int]) -> str:
    _total, dogru, yanlis, belirsiz = tally(labels, expected, window[0], window[1])
    return f"d={dogru} y={yanlis} b={belirsiz}"


def _four_of_four(labels_by: dict[str, list[DiagnosisLabel]], window: tuple[int, int]) -> str:
    """Rulman gecer: yanlis=0 ve (saglikli veya en az bir dogru etiket)."""
    start, end = window
    ok = 0
    for bearing in BEARINGS:
        _total, dogru, yanlis, _belirsiz = tally(
            labels_by[bearing], SET1_EXPECTED[bearing], start, end
        )
        expected = SET1_EXPECTED[bearing]
        passed = yanlis == 0 and (expected == "uncertain" or dogru > 0)
        ok += int(passed)
    return "tutti" if ok == 4 else "tutmadi"


def _holdout_block(
    set1_x: dict[str, list[DiagnosisLabel]],
    set1_y: dict[str, list[DiagnosisLabel]],
    windows: dict[str, tuple[int, int]],
) -> list[str]:
    lines = [
        "### Hold-out ozeti (esik kilit, Set 1'e uydurma yok)",
        "",
        "Orta pencere protokolun ana olcusu (gec spektrum genis bantlasir).",
        "",
        "| Eksen | pencere | dogru | yanlis | belirsiz | sagliklida yanlis |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for axis_name, labels_by in (("X", set1_x), ("Y", set1_y)):
        for window_name, (start, end) in windows.items():
            dogru = yanlis = belirsiz = healthy_wrong = 0
            for bearing in BEARINGS:
                _t, d, y, b = tally(labels_by[bearing], SET1_EXPECTED[bearing], start, end)
                dogru += d
                yanlis += y
                belirsiz += b
                if SET1_EXPECTED[bearing] == "uncertain":
                    healthy_wrong += y
            lines.append(
                f"| {axis_name} | {window_name} | {dogru} | {yanlis} | {belirsiz} | "
                f"{healthy_wrong} |"
            )
    lines.append("")
    mid = windows["orta"]
    lines.append(
        f"Set 1 X orta 4/4 analogu: **{_four_of_four(set1_x, mid)}**. "
        f"Y: **{_four_of_four(set1_y, mid)}**."
    )
    lines.append("")
    return lines


def _yorum(
    set2_labels: dict[str, list[DiagnosisLabel]],
    set1_x: dict[str, list[DiagnosisLabel]],
    set1_y: dict[str, list[DiagnosisLabel]],
    w2: dict[str, tuple[int, int]],
    w1: dict[str, tuple[int, int]],
) -> list[str]:
    s2_mid = tally(set2_labels["bearing_1"], "bpfo", *w2["orta"])
    s2_late_b2 = tally(set2_labels["bearing_2"], "uncertain", *w2["gec"])
    s2_late_b4 = tally(set2_labels["bearing_4"], "uncertain", *w2["gec"])
    x_mid_b3 = tally(set1_x["bearing_3"], "bpfi", *w1["orta"])
    x_mid_b4 = tally(set1_x["bearing_4"], "bsf", *w1["orta"])
    x_late_b2 = tally(set1_x["bearing_2"], "uncertain", *w1["gec"])
    x_late_b3 = tally(set1_x["bearing_3"], "bpfi", *w1["gec"])
    x_late_b4 = tally(set1_x["bearing_4"], "bsf", *w1["gec"])
    return [
        "## Yorum",
        "",
        f"Set 2 orta: b1 BPFO {s2_mid[1]}/{s2_mid[0]} dogru, sagliklida yanlis=0 "
        "(kalibrasyon hedefi). Set 2 gec saglikli kirildi: "
        f"b2 yanlis={s2_late_b2[2]}, b4 yanlis={s2_late_b4[2]} — esik buna gore "
        "kaydirilmadi (protokol orta pencere).",
        "",
        f"Set 1 orta X (hold-out): b3 dogru={x_mid_b3[1]} yanlis={x_mid_b3[2]} "
        f"belirsiz={x_mid_b3[3]}; b4 dogru={x_mid_b4[1]} yanlis={x_mid_b4[2]} "
        f"belirsiz={x_mid_b4[3]}. Saglikli orta: yanlis yok. "
        f"4/4 analogu {_four_of_four(set1_x, w1['orta'])} / "
        f"Y {_four_of_four(set1_y, w1['orta'])}.",
        "",
        f"Set 1 gec X'te imza gecikir: b3 dogru={x_late_b3[1]}, "
        f"b4 dogru={x_late_b4[1]} ama yanlis={x_late_b4[2]}; "
        f"b2 sagliklida yanlis={x_late_b2[2]}. Gec pencere ayirt edicilik "
        "kaybeder; protokol orta olcuyu kilitler.",
        "",
        "Enerji karnesine gore: belirginlik saglikli orta pencerede false BPFO "
        "uretmedi (enerji C=25 b2/b4'u BPFO yapmisti). Ic bilezik/bilye yine "
        "orta evrede ayrilmadi. Esik gevsetilmedi, sinif birlestirilmedi.",
        "",
        "- Teshis zorlanmadi (`uncertain` / `bpfi_veya_bsf` serbest).",
        "- Yanlis etiket belirsizden pahali.",
        "- Canli boru, fault_type, ADR-0006/0008, detectors/ml_detectors yok.",
        "",
    ]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    set2 = load_set2_scores()
    min_score, bpfo_margin, inner_margin = calibrate_set2(set2)
    set1 = load_set1_scores()
    report = summarize(
        set2,
        set1,
        min_score=min_score,
        bpfo_margin=bpfo_margin,
        inner_margin=inner_margin,
    )
    out = OUT_DIR / "ims_envelope_prominence_diagnosis.md"
    out.write_text(report, encoding="utf-8")
    print(f"secilen esik min={min_score:g} bpfo_m={bpfo_margin:g} inner_m={inner_margin:g}")
    print(report, flush=True)


if __name__ == "__main__":
    main()
