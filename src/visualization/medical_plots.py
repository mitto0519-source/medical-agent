"""Visualization module for medical research"""

import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from typing import Optional, List


class MedicalVisualizer:
    """Create publication-ready medical visualizations"""
    
    def __init__(self, style: str = 'whitegrid', font_scale: float = 1.2):
        """Initialize visualizer with style settings"""
        sns.set_style(style)
        sns.set_context("paper", font_scale=font_scale)
        plt.rcParams['figure.dpi'] = 300
        plt.rcParams['savefig.dpi'] = 300
    
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
