"""IMS Set 1 envelope teshisi — hold-out. Set 2 envelope esikleri kilit; retune yok.

NASA: b3 ic bilezik, b4 makara; b1/b2 saglikli. Hilbert 2–10 kHz (ADR-0013).
Canli `anomaly_events` yok.
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

CACHE_PATH = ROOT / "data" / "ims_set1_envelope_bands.npz"
OUT_DIR = Path(__file__).resolve().parent
FILE_NAME = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{2}$")
BASELINE = 200
TAIL = 50
BEARINGS = ("bearing_1", "bearing_2", "bearing_3", "bearing_4")
AXES = ("x", "y")
CHANNELS = tuple(f"{bearing}_{axis}" for bearing in BEARINGS for axis in AXES)
# NASA 1st_test: ch1=b1x … ch8=b4y.
NASA = {
    "bearing_1": "saglikli",
    "bearing_2": "saglikli",
    "bearing_3": "ic bilezik",
    "bearing_4": "makara",
}
EXPECTED = {
    "bearing_1": "uncertain",
    "bearing_2": "uncertain",
    "bearing_3": "bpfi",
    "bearing_4": "bsf",
}
CODE = {"uncertain": 0.0, "bpfo": 1.0, "bpfi": 2.0, "bsf": 3.0}


def _data_dir() -> Path:
    root = ROOT / "data" / "ims_set1"
    nested = root / "1st_test"
    if nested.is_dir():
        return nested
    return root


def _files() -> list[Path]:
    data_dir = _data_dir()
    if not data_dir.is_dir():
        raise SystemExit(f"IMS Set 1 klasoru yok: {data_dir}")
    files = sorted(
        path for path in data_dir.iterdir() if path.is_file() and FILE_NAME.match(path.name)
    )
    if not files:
        raise SystemExit(f"Set 1 dosyasi yok: {data_dir}")
    return files


def load_bands() -> dict[str, dict[str, np.ndarray]]:
    if CACHE_PATH.is_file():
        payload = np.load(CACHE_PATH)
        return {
            band: {channel: payload[f"{band}_{channel}"] for channel in CHANNELS}
            for band in BANDS
        }
    files = _files()
    n_files = len(files)
    store = {band: {channel: np.zeros(n_files) for channel in CHANNELS} for band in BANDS}
    for index, path in enumerate(files):
        samples = np.loadtxt(path, dtype=np.float64)
        if samples.ndim == 1:
            samples = samples.reshape(-1, 1)
        if samples.shape[1] < 8:
            raise SystemExit(f"Set 1 8 kanal beklenir, {samples.shape[1]}: {path.name}")
        for column, channel in enumerate(CHANNELS):
            energy = envelope_band_energy(samples[:, column].tolist())
            for band in BANDS:
                store[band][channel][index] = energy[band]
    np.savez(
        CACHE_PATH,
        **{
            f"{band}_{channel}": store[band][channel]
            for band in BANDS
            for channel in CHANNELS
        },
    )
    return store


def _baseline(store: dict[str, dict[str, np.ndarray]], channel: str) -> FftBandBaseline:
    return FftBandBaseline(
        mean={band: float(np.mean(store[band][channel][:BASELINE])) for band in BANDS},
        std={band: float(np.std(store[band][channel][:BASELINE])) for band in BANDS},
    )


def diagnose_series(
    store: dict[str, dict[str, np.ndarray]],
    channel: str,
    *,
    abs_z: float = ENVELOPE_ABS_Z,
    dominance: float = ENVELOPE_DOMINANCE,
    companion_z: float = ENVELOPE_COMPANION_Z,
) -> tuple[list[str], FftBandBaseline]:
    baseline = _baseline(store, channel)
    n_files = len(store["bpfo"][channel])
    labels: list[str] = []
    for index in range(n_files):
        if index < BASELINE:
            labels.append("warming_up")
            continue
        energy = {band: float(store[band][channel][index]) for band in BANDS}
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


def _energy_only(
    energy: dict[str, float], baseline: FftBandBaseline, band: str
) -> bool:
    z_scores = band_z_scores(energy, baseline)
    if z_scores[band] < ENVELOPE_ABS_Z:
        return False
    others = max(float(energy[name]) for name in BANDS if name != band)
    return float(energy[band]) >= ENVELOPE_DOMINANCE * max(others, 1e-12)


def count_energy_only(
    store: dict[str, dict[str, np.ndarray]],
    channel: str,
    baseline: FftBandBaseline,
    band: str,
) -> int:
    n_files = len(store["bpfo"][channel])
    hits = 0
    for index in range(BASELINE, n_files):
        energy = {band_name: float(store[band_name][channel][index]) for band_name in BANDS}
        if _energy_only(energy, baseline, band):
            hits += 1
    return hits


def _peak_z_x(
    store: dict[str, dict[str, np.ndarray]],
) -> list[tuple[str, dict[str, float]]]:
    rows: list[tuple[str, dict[str, float]]] = []
    for bearing in BEARINGS:
        channel = f"{bearing}_x"
        baseline = _baseline(store, channel)
        n_files = len(store["bpfo"][channel])
        peak = {band: float("-inf") for band in BANDS}
        for index in range(BASELINE, n_files):
            energy = {band: float(store[band][channel][index]) for band in BANDS}
            z_scores = band_z_scores(energy, baseline)
            for band in BANDS:
                peak[band] = max(peak[band], z_scores[band])
        rows.append((bearing, peak))
    return rows


def protocol_x(
    store: dict[str, dict[str, np.ndarray]],
    *,
    abs_z: float,
    dominance: float,
    companion_z: float,
) -> tuple[bool, dict[str, str]]:
    """Birincil protokol: X ekseni (Set 2 tek-kanal analogu)."""
    diagnoses: dict[str, str] = {}
    ok = True
    for bearing in BEARINGS:
        labels, _ = diagnose_series(
            store,
            f"{bearing}_x",
            abs_z=abs_z,
            dominance=dominance,
            companion_z=companion_z,
        )
        fault, _ = first_fault(labels)
        diagnoses[bearing] = fault
        if fault != EXPECTED[bearing]:
            ok = False
    return ok, diagnoses


def _row(
    store: dict[str, dict[str, np.ndarray]], channel: str
) -> dict[str, object]:
    bearing = channel.rsplit("_", 1)[0]
    labels, baseline = diagnose_series(store, channel)
    fault, first_at = first_fault(labels)
    counts = {name: labels.count(name) for name in (*BANDS, "uncertain", "warming_up")}
    late = {band: float(np.mean(store[band][channel][-TAIL:])) for band in BANDS}
    target = EXPECTED[bearing]
    others = [name for name in BANDS if name != "bpfo"]
    energy_dom_bpfo = late["bpfo"] / max(late[name] for name in others)
    target_band = "bpfi" if target == "bpfi" else "bsf" if target == "bsf" else "bpfo"
    others_t = [name for name in BANDS if name != target_band]
    energy_dom_target = late[target_band] / max(late[name] for name in others_t)
    z_late = {
        band: (late[band] - baseline.mean[band]) / max(baseline.std[band], 1e-12)
        for band in BANDS
    }
    return {
        "channel": channel,
        "bearing": bearing,
        "diagnosis": fault,
        "first_at": first_at,
        "n_bpfo": counts["bpfo"],
        "n_bpfi": counts["bpfi"],
        "n_bsf": counts["bsf"],
        "n_uncertain": counts["uncertain"],
        "n_energy_only_target": count_energy_only(store, channel, baseline, target_band),
        "late": late,
        "z_late": z_late,
        "energy_dom_bpfo": energy_dom_bpfo,
        "energy_dom_target": energy_dom_target,
        "expected": target,
        "ok": fault == target,
        "labels": labels,
        "baseline": baseline,
    }


def _fmt_first(first_at: object) -> str:
    return "—" if first_at is None else str(first_at)


def _sensitivity_x(store: dict[str, dict[str, np.ndarray]]) -> list[str]:
    lines = [
        "",
        "## Hold-out hassasiyet (retune degil)",
        "",
        "Asagidaki tarama Set 2 esiklerini **degistirmez**. Yalniz bu sette hangi",
        "C/abs_z 4/4 X-protokolunu tutardi — overfitting notu, yeni default degil.",
        "",
        "### companion_z (abs_z=12, D=3) — X ekseni 4/4",
        "",
        "| companion_z | 4/4 X | b1 | b2 | b3 | b4 |",
        "|---:|---|---|---|---|---|",
    ]
    for companion in (8.0, 15.0, 25.0, 40.0, 80.0):
        ok, diagnoses = protocol_x(
            store, abs_z=12.0, dominance=3.0, companion_z=companion
        )
        cells = " | ".join(diagnoses[bearing] for bearing in BEARINGS)
        lines.append(f"| {companion:g} | {'ok' if ok else 'FAIL'} | {cells} |")
    lines.extend(
        [
            "",
            "### abs_z (D=3, C=25) — X ekseni 4/4",
            "",
            "| abs_z | 4/4 X | b1 | b2 | b3 | b4 |",
            "|---:|---|---|---|---|---|",
        ]
    )
    for abs_z in (0.0, 12.0, 20.0, 50.0):
        ok, diagnoses = protocol_x(
            store, abs_z=abs_z, dominance=3.0, companion_z=25.0
        )
        cells = " | ".join(diagnoses[bearing] for bearing in BEARINGS)
        lines.append(f"| {abs_z:g} | {'ok' if ok else 'FAIL'} | {cells} |")
    lines.append("")
    return lines


def write_outputs(store: dict[str, dict[str, np.ndarray]]) -> None:
    n_files = len(store["bpfo"][CHANNELS[0]])
    rows = [_row(store, channel) for channel in CHANNELS]
    primary = [row for row in rows if str(row["channel"]).endswith("_x")]
    primary_ok = all(bool(row["ok"]) for row in primary)
    frozen_ok, frozen = protocol_x(
        store,
        abs_z=ENVELOPE_ABS_Z,
        dominance=ENVELOPE_DOMINANCE,
        companion_z=ENVELOPE_COMPANION_Z,
    )

    lines = [
        "# IMS Set 1 envelope teshisi (hold-out)",
        "",
        "> Set 2 envelope esikleri kilit (abs_z=12, D=3, C=25). Retune yok.",
        "> Canli `fault_type` yok (ADR-0013).",
        "",
        "Hilbert 2–10 kHz, sonra ayni BPFO/BPFI/BSF kovalar.",
        "Grafik: `ims_set1_envelope_diagnosis.png`.",
        "",
        "NASA 1st_test: 8 kanal (rulman basina X/Y). Birincil protokol **X**",
        "(Set 2 tek ivmeolcer analogu). Y ayri rapor.",
        "",
        f"Dosya sayisi: **{n_files}**. Baseline ilk {BASELINE}, gec son {TAIL}.",
        "",
        "Beklenti: b3=`bpfi` (ic bilezik), b4=`bsf` (makara), b1/b2=`uncertain`.",
        "",
        f"## Birincil (X) — {'4/4 tuttu' if frozen_ok else '4/4 TUTMADI'}",
        "",
        "| Rulman | NASA | teshis | ilk | #BPFO | #BPFI | #BSF | #e-only | #belirsiz | ok |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in primary:
        mark = "ok" if row["ok"] else "FAIL"
        lines.append(
            f"| {row['bearing']} | {NASA[str(row['bearing'])]} | {row['diagnosis']} "
            f"| {_fmt_first(row['first_at'])} | {row['n_bpfo']} | {row['n_bpfi']} "
            f"| {row['n_bsf']} | {row['n_energy_only_target']} "
            f"| {row['n_uncertain']} | {mark} |"
        )
    lines.extend(
        [
            "",
            f"Donuk esik X teshisleri: {frozen}.",
            "",
            "## Y ekseni (ayni esik, ayri karne)",
            "",
            "| Rulman | NASA | teshis | ilk | #BPFO | #BPFI | #BSF | #belirsiz | ok |",
            "|---|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in rows:
        if not str(row["channel"]).endswith("_y"):
            continue
        mark = "ok" if row["ok"] else "FAIL"
        lines.append(
            f"| {row['bearing']} | {NASA[str(row['bearing'])]} | {row['diagnosis']} "
            f"| {_fmt_first(row['first_at'])} | {row['n_bpfo']} | {row['n_bpfi']} "
            f"| {row['n_bsf']} | {row['n_uncertain']} | {mark} |"
        )
    lines.extend(
        [
            "",
            "## Gec pencere (son 50) — X",
            "",
            "| Rulman | E_BPFO | E_BPFI | E_BSF | BPFO baskin | hedef baskin | "
            "z_BPFO | z_BPFI | z_BSF |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in primary:
        late = row["late"]
        z_late = row["z_late"]
        assert isinstance(late, dict)
        assert isinstance(z_late, dict)
        lines.append(
            f"| {row['bearing']} | {late['bpfo']:.4g} | {late['bpfi']:.4g} | "
            f"{late['bsf']:.4g} | {row['energy_dom_bpfo']:.1f}x | "
            f"{row['energy_dom_target']:.1f}x | {z_late['bpfo']:.1f} | "
            f"{z_late['bpfi']:.1f} | {z_late['bsf']:.1f} |"
        )
    lines.extend(
        [
            "",
            "hedef baskin = NASA bandinin (b3 BPFI, b4 BSF, sagliklilarda BPFO)",
            "enerjisi / max(diger iki). enerji-only = (a) z + enerji orani,",
            "**companion yok**.",
            "",
            "## Hold-out (esik kilit, retune yok)",
            "",
            "b3: max z_BPFI cok yuksek (~1257) ama gec pencerede E_BPFI ~ E_BPFO",
            "(hedef baskin 1.0x) — 3x hakimiyet yok, kural BPFI diyemez.",
            "b4: NASA makara; C=25 ile kural BPFO basar. C=8'de BSF olurdu ama",
            "b2 false BPFO. Grid'de hicbir (C, abs_z) 4/4 yapmiyor.",
            "Envelope Set 2 dis bilezigi ayirdi; Set 1 ic/makara yine imza.",
            "",
            "| Rulman | max z_BPFO | max z_BPFI | max z_BSF |",
            "|---|---:|---:|---:|",
        ]
    )
    for bearing, max_z in _peak_z_x(store):
        lines.append(
            f"| {bearing} | {max_z['bpfo']:.1f} | {max_z['bpfi']:.1f} | "
            f"{max_z['bsf']:.1f} |"
        )
    lines.extend(
        [
            "",
            "Envelope Set 2'de dis bilezik vs kaplin (C=25). Bu hold-out ic",
            "bilezik/makara icin ayni kurali dener; tutmazsa canli yok.",
            "",
        ]
    )
    lines.extend(_sensitivity_x(store))
    lines.extend(
        [
            "Yalniz Set 1 envelope hold-out. Esikler Set 2 envelope (ADR-0013).",
            "`fault_type` bu kurala, hold-out tutmadan, baglanmaz.",
            "",
        ]
    )
    (OUT_DIR / "ims_set1_envelope_diagnosis.md").write_text("\n".join(lines), encoding="utf-8")

    index = np.arange(n_files)
    figure, axes = plt.subplots(4, 1, figsize=(10, 11), sharex=True)
    by_channel = {str(row["channel"]): row for row in rows}
    for bearing in BEARINGS:
        channel = f"{bearing}_x"
        row = by_channel[channel]
        baseline = row["baseline"]
        assert isinstance(baseline, FftBandBaseline)
        for axis, band in zip(axes[:3], BANDS, strict=True):
            series = store[band][channel]
            mean = float(baseline.mean[band])
            std = float(max(baseline.std[band], 1e-12))
            axis.plot(index, (series - mean) / std, label=bearing, linewidth=0.9)
        labels = row["labels"]
        assert isinstance(labels, list)
        codes = np.array([CODE.get(label, 0.0) for label in labels])
        axes[3].plot(index, codes, label=bearing, linewidth=1.1)
    for axis in axes:
        axis.axvline(BASELINE - 0.5, color="gray", linestyle=":", linewidth=0.8)
        axis.grid(True, alpha=0.3)
        axis.legend(loc="upper left")
    axes[0].axhline(ENVELOPE_ABS_Z, color="gray", linestyle="--", linewidth=0.8)
    axes[0].set_ylabel("z env BPFO")
    title = "tuttu" if primary_ok else "TUTMADI"
    axes[0].set_title(f"Set 1 envelope hold-out (X) — {title}")
    axes[1].axhline(ENVELOPE_ABS_Z, color="gray", linestyle="--", linewidth=0.8)
    axes[1].set_ylabel("z env BPFI (b3 hedef)")
    axes[2].axhline(ENVELOPE_ABS_Z, color="gray", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("z env BSF (b4 hedef)")
    axes[3].set_ylabel("teshis")
    axes[3].set_yticks([0, 1, 2, 3], ["belirsiz", "BPFO", "BPFI", "BSF"])
    axes[3].set_xlabel("dosya index")
    figure.tight_layout()
    figure.savefig(OUT_DIR / "ims_set1_envelope_diagnosis.png", dpi=120)
    plt.close(figure)

    if not frozen_ok:
        print("hold-out 4/4 TUTMADI (beklenen bilimsel sonuc olabilir; karne yazildi)")


def main() -> None:
    store = load_bands()
    write_outputs(store)


if __name__ == "__main__":
    main()
