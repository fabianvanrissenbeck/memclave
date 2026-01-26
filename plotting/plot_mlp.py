#!/usr/bin/env python3
"""
CSV format (wide):
- First column: System (or Test/Row/Name accepted)
- Remaining columns: N values (e.g., 512,1024,2048,...) as column headers
- Cell values: runtime in ms (consistent definition across systems)

By default, plots *speedup over CPU* (CPU baseline = 1.0), like Fig.3.
You can switch to runtime plot using --mode runtime.
"""

from __future__ import annotations

import argparse
import io
import sys
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt


# Okabe–Ito (colorblind-friendly)
COLOR_CPU = "#009E73"      # bluish green
COLOR_UPMEM = "#E69F00"    # orange
COLOR_MEMCLAVE = "#0072B2" # blue

# Hatches: lines / sparse dots / dense dots
HATCH_CPU = "//"
HATCH_UPMEM = "."
HATCH_MEMCLAVE = ".."

DEFAULT_ORDER = [
    "CPU",
    "PIM-insecure",
    "Memclave",
]

ALIASES = {
    "UPMEM": "PIM-insecure",
    "PIM insecure": "PIM-insecure",
    "PIM-insecure (DPU)": "PIM-insecure",
    "Memclave (enc)": "Memclave",
    "Memclave": "Memclave",
}

SYSTEM_STYLE = {
    "CPU": (COLOR_CPU, HATCH_CPU),
    "PIM-insecure": (COLOR_UPMEM, HATCH_UPMEM),
    "Memclave": (COLOR_MEMCLAVE, HATCH_MEMCLAVE),
}


# ---------------------------
# Helpers
# ---------------------------

def read_csv(path: str) -> pd.DataFrame:
    if path == "-" or path is None:
        data = sys.stdin.read()
        if not data.strip():
            raise ValueError("No CSV provided on stdin.")
        return pd.read_csv(io.StringIO(data))
    return pd.read_csv(path)

def detect_system_col(df: pd.DataFrame) -> str:
    for c in ["System", "Test", "Row", "Name"]:
        if c in df.columns:
            return c
    raise ValueError("CSV must have a first column named one of: System, Test, Row, Name")

def canonicalize_system(name: str) -> str:
    s = str(name).strip()
    return ALIASES.get(s, s)

def parse_N_columns(df: pd.DataFrame, system_col: str) -> List[int]:
    cols = [c for c in df.columns if c != system_col]
    if not cols:
        raise ValueError("CSV must have N columns after the System column (e.g., 512,1024,...)")
    Ns: List[int] = []
    for c in cols:
        try:
            Ns.append(int(str(c).strip()))
        except Exception as e:
            raise ValueError(
                f"Column header '{c}' is not an integer N. "
                f"Please name columns as integers (e.g., 512,1024,...)."
            ) from e
    return Ns

def parse_ylim(s: str) -> Tuple[float, float]:
    a, b = s.split(",")
    return float(a.strip()), float(b.strip())

def set_ylim_with_headroom(ax, ylim: Tuple[float, float], headroom_factor: float):
    y0, y1 = ylim
    ax.set_ylim(y0, y1 * headroom_factor)

def safe_ratio(num: np.ndarray, den: np.ndarray) -> np.ndarray:
    den2 = np.where(den == 0, np.nan, den)
    return num / den2

def fmt_val(v: float, mode: str) -> str:
    if v is None or np.isnan(v) or np.isinf(v):
        return ""
    if mode == "speedup":
        # hide baseline value like Fig3
        if abs(v - 1.0) < 1e-12:
            return ""
        if v >= 0.1:
            return f"{v:.2f}"
        s = f"{v:.0e}"
        return s.replace("e-0", "e-").replace("e+0", "e").replace("e+", "e")
    else:
        # runtime in ms
        if v < 1000:
            return f"{v:.2f}"
        if v < 10000:
            return f"{v:.0f}"
        s = f"{v:.0e}"
        return s.replace("e-0", "e-").replace("e+0", "e").replace("e+", "e")

