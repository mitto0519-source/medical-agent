"""통계 분석 + 그림 출력 — VS Code Interactive Window용.

사용법:
  VS Code에서 이 파일을 열고 각 셀(# %%)을 Shift+Enter로 실행.
  그림은 오른쪽 Interactive 패널에 인라인으로 출력됩니다.
  또는 Jupyter Notebook(.ipynb)으로 변환해도 동일하게 동작.

데이터 교체: df = pd.read_csv("your_file.csv") 로 변경하면 됩니다.
"""

# %% [Setup]
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from src.config.env import bootstrap
bootstrap()

from src.statistics.medical_stats import MedicalStatistics
from src.visualization.medical_plots import MedicalVisualizer

viz = MedicalVisualizer()
stats = MedicalStatistics()

# ── 샘플 데이터 (실제 데이터로 교체) ────────────────────────────────────────
np.random.seed(42)
df = pd.DataFrame({
    "BMI":       np.random.normal(23.5, 3.2, 500),
    "SBP":       np.random.normal(118, 14, 500),
    "DBP":       np.random.normal(76, 9, 500),
    "Age":       np.random.randint(13, 19, 500),
    "Gender":    np.random.choice(["Male", "Female"], 500),
    "Obese":     np.random.choice([0, 1], 500, p=[0.8, 0.2]),
    "SleepHrs":  np.random.normal(6.5, 1.2, 500).clip(3, 10),
    "ScreenHrs": np.random.exponential(3, 500).clip(0, 12),
})
print(f"데이터 로드 완료: {df.shape[0]}행 × {df.shape[1]}열")
print(df.head(3))


# %% [기술통계 + 분포 그림]
sel_cols = ["BMI", "SBP", "SleepHrs", "ScreenHrs"]
desc = MedicalStatistics.descriptive_stats(df[sel_cols])
print(desc)

fig = MedicalVisualizer.auto_figure("descriptive", df, cols=sel_cols)
plt.show()


# %% [독립표본 t검정: BMI by Gender]
result = MedicalStatistics.independent_t_test(df, "BMI", "Gender")
print(f"\nt-test: BMI by Gender")
print(f"  t = {result.get('t_statistic', '?'):.3f}")
print(f"  p = {result.get('p_value', '?'):.4f}")
print(f"  Cohen's d = {result.get('cohens_d', '?')}")

fig = MedicalVisualizer.auto_figure("ttest", df, result=result,
                                    val_col="BMI", grp_col="Gender")
plt.show()


# %% [카이제곱: Gender × Obese]
result_chi2 = MedicalStatistics.chi_square_test(df, "Gender", "Obese")
print(f"\nChi-square: Gender × Obese")
print(f"  χ² = {result_chi2.get('chi2_statistic', '?'):.3f}")
print(f"  p  = {result_chi2.get('p_value', '?'):.4f}")

fig = MedicalVisualizer.auto_figure("chi2", df, var1="Gender", var2="Obese")
plt.show()


# %% [일원분산분석: SBP by Age]
result_anova = MedicalStatistics.one_way_anova(df, "SBP", "Age")
print(f"\nANOVA: SBP by Age")
print(f"  F = {result_anova.get('f_statistic', '?'):.3f}")
print(f"  p = {result_anova.get('p_value', '?'):.4f}")

fig = MedicalVisualizer.auto_figure("anova", df, result=result_anova,
                                    val_col="SBP", grp_col="Age")
plt.show()


# %% [상관분석 히트맵]
corr_cols = ["BMI", "SBP", "DBP", "SleepHrs", "ScreenHrs"]
corr = df[corr_cols].corr()
print(f"\n상관행렬:\n{corr.round(3)}")

fig = MedicalVisualizer.auto_figure("correlation", df, cols=corr_cols)
plt.show()


# %% [로지스틱 회귀: Obese ~ BMI + SleepHrs + ScreenHrs]
predictors = ["BMI", "SleepHrs", "ScreenHrs"]
result_logit = MedicalStatistics.logistic_regression(df, "Obese", predictors)
print(f"\n로지스틱 회귀:")
print(result_logit)

fig = MedicalVisualizer.auto_figure("logistic", df, result=result_logit)
plt.show()


# %% [선형 회귀: SBP ~ BMI]
result_lm = MedicalStatistics.linear_regression(df, "SBP", ["BMI"])
print(f"\n선형 회귀: SBP ~ BMI")
print(result_lm)

fig = MedicalVisualizer.auto_figure("linear", df, result=result_lm,
                                    outcome="SBP", predictors=["BMI"])
plt.show()


# %% [그림 파일로 저장]
# 저장하고 싶은 그림은 save_figure() 사용
fig = MedicalVisualizer.auto_figure("correlation", df, cols=corr_cols)
saved = MedicalVisualizer.save_figure(fig, "correlation_matrix", fmt="jpg", dpi=300)
print(f"\n저장 완료: {saved.resolve()}")

# Windows에서 바로 열기
import subprocess
subprocess.Popen(["start", "", str(saved)], shell=True)
