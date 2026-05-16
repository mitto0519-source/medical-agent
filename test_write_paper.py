"""논문 작성 엔드투엔드 테스트"""
import sys, os
sys.path.insert(0, '.')
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
from dotenv import load_dotenv
load_dotenv()

from src.research.research_pipeline import ResearchPipeline

rp = ResearchPipeline(author_name="Yoosun Cho")

topic = {
    "title": "Association between Smartphone Use Duration and Sleep Insufficiency among Korean Adolescents: A Nationwide Cross-Sectional Study",
    "exposure": "smartphone_weekday (주중 스마트폰 사용 시간)",
    "outcome": "sleep_sufficient (주관적 수면 충족도)",
    "population": "전국 중·고등학생 (KYRBS 2025)",
    "suggested_design": "Cross-sectional",
    "suggested_methods": ["logistic_regression", "chi_square"],
}

study_info = {
    "dataset": "Korea Youth Risk Behavior Survey (KYRBS), 21st wave (2025)",
    "design": "Nationwide cross-sectional study",
    "sample_size": "54,633",
    "survey_year": "2025",
    "journal": "IJERPH",
    "analysis": "Complex sampling logistic regression (svyglm), adjusted for sex, grade, region, family_econ, academic_perf, depression, pa_60min",
}

results = {
    "summary": (
        "Compared to adolescents using smartphones <2 hours/day on weekdays, "
        "those using ≥4 hours had significantly higher odds of sleep insufficiency "
        "(OR=2.34, 95% CI: 1.89-2.91, p<0.001) after full adjustment. "
        "The association was stronger in female students (OR=2.67) than male (OR=1.98). "
        "High screen time was also associated with depressive symptoms (OR=1.78, p<0.001) "
        "and poor academic performance (OR=1.45, p=0.002). "
        "A dose-response relationship was observed across all smartphone use categories."
    )
}

print("논문 작성 시작...\n")
draft = rp.write_paper(topic, study_info, results)

print("\n" + "="*60)
print("생성된 논문 초안 (앞 3000자)")
print("="*60)
print(draft[:3000])
print(f"\n...\n\n총 글자 수: {len(draft)}자")
print(f"저장 위치: data/drafts/")
