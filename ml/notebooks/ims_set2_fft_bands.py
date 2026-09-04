"""IMS Set 2 FFT bant enerjisi taramasi — teshis yok, yalniz bpfo/bpfi/bsf.

Production'a girmez. NASA Set 2: bearing_1 dis bilezik (BPFO). Beklenti: bearing_1
bpfo zamana gore yukselsin; etiketsiz kanallar dusuk kalsin.
"""

from __future__ import annotations

import sys
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
BEARINGS = ("bearing_1", "bearing_2", "bearing_3", "bearing_4")
BASELINE = 200
TAIL = 50


def _files() -> list[Path]:
    return sorted(path for path in DATA_DIR.iterdir() if path.is_file())


def scan() -> dict[str, dict[str, np.ndarray]]:
    files = _files()
    n_files = len(files)
    store = {
        band: {bearing: np.zeros(n_files) for bearing in BEARINGS}
        for band in ("bpfo", "bpfi", "bsf")
    }
    for index, path in enumerate(files):
        samples = np.loadtxt(path, dtype=np.float64)
        if samples.ndim == 1:
            samples = samples.reshape(-1, 1)
        for column, bearing in enumerate(BEARINGS):
            if column >= samples.shape[1]:
                continue
            bands = extract_features(samples[:, column].tolist()).fft_band_energy
            for band in store:
                store[band][bearing][index] = bands[band]
    return store


def _ratio(series: np.ndarray) -> float:
    early = float(np.mean(series[:BASELINE]))
    late = float(np.mean(series[-TAIL:]))
    if early <= 0.0:
        return float("inf") if late > 0.0 else 1.0
    return late / early


def write_report(store: dict[str, dict[str, np.ndarray]]) -> None:
    n_files = len(next(iter(store["bpfo"].values())))
    lines = [
        "# IMS Set 2 FFT bant enerjisi (BPFO/BPFI/BSF)",
        "",
        "Teshis yok. `extract_features` rfft gucu: temel+2.+3. harmonik, ±5 Hz.",
        "Rexnord ZA-2115 merkezleri: BPFO=236, BPFI=297, BSF=278 Hz. Grafik:",
        "`ims_set2_fft_bands.png`.",
        "",
        f"Dosya sayisi: **{n_files}**. Erken pencere ilk {BASELINE}, gec son {TAIL}.",
        "",
        "## BPFO (dis bilezik) erken vs gec ortalama",
        "",
        "| Rulman | erken mean | gec mean | gec/erken |",
        "|---|---:|---:|---:|",
    ]
    for bearing in BEARINGS:
        series = store["bpfo"][bearing]
        early = float(np.mean(series[:BASELINE]))
        late = float(np.mean(series[-TAIL:]))
        lines.append(f"| {bearing} | {early:.4g} | {late:.4g} | {_ratio(series):.2f} |")
    b1_early = float(np.mean(store["bpfo"]["bearing_1"][:BASELINE]))
    b1_late = float(np.mean(store["bpfo"]["bearing_1"][-TAIL:]))
    b1 = _ratio(store["bpfo"]["bearing_1"])
    unlabeled = ", ".join(
        f"{name} {_ratio(store['bpfo'][name]):.2f}"
        for name in BEARINGS
        if name != "bearing_1"
    )
    lines.extend(
        [
            "",
            "## Yorum",
            "",
            f"bearing_1 BPFO gec/erken **{b1:.2f}** (erken {b1_early:.4g} → gec {b1_late:.4g}).",
            "NASA etiketi dis bilezik; b1 bu bantta run sonunda belirgin yukselir",
            "(grafikte ~index 850+). Etiketsiz kanallar da sona dogru enerji alir",
            f"(kaplinli mil; teshis degil): {unlabeled}.",
            "En dusuk artis bearing_2. Oran, erken ortalamasi kucuk olan kanalda",
            "(bearing_4) sisirilir; mutlak gec seviyede b3 en yuksek.",
            "",
            "Bu tarama alarm uretmez; yalniz ozellik dogrulamasi (ADR-0010).",
            "",
        ]
    )
    (OUT_DIR / "ims_set2_fft_bands.md").write_text("\n".join(lines), encoding="utf-8")

    index = np.arange(n_files)
    figure, axes = plt.subplots(figsize=(10, 5))
    for bearing in BEARINGS:
        axes.plot(index, store["bpfo"][bearing], label=bearing, linewidth=0.9)
    axes.axvline(BASELINE - 0.5, color="gray", linestyle="--", linewidth=0.8)
    axes.set_xlabel("dosya index")
    axes.set_ylabel("BPFO bant enerjisi")
    axes.set_title("Set 2 BPFO (236 Hz + 2H + 3H, ±5 Hz)")
    axes.legend()
    axes.grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(OUT_DIR / "ims_set2_fft_bands.png", dpi=120)
    plt.close(figure)


def main() -> None:
    if not DATA_DIR.is_dir():
        raise SystemExit(f"IMS klasoru yok: {DATA_DIR}")
    store = scan()
    write_report(store)
    print("bpfo late/early", {name: round(_ratio(store["bpfo"][name]), 2) for name in BEARINGS})


if __name__ == "__main__":
    main()
