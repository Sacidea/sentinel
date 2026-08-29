"""IMS Set 2 FFT ariza teshisi — offline. anomaly_events yazilmaz (ADR-0011).

NASA: bearing_1 dis bilezik. Beklenti: b1=BPFO; b2/3/4=belirsiz (kaplin BPFO
artisina ragmen). Esikler sihirli degil; karnesi `ims_set2_fft_diagnosis.md`.
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

from stream_processor.domain.features import extract_features  # noqa: E402
from stream_processor.domain.fft_diagnosis import (  # noqa: E402
    BANDS,
    DEFAULT_ABS_Z,
    DEFAULT_COMPANION_Z,
    DEFAULT_DOMINANCE,
    FftBandBaseline,
    band_z_scores,
    diagnose_fft_bands,
)

DATA_DIR = ROOT / "data" / "ims"
CACHE_PATH = ROOT / "data" / "ims_set2_fft_bands.npz"
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
            energy = extract_features(samples[:, column].tolist()).fft_band_energy
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
    abs_z: float = DEFAULT_ABS_Z,
    dominance: float = DEFAULT_DOMINANCE,
    companion_z: float = DEFAULT_COMPANION_Z,
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


def _energy_only_bpfo(energy: dict[str, float], baseline: FftBandBaseline) -> bool:
    """(a)+(b enerji orani); companion yok — kaplin tuzağini gostermek icin."""
    z_scores = band_z_scores(energy, baseline)
    if z_scores["bpfo"] < DEFAULT_ABS_Z:
        return False
    others = max(float(energy[name]) for name in BANDS if name != "bpfo")
    return float(energy["bpfo"]) >= DEFAULT_DOMINANCE * max(others, 1e-12)


def count_energy_only_bpfo(
    store: dict[str, dict[str, np.ndarray]], bearing: str, baseline: FftBandBaseline
) -> int:
    n_files = len(store["bpfo"][bearing])
    hits = 0
    for index in range(BASELINE, n_files):
        energy = {band: float(store[band][bearing][index]) for band in BANDS}
        if _energy_only_bpfo(energy, baseline):
            hits += 1
    return hits


def protocol_score(
    store: dict[str, dict[str, np.ndarray]],
    *,
    abs_z: float,
    dominance: float,
    companion_z: float,
) -> tuple[bool, int, int]:
    """4/4 protokol: b1 bpfo, digerleri belirsiz. Donen: ok, b1 #bpfo, etiketsiz #teshis."""
    unlabeled_hits = 0
    b1_hits = 0
    labeled_ok = True
    unlabeled_ok = True
    for bearing in BEARINGS:
        labels, _ = diagnose_series(
            store, bearing, abs_z=abs_z, dominance=dominance, companion_z=companion_z
        )
        fault, _ = first_fault(labels)
        n_fault = sum(1 for label in labels if label in BANDS)
        if bearing == LABELED:
            b1_hits = labels.count("bpfo")
            if fault != "bpfo":
                labeled_ok = False
        else:
            unlabeled_hits += n_fault
            if fault != "uncertain":
                unlabeled_ok = False
    return labeled_ok and unlabeled_ok, b1_hits, unlabeled_hits


def _peak_companion_rows(
    store: dict[str, dict[str, np.ndarray]],
) -> list[tuple[str, float, float, int]]:
    rows: list[tuple[str, float, float, int]] = []
    for bearing in BEARINGS:
        baseline = _baseline(store, bearing)
        n_files = len(store["bpfo"][bearing])
        max_z_bpfo = float("-inf")
        max_companion = float("-inf")
        for index in range(BASELINE, n_files):
            energy = {band: float(store[band][bearing][index]) for band in BANDS}
            z_scores = band_z_scores(energy, baseline)
            max_z_bpfo = max(max_z_bpfo, z_scores["bpfo"])
            max_companion = max(max_companion, z_scores["bpfi"], z_scores["bsf"])
        rows.append(
            (
                bearing,
                max_z_bpfo,
                max_companion,
                count_energy_only_bpfo(store, bearing, baseline),
            )
        )
    return rows


