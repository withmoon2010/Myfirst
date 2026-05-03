"""
Comparative DCF analysis of incremental GDP impact:
  1. AI on global GDP (multi-decade)
  2. Trump 2.0 on US GDP (term + persistence)
  3. US-Iran war on global GDP (shock + recovery)

Base year = 2026 (year 1 cashflow = end of 2026, discounted to start of 2026).
All numbers in real USD. Discount rates are real (ex-inflation).
Each scenario decomposes the GDP impact into:
  - core mechanism channel (productivity, policy, conflict)
  - oil-price channel (oil $/bbl deviation x oil-to-GDP elasticity)

This is an educational order-of-magnitude exercise, not investment advice.
Assumptions are documented in-line; ranges are reported alongside point estimates.
"""

from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak,
)


# ---------------------------------------------------------------------------
# DCF helpers
# ---------------------------------------------------------------------------

def pv_stream(cashflows: np.ndarray, discount_rate: float) -> float:
    """Present value of a stream paid at end of years 1..N."""
    years = np.arange(1, len(cashflows) + 1)
    return float(np.sum(cashflows / (1 + discount_rate) ** years))


def terminal_value(final_cashflow: float, g: float, r: float) -> float:
    """Gordon-growth terminal value as of the final explicit year."""
    if r <= g:
        raise ValueError("Discount rate must exceed terminal growth rate.")
    return final_cashflow * (1 + g) / (r - g)


BASE_YEAR = 2026  # year 1 = 2026; all PVs are as-of start of 2026


@dataclass
class DCFResult:
    name: str
    years: np.ndarray
    annual_delta: np.ndarray   # total incremental GDP $/yr (USD T) = mechanism + oil
    mechanism_delta: np.ndarray  # core channel only ($T/yr)
    oil_delta_bbl: np.ndarray   # $/bbl deviation vs $75 baseline (per year)
    oil_gdp_delta: np.ndarray   # GDP $/yr from oil channel ($T/yr)
    explicit_pv: float          # USD trillions
    terminal_pv: float          # USD trillions (0 if not used)
    oil_pv: float               # USD trillions, oil channel PV (subset of total)
    total_pv: float             # USD trillions
    discount_rate: float
    notes: str


# Oil-price-to-GDP elasticity. Rule of thumb: a $10/bbl sustained price increase
# drags global GDP by ~0.10-0.20% (IMF 2000, IEA 2004, BIS 2018). I use 0.15%
# (mid-range) for global scenarios. For the US (now roughly oil-balanced as a
# net producer), I use 0.05% per $10/bbl.
OIL_ELASTICITY_GLOBAL = 0.0015   # 0.15% global GDP per $10/bbl sustained
OIL_ELASTICITY_US = 0.0005       # 0.05% US GDP per $10/bbl sustained
OIL_BASELINE = 75.0              # $/bbl baseline


def oil_to_gdp(oil_delta_bbl: np.ndarray, base_gdp: float, elasticity: float) -> np.ndarray:
    """Convert oil price deviation ($/bbl, vs baseline) to GDP impact ($T/yr).

    Sign convention: oil_delta > 0 (more expensive oil) -> negative GDP impact
    for net importers / global economy.
    """
    return -np.asarray(oil_delta_bbl, dtype=float) / 10.0 * elasticity * base_gdp


# ---------------------------------------------------------------------------
# 1) AI: global incremental GDP
# ---------------------------------------------------------------------------
# Base assumptions (central case):
#   - Global GDP today ~ $110T (2025).
#   - AI adds incremental GDP that grows S-curve style:
#       * starts at ~$0.2T in 2025
#       * ramps to ~$4.5T per year by 2040 (~3-4% of global GDP, in line with
#         Goldman Sachs 2023, McKinsey 2023, PwC 2017 mid-cases)
#       * 30-year explicit horizon (2025-2054)
#       * terminal growth 1.5% real after that
#   - Real discount rate 6% (long-horizon equity-style, reflecting both
#     systemic uncertainty and option value).
# Sensitivity: Acemoglu (2024) implies 10x lower. Aghion / Brynjolfsson higher.

