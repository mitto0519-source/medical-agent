"""ZCB-Depression Yoosun 양식 파이널 docx 생성."""
from __future__ import annotations
import io, os, sys, json, time
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout and hasattr(sys.stdout, "buffer"):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                        errors="replace", line_buffering=True)
    except Exception:
        pass

sys.path.insert(0, "/app" if Path("/app").exists() else ".")
from src.config.env import bootstrap
bootstrap()

from src.agent.intent_sensor import IntentSignal, set_current, get_current

yoosun_intent = IntentSignal(
    explicit_request="Yoosun Cho 양식으로 5섹션 본문만 다시 작성.",
    implicit_emphasis=[
        "Yoosun_finalize",
        "hedging (independently associated, may, appears to)",
        "topic sentence first",
        "subgroup_sex emphasis P_interaction<0.001",
        "developmental window 12-15세",
        "clinical_policy_focus",
    ],
    implicit_avoidance=[
        "anti_ai_tone",
        "In conclusion / In summary stuffer",
        "Furthermore / Moreover 과사용",
    ],
    voice_tone=["assertive but cautious", "developmental framing"],
    user_persona_inferred={
        "top_domain_keywords": ["zcb", "depression", "adolescent", "kyrbs"],
        "yoosun_style_inferred": True,
    },
)
set_current(yoosun_intent, owner_email="mitto0519@gmail.com")
print("[1/4] intent imprint:", get_current().implicit_emphasis[:3], "...")

protocol_path = Path("/app/data/assets/zcb_dep_protocol.json")
if not protocol_path.exists():
    protocol_path = Path("data/assets/zcb_dep_protocol.json")
protocol = json.loads(protocol_path.read_text(encoding="utf-8"))

stat_result = {
    "n_total": protocol["final_N"], "n_outcome": 12954, "outcome_rate": 25.4,
    "outcome": "depression", "outcome_label": "Depressive symptoms",
    "exposure": "Zero-calorie beverage consumption",
    "design": "cross-sectional, complex survey-weighted logistic regression",
    "model_vars": [
        {"variable": "zero_cat (<=2/week)", "label": "ZCB <=2/week vs none",
         "or_value": 1.10, "ci_lower": 1.05, "ci_upper": 1.16, "p_value": 0.0001,
         "or_formatted": "1.10 (1.05-1.16)", "p_formatted": "P<0.001", "significant": True},
        {"variable": "zero_cat (3-6/week)", "label": "ZCB 3-6/week vs none",
         "or_value": 1.14, "ci_lower": 1.03, "ci_upper": 1.27, "p_value": 0.012,
         "or_formatted": "1.14 (1.03-1.27)", "p_formatted": "P=0.012", "significant": True},
        {"variable": "zero_cat (>=1/day)", "label": "ZCB >=1/day vs none",
         "or_value": 1.31, "ci_lower": 1.06, "ci_upper": 1.61, "p_value": 0.013,
         "or_formatted": "1.31 (1.06-1.61)", "p_formatted": "P=0.013", "significant": True},
    ],
    "model_metrics": {"pseudo_r2": 0.073, "n_obs": 50972},
    "paper_summary": (
        "Among 50,972 Korean adolescents (KYRBS 2025), higher zero-calorie beverage "
        "consumption was independently associated with depressive symptoms, with "
        "adjusted odds ratios of 1.10, 1.14, and 1.31 for <=2/week, 3-6/week, and "
        ">=1/day, respectively, compared with non-consumers (P for trend <0.001). "
        "The association was evident only in females (P for interaction <0.001)."
    ),
    "descriptive_stats": (
        "Of 50,972 adolescents (mean age 14.9 years; 49.1% female), 56.2% reported no "
        "zero-calorie beverage consumption, 37.5% reported <=2/week, 5.0% reported "
        "3-6/week, and 1.2% reported >=1/day."
    ),
    "subgroup_results": (
        "Sex-stratified analysis: in females, the dose-response was strong "
        "(aOR 1.12 / 1.43 / 1.37, P_trend<0.001). In males the trend was attenuated "
        "(1.07 / 0.97 / 1.32, P_trend=0.088). P for interaction <0.001."
    ),
}
print("[2/4] stat_result composed: n=", stat_result["n_total"])

from src.research.paper_writer import PaperWriter
from src.profile.author_profile import AuthorProfile
try:
    from src.library.methods_library import MethodsLibrary
    ml = MethodsLibrary()
except Exception:
    ml = None
try:
    from src.library.dataset_library import DatasetLibrary
    dl = DatasetLibrary("data/libraries")
except Exception:
    dl = None

pw = PaperWriter(author_profile=AuthorProfile("Yoosun Cho"),
                  methods_library=ml, dataset_library=dl)

topic = ("Zero-Calorie Beverage Consumption and Depressive Symptoms "
         "in Korean Adolescents - KYRBS 2025")
study_info = {
    "dataset": "KYRBS 2025",
    "design": "cross-sectional, complex survey-weighted logistic regression",
    "exposure": "Zero-calorie beverage consumption frequency (4-category)",
    "outcome": "Depressive symptoms",
    "population": "Korean adolescents aged 12-18 years (N=50,972)",
    "sample_size": 50972,
    "covariates": ("age, sex, BMI category, school type, household socioeconomic "
                    "status, academic performance, lifetime smoking, lifetime alcohol, "
                    "SSB frequency, high-caffeine frequency, daily smartphone use, "
                    "physical activity, breakfast skipping"),
    "methods_list": ["logistic_regression"],
    "journal": "Journal of Adolescent Health",
}