def _sensitivity_tables(store: dict[str, dict[str, np.ndarray]]) -> list[str]:
    peaks = _peak_companion_rows(store)
    unlabeled_max_c = max(row[2] for row in peaks if row[0] != LABELED)
    lines = [
        "",
        "## Esik hassasiyeti (Set 2, ayni veri — overfitting notu)",
        "",
        "Esikler bu sette aranip yine bu sette dogrulandi. Asagidaki 1D taramalar",
        "hangi sayinin 4/4'u tasiydigini gosterir; hold-out (Set 1) degildir.",
        "",
        "| Rulman | max z_BPFO | max companion (z_BPFI,z_BSF) | energy-only n |",
        "|---|---:|---:|---:|",
    ]
    for bearing, max_z_bpfo, max_companion, n_energy in peaks:
        lines.append(
            f"| {bearing} | {max_z_bpfo:.2f} | {max_companion:.2f} | {n_energy} |"
        )
    b2_c = next(row[2] for row in peaks if row[0] == "bearing_2")
    lines.extend(
        [
            "",
            f"bearing_2 max companion={b2_c:.2f}; etiketsizlerin ustu "
            f"{unlabeled_max_c:.2f}. Tam kuralda b2/3/4'u eleyen abs_z degil "
            "companion'dir (energy-only bu snapshot'lari BPFO sayardi).",
            "",
            "### abs_z (D=3, C=8) — genis plato",
            "",
            "| abs_z | 4/4 | b1 #teshis | etiketsiz #teshis |",
            "|---:|---|---:|---:|",
        ]
    )
    for abs_z in (0.0, 10.0, 12.0, 15.0, 20.0, 50.0, 100.0):
        ok, b1_hits, unlabeled = protocol_score(
            store, abs_z=abs_z, dominance=3.0, companion_z=8.0
        )
        lines.append(
            f"| {abs_z:g} | {'ok' if ok else 'FAIL'} | {b1_hits} | {unlabeled} |"
        )
    lines.extend(
        [
            "",
            "C=8 varken abs_z=0 bile etiketsizleri tutar. 12, oran-sismesi bekcisi;",
            "Set 2 4/4'unun asil nedeni companion boslugudur.",
            "",
            "### companion_z (abs_z=12, D=3) — alt sinir dar",
            "",
            "| companion_z | 4/4 | b1 #teshis | etiketsiz #teshis |",
            "|---:|---|---:|---:|",
        ]
    )
    for companion in (5.0, 6.0, 7.0, 7.5, 8.0, 10.0, 15.0, 40.0):
        ok, b1_hits, unlabeled = protocol_score(
            store, abs_z=12.0, dominance=3.0, companion_z=companion
        )
        lines.append(
            f"| {companion:g} | {'ok' if ok else 'FAIL'} | {b1_hits} | {unlabeled} |"
        )
    lines.extend(
        [
            "",
            "C=7 → etiketsiz false BPFO; C=8 → 0. 8, b2'nin en yuksek companion'i",
            f"({b2_c:.2f}) hemen ustune oturur — altta bicak agrisi, ustte plato.",
            "",
            "### Gerekce",
            "",
            "Yapi fiziksel: tek-kova kaplin vs birden fazla karakteristigin cikmasi.",
            "Sayilar istatistiksel p-degeri degil. z>=8 Gaussian'da asiri kucuk",
            "olurdu ama bant enerjisi iid normal degil; 8 = bu runda saglikli",
            "kanallarin ustune cik. Hold-out Set 1 4/4 tutmadi",
            "(`ims_set1_fft_diagnosis.md`); teshis envelope'a (ADR-0012).",
            "Set 2'ye kalibre; baska sette yeniden ayar bu kurali kurtarmaz.",
            "",
        ]
    )
    return lines


