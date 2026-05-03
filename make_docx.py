"""
Generate GDP.docx — same content as the PDF, native Word format.
Reuses DCF models from analysis.py.
"""
from analysis import (
    run_ai_dcf, run_trump_dcf, run_iran_war_dcf, run_internet_2000_dcf,
    ai_sensitivity, trump_sensitivity, iran_sensitivity,
    make_charts, fmt_t, INFLATION_2000_TO_2026,
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
             "Base year: 2026 (year 1 = 2026; PV as of start-of-2026)    "
             "Units: real USD trillions, ex-inflation discount rates    "
             "Channels: mechanism + oil-price",
             size=9, italic=True, color=RGBColor(0x80, 0x80, 0x80))

    # Executive summary
    add_h2(doc, "Executive summary")
    add_para(doc,
             f"Under central-case assumptions, with year 1 = 2026 and PV measured as of "
             f"start-of-2026: AI's incremental GDP has a present value of "
             f"{fmt_t(ai.total_pv)} (global, 30-year explicit + Gordon terminal, "
             f"discount rate {ai.discount_rate:.0%}; oil channel contributes "
             f"{fmt_t(ai.oil_pv)}). Trump 2.0's incremental US GDP has a present value "
             f"of {fmt_t(trump.total_pv)} (20-year horizon, discount rate "
             f"{trump.discount_rate:.0%}; oil channel contributes {fmt_t(trump.oil_pv)}). "
             f"A US-Iran kinetic war has a present value of {fmt_t(iran.total_pv)} in "
             f"incremental global GDP (10-year horizon, discount rate "
             f"{iran.discount_rate:.0%}; oil channel contributes {fmt_t(iran.oil_pv)} "
             f"and is the dominant transmission mechanism). Conditional on the war "
             f"occurring — not probability-weighted.")
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
    _internet_preview = run_internet_2000_dcf()
    _internet_pv_2026 = _internet_preview.total_pv * INFLATION_2000_TO_2026
    _ai_internet = ai.total_pv / _internet_pv_2026
    add_para(doc,
             f"Sanity check vs. dot-com era forecasts. The synthesized 1999-2000 "
             f"consensus forecast for the internet's incremental global GDP, when FV'd "
             f"to 2026 dollars (CPI x{INFLATION_2000_TO_2026}), has a PV of "
             f"{fmt_t(_internet_pv_2026)}. Today's AI forecast at {fmt_t(ai.total_pv)} "
             f"is only {_ai_internet:.2f}x larger — effectively the same order of "
             f"magnitude. See section 4 for the detailed comparison.")

    add_table(doc,
              ["Scenario", "Horizon", "Discount", "Mechanism PV", "Oil PV", "Terminal PV", "Total PV"],
              [
                  [ai.name, f"{len(ai.years)} y", f"{ai.discount_rate:.0%}",
                   fmt_t(ai.total_pv - ai.terminal_pv - ai.oil_pv), fmt_t(ai.oil_pv),
                   fmt_t(ai.terminal_pv), fmt_t(ai.total_pv)],
                  [trump.name, f"{len(trump.years)} y", f"{trump.discount_rate:.0%}",
                   fmt_t(trump.explicit_pv - trump.oil_pv), fmt_t(trump.oil_pv),
                   fmt_t(trump.terminal_pv), fmt_t(trump.total_pv)],
                  [iran.name, f"{len(iran.years)} y", f"{iran.discount_rate:.0%}",
                   fmt_t(iran.explicit_pv - iran.oil_pv), fmt_t(iran.oil_pv),
                   fmt_t(iran.terminal_pv), fmt_t(iran.total_pv)],
              ])
    doc.add_paragraph()
    doc.add_picture(chart_paths["total"], width=Inches(6.2))

    doc.add_page_break()

    # Methodology
    add_h2(doc, "Methodology")
    add_para(doc,
             "I model each scenario as an annual stream of incremental GDP relative to a "
             "no-event counterfactual, starting in 2026, then discount to a present value "
             "as of start-of-2026 using a real (ex-inflation) discount rate. "
             "PV = Σ ΔGDP_t / (1+r)^t, with a Gordon-growth terminal value where "
             "economic fundamentals justify it (only AI). For the political and war "
             "scenarios, the impact decays inside the explicit horizon, so no terminal "
             "value is added.")
    add_para(doc,
             "Two channels are aggregated for each scenario: (a) the core mechanism "
             "(productivity, policy, conflict) and (b) an oil-price channel that "
             "converts a $/bbl deviation vs a $75 baseline into GDP impact via an "
             "oil-to-GDP elasticity (0.15% global GDP per $10/bbl sustained for global "
             "scenarios; 0.05% US GDP per $10/bbl for the now oil-balanced US). This "
             "makes the oil-driven portion of each scenario's PV explicit.")
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
    doc.add_paragraph()
    add_h3(doc, "Oil-price assumption per scenario")
    add_para(doc,
             "Three different oil tracks. The Iran-war track is a sharp spike that "
             "dominates that scenario's PV. The AI track is a slow, persistent rise from "
             "datacenter energy demand. The Trump 2.0 track is a small drop from US "
             "production growth and tariff-driven demand softening, fading after the term.")
    doc.add_picture(chart_paths["oil"], width=Inches(6.2))

    doc.add_page_break()

    # AI section
    add_h2(doc, "1) AI — global incremental GDP")
    add_h3(doc, "Assumptions")
    add_table(doc, ["Parameter", "Value"],
              [
                  ["Global GDP base (2026)", "$110T"],
                  ["Adoption profile", "Logistic ramp; $0.2T (2026) -> $4.5T (2040)"],
                  ["Post-peak growth", "+2%/yr through 2055"],
                  ["Explicit horizon", "30 years (2026-2055)"],
                  ["Terminal growth", "1.5% real"],
                  ["Real discount rate", f"{ai.discount_rate:.0%}"],
                  ["Oil channel", "Datacenter electricity demand pushes WTI +$7/bbl by 2035, persists"],
                  ["Anchors",
                   "Goldman Sachs 2023 (~7% global GDP / 10y); McKinsey 2023 "
                   "($13-25T/yr by 2040); PwC 2017 ($15.7T by 2030)"],
              ],
              header_color="1f77b4")
    doc.add_paragraph()
    add_para(doc,
             f"Result: Explicit-horizon PV {fmt_t(ai.explicit_pv)} + terminal PV "
             f"{fmt_t(ai.terminal_pv)} = total PV {fmt_t(ai.total_pv)}. Of which the "
             f"oil channel contributes {fmt_t(ai.oil_pv)} (a small drag from "
             f"datacenter-driven oil prices). The terminal value is large because a "
             f"permanent productivity uplift compounds forever; even at 6% real "
             f"discounting, a $7-8T perpetual annual delta is worth on the order of "
             f"$100T+ in present value terms.")

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
                  ["Net peak (mechanism)", "-0.7% of US GDP"],
                  ["US GDP base (2026)", "$29T"],
                  ["Profile", "Full peak y1-3 (2026-28), handoff y4 (2029), decay through 2045"],
                  ["Real discount rate", f"{trump.discount_rate:.0%}"],
                  ["Oil channel", "WTI -$5/bbl during term (drill-baby-drill + tariff demand softening)"],
                  ["Oil GDP elasticity", "0.05% US GDP per $10/bbl (US is roughly oil-balanced)"],
              ],
              header_color="d62728")
    doc.add_paragraph()
    add_para(doc,
             f"Result: Total PV {fmt_t(trump.total_pv)}, of which mechanism is "
             f"{fmt_t(trump.explicit_pv - trump.oil_pv)} and oil channel is "
             f"{fmt_t(trump.oil_pv)} (cheaper oil is a small positive offset). The "
             f"sign of the mechanism is negative in the central case but the magnitude "
             f"is small relative to AI: a 0.7% level shock on a $29T economy that "
             f"decays over 20 years is ~$2-2.5T undiscounted, ~$1-1.5T discounted. "
             f"Reasonable bull cases (deregulation > tariff drag) flip the sign without "
             f"changing the order of magnitude.")

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
                  ["Oil price track (channel)", "$75 (2026) -> $120 Y1 -> $100 Y2 -> $85 Y3 -> $77 Y4 -> baseline"],
                  ["Oil-to-GDP elasticity", "0.15% global GDP per $10/bbl sustained"],
                  ["Strait of Hormuz / shipping (mech)", "-0.2% of global GDP, year 1 only"],
                  ["Direct US fiscal cost (mech)", "$300-700B over 5y (mid $500B), -0.05% global GDP/yr"],
                  ["Financial conditions tightening (mech)", "-0.2% of global GDP, year 1 only"],
                  ["Long-tail Mid-East instability (mech)", "-0.05% of global GDP, years 6-10"],
                  ["Global GDP base (2026)", "$110T"],
                  ["Real discount rate", f"{iran.discount_rate:.0%}"],
                  ["Probability weighting", "NOT applied (conditional PV)"],
              ],
              header_color="7f0e0e")
    doc.add_paragraph()
    add_para(doc,
             f"Result: Total PV {fmt_t(iran.total_pv)}, of which the oil channel alone "
             f"is {fmt_t(iran.oil_pv)} (~{abs(iran.oil_pv/iran.total_pv)*100:.0f}% of "
             f"the total). Non-oil mechanism channels (Hormuz shipping, fiscal cost, "
             f"financial tightening, instability) contribute "
             f"{fmt_t(iran.explicit_pv - iran.oil_pv)}. Front-loaded: ~70% of the loss "
             f"falls in years 1-3 (2026-2028). If you assign a 20% probability of an "
             f"actual kinetic war over the next 4 years, the expected-value PV is "
             f"roughly {fmt_t(iran.total_pv * 0.20)}; at 5%, "
             f"{fmt_t(iran.total_pv * 0.05)}.")

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

    # 4) Dot-com era benchmark
    internet = run_internet_2000_dcf()
    internet_pv_2026usd = internet.total_pv * INFLATION_2000_TO_2026
    ai_internet_ratio = ai.total_pv / internet_pv_2026usd

    add_h2(doc, "4) Benchmark: dot-com era internet forecast (1999-2000)")
    add_para(doc,
             "Are today's AI GDP forecasts unprecedented, or do they look like every "
             "other transformative-tech hype cycle? To check, I built a synthesized "
             "1999-2000 consensus optimistic forecast for the internet's incremental "
             "global GDP, computed its DCF as of 2000 in 2000 dollars, then re-expressed "
             f"in 2026 dollars (FV factor x{INFLATION_2000_TO_2026:.2f}, US CPI cumulative "
             "2000→2026). Same DCF mechanics as AI: 30y explicit horizon, Gordon terminal "
             "at 1.5%, 6% real discount rate.")

    add_h3(doc, "Forecast assumptions (in 2000 dollars)")
    add_table(doc, ["Parameter", "Value"],
              [
                  ["Global GDP base (2000)", "$33T nominal"],
                  ["Year 1 (2001) starting delta", "$0.15T (2000$)"],
                  ["Peak delta (year 18, ~2018)", "$2.5T/yr (2000$)"],
                  ["Adoption profile", "Logistic ramp; +2%/yr post-peak"],
                  ["Explicit horizon", "30 years (2001-2030)"],
                  ["Terminal growth", "1.5% real"],
                  ["Real discount rate", f"{internet.discount_rate:.0%}"],
                  ["FV factor 2000$ → 2026$", f"x{INFLATION_2000_TO_2026:.2f} (US CPI)"],
                  ["Anchors",
                   "Goldman Sachs (Hatzius, 1999): Internet adds ~0.5% to global growth "
                   "permanently. Forrester 2000: $6.8T global B2B e-commerce by 2004. "
                   "Cisco/U.Texas (1999): Internet economy $850B in 2000. WEF 'Long "
                   "Boom' thesis."],
              ],
              header_color="2ca02c")
    doc.add_paragraph()

    add_h3(doc, "Result — the punchline")
    add_table(doc,
              ["", "PV in 2000 dollars", "PV in 2026 dollars (FV x1.85)"],
              [
                  ["Explicit-horizon PV", fmt_t(internet.explicit_pv),
                   fmt_t(internet.explicit_pv * INFLATION_2000_TO_2026)],
                  ["Terminal PV", fmt_t(internet.terminal_pv),
                   fmt_t(internet.terminal_pv * INFLATION_2000_TO_2026)],
                  ["Total PV", fmt_t(internet.total_pv),
                   fmt_t(internet_pv_2026usd)],
                  ["AI 2026 forecast (for reference)", "—", fmt_t(ai.total_pv)],
                  ["Ratio AI / Internet (in 2026$)", "—", f"{ai_internet_ratio:.2f}x"],
              ],
              header_color="2ca02c")
    doc.add_paragraph()

    add_para(doc,
             f"In 2026-dollar terms, the late-1990s internet forecast had a present "
             f"value of roughly {fmt_t(internet_pv_2026usd)}, versus today's AI "
             f"forecast of {fmt_t(ai.total_pv)}. The AI forecast is only "
             f"{ai_internet_ratio:.2f}x larger — effectively the same order of "
             f"magnitude, possibly within the noise of either model's assumption set. "
             f"This is the most important calibration in the report: when adjusted for "
             f"inflation and put into the same DCF framework, today's AI GDP forecasts "
             f"are NOT obviously larger than what serious analysts believed about the "
             f"internet at the peak of the dot-com bubble.")
    doc.add_paragraph()
    doc.add_picture(chart_paths["internet_vs_ai"], width=Inches(6.2))
    doc.add_paragraph()

    add_h3(doc, "What this comparison does and does not say")
    add_para(doc,
             "It does NOT say AI is a bubble or that current forecasts are wrong. The "
             "actual realized internet GDP impact (BEA digital-economy series, 2000-2024) "
             "ended up being a meaningful fraction of the optimistic 2000 forecast — "
             "perhaps 50-70% of it. The dot-com bust was a valuation event, not a GDP "
             "event. So a forecast PV of ~$43T (2026$) for the internet was, ex-post, "
             "not crazy — a substantial fraction was actually delivered.")
    add_para(doc,
             "It DOES say: (i) Forecasts of 'total GDP a transformative tech will add' "
             "are remarkably similar across cycles when normalized to real units. The "
             "forecasted ceiling moves with global GDP, not with the technology. "
             "(ii) The base rate for these forecasts being substantially right exists "
             "but is lower than the forecasters thought. (iii) If AI's realized impact "
             "is 50-70% of the central forecast (matching internet's hit rate), the "
             "realized PV is still in the $25-35T range — smaller than the headline "
             "but still ~10-20x larger than Trump 2.0 or an Iran war.")
    add_para(doc,
             "Caveats on the internet number: (i) The 2000-era forecast is a synthesized "
             "consensus, not any single published number. Different anchors give a range "
             "of $25-65T (2026$) for the PV. (ii) The 6% real discount rate is "
             "anachronistic-friendly: 1999-2000 nominal long rates were ~6% with low "
             "inflation expectations, so a real discount of 4-5% would be more "
             "historically faithful and would push the PV higher (to $50-60T in 2026$). "
             "At 4% real discounting, the internet PV would actually exceed the AI PV.",
             size=9, italic=True, color=RGBColor(0x80, 0x80, 0x80))

    doc.add_page_break()

    # Comparison
    add_h2(doc, "Comparison & interpretation")
    add_para(doc, "Four observations matter more than any single number:")
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
    add_para(doc,
             f"4. AI's forecast is not historically unprecedented. The 2000-era "
             f"internet forecast, FV'd to 2026 dollars, has a PV of "
             f"~{fmt_t(internet_pv_2026usd)} — only {ai_internet_ratio:.2f}x smaller "
             f"than today's AI forecast of {fmt_t(ai.total_pv)}. At a more "
             f"historically appropriate 4% real discount rate, the internet forecast "
             f"PV would actually exceed AI's. Read this two ways: it is reassuring "
             f"(productivity-tech forecasts have a track record of partial delivery), "
             f"and cautionary (forecasters systematically over-anchor on global GDP "
             f"rather than on the technology's actual diffusion curve).")

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
