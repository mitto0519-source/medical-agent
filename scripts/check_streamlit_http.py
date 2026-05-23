import requests

try:
    r = requests.get('http://localhost:8501', timeout=10)
    print('STATUS', r.status_code)
    print(r.text[:800])
except Exception as e:
    print('ERROR', repr(e))
