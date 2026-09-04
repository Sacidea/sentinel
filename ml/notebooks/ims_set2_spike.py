"""IMS Set 2 format spike — atılabilir keşif (bkz. planning/13.2, 15).

Production'a girmez. Amaç: 20.480 nokta / 4 kanal / timestamp isim doğrulamak,
RMS-kurtosis bozulmasını görmek, ilk BASELINE_WINDOW snapshot'ın sağlıklı olup olmadığını
aynı `extract_features` tanımıyla ölçmek.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "stream-processor" / "src"))

from stream_processor.domain.features import extract_features  # noqa: E402

DATA_DIR = ROOT / "data" / "ims"
OUT_DIR = Path(__file__).resolve().parent
BASELINE_WINDOW = 200
BEARINGS = ("bearing_1", "bearing_2", "bearing_3", "bearing_4")


def _files() -> list[Path]:
    paths = [path for path in DATA_DIR.iterdir() if path.is_file()]
    return sorted(paths, key=lambda path: path.name)


def _timestamp(name: str) -> datetime:
    return datetime.strptime(name, "%Y.%m.%d.%H.%M.%S").replace(tzinfo=UTC)


def scan() -> dict[str, object]:
    files = _files()
    n_files = len(files)
    rows = np.zeros(n_files, dtype=np.int32)
    cols = np.zeros(n_files, dtype=np.int32)
    names: list[str] = []
    times: list[datetime] = []
    rms = {bearing: np.zeros(n_files) for bearing in BEARINGS}
    kurtosis = {bearing: np.zeros(n_files) for bearing in BEARINGS}
    parse_errors = 0

    for index, path in enumerate(files):
        names.append(path.name)
        try:
            times.append(_timestamp(path.name))
        except ValueError:
            parse_errors += 1
            times.append(datetime.fromtimestamp(0, tz=UTC))
        samples = np.loadtxt(path, dtype=np.float64)
        if samples.ndim == 1:
            samples = samples.reshape(-1, 1)
        rows[index] = samples.shape[0]
        cols[index] = samples.shape[1]
        for column, bearing in enumerate(BEARINGS):
            if column >= samples.shape[1]:
                continue
            features = extract_features(samples[:, column].tolist())
            rms[bearing][index] = features.rms
            kurtosis[bearing][index] = features.kurtosis

    return {
        "n_files": n_files,
        "names": names,
        "times": times,
        "rows": rows,
        "cols": cols,
        "rms": rms,
        "kurtosis": kurtosis,
        "parse_errors": parse_errors,
    }


def _z_crossings(values: np.ndarray, window: int, threshold: float) -> int | None:
    baseline = values[:window]
    mean = float(np.mean(baseline))
    std = float(np.std(baseline))
    if std <= 1e-12:
        return None
    z = np.abs((values - mean) / std)
    hits = np.flatnonzero(z[window:] >= threshold)
    if len(hits) == 0:
        return None
    return int(hits[0] + window)


def summarize(result: dict[str, object]) -> str:
    rows = result["rows"]
    cols = result["cols"]
    times = result["times"]
    n_files = int(result["n_files"])
    lines = [
        "# IMS Set 2 spike bulguları",
        "",
        f"- Dosya sayısı: **{n_files}**",
        f"- Ilk / son: `{result['names'][0]}` -> `{result['names'][-1]}`",
        f"- Zaman araligi: {times[0].isoformat()} -> {times[-1].isoformat()}",
        f"- Satır sayısı (min/max): {int(rows.min())} / {int(rows.max())}"
        f" — 20480 beklenen: **{bool(np.all(rows == 20480))}**",
        f"- Sütun sayısı (min/max): {int(cols.min())} / {int(cols.max())}"
        f" — 4 beklenen: **{bool(np.all(cols == 4))}**",
        f"- Timestamp parse hatası: {result['parse_errors']}",
        "",
        f"## Baseline penceresi (ilk {BASELINE_WINDOW} snapshot)",
        "",
        "| Rulman | RMS mean | RMS std | son 50 RMS mean | kurtosis mean | kurtosis std | |z|≥3 ilk index (RMS) | |z|≥3 ilk index (kurtosis) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    rms_map = result["rms"]
    kurt_map = result["kurtosis"]
    for bearing in BEARINGS:
        rms = rms_map[bearing]
        kurt = kurt_map[bearing]
        rms_hit = _z_crossings(rms, BASELINE_WINDOW, 3.0)
        kurt_hit = _z_crossings(kurt, BASELINE_WINDOW, 3.0)
        lines.append(
            "| {bearing} | {rms_mean:.4f} | {rms_std:.4f} | {rms_tail:.4f} | {k_mean:.3f} | {k_std:.3f} | {rms_hit} | {kurt_hit} |".format(
                bearing=bearing,
                rms_mean=float(np.mean(rms[:BASELINE_WINDOW])),
                rms_std=float(np.std(rms[:BASELINE_WINDOW])),
                rms_tail=float(np.mean(rms[-50:])),
                k_mean=float(np.mean(kurt[:BASELINE_WINDOW])),
                k_std=float(np.std(kurt[:BASELINE_WINDOW])),
                rms_hit=rms_hit if rms_hit is not None else "—",
                kurt_hit=kurt_hit if kurt_hit is not None else "—",
            )
        )
    lines.extend(
        [
            "",
            "## Yorum",
            "",
            "- İlk 200 sağlıklı sayılır eğer RMS mean, son 50'ye göre belirgin düşük/stabil ve erken |z|≥3 yoksa.",
            "- Set 2 literatürü: test sonunda **bearing_1** dış bilezik arızası.",
            "",
        ]
    )
    return "\n".join(lines)


def plot(result: dict[str, object]) -> Path:
    rms_map = result["rms"]
    kurt_map = result["kurtosis"]
    n_files = int(result["n_files"])
    x = np.arange(n_files)
    figure, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    for bearing in BEARINGS:
        axes[0].plot(x, rms_map[bearing], label=bearing, linewidth=1.0)
        axes[1].plot(x, kurt_map[bearing], label=bearing, linewidth=1.0)
    for axis in axes:
        axis.axvline(BASELINE_WINDOW - 0.5, color="black", linestyle="--", linewidth=1.0)
        axis.grid(True, alpha=0.3)
        axis.legend(loc="upper left")
    axes[0].set_ylabel("RMS")
    axes[1].set_ylabel("Kurtosis (Pearson)")
    axes[1].set_xlabel("Snapshot index (10 dk aralık)")
    axes[0].set_title("IMS Set 2 — RMS / kurtosis (kesik çizgi = baseline 200)")
    figure.tight_layout()
    out = OUT_DIR / "ims_set2_spike.png"
    figure.savefig(out, dpi=120)
    plt.close(figure)
    return out


def main() -> None:
    if not DATA_DIR.is_dir() or not any(DATA_DIR.iterdir()):
        raise SystemExit(f"IMS dosyası yok: {DATA_DIR}")
    result = scan()
    report = summarize(result)
    plot_path = plot(result)
    stats_path = OUT_DIR / "ims_set2_spike_stats.md"
    stats_path.write_text(report + f"Grafik: `{plot_path.name}`\n", encoding="utf-8")
    print(report.encode("ascii", "replace").decode("ascii"))
    print(f"grafik: {plot_path}")
    print(f"istatistik: {stats_path}")


if __name__ == "__main__":
    main()
