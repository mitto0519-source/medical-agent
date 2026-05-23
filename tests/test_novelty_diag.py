import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def test_novelty_checker_runs():
    from src.research.novelty_checker import NoveltyChecker

    nc = NoveltyChecker()
    # minimal inputs to mimic Streamlit call
    kwargs = {
        "topic": "Test topic",
        "exposure": "smoking",
        "outcome": "asthma",
        "population": "",
    }
    res = nc.check(**kwargs)
    assert isinstance(res, dict), f"Expected dict result, got {type(res)}"
