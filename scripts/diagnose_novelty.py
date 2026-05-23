from pathlib import Path
import sys, traceback
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.research.novelty_checker import NoveltyChecker


def run():
    nc = NoveltyChecker()
    inputs = {
        "topic": "Test topic",
        "exposure": "smoking",
        "outcome": "asthma",
        "population": "",
    }
    print("Inputs types:")
    for k, v in inputs.items():
        print(f" - {k}: {type(v)}")
    try:
        res = nc.check(**inputs)
        print("Result:")
        print(res)
    except Exception as e:
        print("Exception raised:", repr(e))
        traceback.print_exc()


if __name__ == '__main__':
    run()
