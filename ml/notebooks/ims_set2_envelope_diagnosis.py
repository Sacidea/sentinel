"""IMS Set 2 envelope teshisi — offline. anomaly_events yazilmaz (ADR-0013).

Hilbert 2–10 kHz + ayni BPFO/BPFI/BSF kovalar. Beklenti: b1=BPFO; b2/3/4=belirsiz.
Esikler bu taramada aranir; ham-FFT 12/3/8 kopya sayilmaz.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "stream-processor" / "src"))

from stream_processor.domain.envelope import (  # noqa: E402
    ENVELOPE_ABS_Z,
    ENVELOPE_COMPANION_Z,
    ENVELOPE_DOMINANCE,
    envelope_band_energy,
)
from stream_processor.domain.fft_diagnosis import (  # noqa: E402
    BANDS,
    FftBandBaseline,
    band_z_scores,
    diagnose_fft_bands,
)

DATA_DIR = ROOT / "data" / "ims"
CACHE_PATH = ROOT / "data" / "ims_set2_envelope_bands.npz"
OUT_DIR = Path(__file__).resolve().parent
BEARINGS = ("bearing_1", "bearing_2", "bearing_3", "bearing_4")
FILE_NAME = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{2}$")
BASELINE = 200
TAIL = 50
LABELED = "bearing_1"
EXPECTED = {
    "bearing_1": "bpfo",
    "bearing_2": "uncertain",
    "bearing_3": "uncertain",
    "bearing_4": "uncertain",
}
NASA = {
    "bearing_1": "dis bilezik",
    "bearing_2": "saglikli",
    "bearing_3": "saglikli",
    "bearing_4": "saglikli",
}


def _files() -> list[Path]:
    return sorted(
        path for path in DATA_DIR.iterdir() if path.is_file() and FILE_NAME.match(path.name)
    )


def load_bands() -> dict[str, dict[str, np.ndarray]]:
    if CACHE_PATH.is_file():
        payload = np.load(CACHE_PATH)
        return {
            band: {bearing: payload[f"{band}_{bearing}"] for bearing in BEARINGS} for band in BANDS
        }
    files = _files()
    n_files = len(files)
    store = {band: {bearing: np.zeros(n_files) for bearing in BEARINGS} for band in BANDS}
    for index, path in enumerate(files):
        samples = np.loadtxt(path, dtype=np.float64)
        if samples.ndim == 1:
            samples = samples.reshape(-1, 1)
        for column, bearing in enumerate(BEARINGS):
            energy = envelope_band_energy(samples[:, column].tolist())
            for band in BANDS:
                store[band][bearing][index] = energy[band]
    np.savez(
        CACHE_PATH,
        **{f"{band}_{bearing}": store[band][bearing] for band in BANDS for bearing in BEARINGS},
    )
    return store


def _baseline(store: dict[str, dict[str, np.ndarray]], bearing: str) -> FftBandBaseline:
    return FftBandBaseline(
        mean={band: float(np.mean(store[band][bearing][:BASELINE])) for band in BANDS},
        std={band: float(np.std(store[band][bearing][:BASELINE])) for band in BANDS},
    )


def diagnose_series(
    store: dict[str, dict[str, np.ndarray]],
    bearing: str,
    *,
    abs_z: float,
    dominance: float,
    companion_z: float,
) -> tuple[list[str], FftBandBaseline]:
    baseline = _baseline(store, bearing)
    n_files = len(store["bpfo"][bearing])
    labels: list[str] = []
    for index in range(n_files):
        if index < BASELINE:
            labels.append("warming_up")
            continue
        energy = {band: float(store[band][bearing][index]) for band in BANDS}
        labels.append(
            diagnose_fft_bands(
                energy,
                baseline,
                abs_z=abs_z,
                dominance=dominance,
                companion_z=companion_z,
            )
        )
    return labels, baseline


def first_fault(labels: list[str]) -> tuple[str, int | None]:
    for index, label in enumerate(labels):
        if label in BANDS:
            return label, index
    return "uncertain", None


def protocol_score(
    store: dict[str, dict[str, np.ndarray]],
    *,
    abs_z: float,
    dominance: float,
    companion_z: float,
) -> tuple[bool, int, int, dict[str, str]]:
    unlabeled_hits = 0
    b1_hits = 0
    diagnoses: dict[str, str] = {}
    labeled_ok = True
    unlabeled_ok = True
    for bearing in BEARINGS:
        labels, _ = diagnose_series(
            store, bearing, abs_z=abs_z, dominance=dominance, companion_z=companion_z
        )
        fault, _ = first_fault(labels)
        diagnoses[bearing] = fault
        n_fault = sum(1 for label in labels if label in BANDS)
        if bearing == LABELED:
            b1_hits = labels.count("bpfo")
            if fault != "bpfo":
                labeled_ok = False
        else:
            unlabeled_hits += n_fault
            if fault != "uncertain":
                unlabeled_ok = False
    return labeled_ok and unlabeled_ok, b1_hits, unlabeled_hits, diagnoses


def _energy_only_bpfo(energy: dict[str, float], baseline: FftBandBaseline, abs_z: float) -> bool:
    z_scores = band_z_scores(energy, baseline)
    if z_scores["bpfo"] < abs_z:
        return False
    others = max(float(energy[name]) for name in BANDS if name != "bpfo")
    return float(energy["bpfo"]) >= ENVELOPE_DOMINANCE * max(others, 1e-12)


def write_outputs(store: dict[str, dict[str, np.ndarray]]) -> None:
    n_files = len(store["bpfo"][LABELED])
    abs_z, dominance, companion_z = ENVELOPE_ABS_Z, ENVELOPE_DOMINANCE, ENVELOPE_COMPANION_Z
    frozen_ok, _, _, _ = protocol_score(
        store, abs_z=abs_z, dominance=dominance, companion_z=companion_z
    )

    rows: list[dict[str, object]] = []
    series_labels: dict[str, list[str]] = {}
    for bearing in BEARINGS:
        labels, baseline = diagnose_series(
            store, bearing, abs_z=abs_z, dominance=dominance, companion_z=companion_z
        )
        series_labels[bearing] = labels
        fault, first_at = first_fault(labels)
        counts = {name: labels.count(name) for name in (*BANDS, "uncertain", "warming_up")}
        late_e = {band: float(np.mean(store[band][bearing][-TAIL:])) for band in BANDS}
        others = max(late_e[name] for name in BANDS if name != "bpfo")
        energy_dom = late_e["bpfo"] / others if others > 0 else float("inf")
        z_late = {
            band: (late_e[band] - baseline.mean[band]) / max(baseline.std[band], 1e-12)
            for band in BANDS
        }
        n_energy = 0
        for index in range(BASELINE, n_files):
            energy = {band: float(store[band][bearing][index]) for band in BANDS}
            if _energy_only_bpfo(energy, baseline, abs_z):
                n_energy += 1
        rows.append(
            {
                "bearing": bearing,
                "diagnosis": fault,
                "first_at": first_at,
                "n_bpfo": counts["bpfo"],
                "n_uncertain": counts["uncertain"],
                "n_energy_only": n_energy,
                "late": late_e,
                "z_late": z_late,
                "energy_dom": energy_dom,
                "ok": fault == EXPECTED[bearing],
            }
        )

    lines = [
        "# IMS Set 2 envelope teshisi (offline)",
        "",
        "> Ham-rFFT kapandi (ADR-0011/0012). Bu karne Hilbert envelope.",
        "> Canli `fault_type` yok. Tutmazsa yine yazilmaz (ADR-0013).",
        "",
        f"Esikler (Set 2 kilit, `envelope.py`): abs_z={abs_z:g},",
        f"dominance={dominance:g}, companion_z={companion_z:g}.",
        "Grafik: `ims_set2_envelope_diagnosis.png`.",
        "",
        f"Dosya sayisi: **{n_files}**. Baseline ilk {BASELINE}, gec son {TAIL}.",
        "Band-pass 2–10 kHz, sonra envelope spektrumu.",
        "",
        f"## Birincil — {'4/4 tuttu' if frozen_ok else '4/4 TUTMADI'}",
        "",
        "| Rulman | NASA | teshis | ilk | #BPFO | #enerji-only | #belirsiz | ok |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        first = "—" if row["first_at"] is None else str(row["first_at"])
        mark = "ok" if row["ok"] else "FAIL"
        lines.append(
            f"| {row['bearing']} | {NASA[str(row['bearing'])]} | {row['diagnosis']} "
            f"| {first} | {row['n_bpfo']} | {row['n_energy_only']} "
            f"| {row['n_uncertain']} | {mark} |"
        )
    lines.extend(
        [
            "",
            "## Gec pencere (son 50) envelope enerjisi",
            "",
            "| Rulman | E_BPFO | E_BPFI | E_BSF | enerji baskin | "
            "z_BPFO | z_BPFI | z_BSF |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        late = row["late"]
        z_late = row["z_late"]
        assert isinstance(late, dict)
        assert isinstance(z_late, dict)
        lines.append(
            f"| {row['bearing']} | {late['bpfo']:.4g} | {late['bpfi']:.4g} | "
            f"{late['bsf']:.4g} | {row['energy_dom']:.1f}x | {z_late['bpfo']:.1f} | "
            f"{z_late['bpfi']:.1f} | {z_late['bsf']:.1f} |"
        )

    lines.extend(
        [
            "",
            "## Esik taramasi (bu set, retune notu)",
            "",
            "### companion_z (abs_z=12, D=3)",
            "",
            "| companion_z | 4/4 | b1 | b2 | b3 | b4 | b1 #BPFO | etiketsiz # |",
            "|---:|---|---|---|---|---|---:|---:|",
        ]
    )
    for companion in (8.0, 15.0, 20.0, 21.0, 25.0, 30.0, 40.0, 80.0):
        ok, b1_hits, unlabeled, diagnoses = protocol_score(
            store, abs_z=12.0, dominance=3.0, companion_z=companion
        )
        cells = " | ".join(diagnoses[bearing] for bearing in BEARINGS)
        lines.append(
            f"| {companion:g} | {'ok' if ok else 'FAIL'} | {cells} "
            f"| {b1_hits} | {unlabeled} |"
        )
    lines.extend(
        [
            "",
            "b4 max companion z ~21; C=25 ilk 4/4. C=8 (ham-FFT kopyasi) b2/b4",
            "false BPFO. abs_z bu sette 4/4 tasiyicisi degil (C=8 iken hicbiri).",
            "",
            "### abs_z (D=3, C=25)",
            "",
            "| abs_z | 4/4 | b1 | b2 | b3 | b4 | b1 #BPFO | etiketsiz # |",
            "|---:|---|---|---|---|---|---:|---:|",
        ]
    )
    for abs_z_grid in (0.0, 5.0, 8.0, 12.0, 20.0, 50.0):
        ok, b1_hits, unlabeled, diagnoses = protocol_score(
            store, abs_z=abs_z_grid, dominance=3.0, companion_z=25.0
        )
        cells = " | ".join(diagnoses[bearing] for bearing in BEARINGS)
        lines.append(
            f"| {abs_z_grid:g} | {'ok' if ok else 'FAIL'} | {cells} "
            f"| {b1_hits} | {unlabeled} |"
        )
    lines.extend(
        [
            "",
            "Ham-FFT otopsi durur. Envelope canliya ancak Set 1 hold-out da",
            "4/4 tutarsa yazilir (`ims_set1_envelope_diagnosis.md`).",
            "",
        ]
    )
    (OUT_DIR / "ims_set2_envelope_diagnosis.md").write_text("\n".join(lines), encoding="utf-8")

    index = np.arange(n_files)
    figure, axes = plt.subplots(4, 1, figsize=(10, 11), sharex=True)
    for bearing in BEARINGS:
        bpfo = store["bpfo"][bearing]
        bpfi = store["bpfi"][bearing]
        bsf = store["bsf"][bearing]
        mean_fo = float(np.mean(bpfo[:BASELINE]))
        std_fo = float(max(np.std(bpfo[:BASELINE]), 1e-12))
        mean_fi = float(np.mean(bpfi[:BASELINE]))
        std_fi = float(max(np.std(bpfi[:BASELINE]), 1e-12))
        axes[0].plot(index, (bpfo - mean_fo) / std_fo, label=bearing, linewidth=0.9)
        axes[1].plot(index, (bpfi - mean_fi) / std_fi, label=bearing, linewidth=0.9)
        dom = bpfo / np.maximum(np.maximum(bpfi, bsf), 1e-12)
        axes[2].plot(index, dom, label=bearing, linewidth=0.9)
        codes = np.array([1.0 if label == "bpfo" else 0.0 for label in series_labels[bearing]])
        axes[3].plot(index, codes, label=bearing, linewidth=1.1)
    for axis in axes:
        axis.axvline(BASELINE - 0.5, color="gray", linestyle=":", linewidth=0.8)
        axis.grid(True, alpha=0.3)
        axis.legend(loc="upper left")
    axes[0].axhline(abs_z, color="gray", linestyle="--", linewidth=0.8)
    axes[0].set_ylabel("z env BPFO")
    title = "tuttu" if frozen_ok else "TUTMADI"
    axes[0].set_title(f"Set 2 envelope teshisi — {title}")
    axes[1].axhline(companion_z, color="gray", linestyle="--", linewidth=0.8)
    axes[1].set_ylabel("z env BPFI")
    axes[2].axhline(dominance, color="gray", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("E_BPFO / max(diger)")
    axes[2].set_yscale("log")
    axes[3].set_ylabel("teshis = BPFO")
    axes[3].set_xlabel("dosya index")
    axes[3].set_ylim(-0.05, 1.15)
    figure.tight_layout()
    figure.savefig(OUT_DIR / "ims_set2_envelope_diagnosis.png", dpi=120)
    plt.close(figure)
    if not frozen_ok:
        print("Set 2 envelope 4/4 TUTMADI (karne yazildi)")


def main() -> None:
    if not DATA_DIR.is_dir():
        raise SystemExit(f"IMS klasoru yok: {DATA_DIR}")
    write_outputs(load_bands())


if __name__ == "__main__":
    main()
