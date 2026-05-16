"""Medical Research Analysis Statistics Module - Pandas Based

Comprehensive pandas-based statistical analysis for medical research.
All methods are built on pandas DataFrames for seamless data manipulation.
"""

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests
import pingouin as pg
from typing import Tuple, Dict, List, Any, Optional, Union


class MedicalStatistics:
    """Pandas-based comprehensive medical statistics analysis"""
    
    @staticmethod
    def descriptive_stats(data: Union[pd.Series, pd.DataFrame]) -> pd.DataFrame:
        """Calculate comprehensive descriptive statistics
        
        Args:
            data: Series or DataFrame
            
        Returns:
            DataFrame with descriptive statistics
        """
        if isinstance(data, pd.Series):
            return pd.DataFrame({
                'mean': [data.mean()],
                'median': [data.median()],
                'std': [data.std()],
                'min': [data.min()],
                'max': [data.max()],
                'q25': [data.quantile(0.25)],
                'q75': [data.quantile(0.75)],
                'iqr': [data.quantile(0.75) - data.quantile(0.25)],
                'skewness': [data.skew()],
                'kurtosis': [data.kurtosis()],
                'count': [data.count()],
                'null_count': [data.isnull().sum()]
            }).T
        else:
            # DataFrame input
            return data.describe().T.assign(
                iqr=lambda x: x['75%'] - x['25%'],
                skewness=lambda x: data.skew(),
                kurtosis=lambda x: data.kurtosis(),
                null_count=lambda x: data.isnull().sum()
            )
    
    @staticmethod
    def grouped_descriptive(df: pd.DataFrame, value_col: str, group_col: str) -> pd.DataFrame:
        """Calculate descriptive statistics grouped by a categorical variable
        
        Args:
            df: Input DataFrame
            value_col: Column with values to analyze
            group_col: Column to group by
            
        Returns:
            DataFrame with grouped statistics
        """
        return df.groupby(group_col)[value_col].agg([
            'count', 'mean', 'median', 'std', 'min', 'max',
            ('q25', lambda x: x.quantile(0.25)),
            ('q75', lambda x: x.quantile(0.75)),
            ('iqr', lambda x: x.quantile(0.75) - x.quantile(0.25))
        ]).round(4)
    
    @staticmethod
    def t_test(group1: pd.Series, group2: pd.Series, paired: bool = False) -> Dict[str, Any]:
        """Perform t-test with effect sizes
        
        Args:
            group1: First group data
            group2: Second group data
            paired: Whether samples are paired
            
        Returns:
            Dictionary with comprehensive test results
        """
        if paired:
            t_stat, p_val = stats.ttest_rel(group1.dropna(), group2.dropna())
        else:
            t_stat, p_val = stats.ttest_ind(group1.dropna(), group2.dropna())
        
        # Calculate effect sizes
        cohens_d = (group1.mean() - group2.mean()) / np.sqrt((group1.std()**2 + group2.std()**2) / 2)
        
        # Calculate 95% Confidence Interval for mean difference
        mean_diff = group1.mean() - group2.mean()
        se_diff = np.sqrt(group1.var()/len(group1) + group2.var()/len(group2))
        ci_lower = mean_diff - 1.96 * se_diff
        ci_upper = mean_diff + 1.96 * se_diff
        
        return {
            't_statistic': t_stat,
            'p_value': p_val,
            'cohens_d': cohens_d,
            'mean_diff': mean_diff,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'significant': p_val < 0.05,
            'group1_mean': group1.mean(),
            'group2_mean': group2.mean(),
            'group1_sd': group1.std(),
            'group2_sd': group2.std(),
            'n1': len(group1.dropna()),
            'n2': len(group2.dropna())
        }
    
    @staticmethod
    def chi_square(contingency_table: Union[pd.DataFrame, np.ndarray]) -> Dict[str, Any]:
        """Perform chi-square test with effect sizes
        
        Args:
            contingency_table: Contingency table (DataFrame or numpy array)
            
        Returns:
            Dictionary with chi-square results
        """
        if isinstance(contingency_table, pd.DataFrame):
            contingency_table = contingency_table.values
            
        chi2, p_val, dof, expected = stats.chi2_contingency(contingency_table)
        
        # Calculate Cramér's V (effect size for chi-square)
        n = contingency_table.sum()
        min_dim = min(contingency_table.shape) - 1
        cramers_v = np.sqrt(chi2 / (n * min_dim)) if min_dim > 0 else 0
        
        return {
            'chi2_statistic': chi2,
            'p_value': p_val,
            'degrees_of_freedom': dof,
            'cramers_v': cramers_v,
            'expected_frequencies': expected,
            'significant': p_val < 0.05
        }
    
    @staticmethod
    def anova(*groups, return_df: bool = False) -> Union[Dict[str, Any], pd.DataFrame]:
        """Perform one-way ANOVA
        
        Args:
            *groups: Variable number of group Series
            return_df: Whether to return as DataFrame
            
        Returns:
            Dictionary or DataFrame with ANOVA results
        """
        f_stat, p_val = stats.f_oneway(*[g.dropna() for g in groups])
        
        # Calculate effect size (eta-squared)
        all_data = pd.concat([pd.Series(g.dropna()) for g in groups])
        grand_mean = all_data.mean()
        
        ss_between = sum([len(g.dropna()) * (g.mean() - grand_mean)**2 for g in groups])
        ss_total = sum([(all_data - grand_mean)**2])
        eta_squared = ss_between / ss_total if ss_total > 0 else 0
        
        result = {
            'f_statistic': f_stat,
            'p_value': p_val,
            'eta_squared': eta_squared,
            'significant': p_val < 0.05,
            'n_groups': len(groups),
            'group_means': [g.mean() for g in groups],
            'group_sds': [g.std() for g in groups],
            'group_ns': [len(g.dropna()) for g in groups]
        }
        
        if return_df:
            return pd.DataFrame([result]).T
        return result
    
    @staticmethod
    def mann_whitney_u(group1: pd.Series, group2: pd.Series) -> Dict[str, Any]:
        """Perform Mann-Whitney U test (non-parametric)
        
        Args:
            group1: First group data
            group2: Second group data
            
        Returns:
            Dictionary with test results
        """
        u_stat, p_val = stats.mannwhitneyu(group1.dropna(), group2.dropna(), alternative='two-sided')
        
        # Calculate effect size (rank-biserial correlation)
        n1, n2 = len(group1.dropna()), len(group2.dropna())
        r = 1 - (2*u_stat) / (n1 * n2)
        
        return {
            'u_statistic': u_stat,
            'p_value': p_val,
            'effect_size_r': r,
            'significant': p_val < 0.05,
            'n1': n1,
            'n2': n2,
            'median1': group1.median(),
            'median2': group2.median()
        }
    
    @staticmethod
    def kruskal_wallis(*groups) -> Dict[str, Any]:
        """Perform Kruskal-Wallis test (non-parametric ANOVA)
        
        Args:
            *groups: Variable number of group Series
            
        Returns:
            Dictionary with test results
        """
        h_stat, p_val = stats.kruskal(*[g.dropna() for g in groups])
        
        return {
            'h_statistic': h_stat,
            'p_value': p_val,
            'significant': p_val < 0.05,
            'n_groups': len(groups),
            'group_medians': [g.median() for g in groups],
            'group_ns': [len(g.dropna()) for g in groups]
        }
    
    @staticmethod
    def correlation(x: pd.Series, y: pd.Series, method: str = 'pearson') -> Dict[str, Any]:
        """Calculate correlation between two variables
        
        Args:
            x: First variable
            y: Second variable
            method: 'pearson', 'spearman', or 'kendall'
            
        Returns:
            Dictionary with correlation results and CI
        """
        # Remove NaNs
        valid_idx = ~(x.isna() | y.isna())
        x_clean = x[valid_idx]
        y_clean = y[valid_idx]
        
        if method == 'pearson':
            corr, p_val = stats.pearsonr(x_clean, y_clean)
        elif method == 'spearman':
            corr, p_val = stats.spearmanr(x_clean, y_clean)
        elif method == 'kendall':
            corr, p_val = stats.kendalltau(x_clean, y_clean)
        else:
            raise ValueError("Method must be 'pearson', 'spearman', or 'kendall'")
        
        # Calculate 95% CI using Fisher's z-transformation
        n = len(x_clean)
        z = 0.5 * np.log((1 + corr) / (1 - corr)) if abs(corr) < 1 else np.inf
        se_z = 1 / np.sqrt(n - 3) if n > 3 else np.inf
        
        z_ci_lower = z - 1.96 * se_z
        z_ci_upper = z + 1.96 * se_z
        
        r_ci_lower = (np.exp(2 * z_ci_lower) - 1) / (np.exp(2 * z_ci_lower) + 1)
        r_ci_upper = (np.exp(2 * z_ci_upper) - 1) / (np.exp(2 * z_ci_upper) + 1)
        
        return {
            'correlation': corr,
            'p_value': p_val,
            'method': method,
            'ci_lower': r_ci_lower,
            'ci_upper': r_ci_upper,
            'significant': p_val < 0.05,
            'n': n
        }
    
    @staticmethod
    def correlation_matrix(df: pd.DataFrame, method: str = 'pearson',
                          p_values: bool = True) -> pd.DataFrame:
        """Calculate correlation matrix with p-values
        
        Args:
            df: DataFrame with numeric columns
            method: 'pearson', 'spearman', or 'kendall'
            p_values: Whether to calculate p-values
            
        Returns:
            DataFrame with correlation matrix
        """
        corr_matrix = df.corr(method=method)
        
        if p_values:
            # Calculate p-values for all pairs
            n = len(df)
            p_matrix = pd.DataFrame(np.zeros_like(corr_matrix),
                                   index=corr_matrix.index,
                                   columns=corr_matrix.columns)
            
            for i in range(len(corr_matrix.columns)):
                for j in range(i, len(corr_matrix.columns)):
                    if i == j:
                        p_matrix.iloc[i, j] = 0
                    else:
                        if method == 'pearson':
                            _, p_val = stats.pearsonr(df.iloc[:, i].dropna(), 
                                                      df.iloc[:, j].dropna())
                        elif method == 'spearman':
                            _, p_val = stats.spearmanr(df.iloc[:, i].dropna(),
                                                       df.iloc[:, j].dropna())
                        else:
                            _, p_val = stats.kendalltau(df.iloc[:, i].dropna(),
                                                       df.iloc[:, j].dropna())
                        p_matrix.iloc[i, j] = p_val
                        p_matrix.iloc[j, i] = p_val
            
            return pd.concat({
                'correlation': corr_matrix,
                'p_value': p_matrix
            }, axis=1)
        
        return corr_matrix
    
    @staticmethod
    def regression_analysis(df: pd.DataFrame, y_col: str, x_cols: List[str]) -> Dict[str, Any]:
        """Perform linear regression analysis
        
        Args:
            df: Input DataFrame
            y_col: Dependent variable column
            x_cols: List of independent variable columns
            
        Returns:
            Dictionary with regression results
        """
        from sklearn.linear_model import LinearRegression
        
        # Prepare data
        X = df[x_cols].dropna()
        y = df.loc[X.index, y_col]
        
        # Fit model
        model = LinearRegression()
        model.fit(X, y)
        
        # Calculate statistics
        y_pred = model.predict(X)
        residuals = y - y_pred
        mse = np.mean(residuals**2)
        rmse = np.sqrt(mse)
        r_squared = model.score(X, y)
        
        # Calculate adjusted R-squared
        n = len(y)
        p = len(x_cols)
        adj_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - p - 1)
        
        # P-values for coefficients
        se = np.sqrt(mse * np.diag(np.linalg.inv(X.T @ X)))
        t_stats = model.coef_ / se
        p_values = [2 * (1 - stats.t.cdf(abs(t), n - p - 1)) for t in t_stats]
        
        result = {
            'intercept': model.intercept_,
            'coefficients': dict(zip(x_cols, model.coef_)),
            'p_values': dict(zip(x_cols, p_values)),
            'r_squared': r_squared,
            'adjusted_r_squared': adj_r_squared,
            'rmse': rmse,
            'mse': mse,
            'n': n
        }
        
        return result
    
    @staticmethod
    def logistic_regression(df: pd.DataFrame, y_col: str, x_cols: List[str]) -> Dict[str, Any]:
        """Perform logistic regression
        
        Args:
            df: Input DataFrame
            y_col: Binary dependent variable column
            x_cols: List of independent variable columns
            
        Returns:
            Dictionary with logistic regression results
        """
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score, confusion_matrix
        
        # Prepare data
        X = df[x_cols].dropna()
        y = df.loc[X.index, y_col]
        
        # Fit model
        model = LogisticRegression(max_iter=1000)
        model.fit(X, y)
        
        # Predictions and probabilities
        y_pred = model.predict(X)
        y_prob = model.predict_proba(X)[:, 1]
        
        # Calculate metrics
        accuracy = model.score(X, y)
        auc = roc_auc_score(y, y_prob)
        
        # Odds ratios
        odds_ratios = np.exp(model.coef_[0])
        
        # Confusion matrix
        tn, fp, fn, tp = confusion_matrix(y, y_pred).ravel()
        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
        
        return {
            'intercept': model.intercept_[0],
            'coefficients': dict(zip(x_cols, model.coef_[0])),
            'odds_ratios': dict(zip(x_cols, odds_ratios)),
            'accuracy': accuracy,
            'auc': auc,
            'sensitivity': sensitivity,
            'specificity': specificity,
            'tp': int(tp),
            'tn': int(tn),
            'fp': int(fp),
            'fn': int(fn),
            'n': len(y)
        }
    
    @staticmethod
    def handle_missing_values(df: pd.DataFrame, strategy: str = 'mean') -> pd.DataFrame:
        """Handle missing values in dataset with method selection
        
        Args:
            df: Input dataframe
            strategy: 'mean', 'median', 'forward_fill', 'backward_fill', 'drop'
            
        Returns:
            Dataframe with missing values handled
        """
        df_copy = df.copy()
        
        # Get numeric columns
        numeric_cols = df_copy.select_dtypes(include=['number']).columns
        
        if strategy == 'mean':
            df_copy[numeric_cols] = df_copy[numeric_cols].fillna(df_copy[numeric_cols].mean())
        elif strategy == 'median':
            df_copy[numeric_cols] = df_copy[numeric_cols].fillna(df_copy[numeric_cols].median())
        elif strategy == 'forward_fill':
            df_copy = df_copy.ffill()
        elif strategy == 'backward_fill':
            df_copy = df_copy.bfill()
        elif strategy == 'drop':
            df_copy = df_copy.dropna()
        
        return df_copy
    
    @staticmethod
    def detect_normality(series: pd.Series, test: str = 'shapiro') -> Dict[str, Any]:
        """Test for normality
        
        Args:
            series: Data series
            test: 'shapiro', 'anderson', 'kstest'
            
        Returns:
            Dictionary with normality test results
        """
        data = series.dropna()
        
        if test == 'shapiro':
            stat, p_val = stats.shapiro(data)
            test_name = "Shapiro-Wilk"
        elif test == 'anderson':
            result = stats.anderson(data)
            stat = result.statistic
            p_val = None
            test_name = "Anderson-Darling"
        elif test == 'kstest':
            # Standardize data
            data_std = (data - data.mean()) / data.std()
            stat, p_val = stats.kstest(data_std, 'norm')
            test_name = "Kolmogorov-Smirnov"
        else:
            raise ValueError("Test must be 'shapiro', 'anderson', or 'kstest'")
        
        return {
            'test': test_name,
            'statistic': stat,
            'p_value': p_val,
            'is_normal': (p_val > 0.05) if p_val is not None else None,
            'n': len(data),
            'skewness': data.skew(),
            'kurtosis': data.kurtosis()
        }


