"""
Example 3: Novelty Detection and Research Gap Analysis

Demonstrates how to use the NoveltyDetector module for research analysis.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.nlp import NoveltyDetector, KeywordExtractor, TextAnalyzer

def example_novelty_detection():
    """Example: Detect research novelty"""
    print("=" * 60)
    print("Example 1: Research Novelty Detection")
    print("=" * 60)
    
    # Sample research corpus
    corpus = [
        "Treatment of hypertension using ACE inhibitors in adults",
        "Blood pressure management with calcium channel blockers",
        "Cardiovascular risk reduction through lifestyle modifications",
        "Comparative efficacy of antihypertensive medications"
    ]
    
    # New research query
    new_research = "Novel endothelin receptor antagonist therapy for resistant hypertension in diabetic patients"
    
    novelty_detector = NoveltyDetector()
    
    # Detect novelty
    gap_analysis = novelty_detector.detect_research_gaps(corpus, new_research, threshold=0.3)
    
    print(f"\\nNew Research: {new_research}")
    print(f"\\nGap Analysis Results:")
    print(f"  Gap Score: {gap_analysis['gap_score']:.4f}")
    print(f"  Is Novel: {gap_analysis['is_novel']}")
    print(f"  Max Similarity: {gap_analysis['max_similarity']:.4f}")
    print(f"  Similar Studies Found: {gap_analysis['similar_count']}")

def example_similar_research():
    """Example: Find similar research"""
    print("\\n" + "=" * 60)
    print("Example 2: Find Similar Research")
    print("=" * 60)
    
    corpus = [
        "RCT of statin therapy in primary prevention",
        "Lipid management guidelines for cardiovascular disease",
        "Genetic factors in cholesterol metabolism",
        "Long-term outcomes of intensive lipid lowering"
    ]
    
    query = "Efficacy of high-dose statins in cholesterol reduction"
    
    novelty_detector = NoveltyDetector()
    similar = novelty_detector.find_similar_research(query, corpus, threshold=0.4)
    
    print(f"\\nSearch Query: {query}")
    print(f"\\nSimilar Research Found: {len(similar)}")
    
    for i, result in enumerate(similar, 1):
        print(f"\\n  {i}. Similarity: {result['similarity']:.4f}")
        print(f"     Text: {result['text']}")

def example_keyword_extraction():
    """Example: Extract keywords from medical text"""
    print("\\n" + "=" * 60)
    print("Example 3: Keyword Extraction")
    print("=" * 60)
    
    medical_text = """
    This randomized controlled trial examined the efficacy of novel antihypertensive therapy
    in patients with resistant hypertension. The study included 200 patients with systolic
    blood pressure exceeding 160 mmHg despite treatment with three or more antihypertensive
    medications. Primary endpoints included reduction in systolic blood pressure and adverse
    events. Secondary endpoints included quality of life and medication adherence.
    """
    
    extractor = KeywordExtractor()
    
    # Extract keywords
    keywords = extractor.extract_keywords(medical_text, top_n=8)
    medical_terms = extractor.extract_medical_terms(medical_text)
    
    print(f"\\nExtracted Keywords:")
    for i, (keyword, freq) in enumerate(keywords, 1):
        print(f"  {i}. {keyword}: {freq} occurrences")
    
    print(f"\\nMedical Terms Found: {', '.join(medical_terms)}")

def example_readability_analysis():
    """Example: Analyze text readability"""
    print("\\n" + "=" * 60)
    print("Example 4: Text Readability Analysis")
    print("=" * 60)
    
    abstract = """
    Background: Hypertension is a major risk factor for cardiovascular disease.
    Objective: To evaluate the efficacy of a novel antihypertensive medication.
    Methods: Randomized, double-blind, placebo-controlled trial with 200 participants.
    Results: The treatment group showed significant blood pressure reduction.
    Conclusion: Novel therapy demonstrates superior efficacy in blood pressure management.
    """
    
    analyzer = TextAnalyzer()
    metrics = analyzer.readability_metrics(abstract)
    
    print(f"\\nText Readability Metrics:")
    print(f"  Word Count: {metrics['word_count']}")
    print(f"  Sentence Count: {metrics['sentence_count']}")
    print(f"  Avg Sentence Length: {metrics['avg_sentence_length']:.2f} words")
    print(f"  Avg Word Length: {metrics['avg_word_length']:.2f} characters")
    print(f"  Flesch-Kincaid Grade Level: {metrics['flesch_kincaid_grade']:.2f}")

if __name__ == '__main__':
    example_novelty_detection()
    example_similar_research()
    example_keyword_extraction()
    example_readability_analysis()
    print("\\n" + "=" * 60)
    print("Examples completed successfully!")
    print("=" * 60)
