"""Entry point: regenerate the complete Prometheus digital twin.

    cd backend
    python -m data_gen.generate --seed 42            # full world -> data/synthetic + data/_truth
    python -m data_gen.validate                      # integrity + S1-S10 checks -> docs/DATA_VALIDATION_REPORT.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .config import SEED, SYNTH_DIR, TRUTH_DIR, N_CUSTOMERS
from .outputs import build_all
from .world import World


def _write(df: pd.DataFrame, path: Path) -> str:
    df = df.reset_index(drop=True)
    for c in df.columns:  # object columns holding dates -> datetime for a clean parquet schema
        if df[c].dtype == object and len(df) and df[c].dropna().map(type).astype(str).str.contains("date").all() and df[c].notna().any():
            df[c] = pd.to_datetime(df[c])
    df.to_parquet(path, index=False, engine="pyarrow", compression="zstd")
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=False).values.tobytes()).hexdigest()


def generate(seed: int = SEED, out_root: Path | None = None, n_customers: int = N_CUSTOMERS) -> dict:
    t0 = time.time()
    synth = (out_root / "synthetic") if out_root else SYNTH_DIR
    truth_dir = (out_root / "_truth") if out_root else TRUTH_DIR
    print(f"[generate] seed={seed} customers={n_customers}")
    w = World(seed, n_customers=n_customers)
    w.run()
    print(f"[generate] simulated in {time.time() - t0:.0f}s; building tables ...", flush=True)
    obs, truth = build_all(w)
    for d in (synth, truth_dir):
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("*.parquet"):  # clear files only (OneDrive can lock the folder itself)
            f.unlink()
    manifest = {"seed": seed, "tables": {}, "truth": {}}
    for name, df in obs.items():
        manifest["tables"][name] = {"rows": int(len(df)), "sha256": _write(df, synth / f"{name}.parquet")}
    for name, df in truth.items():
        manifest["truth"][name] = {"rows": int(len(df)), "sha256": _write(df, truth_dir / f"{name}.parquet")}
    manifest["elapsed_s"] = round(time.time() - t0, 1)
    (synth / "_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[generate] wrote {len(obs)} observed + {len(truth)} truth tables in {manifest['elapsed_s']}s")
    for k, v in manifest["tables"].items():
        print(f"   {k:28s} {v['rows']:>10,}")
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", type=str, default=None, help="alternative output root (used by the determinism check)")
    ap.add_argument("--customers", type=int, default=N_CUSTOMERS)
    a = ap.parse_args()
    generate(a.seed, Path(a.out) if a.out else None, a.customers)


if __name__ == "__main__":
    main()