class SurvivalAnalysis:
    """Kaplan-Meier and survival analysis methods using pandas"""
    
    @staticmethod
    def kaplan_meier(durations: pd.Series, event_observed: pd.Series,
                    group: Optional[pd.Series] = None) -> Dict[str, Any]:
        """Perform Kaplan-Meier survival analysis
        
        Args:
            durations: Time to event or censoring
            event_observed: Event indicator (1=event, 0=censored)
            group: Optional grouping variable
            
        Returns:
            Dictionary with KM analysis results
        """
        from lifelines import KaplanMeierFitter
        
        kmf = KaplanMeierFitter()
        kmf.fit(durations, event_observed)
        
        result = {
            'kmf': kmf,
            'survival_func': kmf.survival_function_,
            'median_survival': kmf.median_survival_time_,
            'confidence_interval': kmf.confidence_interval_survival_function_,
            'event_count': event_observed.sum(),
            'n': len(durations)
        }
        
        return result
    
    @staticmethod
    def cox_regression(df: pd.DataFrame, duration_col: str, event_col: str,
                      x_cols: List[str]) -> Dict[str, Any]:
        """Perform Cox proportional hazards regression
        
        Args:
            df: Input DataFrame
            duration_col: Time to event column
            event_col: Event indicator column
            x_cols: List of covariate columns
            
        Returns:
            Dictionary with regression results
        """
        from lifelines import CoxPHFitter
        
        # Prepare data
        cox_data = df[[duration_col, event_col] + x_cols].dropna()
        
        # Fit Cox model
        cph = CoxPHFitter()
        cph.fit(cox_data, duration_col=duration_col, event_col=event_col)
        
        # Extract results
        results = {
            'summary': cph.summary,
            'concordance_index': cph.concordance_index_,
            'log_likelihood': cph.log_likelihood_,
            'n_observations': cph.event_observed.sum(),
            'n_censored': (~cox_data[event_col].astype(bool)).sum(),
            'hazard_ratios': dict(zip(x_cols, np.exp(cph.params_)))
        }
        
        return results
    
    @staticmethod
    def log_rank_test(durations1: pd.Series, event1: pd.Series,
                     durations2: pd.Series, event2: pd.Series) -> Dict[str, Any]:
        """Perform log-rank test comparing survival curves
        
        Args:
            durations1: Group 1 durations
            event1: Group 1 events
            durations2: Group 2 durations
            event2: Group 2 events
            
        Returns:
            Dictionary with log-rank test results
        """
        from lifelines.statistics import logrank_test
        
        result = logrank_test(durations1, durations2, event1, event2)
        
        return {
            'test_statistic': result.test_statistic,
            'p_value': result.p_value,
            'significant': result.p_value < 0.05,
            'degrees_of_freedom': result.degrees_of_freedom,
            'n1': len(durations1),
            'n2': len(durations2)
        }


