"""
Example 2: Data Management and Cleaning

Demonstrates how to use the MedicalDatabase and DataCleaner modules.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import numpy as np
from src.database import MedicalDatabase, DataCleaner

def example_data_cleaning():
    """Example: Clean and prepare medical data"""
    print("=" * 60)
    print("Example 1: Data Cleaning")
    print("=" * 60)
    
    # Create sample data with missing values and outliers
    np.random.seed(42)
    n = 100
    
    data = {
        'patient_id': range(1, n+1),
        'age': np.random.normal(55, 15, n),
        'blood_pressure': np.random.normal(130, 15, n),
        'cholesterol': np.random.normal(200, 40, n)
    }
    
    df = pd.DataFrame(data)
    
    # Add some missing values
    df.loc[np.random.choice(df.index, 5), 'blood_pressure'] = np.nan
    df.loc[np.random.choice(df.index, 3), 'cholesterol'] = np.nan
    
    print(f"\\nOriginal data shape: {df.shape}")
    print(f"Missing values:\\n{df.isnull().sum()}")
    
    # Clean data
    cleaner = DataCleaner()
    df_clean = cleaner.handle_missing_values(df, strategy='mean')
    
    print(f"\\nCleaned data shape: {df_clean.shape}")
    print(f"Missing values after cleaning:\\n{df_clean.isnull().sum()}")

def example_outlier_detection():
    """Example: Detect outliers"""
    print("\\n" + "=" * 60)
    print("Example 2: Outlier Detection")
    print("=" * 60)
    
    # Create data with outliers
    data = {
        'cholesterol': [200, 210, 205, 215, 500, 220, 210, 205]  # 500 is outlier
    }
    df = pd.DataFrame(data)
    
    cleaner = DataCleaner()
    
    # Detect outliers using IQR method
    outliers_iqr = cleaner.detect_outliers(df, method='iqr', threshold=1.5)
    
    # Detect outliers using z-score
    outliers_zscore = cleaner.detect_outliers(df, method='zscore', threshold=3)
    
    print(f"\\nData: {list(df['cholesterol'])}")
    print(f"\\nOutliers (IQR method): {outliers_iqr['cholesterol'].sum()} found")
    print(f"Outliers (Z-score method): {outliers_zscore['cholesterol'].sum()} found")

def example_database_operations():
    """Example: Database operations"""
    print("\\n" + "=" * 60)
    print("Example 3: Database Operations")
    print("=" * 60)
    
    # Create in-memory database for demo
    db = MedicalDatabase(':memory:')
    
    # Create table
    columns = {
        'patient_id': 'INTEGER PRIMARY KEY',
        'age': 'INTEGER',
        'blood_pressure': 'REAL',
        'outcome': 'TEXT'
    }
    db.create_table('patients', columns)
    
    # Insert sample data
    data = pd.DataFrame({
        'patient_id': [1, 2, 3, 4, 5],
        'age': [45, 52, 58, 35, 62],
        'blood_pressure': [140, 150, 160, 130, 170],
        'outcome': ['Improved', 'Stable', 'Improved', 'Declined', 'Improved']
    })
    
    db.insert_data('patients', data)
    
    # Query data
    result = db.query("SELECT * FROM patients WHERE age > 50")
    
    print(f"\\nInserted {len(data)} patients into database")
    print(f"\\nPatients over 50 years old:")
    print(result.to_string(index=False))
    
    # Close database
    db.close()

if __name__ == '__main__':
    example_data_cleaning()
    example_outlier_detection()
    example_database_operations()
    print("\\n" + "=" * 60)
    print("Examples completed successfully!")
    print("=" * 60)