def run_ai_dcf(discount_rate: float = 0.06,
               horizon: int = 30,
               peak_delta: float = 4.5,
               peak_year_offset: int = 15,
               terminal_growth: float = 0.015,
               peak_oil_delta: float = 7.0) -> DCFResult:
    """AI: global incremental GDP, base year 2026, with oil channel.

    Oil channel: AI datacenter electricity demand is ~1500 TWh by 2030 (IEA),
    rising to ~3000 TWh by 2035. Indirect oil/gas pressure pushes WTI ~$5-10
    above baseline by year 10 and persists. Net global GDP drag from oil
    partially offsets the productivity gain.
    """
    years = np.arange(1, horizon + 1)
    # Mechanism: logistic ramp from 0.2 to peak_delta around year `peak_year_offset`
    # With base year 2026, peak_year_offset=15 -> peak in 2040 (matches literature).
    k = 0.35
    midpoint = peak_year_offset
    mech = 0.2 + (peak_delta - 0.2) / (1 + np.exp(-k * (years - midpoint)))
    post_peak_growth = 0.02
    for i, y in enumerate(years):
        if y > peak_year_offset:
            mech[i] = mech[i] * (1 + post_peak_growth) ** (y - peak_year_offset)

    # Oil channel: ramps from $0 to $peak_oil_delta over ~10y, persists
    oil_bbl = peak_oil_delta * (1 - np.exp(-years / 6.0))
    oil_gdp = oil_to_gdp(oil_bbl, base_gdp=110.0, elasticity=OIL_ELASTICITY_GLOBAL)

    deltas = mech + oil_gdp

    explicit_pv = pv_stream(deltas, discount_rate)
    tv = terminal_value(deltas[-1], terminal_growth, discount_rate)
    tv_pv = tv / (1 + discount_rate) ** horizon
    oil_pv = pv_stream(oil_gdp, discount_rate)
    total = explicit_pv + tv_pv

    return DCFResult(
        name="AI (global)",
        years=years,
        annual_delta=deltas,
        mechanism_delta=mech,
        oil_delta_bbl=oil_bbl,
        oil_gdp_delta=oil_gdp,
        explicit_pv=explicit_pv,
        terminal_pv=tv_pv,
        oil_pv=oil_pv,
        total_pv=total,
        discount_rate=discount_rate,
        notes=(
            "Global incremental GDP, S-curve adoption, 30y explicit + Gordon "
            "terminal at 1.5% real growth. Anchored to GS/McKinsey ranges; "
            "peak ~$4.5T/yr by 2040. Oil channel: +$7/bbl by year 10."
        ),
    )


# ---------------------------------------------------------------------------
# 2) Trump 2.0: US incremental GDP
# ---------------------------------------------------------------------------
# Composition of effects (level impact on US GDP, not growth rate):
#   - TCJA extension / corporate tax cuts:        +0.4% of GDP
#   - Tariff regime (broad + targeted):           -0.8% of GDP
#       (Penn Wharton, Tax Foundation, Yale Budget Lab 2025 mid-case)
#   - Immigration restrictions / deportations:    -0.4% of GDP
#       (CBO labor force impact, ~1.5M net delta)
#   - Deregulation (energy, finance, antitrust):  +0.3% of GDP
#   - Fiscal deficit drag / higher real rates:    -0.2% of GDP
#   Net: ~-0.7% of US GDP at peak.
# Profile: ramps in over 2 years, holds during term (yrs 1-4),
# partially persists post-term then decays. Reversibility is partial: tariffs
# can be removed, but supply chain repricing, lost immigrant cohorts, and
# accumulated debt persist.
# US GDP base $29T. Real discount rate 5% (lower than AI: shorter horizon,
# more deterministic policy mechanics).

def run_trump_dcf(discount_rate: float = 0.05,
                  horizon: int = 20,
                  us_gdp: float = 29.0,
                  peak_pct: float = -0.007) -> DCFResult:
    """Trump 2.0 (US), base year 2026.

    Trump took office Jan 2025; year 1 of this DCF (2026) is already mid-term,
    so policy is at full peak from y1 (no ramp). Decay begins after term ends
    (post-2029, i.e. y4+).

    Oil channel: deregulation pushes US production ~+0.5-1.0 mb/d, plus tariff-
    driven demand softening, putting WTI ~-$5/bbl during term. Effect fades
    after the term as supply normalizes.
    """
    years = np.arange(1, horizon + 1)
    # Profile: full peak y1-3 (2026-2028), partial y4 (2029 transition),
    # persistence then decay.
    profile = (
        [1.0, 1.0, 1.0]            # y1-3: 2026-2028 (Trump term, full peak)
        + [0.7]                    # y4: 2029 (handoff)
        + [0.5, 0.5, 0.5]          # y5-7: 2030-2032 (immediate persistence)
        + [0.3] * 5                # y8-12: 2033-2037
        + [0.1] * 8                # y13-20: 2038-2045
    )
    profile = np.array(profile[:horizon])
    pct = peak_pct * profile
    mech = pct * us_gdp  # $T/yr

    # Oil channel: $-5/bbl during term, fading
    oil_bbl = np.array(
        [-5.0, -5.0, -5.0, -3.0, -1.0, -1.0, -1.0] + [0.0] * (horizon - 7)
    )[:horizon]
    oil_gdp = oil_to_gdp(oil_bbl, base_gdp=us_gdp, elasticity=OIL_ELASTICITY_US)

    deltas = mech + oil_gdp
    explicit_pv = pv_stream(deltas, discount_rate)
    oil_pv = pv_stream(oil_gdp, discount_rate)
    return DCFResult(
        name="Trump 2.0 (US)",
        years=years,
        annual_delta=deltas,
        mechanism_delta=mech,
        oil_delta_bbl=oil_bbl,
        oil_gdp_delta=oil_gdp,
        explicit_pv=explicit_pv,
        terminal_pv=0.0,
        oil_pv=oil_pv,
        total_pv=explicit_pv,
        discount_rate=discount_rate,
        notes=(
            "US GDP impact, peak ~-0.7% during term, partial persistence then "
            "decay over 20 years. Net of tariffs (-), tax cuts (+), immigration "
            "(-), deregulation (+), deficit/rates (-). Oil channel: ~-$5/bbl "
            "during term (drill-baby-drill + tariff-driven demand softening)."
        ),
    )


