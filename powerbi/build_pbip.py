"""Generate the Power BI Project (Tasklane.pbip): semantic model (TMDL) + 4-page report (PBIR).

Open Tasklane.pbip in Power BI Desktop (April 2025 or later), then File > Save a copy to produce a .pbix.
Re-run this script after editing measures or layout; it rewrites both folders and measures.dax.
Prerequisite: python/export_powerbi_data.py has written powerbi/data/*.csv.
"""
import json
import re
import shutil
import uuid
from pathlib import Path

root = Path(__file__).resolve().parent
NAME = "Tasklane"
sm, rp = root / f"{NAME}.SemanticModel", root / f"{NAME}.Report"
data_dir = root / "data"
T = "\t"


def gid(s):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{NAME}/{s}"))


# ----------------------------------------------------------------------------- tables
S, I, F, D = "string", "int64", "double", "dateTime"
TABLES = {
    "fact_user": [("user_id", S), ("signup_date", D), ("signup_month", D), ("channel", S), ("device", S), ("company_size", S),
                  ("engagement_tier", S), ("is_verified", I), ("has_project", I), ("is_activated", I), ("activation_status", S),
                  ("is_paid", I), ("plan", S), ("billing_period", S), ("mrr_usd", F), ("sub_start_date", D), ("sub_end_date", D),
                  ("is_churned", I), ("customer_months", I), ("w1_active", I), ("w4_active", I), ("w8_active", I),
                  ("experiment_variant", S), ("in_experiment", I), ("is_paid_30d", I), ("test_week", I)],
    "dim_date": [("date", D), ("week_start", D), ("month_start", D), ("month_label", S), ("year", I)],
    "cohort_retention_weekly": [("signup_week", D), ("week_idx", I), ("cohort_size", I), ("active_users", I), ("retention_pct", F)],
    "mrr_monthly": [("month", S), ("customers_start", I), ("new_customers", I), ("churned_customers", I), ("mrr_start", F),
                    ("new_mrr", F), ("churned_mrr", F)],
    "dim_funnel_stage": [("stage", S), ("stage_order", I)],
}
MTYPE = {S: "type text", I: "Int64.Type", F: "type number", D: "type date"}
DATE_FMT = "yyyy-mm-dd"

