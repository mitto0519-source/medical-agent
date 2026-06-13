"""Application configuration"""

import os
# RULE: 단일 .env 로드 — src.config.env.bootstrap()가 entry point에서 처리.
# 여기서 직접 load_dotenv() 호출 제거 (override 충돌 + RULE-5 위반).
from src.config.env import bootstrap
bootstrap()

class Config:
    """Base configuration"""
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    
    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', '../data/medical_research.db')
    
    # Model settings
    SENTENCE_MODEL = os.getenv('SENTENCE_MODEL', 'all-MiniLM-L6-v2')
    
    # API settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    DATABASE_PATH = ':memory:'

# Select config based on environment
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

current_config = config.get(os.getenv('FLASK_ENV', 'development'))
