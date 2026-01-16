#!/usr/bin/env python3
"""
PrIM-style 3-panel plot for Memclave vs UPMEM vs CPU.
"""

from __future__ import annotations

import argparse
import io
import sys
from dataclasses import dataclass
from typing import Optional, Tuple, List

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt


# ---------------------------
# Config
# ---------------------------

PRIM_ORDER = [
    "VA", "SEL", "UNI", "BS",
    "HST-S", "HST-L", "RED", "SCAN-SSA", "SCAN-RSS", "TRNS",
    "GEMV", "SpMV", "TS", "BFS", "MLP", "NW",
]
PRIM_SPLIT_AFTER = "TRNS"

REQUIRED = ["Test", "CPU", "DPU", "M_C2D", "M_D2C", "UPMEM", "U_C2D", "U_D2C"]

# Okabe–Ito (colorblind-friendly)
COLOR_CPU = "#009E73"      # bluish green
COLOR_UPMEM = "#E69F00"    # orange
COLOR_MEMCLAVE = "#0072B2" # blue

# Hatches: lines / sparse dots / dense dots
HATCH_CPU = "///"
HATCH_UPMEM = "..."
HATCH_MEMCLAVE = "....."


# ---------------------------
# Data utilities
# ---------------------------

def read_csv(path: str) -> pd.DataFrame:
    if path == "-" or path is None:
        data = sys.stdin.read()
        if not data.strip():
            raise ValueError("No CSV provided on stdin.")
        return pd.read_csv(io.StringIO(data))
    return pd.read_csv(path)

def ensure_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