# ----------------------------------------------------------------------------- measures
PCT, PCT2, CNT, USD, USD2 = "0.0%", "0.00%", "#,0", "$#,0", "$#,0.00"
MEASURES = [
    # funnel and conversion
    ("Signups", "COUNTROWS ( fact_user )", CNT),
    ("Verified Users", "CALCULATE ( COUNTROWS ( fact_user ), fact_user[is_verified] = 1 )", CNT),
    ("Project Users", "CALCULATE ( COUNTROWS ( fact_user ), fact_user[has_project] = 1 )", CNT),
    ("Activated Users", "CALCULATE ( COUNTROWS ( fact_user ), fact_user[is_activated] = 1 )", CNT),
    ("Paid Users", "CALCULATE ( COUNTROWS ( fact_user ), fact_user[is_paid] = 1 )", CNT),
    ("Activation Rate", "DIVIDE ( [Activated Users], [Signups] )", PCT),
    ("Paid Conversion", "DIVIDE ( [Paid Users], [Signups] )", PCT),
    ("Paid per Activated User", "DIVIDE ( CALCULATE ( [Paid Users], fact_user[is_activated] = 1 ), [Activated Users] )", PCT),
    ("Funnel Users",
     "SWITCH ( SELECTEDVALUE ( dim_funnel_stage[stage] ),\n"
     "    \"Signed up\", [Signups], \"Verified email\", [Verified Users], \"Created first project\", [Project Users],\n"
     "    \"Activated\", [Activated Users], \"Paid\", [Paid Users] )", CNT),
    # retention (flags are blank when the week is not yet observable, so AVERAGE ignores those users)
    ("W1 Retention", "AVERAGE ( fact_user[w1_active] )", PCT),
    ("W4 Retention", "AVERAGE ( fact_user[w4_active] )", PCT),
    ("W8 Retention", "AVERAGE ( fact_user[w8_active] )", PCT),
    ("Cohort Retention", "DIVIDE ( SUM ( cohort_retention_weekly[active_users] ), SUM ( cohort_retention_weekly[cohort_size] ) )", PCT),
    # revenue and churn
    ("New MRR per Signup", "DIVIDE ( SUM ( fact_user[mrr_usd] ), [Signups] )", USD2),
    ("Avg MRR per Customer", "DIVIDE ( SUM ( fact_user[mrr_usd] ), [Paid Users] )", USD),
    ("Customers Churned", "CALCULATE ( COUNTROWS ( fact_user ), fact_user[is_churned] = 1 )", CNT),
    ("Customer Months", "SUM ( fact_user[customer_months] )", CNT),
    ("Monthly Churn Rate", "DIVIDE ( [Customers Churned], [Customer Months] )", PCT2),
    ("New MRR", "SUM ( mrr_monthly[new_mrr] )", USD),
    ("Churned MRR", "SUM ( mrr_monthly[churned_mrr] )", USD),
    ("Net New MRR", "[New MRR] - [Churned MRR]", USD),
    ("MRR Churn Rate", "DIVIDE ( [Churned MRR], SUM ( mrr_monthly[mrr_start] ) )", PCT),
    # experiment (Wald interval; the notebook uses Newcombe and a pooled z-test, results agree closely)
    ("Exp Users", "CALCULATE ( COUNTROWS ( fact_user ), fact_user[in_experiment] = 1 )", CNT),
    ("Exp Activated", "CALCULATE ( COUNTROWS ( fact_user ), fact_user[in_experiment] = 1, fact_user[is_activated] = 1 )", CNT),
    ("Exp Activation Rate", "DIVIDE ( [Exp Activated], [Exp Users] )", PCT),
    ("Exp Paid 30d Rate",
     "DIVIDE ( CALCULATE ( COUNTROWS ( fact_user ), fact_user[in_experiment] = 1, fact_user[is_paid_30d] = 1 ), [Exp Users] )", PCT),
    ("Control Activation Rate", "CALCULATE ( [Exp Activation Rate], fact_user[experiment_variant] = \"control\" )", PCT),
    ("Treatment Activation Rate", "CALCULATE ( [Exp Activation Rate], fact_user[experiment_variant] = \"treatment\" )", PCT),
    ("Activation Lift", "[Treatment Activation Rate] - [Control Activation Rate]", "+0.00%;-0.00%"),
    ("Relative Lift", "DIVIDE ( [Activation Lift], [Control Activation Rate] )", "+0.0%;-0.0%"),
    ("Lift Std Error",
     "VAR pc = [Control Activation Rate]\n"
     "VAR pt = [Treatment Activation Rate]\n"
     "VAR nc = CALCULATE ( [Exp Users], fact_user[experiment_variant] = \"control\" )\n"
     "VAR nt = CALCULATE ( [Exp Users], fact_user[experiment_variant] = \"treatment\" )\n"
     "RETURN SQRT ( DIVIDE ( pc * ( 1 - pc ), nc ) + DIVIDE ( pt * ( 1 - pt ), nt ) )", "0.0000"),
    ("Lift CI Low", "[Activation Lift] - 1.96 * [Lift Std Error]", "+0.00%;-0.00%"),
    ("Lift CI High", "[Activation Lift] + 1.96 * [Lift Std Error]", "+0.00%;-0.00%"),
    ("Lift z-score", "DIVIDE ( [Activation Lift], [Lift Std Error] )", "0.00"),
    ("Lift p-value", "2 * ( 1 - NORM.S.DIST ( ABS ( [Lift z-score] ), TRUE ) )", "0.0000"),
    ("Lift p-value Text", "IF ( [Lift p-value] < 0.0001, \"< 0.0001\", FORMAT ( [Lift p-value], \"0.0000\" ) )", "@"),
    ("Lift Summary",
     "FORMAT ( [Activation Lift] * 100, \"+0.00;-0.00\" ) & \" pts (95% CI \" & FORMAT ( [Lift CI Low] * 100, \"+0.00;-0.00\" )\n"
     "    & \" to \" & FORMAT ( [Lift CI High] * 100, \"+0.00;-0.00\" ) & \")\"", "@"),
]

