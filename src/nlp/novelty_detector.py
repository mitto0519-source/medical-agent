"""NLP module for research gap and novelty detection"""

from sentence_transformers import SentenceTransformer, util
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from collections import Counter
import re


class NoveltyDetector:
    """Detect research novelty and gaps using embeddings"""
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """Initialize with pre-trained sentence transformer
        
        Args:
            model_name: HuggingFace model name
        """
        self.model = SentenceTransformer(model_name)
    
    def find_similar_research(self, query: str, corpus: List[str],
                            threshold: float = 0.5) -> List[Dict]:
        """Find similar research papers/abstracts
        
        Args:
            query: Research query or abstract
            corpus: List of existing research papers/abstracts
            threshold: Similarity threshold (0-1)
            
        Returns:
            List of similar papers with similarity scores
        """
        query_embedding = self.model.encode(query, convert_to_tensor=True)
        corpus_embeddings = self.model.encode(corpus, convert_to_tensor=True)
        
        cos_scores = util.pytorch_cos_sim(query_embedding, corpus_embeddings)[0]
        
        results = []
        for idx, score in enumerate(cos_scores):
            if score >= threshold:
                results.append({
                    'index': idx,
                    'text': corpus[idx],
                    'similarity': float(score)
                })
        
        return sorted(results, key=lambda x: x['similarity'], reverse=True)
    
    def detect_research_gaps(self, existing_research: List[str],
                           new_research: str, threshold: float = 0.3) -> Dict:
        """Detect potential research gaps
        
        Args:
            existing_research: List of existing research
            new_research: New research to compare
            threshold: Difference threshold for gaps
            
        Returns:
            Dictionary with gap analysis
        """
        new_embedding = self.model.encode(new_research, convert_to_tensor=True)
        existing_embeddings = self.model.encode(existing_research, convert_to_tensor=True)
        
        similarities = util.pytorch_cos_sim(new_embedding, existing_embeddings)[0]
        
        max_similarity = float(max(similarities))
        gap_score = 1 - max_similarity
        
        is_novel = gap_score >= threshold
        
        return {
            'gap_score': gap_score,
            'is_novel': is_novel,
            'max_similarity': max_similarity,
            'similar_count': int((similarities >= (1 - threshold)).sum())
        }


class KeywordExtractor:
    """Extract key concepts from medical texts"""
    
    @staticmethod
    def extract_keywords(text: str, top_n: int = 10) -> List[Tuple[str, int]]:
        """Extract frequent keywords
        
        Args:
            text: Input text
            top_n: Number of top keywords
            
        Returns:
            List of (keyword, frequency) tuples
        """
        # Simple tokenization and filtering
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())
        
        # Remove common stop words
        stop_words = {'the', 'and', 'for', 'with', 'from', 'are', 'was', 'is', 'or', 'an'}
        words = [w for w in words if w not in stop_words]
        
        freq = Counter(words)
        return freq.most_common(top_n)
    
    @staticmethod
    def extract_medical_terms(text: str) -> List[str]:
        """Extract medical terminology (case-insensitive)
        
        Args:
            text: Input text
            
        Returns:
            List of detected medical terms
        """
        # Common medical term patterns
        patterns = [
            r'\b[a-z]*itis\b',  # inflammation
            r'\b[a-z]*oma\b',   # tumor
            r'\b[a-z]*osis\b',  # condition
            r'\b[A-Z]{2,}\b'     # acronyms
        ]
        
        terms = []
        for pattern in patterns:
            terms.extend(re.findall(pattern, text, re.IGNORECASE))
        
        return list(set(terms))


class TextAnalyzer:
    """Analyze text characteristics and metrics"""
    
    @staticmethod
    def readability_metrics(text: str) -> Dict:
        """Calculate text readability metrics
        
        Args:
            text: Input text
            
        Returns:
            Dictionary with readability metrics
        """
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        words = text.split()
        characters = len(text)
        
        avg_sentence_length = len(words) / len(sentences) if sentences else 0
        avg_word_length = characters / len(words) if words else 0
        
        return {
            'word_count': len(words),
            'sentence_count': len(sentences),
            'character_count': characters,
            'avg_sentence_length': avg_sentence_length,
            'avg_word_length': avg_word_length,
            'flesch_kincaid_grade': max(0, 0.39 * avg_sentence_length + 11.8 * avg_word_length - 15.59)
        }
