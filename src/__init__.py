"""Medical Agent package — lazy imports to avoid dependency conflicts."""


def __getattr__(name):
    if name in ("MedicalStatistics", "SurvivalAnalysis"):
        from .statistics import MedicalStatistics, SurvivalAnalysis
        return locals()[name]
    if name == "MedicalVisualizer":
        from .visualization import MedicalVisualizer
        return MedicalVisualizer
    raise AttributeError(f"module 'src' has no attribute {name!r}")