class CategoricalAnalysis:
    """Methods for categorical data analysis with pandas"""
    
    @staticmethod
    def contingency_table(df: pd.DataFrame, row_var: str, col_var: str) -> pd.DataFrame:
        """Create contingency table
        
        Args:
            df: Input DataFrame
            row_var: Row variable
            col_var: Column variable
            
        Returns:
            Contingency table as DataFrame
        """
        return pd.crosstab(df[row_var], df[col_var], margins=True)
    
    @staticmethod
    def proportion_test(successes: Union[int, List[int]],
                       totals: Union[int, List[int]]) -> Dict[str, Any]:
        """Perform proportion test (binomial or chi-square)
        
        Args:
            successes: Number of successes (or list of successes)
            totals: Total sample size (or list of totals)
            
        Returns:
            Dictionary with test results
        """
        from statsmodels.stats.proportion import proportions_ztest
        
        if isinstance(successes, int):
            # Single proportion
            prop = successes / totals
            se = np.sqrt(prop * (1 - prop) / totals)
            z_stat = (prop - 0.5) / se if se > 0 else 0
            p_val = 2 * (1 - stats.norm.cdf(abs(z_stat)))
            
            return {
                'proportion': prop,
                'z_statistic': z_stat,
                'p_value': p_val,
                'se': se,
                'successes': successes,
                'total': totals
            }
        else:
            # Multiple proportions
            z_stat, p_val = proportions_ztest(successes, totals)
            
            return {
                'z_statistic': z_stat,
                'p_value': p_val,
                'proportions': [s/t for s, t in zip(successes, totals)],
                'successes': successes,
                'totals': totals
            }
    
    @staticmethod
    def mcnemar_test(df: pd.DataFrame, var1: str, var2: str) -> Dict[str, Any]:
        """Perform McNemar's test for paired binary data
        
        Args:
            df: Input DataFrame
            var1: First variable
            var2: Second variable
            
        Returns:
            Dictionary with McNemar test results
        """
        # Create 2x2 table
        table = pd.crosstab(df[var1], df[var2])
        
        # McNemar statistic
        if table.shape == (2, 2):
            a = table.iloc[0, 0]  # both positive
            b = table.iloc[0, 1]  # var1 positive, var2 negative
            c = table.iloc[1, 0]  # var1 negative, var2 positive
            d = table.iloc[1, 1]  # both negative
            
            chi2 = (b - c)**2 / (b + c) if (b + c) > 0 else 0
            p_val = 1 - stats.chi2.cdf(chi2, 1)
            
            return {
                'chi2_statistic': chi2,
                'p_value': p_val,
                'significant': p_val < 0.05,
                'agreement': (a + d) / (a + b + c + d),
                'table': table
            }
        else:
            raise ValueError("McNemar test requires 2x2 contingency table")


