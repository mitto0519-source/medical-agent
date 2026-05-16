"""Medical Agent package — lazy imports to avoid dependency conflicts."""


def __getattr__(name):
    if name in ("MedicalStatistics", "SurvivalAnalysis"):
        from .statistics import MedicalStatistics, SurvivalAnalysis
        return locals()[name]
    if name == "MedicalVisualizer":
        from .visualization import MedicalVisualizer
        return MedicalVisualizer
    if name in ("MedicalDatabase", "DataCleaner"):
        from .database import MedicalDatabase, DataCleaner
        return locals()[name]
    if name in ("NoveltyDetector", "KeywordExtractor", "TextAnalyzer"):
        from .nlp import NoveltyDetector, KeywordExtractor, TextAnalyzer
        return locals()[name]
    if name in ("ManuscriptGenerator", "CitationFormatter"):
        from .papergen import ManuscriptGenerator, CitationFormatter
        return locals()[name]
    raise AttributeError(f"module 'src' has no attribute {name!r}")
