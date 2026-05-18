import sys; sys.stdout.reconfigure(encoding='utf-8')
from src.config.env import bootstrap; bootstrap()
from src.config.models import thinking_config, _THINKING_BUDGET

for task in ['topic_generation', 'novelty_check', 'feasibility', 'paper_writing', 'qa']:
    cfg = thinking_config(task)
    print(f'{task}: {cfg}')

print()
print('standard budget:', _THINKING_BUDGET['standard'])
print('premium budget: ', _THINKING_BUDGET['premium'])
print()
print('budget cap test (budget=5000, max_tokens=3000):')
t = {'type': 'enabled', 'budget_tokens': 5000}
if t.get('type') == 'enabled' and t.get('budget_tokens', 0) >= 3000:
    t = {'type': 'disabled'}
print('result:', t)