RELATIONSHIPS = [("fact_user.signup_date", "dim_date.date", [])]


def q(name):
    return f"'{name}'" if re.search(r"[^A-Za-z0-9_]", name) else name


def indent_expr(expr, n):
    return "\n".join(T * n + line for line in expr.split("\n"))


def m_source(table):
    cols = TABLES[table]
    typed = ", ".join(f'{{"{c}", {MTYPE[t]}}}' for c, t in cols if t != S)
    lines = ["let",
             f'    Source = Csv.Document(File.Contents(DataFolder & "{table}.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
             "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
             f'    Typed = Table.TransformColumnTypes(Promoted, {{{typed}}}, "en-US")',
             "in", "    Typed"]
    return indent_expr("\n".join(lines), 4)


def column_block(table, c, t):
    out = [f"{T}column {q(c)}", f"{T*2}dataType: {t}"]
    if t == D:
        out.append(f"{T*2}formatString: {DATE_FMT}")
    if table == "dim_date" and c == "date":
        out.append(f"{T*2}isKey")
    out += [f"{T*2}sourceColumn: {c}"]
    if table == "dim_funnel_stage" and c == "stage":
        out.append(f"{T*2}sortByColumn: stage_order")
    out += [f"{T*2}summarizeBy: none", f"{T*2}lineageTag: {gid('col/' + table + '/' + c)}"]
    return "\n".join(out)


def measure_block(name, expr, fmt):
    head = f"{T}measure {q(name)} =\n{indent_expr(expr, 3)}" if "\n" in expr else f"{T}measure {q(name)} = {expr}"
    return f"{head}\n{T*2}formatString: {fmt}\n{T*2}lineageTag: {gid('m/' + name)}"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf8", newline="\n")


