"""
Generate GDP.docx — same content as the PDF, native Word format.
Reuses DCF models from analysis.py.
"""
from analysis import (
    run_ai_dcf, run_trump_dcf, run_iran_war_dcf,
    ai_sensitivity, trump_sensitivity, iran_sensitivity,
    make_charts, fmt_t,
)

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def shade_cell(cell, hex_color: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def add_table(doc: Document, headers, rows, header_color="222222", first_col_color=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = h
        for run in hdr[i].paragraphs[0].runs:
            run.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            run.font.size = Pt(10)
        shade_cell(hdr[i], header_color)
    for r_idx, row in enumerate(rows):
        cells = table.rows[r_idx + 1].cells
        for c_idx, val in enumerate(row):
            cells[c_idx].text = str(val)
            for run in cells[c_idx].paragraphs[0].runs:
                run.font.size = Pt(9)
            if first_col_color and c_idx == 0:
                shade_cell(cells[c_idx], first_col_color)
                for run in cells[c_idx].paragraphs[0].runs:
                    run.bold = True
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    return table


def add_h1(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(20)


def add_h2(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(15)


def add_h3(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(12)


def add_para(doc, text, size=10, italic=False, color=None):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.italic = italic
    if color:
        run.font.color.rgb = color
    return p


def main():
    ai = run_ai_dcf()
    trump = run_trump_dcf()
    iran = run_iran_war_dcf()
    chart_paths = make_charts(ai, trump, iran, ".")

    doc = Document()
    # narrow-ish margins
    for s in doc.sections:
        s.left_margin = Inches(0.8)
        s.right_margin = Inches(0.8)
        s.top_margin = Inches(0.7)
        s.bottom_margin = Inches(0.7)

    # Title
    add_h1(doc, "Comparative DCF: Incremental GDP Impact")
    add_h3(doc, "AI vs. Trump 2.0 vs. US-Iran War (illustrative, order-of-magnitude)")
    add_para(doc,
             "Author: Claude (Opus 4.7)    Date: 2026-05-03    "
             "Units: real USD trillions, ex-inflation discount rates",
             size=9, italic=True, color=RGBColor(0x80, 0x80, 0x80))

    # Executive summary
    add_h2(doc, "Executive summary")
    add_para(doc,
             f"Under central-case assumptions: AI's incremental GDP has a present value of "
             f"{fmt_t(ai.total_pv)} (global, 30-year explicit + Gordon terminal, "
             f"discount rate {ai.discount_rate:.0%}). Trump 2.0's incremental US GDP has a "
             f"present value of {fmt_t(trump.total_pv)} (20-year horizon, "
             f"discount rate {trump.discount_rate:.0%}). A US-Iran kinetic war has a "
             f"present value of {fmt_t(iran.total_pv)} in incremental global GDP "
             f"(10-year horizon, discount rate {iran.discount_rate:.0%}, conditional on "
             f"the war occurring — not probability-weighted).")
    ratio_at = abs(ai.total_pv / trump.total_pv) if trump.total_pv else float("inf")
    ratio_ai = abs(ai.total_pv / iran.total_pv) if iran.total_pv else float("inf")
    add_para(doc,
             f"The order of magnitude is the headline: AI's PV is roughly "
             f"{ratio_at:,.0f}x the absolute size of Trump 2.0's net GDP impact and "
             f"{ratio_ai:,.0f}x the absolute size of an Iran war shock. Even after "
             f"loosening AI assumptions toward Acemoglu-style skepticism, AI dominates "
             f"by at least one order of magnitude in our central case — because it is a "
             f"long-duration productivity shock compounded over decades, while political "
             f"and geopolitical shocks act on shorter horizons with bounded amplitude.")

    add_table(doc,
              ["Scenario", "Horizon", "Discount", "Explicit PV", "Terminal PV", "Total PV"],
              [
                  [ai.name, f"{len(ai.years)} y", f"{ai.discount_rate:.0%}",
                   fmt_t(ai.explicit_pv), fmt_t(ai.terminal_pv), fmt_t(ai.total_pv)],
                  [trump.name, f"{len(trump.years)} y", f"{trump.discount_rate:.0%}",
                   fmt_t(trump.explicit_pv), fmt_t(trump.terminal_pv), fmt_t(trump.total_pv)],
                  [iran.name, f"{len(iran.years)} y", f"{iran.discount_rate:.0%}",
                   fmt_t(iran.explicit_pv), fmt_t(iran.terminal_pv), fmt_t(iran.total_pv)],
              ])
    doc.add_paragraph()
    doc.add_picture(chart_paths["total"], width=Inches(6.2))

    doc.add_page_break()

    # Methodology
    add_h2(doc, "Methodology")
    add_para(doc,
             "I model each scenario as an annual stream of incremental GDP relative to a "
             "no-event counterfactual, then discount to a present value using a real "
             "(ex-inflation) discount rate. PV = Σ ΔGDP_t / (1+r)^t, with a Gordon-growth "
             "terminal value where economic fundamentals justify it (only AI). For the "
             "political and war scenarios, the impact decays inside the explicit horizon, "
             "so no terminal value is added.")
    add_para(doc,
             "Three deliberate choices shape the comparison: (1) AI is global and very "
             "long-horizon, while Trump 2.0 is mostly US and 4-20y, while the Iran war "
             "shock is global but front-loaded and short. (2) The discount rate is held "
             "between 5-6% real to keep magnitudes comparable, then varied in sensitivity "
             "tables. (3) War PV is conditional on occurrence, not probability-weighted; "
             "if you assign a probability p, multiply by p for an expected value.")

    add_h3(doc, "Charts")
    doc.add_picture(chart_paths["annual"], width=Inches(6.2))
    doc.add_paragraph()
    doc.add_picture(chart_paths["cumulative"], width=Inches(6.2))

    doc.add_page_break()

    # AI section
    add_h2(doc, "1) AI — global incremental GDP")
    add_h3(doc, "Assumptions")
    add_table(doc, ["Parameter", "Value"],
              [
                  ["Global GDP base (2025)", "$110T"],
                  ["Adoption profile", "Logistic ramp; $0.2T (2025) -> $4.5T (~2040)"],
                  ["Post-peak growth", "+2%/yr through year 30"],
                  ["Explicit horizon", "30 years"],
                  ["Terminal growth", "1.5% real"],
                  ["Real discount rate", f"{ai.discount_rate:.0%}"],
                  ["Anchors",
                   "Goldman Sachs 2023 (~7% global GDP / 10y); McKinsey 2023 "
                   "($13-25T/yr by 2040); PwC 2017 ($15.7T by 2030)"],
              ],
              header_color="1f77b4")
    doc.add_paragraph()
    add_para(doc,
             f"Result: Explicit-horizon PV {fmt_t(ai.explicit_pv)} + terminal PV "
             f"{fmt_t(ai.terminal_pv)} = total PV {fmt_t(ai.total_pv)}. The "
             f"terminal value is large because a permanent productivity uplift compounds "
             f"forever; even at 6% real discounting, a $7-8T perpetual annual delta is "
             f"worth on the order of $100T+ in present value terms.")

    rates, peaks, grid = ai_sensitivity()
    rows = []
    for i, p in enumerate(peaks):
        rows.append([f"${p:.1f}T"] + [fmt_t(grid[i, j]) for j in range(len(rates))])
    add_h3(doc, "Sensitivity (total PV, $T)")
    add_table(doc,
              ["Peak $T/yr by 2040 \\ Discount"] + [f"{r:.0%}" for r in rates],
              rows, header_color="1f77b4", first_col_color="1f77b4")
    doc.add_paragraph()
    add_para(doc,
             "Caveats: (i) Acemoglu (MIT, 2024) argues only 0.5% cumulative TFP gain "
             "over 10 years — an order of magnitude lower than the central case. "
             "(ii) Excludes distributional, employment, and existential-risk side "
             "effects, which are not GDP-additive but materially affect welfare. "
             "(iii) Capex needed to realize the gain (datacenters, energy, chips) is "
             "subtracted from output but not netted here.",
             size=9, italic=True, color=RGBColor(0x80, 0x80, 0x80))

    doc.add_page_break()

    # Trump section
    add_h2(doc, "2) Trump 2.0 — US incremental GDP")
    add_h3(doc, "Assumptions (level effects on US GDP)")
    add_table(doc, ["Parameter", "Value"],
              [
                  ["TCJA extension / corporate tax", "+0.4% of US GDP (Tax Foundation)"],
                  ["Tariffs (broad + targeted)", "-0.8% of US GDP (Penn Wharton, Yale Budget Lab)"],
                  ["Immigration restriction", "-0.4% of US GDP (CBO labor force)"],
                  ["Deregulation", "+0.3% of US GDP"],
                  ["Deficit / higher real rates", "-0.2% of US GDP"],
                  ["Net peak", "-0.7% of US GDP"],
                  ["US GDP base", "$29T"],
                  ["Profile", "Ramp y1, peak y2-4, decay y5-20"],
                  ["Real discount rate", f"{trump.discount_rate:.0%}"],
              ],
              header_color="d62728")
    doc.add_paragraph()
    add_para(doc,
             f"Result: Total PV {fmt_t(trump.total_pv)}. The sign is negative in the "
             f"central case but the magnitude is small relative to AI: a 0.7% level "
             f"shock on a $29T economy that decays over 20 years is ~$2-2.5T "
             f"undiscounted, ~$1-1.5T discounted. Reasonable bull cases (deregulation > "
             f"tariff drag) flip the sign without changing the order of magnitude.")

    rates, peaks, grid = trump_sensitivity()
    label_map = {-0.015: "-1.5% (bear)", -0.007: "-0.7% (base)",
                 0.0: "0%", 0.007: "+0.7% (bull)"}
    rows = []
    for i, p in enumerate(peaks):
        rows.append([label_map[p]] + [fmt_t(grid[i, j]) for j in range(len(rates))])
    add_h3(doc, "Sensitivity (total PV, $T)")
    add_table(doc, ["Peak %GDP \\ Discount"] + [f"{r:.0%}" for r in rates],
              rows, header_color="d62728", first_col_color="d62728")
    doc.add_paragraph()
    add_para(doc,
             "Caveats: (i) Excludes spillovers to non-US economies (likely negative "
             "via tariff retaliation but partially offset by reshoring). (ii) Treats "
             "policy as a level shock; if Trump 2.0 alters the long-run global trade "
             "architecture (durable bloc-formation), the persistent drag could be "
             "larger and longer. (iii) Excludes any AI-policy interaction; "
             "deregulation around energy/datacenters could be a meaningful AI tailwind.",
             size=9, italic=True, color=RGBColor(0x80, 0x80, 0x80))

    doc.add_page_break()

    # Iran section
    add_h2(doc, "3) US-Iran war — global incremental GDP")
    add_h3(doc, "Assumptions (conditional on conflict, central case)")
    add_table(doc, ["Parameter", "Value"],
              [
                  ["Oil price shock", "$75 -> $120 for ~12m, decay over 3y"],
                  ["Oil-to-GDP elasticity", "$10 sustained = ~0.15% global GDP drag"],
                  ["Strait of Hormuz / shipping", "-0.2% of global GDP, year 1 only"],
                  ["Direct US fiscal cost", "$300-700B over 5y (mid $500B)"],
                  ["Financial conditions tightening", "-0.2% of global GDP, year 1 only"],
                  ["Long-tail Mid-East instability", "-0.05% of global GDP, years 6-10"],
                  ["Global GDP base", "$110T"],
                  ["Real discount rate", f"{iran.discount_rate:.0%}"],
                  ["Probability weighting", "NOT applied (conditional PV)"],
              ],
              header_color="7f0e0e")
    doc.add_paragraph()
    add_para(doc,
             f"Result: Total PV {fmt_t(iran.total_pv)}. Front-loaded: ~70% of the loss "
             f"falls in years 1-3. If you assign a 20% probability of an actual kinetic "
             f"war over the next 4 years, the expected-value PV is roughly "
             f"{fmt_t(iran.total_pv * 0.20)}; at 5%, {fmt_t(iran.total_pv * 0.05)}.")

    rates, sevs, grid = iran_sensitivity()
    sev_label = {0.5: "0.5x (limited strikes)", 1.0: "1.0x (base)",
                 1.5: "1.5x (extended air war)", 2.5: "2.5x (Hormuz closure)"}
    rows = []
    for i, s in enumerate(sevs):
        rows.append([sev_label[s]] + [fmt_t(grid[i, j]) for j in range(len(rates))])
    add_h3(doc, "Sensitivity (total PV, $T) — conditional")
    add_table(doc, ["Severity \\ Discount"] + [f"{r:.0%}" for r in rates],
              rows, header_color="7f0e0e", first_col_color="7f0e0e")
    doc.add_paragraph()
    add_para(doc,
             "Caveats: (i) Hormuz closure is a fat-tail scenario: ~20% of global oil "
             "and ~30% of LNG transit. A 3-month closure could push the shock to "
             "multiples of the central case. (ii) Excludes nuclear escalation "
             "(non-modelable in DCF terms). (iii) Excludes regional spillovers to "
             "Israel-Lebanon, Yemen-Saudi shipping. (iv) Defense Keynesian-stimulus "
             "offset is small (~0.05% US GDP) and embedded in the fiscal-cost line.",
             size=9, italic=True, color=RGBColor(0x80, 0x80, 0x80))

    doc.add_page_break()

    # Comparison
    add_h2(doc, "Comparison & interpretation")
    add_para(doc, "Three observations matter more than any single number:")
    add_para(doc,
             f"1. Duration dominates magnitude. AI's PV is ~{ratio_at:.0f}x Trump 2.0's "
             f"not because the annual flow is ~{ratio_at:.0f}x larger — at peak it's "
             f"only ~22x — but because AI compounds over a 30-year explicit horizon "
             f"plus a perpetual terminal value, while Trump 2.0 decays inside 20 years "
             f"and the war shock decays inside 10. DCF rewards persistence heavily.")
    add_para(doc,
             "2. Sign is contested only for Trump 2.0. AI's central PV is robustly "
             "positive across plausible parameterizations (it stays positive even if "
             "you halve the peak and double the discount rate). The Iran-war PV is "
             "robustly negative. Trump 2.0 is the only scenario where reasonable "
             "analysts disagree on the sign, because the policy bundle nets several "
             "large opposing forces.")
    add_para(doc,
             "3. The framing arbitrages probability. AI is treated here as a "
             "near-certainty (the technology exists; deployment is the question). "
             "The war is conditional on occurrence. If you probability-weight (e.g., "
             "20% chance of war) and risk-weight (apply a higher discount rate to AI "
             "for deployment risk), the gap narrows but does not close. AI remains "
             "the dominant economic force in every scenario where it is not actively "
             "suppressed.")

    add_h3(doc, "What this analysis is NOT")
    add_para(doc,
             "Not a welfare analysis: GDP omits distribution, leisure, environmental "
             "stocks, and existential risk. Not a forecast: assumptions are deliberate "
             "central cases anchored to published estimates. Not investment advice. "
             "Not probability-weighted for the war scenario. The headline ratios are "
             "stable across reasonable assumption changes; the absolute numbers should "
             "be read as orders of magnitude (one significant figure).",
             size=9, italic=True, color=RGBColor(0x80, 0x80, 0x80))

    out = "GDP.docx"
    doc.save(out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
