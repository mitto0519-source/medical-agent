import sys, os
sys.path.insert(0, '.')
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from src.library.dataset_library import DatasetLibrary

lib = DatasetLibrary('data/libraries')
print('등록된 데이터셋:', lib.list_datasets())
ds = lib.get_dataset('KYRBS')
print(f'KYRBS 변수 수: {len(ds["variables"])}개')
print(f'교란변수: {len(ds["common_confounders"])}개')
print(f'분석 주의사항: {len(ds["analysis_notes"])}개')

# 도메인별 요약
domains = {
    '인구사회': ['sex','grade','school_type','region','family_type','father_edu','mother_edu','family_econ','academic_perf','residence_type','parent_nationality','birth_year'],
    '흡연': [k for k in ds['variables'] if k.startswith('cig_') or k.startswith('ecig_') or k.startswith('iqos_') or k in ['tobacco_purchase','quit_attempt','secondhand_home','secondhand_public']],
    '음주': [k for k in ds['variables'] if k.startswith('alc_')],
    '신체활동': [k for k in ds['variables'] if k.startswith('pa_') or k.startswith('sit_') or k.startswith('pe_') or k.startswith('sport') or k.startswith('commute')],
    '식생활': [k for k in ds['variables'] if k.endswith('_intake') or k in ['breakfast_skip']],
    '비만': ['height','weight','bmi','bmi_category','body_image','weight_control','mukbang_watch'],
    '정신건강': [k for k in ds['variables'] if k.startswith('sui') or k in ['stress','depression']],
    '수면': [k for k in ds['variables'] if k.startswith('sleep')],
    '가중치': ['wt','strata_id','cluster_id'],
}
print()
for domain, vars in domains.items():
    exists = [v for v in vars if v in ds['variables']]
    print(f'  {domain}: {len(exists)}개 — {exists}')