def build_model():
    if sm.exists():
        shutil.rmtree(sm)
    write(sm / "definition.pbism", json.dumps({"version": "4.0", "settings": {}}, indent=2))
    write(sm / "definition" / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
    names = list(TABLES) + ["_Measures"]
    refs = "\n".join(f"ref table {q(n)}" for n in names)
    write(sm / "definition" / "model.tmdl",
          "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tdiscourageImplicitMeasures\n\n"
          f"{refs}\n\nref expression DataFolder\n")
    folder = str(data_dir).rstrip("\\/") + "\\"
    write(sm / "definition" / "expressions.tmdl",
          f'expression DataFolder = "{folder}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
          f"{T}lineageTag: {gid('expr/DataFolder')}\n")
    for table, cols in TABLES.items():
        parts = [f"table {table}"]
        if table == "dim_date":
            parts.append(f"{T}dataCategory: Time")
        parts += [f"{T}lineageTag: {gid('t/' + table)}", ""]
        for c, t in cols:
            parts += [column_block(table, c, t), ""]
        parts += [f"{T}partition {table} = m\n{T*2}mode: import\n{T*2}source =\n{m_source(table)}", ""]
        write(sm / "definition" / "tables" / f"{table}.tmdl", "\n".join(parts))
    parts = ["table _Measures", f"{T}lineageTag: {gid('t/_Measures')}", "",
             f"{T}column Value\n{T*2}isHidden\n{T*2}dataType: int64\n{T*2}sourceColumn: [Value]\n{T*2}summarizeBy: none\n{T*2}lineageTag: {gid('col/_v')}", ""]
    for n, e, f in MEASURES:
        parts += [measure_block(n, e, f), ""]
    parts += [f"{T}partition _Measures = calculated\n{T*2}mode: import\n{T*2}source = {{1}}", ""]
    write(sm / "definition" / "tables" / "_Measures.tmdl", "\n".join(parts))
    rel = []
    for frm, to, extra in RELATIONSHIPS:
        body = [f"relationship {gid('rel/' + frm + to)}"] + [f"{T}{e}" for e in extra] + [f"{T}fromColumn: {frm}", f"{T}toColumn: {to}"]
        rel.append("\n".join(body))
    write(sm / "definition" / "relationships.tmdl", "\n\n".join(rel) + "\n")
    # human-readable copy of every measure
    lines = ["// Tasklane measures. Generated by build_pbip.py; paste into a _Measures table if rebuilding the model by hand.", ""]
    for n, e, f in MEASURES:
        lines += [f"{n} =", *["    " + x for x in e.split("\n")], ""]
    write(root / "measures.dax", "\n".join(lines))


# ----------------------------------------------------------------------------- report
def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def field(kind, table, prop):
    return {kind: {"Expression": {"SourceRef": {"Entity": table}}, "Property": prop}}


def proj(kind, table, prop):
    return {"field": field(kind, table, prop), "queryRef": f"{table}.{prop}", "nativeQueryRef": prop}


def C(t, p): return ("Column", t, p)
def Ms(p): return ("Measure", "_Measures", p)


def visual(name, vtype, x, y, w, h, roles=None, title=None, sort=None, labels=False, extra_objects=None, z=0):
    v = {"visualType": vtype, "drillFilterOtherVisuals": True}
    if roles:
        v["query"] = {"queryState": {role: {"projections": [proj(*f) for f in fs]} for role, fs in roles.items()}}
        if sort:
            v["query"]["sortDefinition"] = {"sort": [{"field": field(*sort[0]), "direction": sort[1]}], "isDefaultSort": True}
    objects = dict(extra_objects or {})
    if labels:
        objects["labels"] = [{"properties": {"show": lit("true")}}]
    if vtype in ("clusteredBarChart", "clusteredColumnChart", "lineChart"):
        objects["categoryAxis"] = [{"properties": {"showAxisTitle": lit("false")}}]
        objects["valueAxis"] = [{"properties": {"showAxisTitle": lit("false")}}]
    if vtype == "card":
        objects["categoryLabels"] = [{"properties": {"show": lit("false")}}]
    if objects:
        v["objects"] = objects
    if title:
        v["visualContainerObjects"] = {"title": [{"properties": {"show": lit("true"), "text": lit(f"'{title}'")}}]}
    return name, {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
        "name": name, "position": {"x": x, "y": y, "width": w, "height": h, "z": z, "tabOrder": z}, "visual": v}


def textbox(name, x, y, w, h, text, size="12pt", bold=False, color="#1F2937"):
    style = {"fontSize": size, "color": color}
    if bold:
        style["fontWeight"] = "bold"
    return visual(name, "textbox", x, y, w, h,
                  extra_objects={"general": [{"properties": {"paragraphs": [{"textRuns": [{"value": text, "textStyle": style}]}]}}]})


def card(name, x, measure, title, w=232, y=112):
    return visual(name, "card", x, y, w, 90, {"Values": [Ms(measure)]}, title=title)


def slicer(name, x, y, w, table, col):
    return visual(name, "slicer", x, y, w, 56, {"Values": [C(table, col)]}, extra_objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}]})