def to_numeric(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in REQUIRED[1:]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out

def reorder_prim(df: pd.DataFrame) -> pd.DataFrame:
    order_map = {name: i for i, name in enumerate(PRIM_ORDER)}
    out = df.copy()
    out["_orig_idx"] = np.arange(len(out))
    out["_order"] = out["Test"].map(order_map)
    out["_order"] = out["_order"].fillna(len(PRIM_ORDER) + out["_orig_idx"]).astype(int)
    out = out.sort_values(["_order", "_orig_idx"]).drop(columns=["_order", "_orig_idx"])
    return out

def safe_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    den2 = den.where(den != 0, np.nan)
    return num / den2


# ---------------------------
# Formatting utilities
# ---------------------------

def parse_ylim(s: str) -> Tuple[float, float]:
    a, b = s.split(",")
    return float(a.strip()), float(b.strip())

def fmt_val(v: float) -> str:
    if v is None or np.isnan(v) or np.isinf(v):
        return ""
    if abs(v - 1.0) < 1e-12:
        return ""  # baseline is obvious

    # compact, paper-friendly
    if v >= 0.1 and v < 1:
        return f"{v:.2f}"
    elif v >= 1:
        return f"{v:.1f}"
    s = f"{v:.0e}"  # 3e-05
    s = s.replace("e-0", "e-").replace("e+0", "e").replace("e+", "e")
    return s


# ---------------------------
# Plot helpers
# ---------------------------

def apply_axis_style(
    ax,
    x,
    tests,
    sep_x: Optional[float],
    xtick_rotation: float,
    xtick_fontsize: int,
    ytick_fontsize: int,
    xtick_pad: float,
    ytick_pad: float,
):
    ax.set_yscale("log")
    ax.axhline(1.0, linewidth=0.8, alpha=0.8, color="0.35")  # baseline
    # vertical separation line removed by setting sep_x=None, but keep code path:
    if sep_x is not None:
        ax.axvline(sep_x, linestyle="--", linewidth=0.9, alpha=0.85, color="0.35")

    ax.grid(True, which="major", axis="y", linestyle="--", linewidth=0.55, alpha=0.55)

    ax.set_xticks(x)
    ax.set_xticklabels(tests, rotation=xtick_rotation, ha="right")

    ax.tick_params(axis="x", labelsize=xtick_fontsize, pad=xtick_pad)
    ax.tick_params(axis="y", labelsize=ytick_fontsize, pad=ytick_pad)

def set_ylim_with_headroom(ax, ylim: Tuple[float, float], headroom_factor: float):
    y0, y1 = ylim
    ax.set_ylim(y0, y1 * headroom_factor)

def annotate_bars_above(ax, bar_container, values, fontsize=7, rotation=90, offset_pts=2.0):
    """
    offset_pts controls how far above the bar top the label sits.
    Increase this if labels visually touch the bar.
    """
    for rect, v in zip(bar_container.patches, values):
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            continue
        h = rect.get_height()
        if h is None or np.isnan(h) or np.isinf(h) or h <= 0:
            continue

        label = fmt_val(float(v))
        if not label:
            continue

        x = rect.get_x() + rect.get_width() / 2.0
        y = h

        ax.annotate(
            label,
            xy=(x, y),
            xytext=(0, offset_pts),   # <-- knobbed
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=fontsize,
            rotation=rotation,
            clip_on=False,
        )

def annotate_na(ax, x, mask_no_data: np.ndarray, y: float, fontsize=9):
    for xi, m in zip(x, mask_no_data):
        if m:
            ax.text(xi, y, "NA", ha="center", va="bottom", fontsize=fontsize, clip_on=False)

@dataclass(frozen=True)
class BarSpec:
    label: str
    values: np.ndarray
    offset: float
    color: str
    hatch: str

def draw_bars(ax, x, specs: List[BarSpec], width: float, edge_lw: float = 0.30):
    out = []
    for s in specs:
        cont = ax.bar(
            x + s.offset, s.values, width,
            label=s.label,
            color=s.color,
            hatch=s.hatch,
            edgecolor="0.1",
            linewidth=edge_lw,
        )
        out.append((cont, s.values))
    return out


# ---------------------------
# Main
# ---------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="results.csv", help="CSV file path or '-' for stdin.")
    ap.add_argument("--out", default="memclave_prim_plots.pdf")
    ap.add_argument("--figsize", default="14,7.6", help="W,H in inches")
    ap.add_argument("--title", default="")

    ap.add_argument("--ylim-kernel", default="1e-5,1e2")
    ap.add_argument("--ylim-c2d", default="1e-2,1e1")
    ap.add_argument("--ylim-d2c", default="1e-2,1e1")

    # headroom = main knob to ensure the *top of y-axis* leaves space for labels over bars
    ap.add_argument("--headroom", type=float, default=30.0)

    # ---- Font knobs
    ap.add_argument("--title-fontsize", type=int, default=11)
    ap.add_argument("--title-pad", type=float, default=10)

    ap.add_argument("--ylabel-fontsize", type=int, default=10)
    ap.add_argument("--ylabel-pad", type=float, default=8)

    ap.add_argument("--xtick-rotation", type=float, default=35)
    ap.add_argument("--xtick-fontsize", type=int, default=10)
    ap.add_argument("--ytick-fontsize", type=int, default=8)
    ap.add_argument("--xtick-pad", type=float, default=1.0)
    ap.add_argument("--ytick-pad", type=float, default=2.0)

    ap.add_argument("--legend-font", type=int, default=9)

    # annotations over bars
    ap.add_argument("--annot-font", type=int, default=9)
    ap.add_argument("--annot-rotation", type=float, default=90)
    ap.add_argument("--annot-offset", type=float, default=1.5, help="Offset above bar top in points")
    ap.add_argument("--no-annotate", action="store_true")

    # NA marker config
    ap.add_argument("--na-y", type=float, default=1.2)
    ap.add_argument("--na-font", type=int, default=9)

    # ---- Layout knobs
    ap.add_argument("--hspace", type=float, default=0.82)
    ap.add_argument("--top", type=float, default=0.84)
    ap.add_argument("--legend-y", type=float, default=0.89)
    ap.add_argument("--pad-inches", type=float, default=0.01)

    # Styling knobs
    ap.add_argument("--hatch-lw", type=float, default=0.35)
    ap.add_argument("--bar-edge-lw", type=float, default=0.30)

    args = ap.parse_args()

    # PDF friendliness
    mpl.rcParams["hatch.linewidth"] = args.hatch_lw
    mpl.rcParams["pdf.fonttype"] = 42
    mpl.rcParams["ps.fonttype"] = 42

    df = read_csv(args.csv)
    ensure_columns(df)
    df = reorder_prim(to_numeric(df))

    tests = df["Test"].astype(str).tolist()
    x = np.arange(len(tests))

    # remove vertical separator line
    sep_x = None

    # ----- Compute metrics
    s_cpu = np.ones(len(df), dtype=float)
    s_u_kernel = safe_ratio(df["CPU"], df["UPMEM"]).to_numpy()
    s_m_kernel = safe_ratio(df["CPU"], df["DPU"]).to_numpy()

    s_u_c2d = np.where(~df["U_C2D"].isna().to_numpy(), 1.0, np.nan)
    s_m_c2d = safe_ratio(df["U_C2D"], df["M_C2D"]).to_numpy()

    s_u_d2c = np.where(~df["U_D2C"].isna().to_numpy(), 1.0, np.nan)
    s_m_d2c = safe_ratio(df["U_D2C"], df["M_D2C"]).to_numpy()

    # ----- Figure
    W, H = (float(v.strip()) for v in args.figsize.split(","))
    fig, axes = plt.subplots(3, 1, figsize=(W, H), sharex=False)

    # Panel 1
    ax = axes[0]
    w3 = 0.25
    specs = [
        BarSpec("CPU", s_cpu, -w3, COLOR_CPU, HATCH_CPU),
        BarSpec("PIM-insecure (64 DPU)", s_u_kernel, 0.0, COLOR_UPMEM, HATCH_UPMEM),
        BarSpec("Memclave (64 DPU)", s_m_kernel, +w3, COLOR_MEMCLAVE, HATCH_MEMCLAVE),
    ]
    conts_kernel = draw_bars(ax, x, specs, width=w3, edge_lw=args.bar_edge_lw)
    ax.set_title("(a) Subkernel Runtime", pad=args.title_pad, fontsize=args.title_fontsize)
    ax.set_ylabel("Speedup over CPU", fontsize=args.ylabel_fontsize, labelpad=args.ylabel_pad)

    apply_axis_style(
        ax, x, tests, sep_x,
        args.xtick_rotation, args.xtick_fontsize, args.ytick_fontsize,
        args.xtick_pad, args.ytick_pad
    )
    set_ylim_with_headroom(ax, parse_ylim(args.ylim_kernel), args.headroom)

    if not args.no_annotate:
        for cont, vals in conts_kernel:
            annotate_bars_above(
                ax, cont, vals,
                fontsize=args.annot_font,
                rotation=args.annot_rotation,
                offset_pts=args.annot_offset,
            )

    # Panel 2
    ax = axes[1]
    w2 = 0.30
    specs = [
        BarSpec("PIM-insecure", s_u_c2d, -w2/2, COLOR_UPMEM, HATCH_UPMEM),
        BarSpec("Memclave", s_m_c2d, +w2/2, COLOR_MEMCLAVE, HATCH_MEMCLAVE),
    ]
    conts_c2d = draw_bars(ax, x, specs, width=w2, edge_lw=args.bar_edge_lw)
    ax.set_title(r"(b) Guest $\rightarrow$ DPU Transfer", pad=args.title_pad, fontsize=args.title_fontsize)
    ax.set_ylabel("Speedup over UPMEM", fontsize=args.ylabel_fontsize, labelpad=args.ylabel_pad)

    apply_axis_style(
        ax, x, tests, sep_x,
        args.xtick_rotation, args.xtick_fontsize, args.ytick_fontsize,
        args.xtick_pad, args.ytick_pad
    )
    set_ylim_with_headroom(ax, parse_ylim(args.ylim_c2d), args.headroom)
    annotate_na(ax, x, np.isnan(s_u_c2d) & np.isnan(s_m_c2d), y=args.na_y, fontsize=args.na_font)

    if not args.no_annotate:
        for cont, vals in conts_c2d:
            annotate_bars_above(
                ax, cont, vals,
                fontsize=args.annot_font,
                rotation=args.annot_rotation,
                offset_pts=args.annot_offset,
            )

    # Panel 3
    ax = axes[2]
    specs = [
        BarSpec("PIM-insecure", s_u_d2c, -w2/2, COLOR_UPMEM, HATCH_UPMEM),
        BarSpec("Memclave", s_m_d2c, +w2/2, COLOR_MEMCLAVE, HATCH_MEMCLAVE),
    ]
    conts_d2c = draw_bars(ax, x, specs, width=w2, edge_lw=args.bar_edge_lw)
    ax.set_title(r"(c) DPU $\rightarrow$ Guest Transfer", pad=args.title_pad, fontsize=args.title_fontsize)
    ax.set_ylabel("Speedup over UPMEM", fontsize=args.ylabel_fontsize, labelpad=args.ylabel_pad)

    apply_axis_style(
        ax, x, tests, sep_x,
        args.xtick_rotation, args.xtick_fontsize, args.ytick_fontsize,
        args.xtick_pad, args.ytick_pad
    )
    set_ylim_with_headroom(ax, parse_ylim(args.ylim_d2c), args.headroom)
    annotate_na(ax, x, np.isnan(s_u_d2c) & np.isnan(s_m_d2c), y=args.na_y, fontsize=args.na_font)

    if not args.no_annotate:
        for cont, vals in conts_d2c:
            annotate_bars_above(
                ax, cont, vals,
                fontsize=args.annot_font,
                rotation=args.annot_rotation,
                offset_pts=args.annot_offset,
            )

    # Legend
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels,
        loc="upper left",
        bbox_to_anchor=(0.58, args.legend_y),
        ncol=len(labels),
        frameon=True,
        fontsize=args.legend_font,
    )

    if args.title.strip():
        fig.suptitle(args.title)

    fig.subplots_adjust(top=args.top, hspace=args.hspace)
    fig.savefig(args.out, bbox_inches="tight", pad_inches=args.pad_inches)
    print(f"Wrote: {args.out}")

if __name__ == "__main__":
    main()