class MultipleComparison:
    """Methods for multiple comparisons and post-hoc tests"""
    
    @staticmethod
    def bonferroni_correction(p_values: Union[List[float], np.ndarray, pd.Series],
                             alpha: float = 0.05) -> Dict[str, Any]:
        """Apply Bonferroni correction
        
        Args:
            p_values: List of p-values
            alpha: Significance level
            
        Returns:
            Dictionary with corrected results
        """
        p_values = np.asarray(p_values)
        adjusted = np.minimum(p_values * len(p_values), 1)
        
        return {
            'p_original': p_values,
            'p_adjusted': adjusted,
            'significant': adjusted < alpha,
            'alpha': alpha,
            'n_tests': len(p_values),
            'method': 'Bonferroni'
        }
    
    @staticmethod
    def fdr_correction(p_values: Union[List[float], np.ndarray, pd.Series],
                      alpha: float = 0.05) -> Dict[str, Any]:
        """Apply False Discovery Rate (FDR) correction
        
        Args:
            p_values: List of p-values
            alpha: Significance level
            
        Returns:
            Dictionary with corrected results
        """
        p_values = np.asarray(p_values)
        reject, adjusted, _, _ = multipletests(p_values, alpha=alpha, method='fdr_bh')
        
        return {
            'p_original': p_values,
            'p_adjusted': adjusted,
            'significant': reject,
            'alpha': alpha,
            'n_tests': len(p_values),
            'method': 'FDR (Benjamini-Hochberg)'
        }
    
    @staticmethod
    def tukey_hsd(groups: List[pd.Series]) -> pd.DataFrame:
        """Perform Tukey HSD post-hoc test
        
        Args:
            groups: List of group Series
            
        Returns:
            DataFrame with pairwise comparisons
        """
        from scipy.stats import tukey_hsd
        
        # Concatenate all groups
        all_data = []
        group_labels = []
        
        for i, group in enumerate(groups):
            all_data.extend(group.dropna().values)
            group_labels.extend([i] * len(group.dropna()))
        
        # Perform Tukey HSD
        result = tukey_hsd(*groups)
        
        return {
            'statistic': result.statistic,
            'pvalue': result.pvalue,
            'comparison_table': result.pvalue
        }
