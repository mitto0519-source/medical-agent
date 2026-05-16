"""Database management for medical research data"""

import sqlite3
import pandas as pd
from typing import List, Dict, Any, Optional
import os


class MedicalDatabase:
    """SQLite database manager for medical research data"""
    
    def __init__(self, db_path: str = 'medical_research.db'):
        """Initialize database connection"""
        self.db_path = db_path
        self.connection = None
        self.connect()
    
    def connect(self):
        """Connect to database"""
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
    
    def create_table(self, table_name: str, columns: Dict[str, str]):
        """Create a new table
        
        Args:
            table_name: Name of the table
            columns: Dict mapping column names to SQL types
        """
        cursor = self.connection.cursor()
        col_defs = ', '.join([f"{name} {sql_type}" for name, sql_type in columns.items()])
        cursor.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({col_defs})")
        self.connection.commit()
    
    def insert_data(self, table_name: str, data: pd.DataFrame):
        """Insert data from DataFrame"""
        data.to_sql(table_name, self.connection, if_exists='append', index=False)
    
    def query(self, sql: str) -> pd.DataFrame:
        """Execute query and return DataFrame"""
        return pd.read_sql_query(sql, self.connection)
    
    def get_table(self, table_name: str) -> pd.DataFrame:
        """Get entire table as DataFrame"""
        return pd.read_sql_query(f"SELECT * FROM {table_name}", self.connection)
    
    def update(self, table_name: str, set_clause: str, where_clause: str):
        """Update records"""
        cursor = self.connection.cursor()
        cursor.execute(f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}")
        self.connection.commit()
    
    def delete(self, table_name: str, where_clause: str):
        """Delete records"""
        cursor = self.connection.cursor()
        cursor.execute(f"DELETE FROM {table_name} WHERE {where_clause}")
        self.connection.commit()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class DataCleaner:
    """Data cleaning utilities for medical research"""
    
    @staticmethod
    def handle_missing_values(df: pd.DataFrame, strategy: str = 'mean',
                             threshold: float = 0.5) -> pd.DataFrame:
        """Handle missing values
        
        Args:
            df: Input DataFrame
            strategy: 'mean', 'median', 'forward_fill', 'backward_fill', 'drop'
            threshold: Drop columns with missing > threshold
            
        Returns:
            Cleaned DataFrame
        """
        df_clean = df.copy()
        
        # Drop columns with too many missing values
        missing_ratio = df_clean.isnull().sum() / len(df_clean)
        cols_to_drop = missing_ratio[missing_ratio > threshold].index
        df_clean = df_clean.drop(columns=cols_to_drop)
        
        # Handle remaining missing values
        if strategy == 'mean':
            numeric_cols = df_clean.select_dtypes(include=['number']).columns
            df_clean[numeric_cols] = df_clean[numeric_cols].fillna(df_clean[numeric_cols].mean())
        elif strategy == 'median':
            numeric_cols = df_clean.select_dtypes(include=['number']).columns
            df_clean[numeric_cols] = df_clean[numeric_cols].fillna(df_clean[numeric_cols].median())
        elif strategy == 'forward_fill':
            df_clean = df_clean.ffill()
        elif strategy == 'backward_fill':
            df_clean = df_clean.bfill()
        elif strategy == 'drop':
            df_clean = df_clean.dropna()
        
        return df_clean
    
    @staticmethod
    def detect_outliers(df: pd.DataFrame, method: str = 'iqr', threshold: float = 1.5) -> pd.DataFrame:
        """Detect outliers in numeric columns
        
        Args:
            df: Input DataFrame
            method: 'iqr' or 'zscore'
            threshold: IQR multiplier (1.5) or z-score threshold (3)
            
        Returns:
            Boolean DataFrame indicating outliers
        """
        numeric_cols = df.select_dtypes(include=['number']).columns
        outliers = pd.DataFrame(False, index=df.index, columns=numeric_cols)
        
        if method == 'iqr':
            Q1 = df[numeric_cols].quantile(0.25)
            Q3 = df[numeric_cols].quantile(0.75)
            IQR = Q3 - Q1
            outliers = ((df[numeric_cols] < (Q1 - threshold * IQR)) |
                       (df[numeric_cols] > (Q3 + threshold * IQR)))
        elif method == 'zscore':
            from scipy.stats import zscore
            outliers = (df[numeric_cols].apply(zscore).abs() > threshold)
        
        return outliers
    
    @staticmethod
    def normalize(df: pd.DataFrame, method: str = 'minmax') -> pd.DataFrame:
        """Normalize numeric columns
        
        Args:
            df: Input DataFrame
            method: 'minmax' or 'zscore'
            
        Returns:
            Normalized DataFrame
        """
        df_norm = df.copy()
        numeric_cols = df_norm.select_dtypes(include=['number']).columns
        
        if method == 'minmax':
            df_norm[numeric_cols] = (df_norm[numeric_cols] - df_norm[numeric_cols].min()) / (
                df_norm[numeric_cols].max() - df_norm[numeric_cols].min())
        elif method == 'zscore':
            df_norm[numeric_cols] = (df_norm[numeric_cols] - df_norm[numeric_cols].mean()) / df_norm[numeric_cols].std()
        
        return df_norm