def _gradient(measure, lo, hi, lo_val=None, hi_val=None):
    rule = {"Input": {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": measure}},
            "FillRule": {"linearGradient2": {"min": {"color": {"Literal": {"Value": f"'{lo}'"}}, **({"value": {"Literal": {"Value": f"{lo_val}D"}}} if lo_val is not None else {})},
                                             "max": {"color": {"Literal": {"Value": f"'{hi}'"}}, **({"value": {"Literal": {"Value": f"{hi_val}D"}}} if hi_val is not None else {})},
                                             "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'noColor'"}}}}}}
    back = {"solid": {"color": {"expr": {"FillRule": rule}}}}
    selector = {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": f"_Measures.{measure}"}
    return {"values": [{"properties": {"backColor": back}, "selector": selector}]}


HEAT = _gradient("Cohort Retention", "#F3F6FA", "#8FB0D3")

NOTE = "Simulated data for the fictional company Tasklane (Jan 2025 to Feb 2026). Internal test accounts excluded. See README for definitions."
PAGES = []


def page(pid, title, headline, visuals, note=NOTE):
    vs = [textbox(f"{pid}_h", 20, 8, 1240, 44, headline, "18pt", True),
          textbox(f"{pid}_n", 20, 690, 1240, 24, note, "9pt", False, "#6B7280")] + visuals
    PAGES.append((pid, title, vs))


FILTERS = lambda p: [slicer(f"{p}_s1", 20, 52, 300, "fact_user", "channel"), slicer(f"{p}_s2", 340, 52, 300, "fact_user", "device"),
                     slicer(f"{p}_s3", 660, 52, 300, "fact_user", "company_size")]

page("p1", "1. Executive summary", "One in three signups activates, and activation is what drives paid conversion", FILTERS("p1") + [
    card("p1_c1", 20, "Signups", "Signups"), card("p1_c2", 272, "Activation Rate", "7-day activation rate"),
    card("p1_c3", 524, "Paid Conversion", "Signup to paid"), card("p1_c4", 776, "Paid per Activated User", "Paid, if activated"),
    card("p1_c5", 1028, "Monthly Churn Rate", "Monthly customer churn"),
    visual("p1_v1", "clusteredBarChart", 20, 215, 560, 465, {"Category": [C("dim_funnel_stage", "stage")], "Y": [Ms("Funnel Users")]},
           "Funnel: where signups drop off", (C("dim_funnel_stage", "stage_order"), "Ascending"), labels=True),
    visual("p1_v2", "lineChart", 600, 215, 660, 225, {"Category": [C("dim_date", "month_label")], "Y": [Ms("Activation Rate")]},
           "7-day activation rate by signup month"),
    visual("p1_v3", "lineChart", 600, 455, 660, 225, {"Category": [C("dim_date", "month_label")], "Y": [Ms("Paid Conversion")]},
           "Signup-to-paid conversion by signup month")])

page("p2", "2. Retention and cohorts", "About one in five signups is still active at week 12; activated users retain far better", [
    slicer("p2_s1", 20, 52, 300, "fact_user", "channel"), slicer("p2_s2", 340, 52, 300, "fact_user", "device"),
    card("p2_c1", 780, "W1 Retention", "Active in week 1", w=150, y=52), card("p2_c2", 940, "W4 Retention", "Active in week 4", w=150, y=52),
    card("p2_c3", 1100, "W8 Retention", "Active in week 8", w=150, y=52),
    visual("p2_v1", "pivotTable", 20, 130, 740, 550,
           {"Rows": [C("cohort_retention_weekly", "signup_week")], "Columns": [C("cohort_retention_weekly", "week_idx")], "Values": [Ms("Cohort Retention")]},
           "Weekly cohorts: share of signups active, by week since signup (all customers)", extra_objects=HEAT),
    visual("p2_v2", "clusteredBarChart", 780, 130, 480, 270, {"Category": [C("fact_user", "activation_status")], "Y": [Ms("W4 Retention")]},
           "Week-4 retention: activated vs not", labels=True),
    visual("p2_v3", "clusteredBarChart", 780, 410, 480, 270, {"Category": [C("fact_user", "channel")], "Y": [Ms("W4 Retention")]},
           "Week-4 retention by channel", (Ms("W4 Retention"), "Descending"), labels=True)])

page("p3", "3. Segments and churn", "Referral and direct signups are worth the most; Starter monthly plans churn fastest", [
    visual("p3_v1", "tableEx", 20, 60, 760, 280,
           {"Values": [C("fact_user", "channel"), Ms("Signups"), Ms("Activation Rate"), Ms("Paid Conversion"), Ms("New MRR per Signup"), Ms("W4 Retention")]},
           "Acquisition channels", (Ms("New MRR per Signup"), "Descending")),
    visual("p3_v2", "clusteredBarChart", 800, 60, 460, 280, {"Category": [C("fact_user", "engagement_tier")], "Y": [Ms("W4 Retention")]},
           "Week-4 retention by week-0 engagement", (Ms("W4 Retention"), "Descending"), labels=True),
    visual("p3_v3", "clusteredColumnChart", 20, 355, 600, 325,
           {"Category": [C("fact_user", "plan")], "Series": [C("fact_user", "billing_period")], "Y": [Ms("Monthly Churn Rate")]},
           "Monthly customer churn by plan and billing", labels=True),
    visual("p3_v4", "clusteredColumnChart", 640, 355, 620, 325,
           {"Category": [C("mrr_monthly", "month")], "Y": [Ms("New MRR"), Ms("Churned MRR")]},
           "New vs churned MRR by month (all customers)")])

page("p4", "4. Experiment readout", "Guided onboarding checklist: higher 7-day activation. Recommendation is to ship via staged rollout", [
    slicer("p4_s1", 20, 52, 300, "fact_user", "company_size"), slicer("p4_s2", 340, 52, 300, "fact_user", "channel"),
    slicer("p4_s3", 660, 52, 300, "fact_user", "device"),
    card("p4_c1", 20, "Control Activation Rate", "Control activation", w=232), card("p4_c2", 272, "Treatment Activation Rate", "Treatment activation", w=232),
    card("p4_c3", 524, "Activation Lift", "Lift (points)", w=232), card("p4_c4", 776, "Lift p-value Text", "p-value (Wald)", w=232),
    card("p4_c5", 1028, "Exp Users", "Users in test", w=232),
    visual("p4_t1", "card", 20, 212, 770, 70, {"Values": [Ms("Lift Summary")]}, title="Activation lift with 95% interval"),
    visual("p4_v1", "clusteredBarChart", 20, 295, 360, 385, {"Category": [C("fact_user", "experiment_variant")], "Y": [Ms("Exp Activation Rate")]},
           "7-day activation by variant", labels=True),
    visual("p4_v2", "lineChart", 400, 295, 390, 385,
           {"Category": [C("fact_user", "test_week")], "Y": [Ms("Exp Activation Rate")], "Series": [C("fact_user", "experiment_variant")]},
           "Activation by test week (noisy week to week)"),
    visual("p4_v3", "tableEx", 810, 212, 450, 468,
           {"Values": [C("fact_user", "experiment_variant"), Ms("Exp Users"), Ms("Exp Activation Rate"), Ms("Exp Paid 30d Rate")]},
           "Variant summary")],
     note="Simulated experiment. Intervals here are Wald approximations; the notebook uses Newcombe intervals and adds guardrails, power and multiple-comparison control. Segment cuts are exploratory.")


def build_report():
    if rp.exists():
        shutil.rmtree(rp)
    write(rp / "definition.pbir", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}}, indent=2))
    d = rp / "definition"
    write(d / "version.json", json.dumps({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"}, indent=2))
    write(d / "report.json", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.0.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY24SU10", "reportVersionAtImport": {"visual": "2.4.0", "page": "2.0.0", "report": "3.0.0"}, "type": "SharedResources"},
            "customTheme": {"name": "theme.json", "reportVersionAtImport": {"visual": "2.4.0", "page": "2.0.0", "report": "3.0.0"}, "type": "RegisteredResources"}},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources", "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources", "items": [{"name": "theme.json", "path": "theme.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True}}, indent=2))
    theme_dir = rp / "StaticResources" / "RegisteredResources"
    theme_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(root / "theme.json", theme_dir / "theme.json")
    write(d / "pages" / "pages.json", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p[0] for p in PAGES], "activePageName": PAGES[0][0]}, indent=2))
    for pid, title, vs in PAGES:
        write(d / "pages" / pid / "page.json", json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
            "name": pid, "displayName": title, "displayOption": "FitToPage", "height": 720, "width": 1280}, indent=2))
        for i, (vname, vj) in enumerate(vs):
            vj["position"]["z"] = vj["position"]["tabOrder"] = i * 10
            write(d / "pages" / pid / "visuals" / vname / "visual.json", json.dumps(vj, indent=2))


if __name__ == "__main__":
    build_model()
    build_report()
    write(root / f"{NAME}.pbip", json.dumps({
        "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}], "settings": {"enableAutoRecovery": True}}, indent=2))
    print("built", root / f"{NAME}.pbip")
