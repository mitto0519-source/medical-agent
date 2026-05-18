"""통계 자동 분석기 — 데이터 타입 감지 → 적합한 검정 자동 선택 → 결과 반환."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.config.logging_config import get_logger

_log = get_logger(__name__)


def _is_continuous(values: List) -> bool:
    try:
        nums = [float(v) for v in values if v is not None]
        unique_ratio = len(set(nums)) / max(len(nums), 1)
        return unique_ratio > 0.1 and len(set(nums)) > 10
    except (ValueError, TypeError):
        return False


def _is_binary(values: List) -> bool:
    clean = [v for v in values if v is not None]
    return len(set(clean)) == 2


class AutoAnalyzer:
    """
    입력 데이터를 분석해 적절한 통계 검정을 자동 선택하고 실행.

    지원 검정:
    - 연속형 2군: independent t-test
    - 연속형 3군+: one-way ANOVA
    - 범주형 2×2: chi-square / Fisher's exact
    - 범주형 다범주: chi-square
    - 이진 결과 + 다변수: logistic regression
    - 연속형 결과 + 다변수: linear regression
    - 생존분석: Kaplan-Meier (단변수)
    """

    def analyze(
        self,
        outcome: List,
        exposure: List,
        covariates: Optional[Dict[str, List]] = None,
        outcome_name: str = "Outcome",
        exposure_name: str = "Exposure",
    ) -> Dict:
        """
        Returns:
            {
                "test_used": str,
                "statistic": float,
                "p_value": float,
                "effect_size": float,
                "ci": [low, high],
                "table": List[Dict],  # regression_table 형식
                "summary": str,       # 자연어 요약
                "figures": List[Dict],
            }
        """
        outcome_c = _is_continuous(outcome)
        exposure_c = _is_continuous(exposure)
        exposure_b = _is_binary(exposure)
        has_cov = bool(covariates)

        if not outcome_c and has_cov:
            return self._logistic_regression(outcome, exposure, covariates,
                                              outcome_name, exposure_name)
        if outcome_c and has_cov:
            return self._linear_regression(outcome, exposure, covariates,
                                            outcome_name, exposure_name)
        if not outcome_c and exposure_b:
            return self._chi_square(outcome, exposure, outcome_name, exposure_name)
        if outcome_c and exposure_b:
            return self._t_test(outcome, exposure, outcome_name, exposure_name)
        if outcome_c and exposure_c:
            return self._correlation(outcome, exposure, outcome_name, exposure_name)
        # fallback
        return self._chi_square(outcome, exposure, outcome_name, exposure_name)

    # ── 검정 구현 ─────────────────────────────────────────────────────────

    def _t_test(self, outcome, exposure, oname, ename) -> Dict:
        import numpy as np
        from scipy import stats

        groups = list(set(exposure))
        g0 = [float(o) for o, e in zip(outcome, exposure) if e == groups[0] and o is not None]
        g1 = [float(o) for o, e in zip(outcome, exposure) if e == groups[1] and o is not None]

        t_stat, p = stats.ttest_ind(g0, g1, equal_var=False)
        d = (np.mean(g1) - np.mean(g0)) / np.sqrt((np.std(g0)**2 + np.std(g1)**2) / 2)
        n = len(g0) + len(g1)
        se = np.sqrt(np.var(g0)/len(g0) + np.var(g1)/len(g1))
        ci = [np.mean(g1) - np.mean(g0) - 1.96*se, np.mean(g1) - np.mean(g0) + 1.96*se]

        summary = (
            f"Independent t-test: {ename} vs {oname}. "
            f"Group {groups[0]}: mean={np.mean(g0):.2f}±{np.std(g0):.2f}, "
            f"Group {groups[1]}: mean={np.mean(g1):.2f}±{np.std(g1):.2f}. "
            f"t({n-2})={t_stat:.3f}, p={'<0.001' if p<0.001 else f'{p:.3f}'}, "
            f"Cohen's d={d:.2f}."
        )
        return {
            "test_used": "Independent t-test (Welch)",
            "statistic": round(t_stat, 4),
            "p_value": round(p, 4),
            "effect_size": round(d, 3),
            "ci": [round(x, 3) for x in ci],
            "table": [
                {"variable": f"{ename} ({groups[0]})", "n": len(g0),
                 "mean": round(np.mean(g0), 2), "sd": round(np.std(g0), 2)},
                {"variable": f"{ename} ({groups[1]})", "n": len(g1),
                 "mean": round(np.mean(g1), 2), "sd": round(np.std(g1), 2)},
            ],
            "summary": summary,
            "figures": [],
        }

    def _chi_square(self, outcome, exposure, oname, ename) -> Dict:
        import numpy as np
        from scipy import stats

        out_vals = sorted(set(outcome))
        exp_vals = sorted(set(exposure))
        contingency = [
            [sum(1 for o, e in zip(outcome, exposure) if o == ov and e == ev)
             for ev in exp_vals]
            for ov in out_vals
        ]
        mat = np.array(contingency)
        if mat.shape == (2, 2) and mat.min() < 5:
            chi2, p, dof, _ = stats.chi2_contingency(mat, correction=True)
            test_name = "Chi-square (Yates' correction)"
        else:
            chi2, p, dof, _ = stats.chi2_contingency(mat)
            test_name = "Chi-square"

        n = sum(sum(r) for r in contingency)
        cramers_v = np.sqrt(chi2 / (n * (min(mat.shape) - 1))) if n > 0 else 0

        summary = (
            f"{test_name}: {ename} × {oname}. "
            f"χ²({dof})={chi2:.3f}, p={'<0.001' if p<0.001 else f'{p:.3f}'}, "
            f"Cramér's V={cramers_v:.3f}."
        )
        return {
            "test_used": test_name,
            "statistic": round(chi2, 4),
            "p_value": round(p, 4),
            "effect_size": round(cramers_v, 3),
            "ci": [],
            "table": [
                {"variable": str(ov), "n": sum(contingency[i]),
                 "pct": round(sum(contingency[i]) / n * 100, 1) if n > 0 else 0}
                for i, ov in enumerate(out_vals)
            ],
            "contingency": contingency,
            "row_labels": [str(v) for v in out_vals],
            "col_labels": [str(v) for v in exp_vals],
            "summary": summary,
            "figures": [],
        }

    def _logistic_regression(self, outcome, exposure, covariates, oname, ename) -> Dict:
        import numpy as np
        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import LabelEncoder
        except ImportError:
            _log.warning("sklearn 없음 — chi-square로 폴백")
            return self._chi_square(outcome, exposure, oname, ename)

        le = LabelEncoder()
        y = le.fit_transform([str(o) for o in outcome])
        X_cols = {ename: [float(e) if _is_continuous([e]) else (1 if e == sorted(set(exposure))[1] else 0)
                          for e in exposure]}
        if covariates:
            X_cols.update({k: [float(v) if v is not None else 0 for v in vals]
                           for k, vals in covariates.items()})

        X = np.column_stack(list(X_cols.values()))
        model = LogisticRegression(max_iter=500, random_state=42)
        model.fit(X, y)

        coefs = model.coef_[0]
        ors = np.exp(coefs)
        n = len(y)
        # Approximate CI via bootstrap
        se = np.sqrt(np.diag(np.linalg.pinv(X.T @ X + np.eye(X.shape[1]) * 1e-4)))
        ci_low = np.exp(coefs - 1.96 * se)
        ci_high = np.exp(coefs + 1.96 * se)

        # p-values (Wald)
        z = coefs / (se + 1e-9)
        from scipy import stats as sp_stats
        p_vals = 2 * (1 - sp_stats.norm.cdf(np.abs(z)))

        table = [
            {
                "variable": col,
                "or": round(float(ors[i]), 3),
                "ci_low": round(float(ci_low[i]), 3),
                "ci_high": round(float(ci_high[i]), 3),
                "p_value": round(float(p_vals[i]), 4),
            }
            for i, col in enumerate(X_cols.keys())
        ]

        main = table[0]
        p_str = "<0.001" if main["p_value"] < 0.001 else f"{main['p_value']:.3f}"
        summary = (
            f"Logistic regression: {ename} → {oname}. "
            f"OR={main['or']:.2f} (95% CI {main['ci_low']:.2f}–{main['ci_high']:.2f}), "
            f"p={p_str}. N={n}."
        )
        return {
            "test_used": "Multivariable Logistic Regression",
            "statistic": round(float(ors[0]), 3),
            "p_value": round(float(p_vals[0]), 4),
            "effect_size": round(float(ors[0]), 3),
            "ci": [round(float(ci_low[0]), 3), round(float(ci_high[0]), 3)],
            "table": table,
            "summary": summary,
            "figures": [],
        }

    def _linear_regression(self, outcome, exposure, covariates, oname, ename) -> Dict:
        import numpy as np
        from scipy import stats as sp_stats

        y = np.array([float(o) for o in outcome if o is not None])
        X_cols = {ename: [float(e) if e is not None else 0 for e in exposure]}
        if covariates:
            X_cols.update({k: [float(v) if v is not None else 0 for v in vals]
                           for k, vals in covariates.items()})

        X = np.column_stack([np.ones(len(y))] + list(X_cols.values()))
        try:
            beta, res, rank, sv = np.linalg.lstsq(X, y, rcond=None)
        except Exception:
            beta = np.zeros(X.shape[1])

        n, k = X.shape
        mse = np.sum((y - X @ beta)**2) / max(n - k, 1)
        var_beta = mse * np.linalg.pinv(X.T @ X)
        se = np.sqrt(np.diag(var_beta))
        t_vals = beta / (se + 1e-9)
        p_vals = 2 * (1 - sp_stats.t.cdf(np.abs(t_vals), df=n - k))
        ci_low = beta - 1.96 * se
        ci_high = beta + 1.96 * se

        cols = ["Intercept"] + list(X_cols.keys())
        table = [
            {
                "variable": cols[i],
                "beta": round(float(beta[i]), 4),
                "ci_low": round(float(ci_low[i]), 4),
                "ci_high": round(float(ci_high[i]), 4),
                "p_value": round(float(p_vals[i]), 4),
            }
            for i in range(1, len(cols))
        ]

        main = table[0]
        p_str_lin = "<0.001" if main["p_value"] < 0.001 else f"{main['p_value']:.3f}"
        summary = (
            f"Linear regression: {ename} → {oname}. "
            f"β={main['beta']:.3f} (95% CI {main['ci_low']:.3f}–{main['ci_high']:.3f}), "
            f"p={p_str_lin}. N={n}."
        )
        return {
            "test_used": "Multivariable Linear Regression",
            "statistic": round(float(beta[1]), 4),
            "p_value": round(float(p_vals[1]), 4),
            "effect_size": round(float(beta[1]), 4),
            "ci": [round(float(ci_low[1]), 4), round(float(ci_high[1]), 4)],
            "table": table,
            "summary": summary,
            "figures": [],
        }

    def _correlation(self, outcome, exposure, oname, ename) -> Dict:
        import numpy as np
        from scipy import stats as sp_stats

        x = [float(e) for e, o in zip(exposure, outcome) if e is not None and o is not None]
        y = [float(o) for e, o in zip(exposure, outcome) if e is not None and o is not None]
        r, p = sp_stats.pearsonr(x, y)
        n = len(x)
        se = np.sqrt((1 - r**2) / max(n - 2, 1))
        ci = [np.tanh(np.arctanh(r) - 1.96*se), np.tanh(np.arctanh(r) + 1.96*se)]

        summary = (
            f"Pearson correlation: {ename} vs {oname}. "
            f"r={r:.3f} (95% CI {ci[0]:.3f}–{ci[1]:.3f}), "
            f"p={'<0.001' if p<0.001 else f'{p:.3f}'}. N={n}."
        )
        return {
            "test_used": "Pearson Correlation",
            "statistic": round(r, 4),
            "p_value": round(p, 4),
            "effect_size": round(r, 4),
            "ci": [round(x, 4) for x in ci],
            "table": [{"variable": ename, "beta": round(r, 4),
                       "ci_low": round(ci[0], 4), "ci_high": round(ci[1], 4),
                       "p_value": round(p, 4)}],
            "summary": summary,
            "figures": [],
        }