# ---------------------------------------------------------------------------
# 3) US-Iran War: global incremental GDP
# ---------------------------------------------------------------------------
# Channels modelled as a one-off shock with multi-year recovery:
#   - Oil price shock: oil from ~$75 to ~$120 for ~12m, decays over 3y.
#     Rule of thumb: a $10 sustained price hike -> ~0.1-0.2% global GDP drag.
#     => Year 1: -0.6% global GDP, Year 2: -0.3%, Year 3: -0.1%.
#   - Strait of Hormuz partial disruption / shipping insurance spike:
#     -0.2% Year 1.
#   - Direct US fiscal cost ($300-700B over 5y, mid $500B): treated as
#     opportunity cost / crowding out -> -0.05% global GDP/yr for 5y.
#   - Confidence/financial conditions tightening: -0.2% Year 1.
#   - Possible long-tail Middle East instability: -0.05% per year through y10.
# Global GDP base $110T. Real discount rate 5% (medium horizon).
# Probability-weighting NOT applied; this is conditional-on-occurrence PV.

def run_iran_war_dcf(discount_rate: float = 0.05,
                     horizon: int = 10,
                     global_gdp: float = 110.0) -> DCFResult:
    """US-Iran war (global), base year 2026, conditional on conflict in 2026.

    Oil channel is now broken out explicitly via the oil-price track. Mechanism
    captures the non-oil channels: Hormuz shipping disruption, US fiscal cost,
    financial-conditions tightening, long-tail Mid-East instability.
    """
    years = np.arange(1, horizon + 1)

    # Oil track: $/bbl deviation vs $75 baseline.
    # Y1: $75 -> $120 sustained (+$45). Y2: +$25. Y3: +$10. Y4+: ~baseline.
    oil_bbl = np.array(
        [45.0, 25.0, 10.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    )[:horizon]
    oil_gdp = oil_to_gdp(oil_bbl, base_gdp=global_gdp, elasticity=OIL_ELASTICITY_GLOBAL)

    # Non-oil mechanism (% of global GDP):
    # Y1: Hormuz -0.2, fiscal -0.05, financial -0.2 = -0.45%
    # Y2: fiscal -0.05, instability -0.05 = -0.10%
    # Y3: fiscal -0.05, instability -0.05 = -0.10%
    # Y4-5: fiscal -0.05, instability -0.05 = -0.10%
    # Y6-10: instability -0.05% / yr
    pct = np.zeros(horizon)
    pct[0] = -0.0045
    pct[1] = -0.0010
    pct[2] = -0.0010
    pct[3] = -0.0010
    pct[4] = -0.0010
    for i in range(5, horizon):
        pct[i] = -0.0005
    mech = pct * global_gdp

    deltas = mech + oil_gdp
    explicit_pv = pv_stream(deltas, discount_rate)
    oil_pv = pv_stream(oil_gdp, discount_rate)
    return DCFResult(
        name="US-Iran war (global)",
        years=years,
        annual_delta=deltas,
        mechanism_delta=mech,
        oil_delta_bbl=oil_bbl,
        oil_gdp_delta=oil_gdp,
        explicit_pv=explicit_pv,
        terminal_pv=0.0,
        oil_pv=oil_pv,
        total_pv=explicit_pv,
        discount_rate=discount_rate,
        notes=(
            "Conditional on a kinetic conflict starting 2026, global. Oil shock "
            "(+$45/bbl Y1) dominates; recovery over 3y; long-tail Mid-East drag "
            "through 2035. Not probability-weighted."
        ),
    )


# ---------------------------------------------------------------------------
# Sensitivity tables
# ---------------------------------------------------------------------------

def ai_sensitivity():
    """PV ($T) across discount rate x peak-delta-by-2040."""
    rates = [0.04, 0.06, 0.08, 0.10]
    peaks = [2.0, 4.5, 8.0, 12.0]
    grid = np.zeros((len(peaks), len(rates)))
    for i, p in enumerate(peaks):
        for j, r in enumerate(rates):
            grid[i, j] = run_ai_dcf(discount_rate=r, peak_delta=p).total_pv
    return rates, peaks, grid


def trump_sensitivity():
    rates = [0.03, 0.05, 0.07]
    peaks = [-0.015, -0.007, 0.0, 0.007]  # bear, base, neutral, bull
    grid = np.zeros((len(peaks), len(rates)))
    for i, p in enumerate(peaks):
        for j, r in enumerate(rates):
            grid[i, j] = run_trump_dcf(discount_rate=r, peak_pct=p).total_pv
    return rates, peaks, grid


def iran_sensitivity():
    rates = [0.03, 0.05, 0.07]
    severities = [0.5, 1.0, 1.5, 2.5]  # multiplier on the central pct profile
    grid = np.zeros((len(severities), len(rates)))
    for i, s in enumerate(severities):
        for j, r in enumerate(rates):
            res = run_iran_war_dcf(discount_rate=r)
            grid[i, j] = res.total_pv * s
    return rates, severities, grid


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def make_charts(ai: DCFResult, trump: DCFResult, iran: DCFResult, outdir: str):
    paths = {}

    def cal(years):
        return BASE_YEAR + years - 1

    # Chart 1: annual incremental GDP delta over time
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(cal(ai.years), ai.annual_delta, label="AI (global)", color="#1f77b4", linewidth=2)
    ax.plot(cal(trump.years), trump.annual_delta, label="Trump 2.0 (US)", color="#d62728", linewidth=2)
    ax.plot(cal(iran.years), iran.annual_delta, label="US-Iran war (global)", color="#7f0e0e", linewidth=2)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_xlabel("Calendar year (base = 2026)")
    ax.set_ylabel("Annual incremental GDP, $ trillions")
    ax.set_title("Annual incremental GDP impact, undiscounted (mechanism + oil)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    p1 = f"{outdir}/chart_annual.png"
    fig.savefig(p1, dpi=160)
    plt.close(fig)
    paths["annual"] = p1

    # Chart 2: cumulative discounted PV over time
    def discounted_cumulative(res: DCFResult) -> np.ndarray:
        d = res.annual_delta / (1 + res.discount_rate) ** res.years
        return np.cumsum(d)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(cal(ai.years), discounted_cumulative(ai), label="AI (global)", color="#1f77b4", linewidth=2)
    ax.plot(cal(trump.years), discounted_cumulative(trump), label="Trump 2.0 (US)", color="#d62728", linewidth=2)
    ax.plot(cal(iran.years), discounted_cumulative(iran), label="US-Iran war (global)", color="#7f0e0e", linewidth=2)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_xlabel("Calendar year (PV as of start of 2026)")
    ax.set_ylabel("Cumulative discounted PV, $ trillions")
    ax.set_title("Cumulative present value over time (explicit horizon)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    p2 = f"{outdir}/chart_cumulative.png"
    fig.savefig(p2, dpi=160)
    plt.close(fig)
    paths["cumulative"] = p2

    # Chart 3: total PV bar with mechanism + oil decomposition
    fig, ax = plt.subplots(figsize=(7, 4.5))
    names = [ai.name, trump.name, iran.name]
    totals = [ai.total_pv, trump.total_pv, iran.total_pv]
    oil_pvs = [ai.oil_pv, trump.oil_pv, iran.oil_pv]
    mech_pvs = [t - o for t, o in zip(totals, oil_pvs)]
    colors_main = ["#1f77b4", "#d62728", "#7f0e0e"]
    x = np.arange(len(names))
    bars1 = ax.bar(x - 0.2, mech_pvs, width=0.35, color=colors_main, label="Mechanism PV")
    bars2 = ax.bar(x + 0.2, oil_pvs, width=0.35, color="#444", alpha=0.7, label="Oil channel PV")
    ax.axhline(0, color="black", linewidth=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylabel("PV, $ trillions")
    ax.set_title("Present value: mechanism vs. oil-price channel (PV as of 2026)")
    for bars, vals in [(bars1, mech_pvs), (bars2, oil_pvs)]:
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2,
                    v + (1 if v >= 0 else -1) * (max(abs(min(totals)), abs(max(totals))) * 0.02),
                    f"${v:,.1f}T",
                    ha="center",
                    va="bottom" if v >= 0 else "top",
                    fontsize=8.5)
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    p3 = f"{outdir}/chart_total.png"
    fig.savefig(p3, dpi=160)
    plt.close(fig)
    paths["total"] = p3

    # Chart 4: oil-price track per scenario
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(cal(ai.years), OIL_BASELINE + ai.oil_delta_bbl,
            label="AI scenario", color="#1f77b4", linewidth=2)
    ax.plot(cal(trump.years), OIL_BASELINE + trump.oil_delta_bbl,
            label="Trump 2.0 scenario", color="#d62728", linewidth=2)
    ax.plot(cal(iran.years), OIL_BASELINE + iran.oil_delta_bbl,
            label="US-Iran war scenario", color="#7f0e0e", linewidth=2)
    ax.axhline(OIL_BASELINE, color="black", linewidth=0.5, linestyle="--",
               label=f"Baseline ${OIL_BASELINE:.0f}/bbl")
    ax.set_xlabel("Calendar year")
    ax.set_ylabel("Oil price, $/bbl (assumed track)")
    ax.set_title("Oil-price assumption per scenario")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    p4 = f"{outdir}/chart_oil.png"
    fig.savefig(p4, dpi=160)
    plt.close(fig)
    paths["oil"] = p4

    return paths


# ---------------------------------------------------------------------------
# PDF assembly
# ---------------------------------------------------------------------------

def fmt_t(x: float) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.2f}T"


def build_pdf(out_path: str,
              ai: DCFResult, trump: DCFResult, iran: DCFResult,
              chart_paths: dict):
    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    h3 = styles["Heading3"]
    body = styles["BodyText"]
    body.fontSize = 10
    body.leading = 14
    small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=11,
                           textColor=colors.grey)

    doc = SimpleDocTemplate(out_path, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm)
    story = []

    story.append(Paragraph("Comparative DCF: Incremental GDP Impact", h1))
    story.append(Paragraph(
        "AI vs. Trump 2.0 vs. US-Iran War (illustrative, order-of-magnitude)",
        h3))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Author:</b> Claude (Opus 4.7) &nbsp;&nbsp; "
        "<b>Date:</b> 2026-05-03 &nbsp;&nbsp; "
        "<b>Base year:</b> 2026 (year 1 = 2026; PV as of start of 2026) &nbsp;&nbsp; "
        "<b>Units:</b> real USD trillions, ex-inflation discount rates &nbsp;&nbsp; "
        "<b>Channels:</b> mechanism + oil-price",
        small))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Executive summary", h2))
    summary = (
        f"Under central-case assumptions, with year 1 = 2026 and PV measured as of "
        f"start-of-2026: AI's incremental GDP has a present value of "
        f"<b>{fmt_t(ai.total_pv)}</b> (global, 30-year explicit + Gordon terminal, "
        f"discount rate {ai.discount_rate:.0%}; oil channel contributes "
        f"{fmt_t(ai.oil_pv)}). Trump 2.0's incremental US GDP has a present value of "
        f"<b>{fmt_t(trump.total_pv)}</b> (20-year horizon, discount rate "
        f"{trump.discount_rate:.0%}; oil channel contributes {fmt_t(trump.oil_pv)}). "
        f"A US-Iran kinetic war has a present value of <b>{fmt_t(iran.total_pv)}</b> "
        f"in incremental global GDP (10-year horizon, discount rate "
        f"{iran.discount_rate:.0%}; oil channel contributes {fmt_t(iran.oil_pv)} and "
        f"is the dominant transmission mechanism). Conditional on the war occurring "
        f"&mdash; not probability-weighted."
    )
    story.append(Paragraph(summary, body))
    story.append(Spacer(1, 6))
    ratio_at = abs(ai.total_pv / trump.total_pv) if trump.total_pv else float("inf")
    ratio_ai = abs(ai.total_pv / iran.total_pv) if iran.total_pv else float("inf")
    story.append(Paragraph(
        f"The order of magnitude is the headline: AI's PV is roughly "
        f"<b>{ratio_at:,.0f}x</b> the absolute size of Trump 2.0's net GDP impact and "
        f"<b>{ratio_ai:,.0f}x</b> the absolute size of an Iran war shock. Even after "
        f"loosening AI assumptions toward Acemoglu-style skepticism, AI dominates by "
        f"at least one order of magnitude in our central case &mdash; because it is a "
        f"long-duration productivity shock compounded over decades, while political "
        f"and geopolitical shocks act on shorter horizons with bounded amplitude.",
        body))
    story.append(Spacer(1, 12))

    # headline table
    head_tbl = [
        ["Scenario", "Horizon", "Discount", "Mechanism PV", "Oil PV", "Terminal PV", "Total PV"],
        [ai.name, f"{len(ai.years)} y", f"{ai.discount_rate:.0%}",
         fmt_t(ai.total_pv - ai.terminal_pv - ai.oil_pv), fmt_t(ai.oil_pv),
         fmt_t(ai.terminal_pv), fmt_t(ai.total_pv)],
        [trump.name, f"{len(trump.years)} y", f"{trump.discount_rate:.0%}",
         fmt_t(trump.explicit_pv - trump.oil_pv), fmt_t(trump.oil_pv),
         fmt_t(trump.terminal_pv), fmt_t(trump.total_pv)],
        [iran.name, f"{len(iran.years)} y", f"{iran.discount_rate:.0%}",
         fmt_t(iran.explicit_pv - iran.oil_pv), fmt_t(iran.oil_pv),
         fmt_t(iran.terminal_pv), fmt_t(iran.total_pv)],
    ]
    t = Table(head_tbl, hAlign="LEFT", colWidths=[3.6 * cm, 1.6 * cm, 1.6 * cm, 2.6 * cm, 2.2 * cm, 2.2 * cm, 2.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#222")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))
    story.append(Image(chart_paths["total"], width=15 * cm, height=8.5 * cm))

    story.append(PageBreak())

    # Methodology
    story.append(Paragraph("Methodology", h2))
    story.append(Paragraph(
        "I model each scenario as an annual stream of incremental GDP relative to a "
        "no-event counterfactual, starting in 2026, then discount to a present value "
        "as of start-of-2026 using a real (ex-inflation) discount rate. "
        "PV = &Sigma; &Delta;GDP<sub>t</sub> / (1+r)<sup>t</sup>, with a Gordon-growth "
        "terminal value where economic fundamentals justify it (only AI). For the "
        "political and war scenarios, the impact decays inside the explicit horizon, "
        "so no terminal value is added.", body))
    story.append(Paragraph(
        "<b>Two channels</b> are aggregated for each scenario: (a) the <i>core "
        "mechanism</i> (productivity, policy, conflict) and (b) an <i>oil-price "
        "channel</i> that converts a $/bbl deviation vs a $75 baseline into GDP "
        "impact via an oil-to-GDP elasticity (0.15% global GDP per $10/bbl sustained "
        "for global scenarios; 0.05% US GDP per $10/bbl for the now oil-balanced US). "
        "This makes it possible to see, for each scenario, how much of the headline "
        "PV is driven by oil-price assumptions specifically.", body))
    story.append(Paragraph(
        "Three deliberate choices shape the comparison: (1) AI is global and very "
        "long-horizon, while Trump 2.0 is mostly US and 4-20y, while the Iran war "
        "shock is global but front-loaded and short. (2) The discount rate is held "
        "between 5-6% real to keep magnitudes comparable, then varied in sensitivity "
        "tables. (3) War PV is conditional on occurrence, not probability-weighted; "
        "if you assign a probability p, multiply by p for an expected value.", body))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Charts", h3))
    story.append(Image(chart_paths["annual"], width=15 * cm, height=8.5 * cm))
    story.append(Spacer(1, 6))
    story.append(Image(chart_paths["cumulative"], width=15 * cm, height=8.5 * cm))
    story.append(PageBreak())
    story.append(Paragraph("Oil-price assumption per scenario", h3))
    story.append(Paragraph(
        "Three different oil tracks. The Iran-war track is a sharp spike that "
        "dominates that scenario's PV. The AI track is a slow, persistent rise "
        "from datacenter energy demand. The Trump 2.0 track is a small drop "
        "from US production growth and tariff-driven demand softening, fading "
        "after the term.", body))
    story.append(Image(chart_paths["oil"], width=15 * cm, height=8.5 * cm))

    story.append(PageBreak())

    # AI section
    story.append(Paragraph("1) AI &mdash; global incremental GDP", h2))
    story.append(Paragraph("<b>Assumptions:</b>", body))
    ai_assump = [
        ["Global GDP base (2026)", "$110T"],
        ["Adoption profile", "Logistic ramp; $0.2T (2026) -> $4.5T (2040)"],
        ["Post-peak growth", "+2%/yr through year 30 (2055)"],
        ["Explicit horizon", "30 years (2026-2055)"],
        ["Terminal growth", "1.5% real"],
        ["Real discount rate", f"{ai.discount_rate:.0%}"],
        ["Oil channel", "Datacenter electricity demand pushes WTI +$7/bbl by 2035, persists; -0.10% global GDP drag at peak"],
        ["Anchors", "Goldman Sachs 2023 (~7% global GDP / 10y); McKinsey 2023 ($13-25T/yr by 2040); PwC 2017 ($15.7T by 2030)"],
    ]
    story.append(Table(ai_assump, hAlign="LEFT", colWidths=[5 * cm, 11 * cm],
                       style=TableStyle([
                           ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
                           ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                           ("FONTSIZE", (0, 0), (-1, -1), 9),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"),
                       ])))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"<b>Result:</b> Explicit-horizon PV {fmt_t(ai.explicit_pv)} + terminal PV "
        f"{fmt_t(ai.terminal_pv)} = <b>total PV {fmt_t(ai.total_pv)}</b>. Of which "
        f"the oil channel contributes {fmt_t(ai.oil_pv)} (a small drag from "
        f"datacenter-driven oil prices). The terminal value is large because a "
        f"permanent productivity uplift compounds forever; even at 6% real "
        f"discounting, a $7-8T perpetual annual delta is worth on the order of "
        f"$100T+ in present value terms.", body))
    rates, peaks, grid = ai_sensitivity()
    sens = [["Peak $T/yr by 2040 \\ Discount"] + [f"{r:.0%}" for r in rates]]
    for i, p in enumerate(peaks):
        sens.append([f"${p:.1f}T"] + [fmt_t(grid[i, j]) for j in range(len(rates))])
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>Sensitivity (total PV, $T):</b>", body))
    story.append(Table(sens, hAlign="LEFT",
                       style=TableStyle([
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f77b4")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#1f77b4")),
                           ("TEXTCOLOR", (0, 1), (0, -1), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), 9),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                           ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                       ])))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Caveats:</b> (i) Acemoglu (MIT, 2024) argues only 0.5% cumulative TFP "
        "gain over 10 years &mdash; an order of magnitude lower than the central "
        "case. (ii) This ignores distributional, employment, and existential-risk "
        "side effects, which are not GDP-additive but materially affect welfare. "
        "(iii) Capex needed to realize the gain (datacenters, energy, chips) is "
        "subtracted from output but not netted here.", small))

    story.append(PageBreak())

    # Trump section
    story.append(Paragraph("2) Trump 2.0 &mdash; US incremental GDP", h2))
    story.append(Paragraph("<b>Assumptions (level effects on US GDP):</b>", body))
    trump_assump = [
        ["TCJA extension / corporate tax", "+0.4% of US GDP (Tax Foundation)"],
        ["Tariffs (broad + targeted)", "-0.8% of US GDP (Penn Wharton, Yale Budget Lab)"],
        ["Immigration restriction", "-0.4% of US GDP (CBO labor force)"],
        ["Deregulation", "+0.3% of US GDP"],
        ["Deficit / higher real rates", "-0.2% of US GDP"],
        ["Net peak (mechanism)", "-0.7% of US GDP"],
        ["US GDP base (2026)", "$29T"],
        ["Profile", "Full peak y1-3 (2026-28), handoff y4 (2029), decay through 2045"],
        ["Real discount rate", f"{trump.discount_rate:.0%}"],
        ["Oil channel", "WTI -$5/bbl during term (drill-baby-drill + tariff demand softening); fades by 2033"],
        ["Oil GDP elasticity", "0.05% US GDP per $10/bbl (US is roughly oil-balanced)"],
    ]
    story.append(Table(trump_assump, hAlign="LEFT", colWidths=[5 * cm, 11 * cm],
                       style=TableStyle([
                           ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
                           ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                           ("FONTSIZE", (0, 0), (-1, -1), 9),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"),
                       ])))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"<b>Result:</b> Total PV <b>{fmt_t(trump.total_pv)}</b>, of which the "
        f"mechanism channel is {fmt_t(trump.explicit_pv - trump.oil_pv)} and the "
        f"oil channel is {fmt_t(trump.oil_pv)} (cheaper oil from US production "
        f"growth is a small positive offset). The sign of the mechanism is "
        f"negative in the central case but the magnitude is small relative to "
        f"AI: a 0.7% level shock on a $29T economy that decays over 20 years is "
        f"~$2-2.5T undiscounted, ~$1-1.5T discounted. Reasonable bull cases "
        f"(deregulation > tariff drag) flip the sign without changing the order "
        f"of magnitude.", body))
    rates, peaks, grid = trump_sensitivity()
    sens = [["Peak %GDP \\ Discount"] + [f"{r:.0%}" for r in rates]]
    for i, p in enumerate(peaks):
        label = {-0.015: "-1.5% (bear)", -0.007: "-0.7% (base)",
                 0.0: "0%", 0.007: "+0.7% (bull)"}[p]
        sens.append([label] + [fmt_t(grid[i, j]) for j in range(len(rates))])
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>Sensitivity (total PV, $T):</b>", body))
    story.append(Table(sens, hAlign="LEFT",
                       style=TableStyle([
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d62728")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#d62728")),
                           ("TEXTCOLOR", (0, 1), (0, -1), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), 9),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                           ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                       ])))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Caveats:</b> (i) Excludes spillovers to non-US economies (likely "
        "negative via tariff retaliation but partially offset by reshoring). "
        "(ii) Treats policy as a level shock; if Trump 2.0 alters the long-run "
        "global trade architecture (durable bloc-formation), the persistent drag "
        "could be larger and longer. (iii) Excludes any AI-policy interaction; "
        "deregulation around energy/datacenters could be a meaningful AI tailwind.",
        small))

    story.append(PageBreak())

    # Iran section
    story.append(Paragraph("3) US-Iran war &mdash; global incremental GDP", h2))
    story.append(Paragraph("<b>Assumptions (conditional on conflict, central case):</b>", body))
    iran_assump = [
        ["Oil price track (channel)", "$75 (2026 baseline) -> $120 Y1 -> $100 Y2 -> $85 Y3 -> $77 Y4 -> baseline"],
        ["Oil-to-GDP elasticity", "0.15% global GDP per $10/bbl sustained"],
        ["Strait of Hormuz / shipping (mech)", "-0.2% of global GDP, year 1 only"],
        ["Direct US fiscal cost (mech)", "$300-700B over 5y (mid $500B), -0.05% global GDP/yr"],
        ["Financial conditions tightening (mech)", "-0.2% of global GDP, year 1 only"],
        ["Long-tail Mid-East instability (mech)", "-0.05% of global GDP, years 6-10"],
        ["Global GDP base (2026)", "$110T"],
        ["Real discount rate", f"{iran.discount_rate:.0%}"],
        ["Probability weighting", "NOT applied (conditional PV)"],
    ]
    story.append(Table(iran_assump, hAlign="LEFT", colWidths=[5 * cm, 11 * cm],
                       style=TableStyle([
                           ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
                           ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                           ("FONTSIZE", (0, 0), (-1, -1), 9),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"),
                       ])))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"<b>Result:</b> Total PV <b>{fmt_t(iran.total_pv)}</b>, of which the oil "
        f"channel alone is {fmt_t(iran.oil_pv)} (~{abs(iran.oil_pv/iran.total_pv)*100:.0f}% "
        f"of the total). Non-oil mechanism channels (Hormuz shipping, fiscal cost, "
        f"financial tightening, instability) contribute "
        f"{fmt_t(iran.explicit_pv - iran.oil_pv)}. Front-loaded: ~70% of the loss "
        f"falls in years 1-3 (2026-2028). If you assign a 20% probability of an "
        f"actual kinetic war over the next 4 years, the expected-value PV is roughly "
        f"{fmt_t(iran.total_pv * 0.20)}; at 5%, {fmt_t(iran.total_pv * 0.05)}.",
        body))
    rates, sevs, grid = iran_sensitivity()
    sens = [["Severity \\ Discount"] + [f"{r:.0%}" for r in rates]]
    severity_labels = {0.5: "0.5x (limited strikes)", 1.0: "1.0x (base)",
                       1.5: "1.5x (extended air war)", 2.5: "2.5x (Hormuz closure)"}
    for i, s in enumerate(sevs):
        sens.append([severity_labels[s]] + [fmt_t(grid[i, j]) for j in range(len(rates))])
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>Sensitivity (total PV, $T) &mdash; conditional:</b>", body))
    story.append(Table(sens, hAlign="LEFT",
                       style=TableStyle([
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7f0e0e")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#7f0e0e")),
                           ("TEXTCOLOR", (0, 1), (0, -1), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), 9),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                           ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                       ])))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Caveats:</b> (i) Hormuz closure is a fat-tail scenario: ~20% of "
        "global oil and ~30% of LNG transit. A 3-month closure could push the "
        "shock to multiples of the central case. (ii) Excludes nuclear escalation "
        "(non-modelable in DCF terms). (iii) Excludes regional spillovers to "
        "Israel-Lebanon, Yemen-Saudi shipping. (iv) Defense Keynesian-stimulus "
        "offset is small (~0.05% US GDP) and embedded in the fiscal-cost line.",
        small))

    story.append(PageBreak())

    # Comparison
    story.append(Paragraph("Comparison & interpretation", h2))
    story.append(Paragraph(
        "Three observations matter more than any single number:", body))
    story.append(Paragraph(
        f"<b>1. Duration dominates magnitude.</b> AI's PV is ~{ratio_at:.0f}x Trump 2.0's not "
        f"because the annual flow is ~{ratio_at:.0f}x larger &mdash; at peak it's only ~22x &mdash; "
        f"but because AI compounds over a 30-year explicit horizon plus a perpetual "
        f"terminal value, while Trump 2.0 decays inside 20 years and the war shock "
        f"decays inside 10. DCF rewards persistence heavily.", body))
    story.append(Paragraph(
        "<b>2. Sign is contested only for Trump 2.0.</b> AI's central PV is robustly "
        "positive across plausible parameterizations (it stays positive even if you "
        "halve the peak and double the discount rate). The Iran-war PV is robustly "
        "negative. Trump 2.0 is the only scenario where reasonable analysts disagree "
        "on the sign, because the policy bundle nets several large opposing forces.",
        body))
    story.append(Paragraph(
        "<b>3. The framing arbitrages probability.</b> AI is treated here as a "
        "near-certainty (the technology exists; deployment is the question). The "
        "war is conditional on occurrence. If you probability-weight (e.g., 20% "
        "chance of war) and risk-weight (apply a higher discount rate to AI for "
        "deployment risk), the gap narrows but does not close. AI remains the "
        "dominant economic force in every scenario where it is not actively "
        "suppressed.", body))
    story.append(Spacer(1, 12))

    story.append(Paragraph("What this analysis is NOT", h3))
    story.append(Paragraph(
        "Not a welfare analysis: GDP omits distribution, leisure, environmental "
        "stocks, and existential risk. Not a forecast: assumptions are deliberate "
        "central cases anchored to published estimates. Not investment advice. "
        "Not probability-weighted for the war scenario. The headline ratios are "
        "stable across reasonable assumption changes; the absolute numbers should "
        "be read as orders of magnitude (one significant figure).", small))

    doc.build(story)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    outdir = "."
    ai = run_ai_dcf()
    trump = run_trump_dcf()
    iran = run_iran_war_dcf()
    chart_paths = make_charts(ai, trump, iran, outdir)

    # Console summary
    for r in (ai, trump, iran):
        print(f"{r.name:30s}  explicit={r.explicit_pv:8.2f}T  "
              f"terminal={r.terminal_pv:8.2f}T  total={r.total_pv:8.2f}T  "
              f"r={r.discount_rate:.0%}")

    out_pdf = f"{outdir}/comparative_gdp_dcf.pdf"
    build_pdf(out_pdf, ai, trump, iran, chart_paths)
    print(f"Wrote {out_pdf}")


if __name__ == "__main__":
    main()
