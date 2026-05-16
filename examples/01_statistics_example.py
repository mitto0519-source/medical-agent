"""
Example 1: Medical Statistics Analysis

Demonstrates how to use the MedicalStatistics module for common statistical tests.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import numpy as np
from src.statistics import MedicalStatistics

def example_basic_statistics():
    """Example: Calculate descriptive statistics"""
    print("=" * 60)
    print("Example 1: Descriptive Statistics")
    print("=" * 60)
    
    # Create sample data
    data = pd.Series([120, 125, 130, 128, 135, 132, 140, 138])
    
    med_stats = MedicalStatistics()
    stats_result = med_stats.descriptive_stats(data)
    
    print("\\nBlood Pressure Measurements (mmHg):", list(data))
    print("\\nDescriptive Statistics:")
    for key, value in stats_result.items():
        print(f"  {key}: {value:.2f}")

def example_t_test():
    """Example: Independent samples t-test"""
    print("\\n" + "=" * 60)
    print("Example 2: T-Test Comparison")
    print("=" * 60)
    
    # Control group blood pressure
    control = pd.Series(np.random.normal(140, 10, 50))
    # Treatment group blood pressure
    treatment = pd.Series(np.random.normal(130, 10, 50))
    
    med_stats = MedicalStatistics()
    result = med_stats.t_test(control, treatment)
    
    print(f"\\nControl group mean: {control.mean():.2f} mmHg")
    print(f"Treatment group mean: {treatment.mean():.2f} mmHg")
    print(f"\\nt-statistic: {result['t_statistic']:.4f}")
    print(f"p-value: {result['p_value']:.4f}")
    print(f"Cohen's d: {result['cohens_d']:.4f}")
    print(f"Significant (p < 0.05): {result['significant']}")

def example_correlation():
    """Example: Calculate correlation"""
    print("\\n" + "=" * 60)
    print("Example 3: Correlation Analysis")
    print("=" * 60)
    
    # Age and cholesterol data
    age = pd.Series([45, 52, 58, 35, 62, 48, 55, 70, 40, 60])
    cholesterol = pd.Series([200, 220, 240, 180, 260, 210, 230, 270, 190, 250])
    
    med_stats = MedicalStatistics()
    
    # Pearson correlation
    pearson = med_stats.correlation(age, cholesterol, method='pearson')
    print(f"\\nPearson Correlation:")
    print(f"  Coefficient: {pearson['correlation']:.4f}")
    print(f"  p-value: {pearson['p_value']:.4f}")
    
    # Spearman correlation
    spearman = med_stats.correlation(age, cholesterol, method='spearman')
    print(f"\\nSpearman Correlation:")
    print(f"  Coefficient: {spearman['correlation']:.4f}")
    print(f"  p-value: {spearman['p_value']:.4f}")

if __name__ == '__main__':
    example_basic_statistics()
    example_t_test()
    example_correlation()
    print("\\n" + "=" * 60)
    print("Examples completed successfully!")
    print("=" * 60)