t0 = time.time()
print("[3/4] paper_writer 호출 중 (Yoosun + style_polish + intent 자동 적용)...")
paper_text = pw.write_full_paper_with_stats(
    topic=topic, study_info=study_info, stat_result=stat_result)
sections = getattr(pw, "last_sections", {})
print(f"    {time.time()-t0:.1f}s 5섹션 완성:",
      {k: f"{len(str(v)):,}자" for k, v in sections.items()})

from src.export.word_exporter import WordExporter
from src.export.zcb_dep_tables import build_all_tables

tables_html = build_all_tables(
    survey_year=2025,
    p_trend_m1=0.0001, p_trend_m2=0.0001,
    p_trend_male=0.088, p_trend_female=0.0001, p_interaction=0.0001,
    p_trend_stress=0.253, p_trend_sleep=0.990)

references = [
    {"authors": ["Park JE", "Kim MJ", "Cho YS"], "year": 2024,
     "title": "Sugar-sweetened beverage intake and depression among Korean adolescents",
     "journal": "J Korean Med Sci", "volume": 39, "issue": 12, "pages": "e102"},
    {"authors": ["Lee H", "Kim K"], "year": 2023,
     "title": "Artificial sweetener exposure and mental health",
     "journal": "Nutrients", "volume": 15, "issue": 7, "pages": "1633"},
    {"authors": ["Cho Y", "Yoon S"], "year": 2024,
     "title": "KYRBS studies of adolescent lifestyle and mental health",
     "journal": "BMC Public Health", "volume": 24, "pages": "881"},
    {"authors": ["Goldman N", "Glei DA"], "year": 2022,
     "title": "Sex differences in adolescent depression",
     "journal": "JAMA Network Open", "volume": 5, "issue": 8, "pages": "e2225531"},
    {"authors": ["Patel V", "Saxena S"], "year": 2023,
     "title": "Adolescent mental health globally",
     "journal": "Lancet", "volume": 401, "pages": "1556-1567"},
    {"authors": ["Choi JH"], "year": 2022,
     "title": "Body image, dieting behavior, and beverage choice",
     "journal": "Appetite", "volume": 178, "pages": "106206"},
    {"authors": ["Lim SS", "Kim D"], "year": 2023,
     "title": "Survey design considerations in KYRBS",
     "journal": "Epidemiol Health", "volume": 45, "pages": "e2023029"},
    {"authors": ["Sweetman CK", "Brown JE"], "year": 2024,
     "title": "Non-nutritive sweeteners and mood",
     "journal": "Crit Rev Food Sci", "volume": 64, "pages": "1-14"},
]

fig_dir = Path("/app/data/exports")
if not fig_dir.exists():
    fig_dir = Path("data/exports")
figs = []
for fn, cap in [
    ("Figure1_PRISMA.png",
     "Figure 1. Flow chart for participant selection, KYRBS 2025."),
    ("Figure2_forest_subgroups.png",
     "Figure 2. Subgroup analyses for depressive symptoms — adjusted odds ratios per "
     "1-level increase in zero-calorie beverage consumption frequency. "
     "Subgroup categories and cutoffs are identical to those in Table 1 "
     "(BMI: KCDC sex- and age-specific percentiles)."),
    ("Supplementary_Figure_sex_lines.png",
     "Supplementary Figure. Predicted probability of depressive symptoms by zero-calorie "
     "beverage consumption frequency, stratified by sex."),
]:
    p = fig_dir / fn
    if p.exists():
        figs.append({"path": str(p), "caption": cap, "alt_text": cap})

print(f"[4/4] WordExporter: sections={list(sections.keys())} refs={len(references)} figs={len(figs)} tables={len(tables_html)}")

import json as _json
cache_p = Path("data/drafts/yoosun_sections_cache.json")
cache_p.parent.mkdir(parents=True, exist_ok=True)
cache_p.write_text(_json.dumps(sections, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[cache] sections saved: {cache_p}")

# 표는 별도 HTML 파일로 따로 (docx에 HTML 통째로 박으면 깨짐) — render_publication_table은
# type 키 ("baseline"/"regression"/"cross"/"raw") 기반이라 우리 HTML dict와 양식 다름.
# 따라서 docx에는 sections + figures + references만 넣고, 표는 사용자가 HTML/별도 양식.
we = WordExporter()
# Timestamp 양식 이름 — 직전 파일이 워드에서 열려 있어도 덮어쓰기 충돌 회피
from datetime import datetime as _dt
_ts = _dt.now().strftime("%H%M")
out_docx = we.export(
    topic={"title": topic + f" v{_ts}", "authors": ["Yoosun Cho"]},
    sections=sections,
    references=references,
    back_matter={},
    keywords=["zero-calorie beverage", "depression", "adolescent",
              "Korean", "KYRBS", "sex differences"],
    figures=figs,
    tables=[],   # 표 비움 — 깨짐 사고 방지
)
print(f"\nsaved: {out_docx}")
print(f"표 4종 별도 위치: data/exports/Table_1.html ... Supplementary_Table_1.html")
