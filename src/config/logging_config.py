import logging

def setup_logging(level=logging.INFO):
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler()
    fmt = '%(asctime)s %(levelname)s [%(name)s] %(message)s'
    handler.setFormatter(logging.Formatter(fmt))
    root.addHandler(handler)
    root.setLevel(level)