def write_outputs(store: dict[str, dict[str, np.ndarray]]) -> None:
    n_files = len(store["bpfo"][LABELED])
    rows: list[dict[str, object]] = []
    series_labels: dict[str, list[str]] = {}
    for bearing in BEARINGS:
        labels, baseline = diagnose_series(store, bearing)
        series_labels[bearing] = labels
        fault, first_at = first_fault(labels)
        counts = {name: labels.count(name) for name in (*BANDS, "uncertain", "warming_up")}
        late_e = {band: float(np.mean(store[band][bearing][-TAIL:])) for band in BANDS}
        others = max(late_e[name] for name in BANDS if name != "bpfo")
        energy_dom = late_e["bpfo"] / others if others > 0 else float("inf")
        z_bpfo = (late_e["bpfo"] - baseline.mean["bpfo"]) / max(baseline.std["bpfo"], 1e-12)
        z_bpfi = (late_e["bpfi"] - baseline.mean["bpfi"]) / max(baseline.std["bpfi"], 1e-12)
        z_bsf = (late_e["bsf"] - baseline.mean["bsf"]) / max(baseline.std["bsf"], 1e-12)
        rows.append(
            {
                "bearing": bearing,
                "diagnosis": fault,
                "first_at": first_at,
                "n_bpfo": counts["bpfo"],
                "n_bpfi": counts["bpfi"],
                "n_bsf": counts["bsf"],
                "n_uncertain": counts["uncertain"],
                "n_energy_only": count_energy_only_bpfo(store, bearing, baseline),
                "late_bpfo": late_e["bpfo"],
                "late_bpfi": late_e["bpfi"],
                "late_bsf": late_e["bsf"],
                "energy_dom": energy_dom,
                "z_bpfo": z_bpfo,
                "z_bpfi": z_bpfi,
                "z_bsf": z_bsf,
                "ok": fault == EXPECTED[bearing],
            }
        )

    lines = [
        "# IMS Set 2 FFT ariza teshisi (offline)",
        "",
        "> Ham-rFFT denendi. Kaplin/bearing_4 siniri bu karnede. Set 1 hold-out",
        "> tutmadi. Canli yok; sonraki deneme envelope (ADR-0011, ADR-0012).",
        "",
        "Canli `anomaly_events` yok. Kural: `diagnose_fft_bands` (ADR-0011).",
        f"Esikler Set 2: abs_z={DEFAULT_ABS_Z:g}, dominance={DEFAULT_DOMINANCE:g},",
        f"companion_z={DEFAULT_COMPANION_Z:g}. Grafik: `ims_set2_fft_diagnosis.png`.",
        "",
        f"Dosya sayisi: **{n_files}**. Baseline ilk {BASELINE}, gec son {TAIL}.",
        "",
        "## Neden enerji-orani yetmedi",
        "",
        "Son 50 dosyanin ortalamasinda **butun** rulmanlarda BPFO, BPFI/BSF'ten",
        "onlarca kat buyuk. Kaplin bu ozellikte 'tum bantlari esit kaldirmiyor';",
        "**yalniz BPFO kovasini** sisiyor. (b) yalniz `E_bpfo / max(E_bpfi, E_bsf)`",
        "olursa bearing_4 da 'BPFO' olur — dunku tuzak.",
        "",
        "Kalibre (b): enerji baskinligi **ve** en az bir diger karakteristigin",
        f"z >= {DEFAULT_COMPANION_Z:g} (gercek dis bilezikte BPFI de baseline'dan cikar;",
        "kaplin BPFI'yi yerinde birakir). (a) aday bandin kendi baseline z'si",
        f">= {DEFAULT_ABS_Z:g} (oran sismesini eker).",
        "",
        "## Gec pencere (son 50) — kosul (a)/(b) ham sayilar",
        "",
        "| Rulman | E_BPFO | E_BPFI | E_BSF | enerji baskinligi | z_BPFO | z_BPFI | z_BSF |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['bearing']} | {row['late_bpfo']:.4g} | {row['late_bpfi']:.4g} | "
            f"{row['late_bsf']:.4g} | {row['energy_dom']:.1f}x | {row['z_bpfo']:.1f} | "
            f"{row['z_bpfi']:.1f} | {row['z_bsf']:.1f} |"
        )
    lines.extend(
        [
            "",
            "## Teshis vs enerji-only tuzak",
            "",
            "enerji-only = (a) z_BPFO + (b) enerji orani, **companion yok**.",
            "Tam kural = ayni AND + companion z.",
            "",
            "| Rulman | NASA | teshis | ilk | #BPFO | #enerji-only | #belirsiz | ok |",
            "|---|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in rows:
        first = "—" if row["first_at"] is None else str(row["first_at"])
        mark = "ok" if row["ok"] else "FAIL"
        lines.append(
            f"| {row['bearing']} | {NASA[str(row['bearing'])]} | {row['diagnosis']} "
            f"| {first} | {row['n_bpfo']} | {row['n_energy_only']} "
            f"| {row['n_uncertain']} | {mark} |"
        )
    b1 = next(row for row in rows if row["bearing"] == "bearing_1")
    b4 = next(row for row in rows if row["bearing"] == "bearing_4")
    lines.extend(
        [
            "",
            f"b1 ilk BPFO etiketi index {b1['first_at']} / {n_files} "
            "(gec donem teyidi; lead-time metrigi degil).",
            "",
            "## bearing_4 (kaplin + oran sismesi) — ozellikle",
            "",
            f"Gec BPFO enerjisi {b4['late_bpfo']:.4g} (b1: {b1['late_bpfo']:.4g}, ayni mertebe).",
            f"Enerji baskinligi {b4['energy_dom']:.1f}x, z_BPFO={b4['z_bpfo']:.0f} —",
            "oran ve mutlak BPFO 'var' der. Bu yuzden enerji-only "
            f"**{b4['n_energy_only']}** snapshot'i BPFO sayar.",
            f"z_BPFI={b4['z_bpfi']:.1f}, z_BSF={b4['z_bsf']:.1f} "
            f"(companion esik {DEFAULT_COMPANION_Z:g}) → companion yok → **belirsiz**.",
            f"Tam kuralda hic BPFO etiketi yok (n={b4['n_bpfo']}).",
            "",
            "## Grid notu",
            "",
            "Yalniz z_BPFO + enerji-D taramasi: b1'i yakalayan hicbir (Z, D) cifti",
            "b2/3/4'u sifirlamadi. Companion ile (abs_z=12, D=3, companion_z=8)",
            "b1>0 ve etiketsiz=0.",
        ]
    )
    lines.extend(_sensitivity_tables(store))
    lines.extend(
        [
            "Yalniz Set 2 kalibrasyon otopsi. Hold-out tutmadi; yol ADR-0012.",
            "Canli entegrasyon (`fault_type`) bu kurala baglanmaz.",
            "",
        ]
    )
    (OUT_DIR / "ims_set2_fft_diagnosis.md").write_text("\n".join(lines), encoding="utf-8")

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
    axes[0].axhline(DEFAULT_ABS_Z, color="gray", linestyle="--", linewidth=0.8)
    axes[0].set_ylabel("z BPFO (a)")
    axes[0].set_title("Set 2 FFT teshisi (offline) — yalniz b1 BPFO")
    axes[0].legend(loc="upper left")
    axes[1].axhline(DEFAULT_COMPANION_Z, color="gray", linestyle="--", linewidth=0.8)
    axes[1].set_ylabel("z BPFI (companion)")
    axes[2].axhline(DEFAULT_DOMINANCE, color="gray", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("E_BPFO / max(BPFI,BSF)")
    axes[2].set_yscale("log")
    axes[3].set_ylabel("teshis = BPFO")
    axes[3].set_xlabel("dosya index")
    axes[3].set_ylim(-0.05, 1.15)
    figure.tight_layout()
    figure.savefig(OUT_DIR / "ims_set2_fft_diagnosis.png", dpi=120)
    plt.close(figure)

    failed = [row["bearing"] for row in rows if not row["ok"]]
    if failed:
        raise SystemExit(f"dogrulama basarisiz: {failed}")


def main() -> None:
    if not DATA_DIR.is_dir():
        raise SystemExit(f"IMS klasoru yok: {DATA_DIR}")
    store = load_bands()
    write_outputs(store)


if __name__ == "__main__":
    main()
