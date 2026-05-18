"""Visualization module for medical research"""

import io
import os
from pathlib import Path
from typing import Optional, List, Union

import matplotlib
# Streamlit sets its own backend; Jupyter sets its own.
# Only force Agg when there is truly no display (CI/server without DISPLAY).
import os as _os
if not _os.environ.get("DISPLAY", "") and _os.name != "nt":
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

_FIGURE_DIR = Path("data/figures")


class MedicalVisualizer:
    """Create publication-ready medical visualizations.

    Static figure methods return matplotlib Figure objects.
    Use save_figure() or figure_bytes() to persist/display them.
    """

    def __init__(self, style: str = "whitegrid", font_scale: float = 1.2):
        sns.set_style(style)
        sns.set_context("paper", font_scale=font_scale)
        plt.rcParams["figure.dpi"] = 300
        plt.rcParams["savefig.dpi"] = 300

    # ── Persistence helpers ───────────────────────────────────────────────────

    @staticmethod
    def save_figure(
        fig: plt.Figure,
        filename: str,
        output_dir: Union[str, Path] = _FIGURE_DIR,
        fmt: str = "jpg",
        dpi: int = 300,
    ) -> Path:
        """Save a matplotlib figure to disk.

        Returns the saved file path.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        if not filename.endswith(f".{fmt}"):
            filename = f"{filename}.{fmt}"
        path = out / filename
        fig.savefig(path, format=fmt, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return path

    @staticmethod
    def figure_bytes(
        fig: plt.Figure,
        fmt: str = "png",
        dpi: int = 150,
    ) -> bytes:
        """Return figure as raw bytes for st.image() or download."""
        buf = io.BytesIO()
        fig.savefig(buf, format=fmt, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()

    # ── Auto figure for each analysis type ───────────────────────────────────

    @staticmethod
    def auto_figure(analysis_type: str, df: pd.DataFrame, result=None, **kwargs) -> Optional[plt.Figure]:
        """Generate the most appropriate figure for a given analysis type.

        analysis_type: 'descriptive' | 'ttest' | 'chi2' | 'anova'
                       | 'correlation' | 'logistic' | 'linear'
        Returns matplotlib Figure or None if not applicable.
        """
        try:
            if analysis_type == "descriptive":
                cols = kwargs.get("cols", list(df.select_dtypes(include="number").columns)[:6])
                numeric = df[cols].select_dtypes(include="number")
                if numeric.empty:
                    return None
                n = len(numeric.columns)
                ncols = min(3, n)
                nrows = (n + ncols - 1) // ncols
                fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows))
                axes = [axes] if n == 1 else list(np.array(axes).flatten())
                for ax, col in zip(axes, numeric.columns):
                    sns.histplot(numeric[col].dropna(), kde=True, ax=ax, color="steelblue")
                    ax.set_title(col, fontsize=11)
                    ax.set_xlabel("")
                for ax in axes[n:]:
                    ax.set_visible(False)
                fig.suptitle("Distribution Overview", fontsize=13, fontweight="bold", y=1.01)
                fig.tight_layout()
                return fig

            elif analysis_type == "ttest":
                val_col = kwargs.get("val_col")
                grp_col = kwargs.get("grp_col")
                if not val_col or not grp_col:
                    return None
                fig, ax = plt.subplots(figsize=(7, 5))
                groups = df[grp_col].dropna().unique()[:2]
                data_plot = df[df[grp_col].isin(groups)][[val_col, grp_col]].dropna()
                sns.boxplot(data=data_plot, x=grp_col, y=val_col, hue=grp_col,
                            ax=ax, palette="Set2", width=0.5, legend=False)
                sns.stripplot(data=data_plot, x=grp_col, y=val_col, ax=ax,
                              color="black", alpha=0.3, size=3, jitter=True)
                p = (result or {}).get("p_value", None)
                if p is not None:
                    sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
                    y_max = data_plot[val_col].max()
                    y_range = data_plot[val_col].max() - data_plot[val_col].min()
                    ax.plot([0, 1], [y_max + y_range * 0.05, y_max + y_range * 0.05], "k-", lw=1.5)
                    ax.text(0.5, y_max + y_range * 0.08, f"p={p:.3f} {sig}",
                            ha="center", va="bottom", fontsize=11)
                ax.set_title(f"{val_col} by {grp_col}", fontsize=13, fontweight="bold")
                ax.set_xlabel(grp_col)
                ax.set_ylabel(val_col)
                fig.tight_layout()
                return fig

            elif analysis_type == "chi2":
                var1 = kwargs.get("var1")
                var2 = kwargs.get("var2")
                if not var1 or not var2:
                    return None
                ct = pd.crosstab(df[var1], df[var2], normalize="index") * 100
                fig, ax = plt.subplots(figsize=(max(7, len(ct.columns) * 1.5), 5))
                ct.plot(kind="bar", ax=ax, colormap="Set2", edgecolor="white", width=0.7)
                ax.set_title(f"{var1} × {var2} (%)", fontsize=13, fontweight="bold")
                ax.set_xlabel(var1)
                ax.set_ylabel("Percentage (%)")
                ax.legend(title=var2, bbox_to_anchor=(1.01, 1), loc="upper left")
                ax.tick_params(axis="x", rotation=45)
                fig.tight_layout()
                return fig

            elif analysis_type == "anova":
                val_col = kwargs.get("val_col")
                grp_col = kwargs.get("grp_col")
                if not val_col or not grp_col:
                    return None
                fig, ax = plt.subplots(figsize=(max(7, df[grp_col].nunique() * 1.2), 5))
                order = df.groupby(grp_col)[val_col].median().sort_values().index
                sns.boxplot(data=df, x=grp_col, y=val_col, hue=grp_col, order=order,
                            ax=ax, palette="Set3", width=0.6, legend=False)
                p = (result or {}).get("p_value", None)
                if p is not None:
                    sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
                    ax.set_title(f"{val_col} by {grp_col}  (p={p:.3f} {sig})",
                                 fontsize=13, fontweight="bold")
                else:
                    ax.set_title(f"{val_col} by {grp_col}", fontsize=13, fontweight="bold")
                ax.set_xlabel(grp_col)
                ax.set_ylabel(val_col)
                ax.tick_params(axis="x", rotation=45)
                fig.tight_layout()
                return fig

            elif analysis_type == "correlation":
                cols = kwargs.get("cols", list(df.select_dtypes(include="number").columns))
                numeric = df[cols].select_dtypes(include="number")
                if len(numeric.columns) < 2:
                    return None
                corr = numeric.corr()
                fig, ax = plt.subplots(figsize=(max(6, len(corr) * 0.9), max(5, len(corr) * 0.8)))
                mask = np.triu(np.ones_like(corr, dtype=bool))
                sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdYlBu_r", center=0,
                            square=True, ax=ax, mask=mask,
                            linewidths=0.5, cbar_kws={"label": "Pearson r"})
                ax.set_title("Correlation Matrix", fontsize=13, fontweight="bold")
                fig.tight_layout()
                return fig

            elif analysis_type == "logistic":
                # Forest plot — OR + 95% CI
                if result is None or not hasattr(result, "iterrows"):
                    return None
                res = result.copy()
                if "OR" not in res.columns:
                    return None
                res = res.dropna(subset=["OR"])
                fig, ax = plt.subplots(figsize=(8, max(4, len(res) * 0.5 + 1)))
                y_pos = range(len(res))
                ax.errorbar(
                    res["OR"], y_pos,
                    xerr=[res["OR"] - res.get("CI_lower", res["OR"]),
                          res.get("CI_upper", res["OR"]) - res["OR"]],
                    fmt="o", color="steelblue", ecolor="gray",
                    capsize=4, markersize=7, linewidth=1.5,
                )
                ax.axvline(1, color="red", linestyle="--", linewidth=1, alpha=0.7)
                ax.set_yticks(list(y_pos))
                ax.set_yticklabels(res.index.tolist() if res.index.dtype == object
                                   else res.get("variable", res.index).tolist())
                ax.set_xlabel("Odds Ratio (95% CI)", fontsize=11)
                ax.set_title("Logistic Regression — Forest Plot", fontsize=13, fontweight="bold")
                ax.grid(True, axis="x", alpha=0.3)
                fig.tight_layout()
                return fig

            elif analysis_type == "linear":
                outcome = kwargs.get("outcome")
                predictors = kwargs.get("predictors", [])
                if not outcome or not predictors:
                    return None
                pred = predictors[0]
                fig, axes = plt.subplots(1, 2, figsize=(12, 5))
                # Scatter + regression line
                x_data = pd.to_numeric(df[pred], errors="coerce").dropna()
                y_data = pd.to_numeric(df[outcome], errors="coerce").reindex(x_data.index).dropna()
                x_data = x_data.reindex(y_data.index)
                if len(x_data) > 1:
                    axes[0].scatter(x_data, y_data, alpha=0.4, s=20, color="steelblue")
                    z = np.polyfit(x_data, y_data, 1)
                    p = np.poly1d(z)
                    xs = np.linspace(x_data.min(), x_data.max(), 200)
                    axes[0].plot(xs, p(xs), "r-", linewidth=2)
                    axes[0].set_xlabel(pred)
                    axes[0].set_ylabel(outcome)
                    axes[0].set_title(f"{outcome} ~ {pred}", fontsize=11, fontweight="bold")
                    axes[0].grid(True, alpha=0.3)
                    # Residual plot
                    y_pred = p(x_data)
                    residuals = y_data - y_pred
                    axes[1].scatter(y_pred, residuals, alpha=0.4, s=20, color="coral")
                    axes[1].axhline(0, color="black", linewidth=1, linestyle="--")
                    axes[1].set_xlabel("Fitted values")
                    axes[1].set_ylabel("Residuals")
                    axes[1].set_title("Residual Plot", fontsize=11, fontweight="bold")
                    axes[1].grid(True, alpha=0.3)
                fig.suptitle("Linear Regression", fontsize=13, fontweight="bold")
                fig.tight_layout()
                return fig

        except Exception:
            return None

        return None
    
    @staticmethod
    def survival_curve(kmf_dict: dict, title: str = "Kaplan-Meier Survival Curve"):
        """Plot Kaplan-Meier survival curve"""
        fig, ax = plt.subplots(figsize=(10, 6))
        kmf = kmf_dict['kmf']
        kmf.plot_survival_function(ax=ax, ci_show=True)
        
        ax.set_xlabel('Time (days)', fontsize=12)
        ax.set_ylabel('Survival Probability', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        return fig
    
    @staticmethod
    def distribution_plot(data: pd.Series, title: str = "Distribution", bins: int = 30):
        """Create distribution plot with KDE"""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        sns.histplot(data=data, kde=True, bins=bins, ax=ax, color='steelblue')
        ax.set_xlabel('Value', fontsize=12)
        ax.set_ylabel('Frequency', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        
        return fig
    
    @staticmethod
    def box_plot(data: pd.DataFrame, y: str, x: Optional[str] = None, title: str = "Box Plot"):
        """Create box plot for comparisons"""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        sns.boxplot(data=data, y=y, x=x, ax=ax, palette='Set2')
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        
        return fig
    
    @staticmethod
    def violin_plot(data: pd.DataFrame, y: str, x: Optional[str] = None, title: str = "Violin Plot"):
        """Create violin plot"""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        sns.violinplot(data=data, y=y, x=x, ax=ax, palette='Set2')
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        
        return fig
    
    @staticmethod
    def heatmap(data: pd.DataFrame, title: str = "Heatmap", cmap: str = 'RdYlBu_r'):
        """Create correlation heatmap"""
        fig, ax = plt.subplots(figsize=(10, 8))
        
        sns.heatmap(data, annot=True, fmt='.2f', cmap=cmap, center=0,
                    square=True, ax=ax, cbar_kws={'label': 'Correlation'})
        ax.set_title(title, fontsize=14, fontweight='bold')
        
        return fig
    
    @staticmethod
    def scatter_with_trend(x: pd.Series, y: pd.Series, title: str = "Scatter Plot"):
        """Create scatter plot with trend line"""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        ax.scatter(x, y, alpha=0.6, s=50, color='steelblue')
        
        # Add trend line
        z = np.polyfit(x.dropna(), y.dropna(), 1)
        p = np.poly1d(z)
        ax.plot(x.sort_values(), p(x.sort_values()), "r--", alpha=0.8, linewidth=2)
        
        ax.set_xlabel('X', fontsize=12)
        ax.set_ylabel('Y', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        return fig
    
    @staticmethod
    def interactive_scatter(data: pd.DataFrame, x: str, y: str, color: Optional[str] = None,
                          title: str = "Interactive Scatter Plot"):
        """Create interactive scatter plot with Plotly"""
        fig = px.scatter(data, x=x, y=y, color=color, title=title,
                        labels={x: x, y: y},
                        height=600, width=900)
        
        fig.update_layout(
            font=dict(size=12),
            title_font_size=16,
            hovermode='closest'
        )
        
        return fig
    
    @staticmethod
    def interactive_box(data: pd.DataFrame, y: str, x: Optional[str] = None,
                       title: str = "Interactive Box Plot"):
        """Create interactive box plot"""
        fig = px.box(data, y=y, x=x, title=title, height=600, width=900)
        
        fig.update_layout(
            font=dict(size=12),
            title_font_size=16
        )
        
        return fig