def annotate_bars(ax, bars, values, mode: str, fontsize=9, rotation=90, offset_pts=1.5):
    for rect, v in zip(bars.patches, values):
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            continue
        h = rect.get_height()
        if h is None or np.isnan(h) or np.isinf(h) or h <= 0:
            continue
        label = fmt_val(float(v), mode)
        if not label:
            continue
        x = rect.get_x() + rect.get_width() / 2.0
        ax.annotate(
            label,
            xy=(x, h),
            xytext=(0, offset_pts),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=fontsize,
            rotation=rotation,
            clip_on=False,
        )

def annotate_na(ax, x_positions, y, mask, fontsize=9):
    for x, m in zip(x_positions, mask):
        if m:
            ax.text(x, y, "NA", ha="center", va="bottom", fontsize=fontsize, clip_on=False)

@dataclass(frozen=True)
class BarSpec:
    label: str
    values: np.ndarray
    offset: float
    color: str
    hatch: str


# ---------------------------
# Main
# ---------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="mlp_results.csv", help="CSV file path or '-' for stdin.")
    ap.add_argument("--out", default="mlp_results.pdf")
    ap.add_argument("--figsize", default="12,4.2", help="W,H in inches")

    ap.add_argument("--mode", choices=["speedup", "runtime"], default="speedup",
                    help="Plot speedup over CPU (default) or raw runtime (ms).")
    ap.add_argument("--baseline", default="CPU",
                    help="Baseline system for speedup mode (default: CPU).")

    ap.add_argument("--title", default="MLP: per-layer speedup over CPU")
    ap.add_argument("--xlabel", default="Problem size N")

    # Defaults updated for speedup plot
    ap.add_argument("--ylabel", default="Speedup over CPU")
    ap.add_argument("--ylim", default="1e-2,1e3", help="ymin,ymax (log scale). Tune to your data.")
    ap.add_argument("--headroom", type=float, default=1.6)

    ap.add_argument("--order", default=",".join(DEFAULT_ORDER),
                    help="Comma-separated row order (system names as in CSV after aliasing).")

    # fonts + layout knobs
    ap.add_argument("--title-fontsize", type=int, default=24)
    ap.add_argument("--title-pad", type=float, default=10)
    ap.add_argument("--label-fontsize", type=int, default=19)
    ap.add_argument("--xtick-fontsize", type=int, default=20)
    ap.add_argument("--ytick-fontsize", type=int, default=17)
    ap.add_argument("--xtick-pad", type=float, default=7.0)
    ap.add_argument("--ytick-pad", type=float, default=5.0)
    ap.add_argument("--legend-font", type=int, default=18)
    ap.add_argument("--legend-ncol", type=int, default=3)

    # bar visuals
    ap.add_argument("--bar-edge-lw", type=float, default=0.30)
    ap.add_argument("--hatch-lw", type=float, default=0.35)
    ap.add_argument("--bar-gap", type=float, default=0.18)

    # annotations
    ap.add_argument("--annot-font", type=int, default=14)
    ap.add_argument("--annot-rotation", type=float, default=90)
    ap.add_argument("--annot-offset", type=float, default=1.5)
    ap.add_argument("--no-annotate", action="store_true")
    ap.add_argument("--na-y", type=float, default=1.2)
    ap.add_argument("--na-font", type=int, default=9)

    ap.add_argument("--pad-inches", type=float, default=0.01)
    args = ap.parse_args()

    mpl.rcParams["hatch.linewidth"] = args.hatch_lw
    mpl.rcParams["pdf.fonttype"] = 42
    mpl.rcParams["ps.fonttype"] = 42

    df = read_csv(args.csv)
    system_col = detect_system_col(df)
    df = df.copy()
    df[system_col] = df[system_col].map(canonicalize_system)

    Ns = parse_N_columns(df, system_col)
    Ns_sorted = sorted(Ns)
    df = df[[system_col] + [str(n) for n in Ns_sorted]]

    for n in Ns_sorted:
        df[str(n)] = pd.to_numeric(df[str(n)], errors="coerce")

    data_rt: Dict[str, np.ndarray] = {}
    for _, row in df.iterrows():
        sysname = str(row[system_col])
        vals = row[[str(n) for n in Ns_sorted]].to_numpy(dtype=float)
        data_rt[sysname] = vals

    order = [canonicalize_system(s.strip()) for s in args.order.split(",") if s.strip()]
    missing = [s for s in order if s not in data_rt]
    if missing:
        print(f"Warning: systems not found in CSV and will be skipped: {missing}", file=sys.stderr)
    order = [s for s in order if s in data_rt]
    if not order:
        raise ValueError("No valid systems found after applying --order and CSV contents.")

    # Compute plotted values
    mode = args.mode
    baseline = canonicalize_system(args.baseline)

    if mode == "speedup":
        if baseline not in data_rt:
            raise ValueError(f"--mode speedup requires baseline '{baseline}' to exist in CSV.")
        base = data_rt[baseline]

        data_plot: Dict[str, np.ndarray] = {}
        for s in order:
            if s == baseline:
                # hard baseline = 1.0 (even if runtime has NaNs)
                data_plot[s] = np.ones_like(base, dtype=float)
                # but if baseline runtime is NaN at some N, speedups are meaningless -> mark those as NaN
                data_plot[s] = np.where(np.isnan(base), np.nan, data_plot[s])
            else:
                data_plot[s] = safe_ratio(base, data_rt[s])
    else:
        data_plot = data_rt

    # X positions
    x = np.arange(len(Ns_sorted), dtype=float)

    # Bars per group
    K = len(order)
    group_width = 1.0 - args.bar_gap
    bar_width = group_width / K
    offsets = (np.arange(K) - (K - 1) / 2.0) * bar_width

    specs: List[BarSpec] = []
    for i, sysname in enumerate(order):
        color, hatch = SYSTEM_STYLE.get(sysname, ("0.7", "//"))
        specs.append(BarSpec(
            label=sysname,
            values=data_plot[sysname],
            offset=float(offsets[i]),
            color=color,
            hatch=hatch,
        ))

    # Figure
    W, H = (float(v.strip()) for v in args.figsize.split(","))
    fig, ax = plt.subplots(1, 1, figsize=(W, H))

    ax.set_yscale("log")
    ax.grid(True, which="major", axis="y", linestyle="--", linewidth=0.55, alpha=0.55)

    if mode == "speedup":
        ax.axhline(1.0, linewidth=0.8, alpha=0.8, color="0.35")

    containers = []
    for s in specs:
        cont = ax.bar(
            x + s.offset,
            s.values,
            width=bar_width,
            label=s.label,
            color=s.color,
            hatch=s.hatch,
            edgecolor="0.1",
            linewidth=args.bar_edge_lw,
        )
        containers.append((cont, s.values))

    ax.set_xticks(x)
    ax.set_xticklabels([str(n) for n in Ns_sorted])
    ax.tick_params(axis="x", labelsize=args.xtick_fontsize, pad=args.xtick_pad)
    ax.tick_params(axis="y", labelsize=args.ytick_fontsize, pad=args.ytick_pad)

    # Titles/labels
    ax.set_title(args.title, pad=args.title_pad, fontsize=args.title_fontsize)
    ax.set_xlabel(args.xlabel, fontsize=args.label_fontsize)
    ax.set_ylabel(args.ylabel, fontsize=args.label_fontsize)

    set_ylim_with_headroom(ax, parse_ylim(args.ylim), args.headroom)

    if not args.no_annotate:
        for cont, vals in containers:
            annotate_bars(
                ax, cont, vals,
                mode=mode,
                fontsize=args.annot_font,
                rotation=args.annot_rotation,
                offset_pts=args.annot_offset,
            )

    # NA marker if all systems are NaN at a given N
    mat = np.vstack([data_plot[s] for s in order])
    na_mask = np.all(np.isnan(mat), axis=0)
    annotate_na(ax, x, y=args.na_y, mask=na_mask, fontsize=args.na_font)

    ax.legend(
        loc="upper left",
        ncol=args.legend_ncol,
        frameon=True,
        fontsize=args.legend_font,
    )

    fig.savefig(args.out, bbox_inches="tight", pad_inches=args.pad_inches)
    print(f"Wrote: {args.out}")

if __name__ == "__main__":
    main()
