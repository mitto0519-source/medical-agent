import sys, os

_dir = os.path.dirname(os.path.abspath(__file__))
_app = os.path.join(_dir, "app", "streamlit_app.py")
os.chdir(_dir)
sys.path.insert(0, _dir)

with open(_app) as _f:
    exec(compile(_f.read(), _app, "exec"), {"__file__": _app, "__name__": "__main__"})
