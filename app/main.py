"""Medical Research Analysis — Flask Web Application"""

from flask import Flask, render_template, request, jsonify
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.statistics import MedicalStatistics
from src.visualization import MedicalVisualizer

app = Flask(__name__)
med_stats = MedicalStatistics()
visualizer = MedicalVisualizer()

# NoveltyDetector loads a sentence-transformer (~80 MB).
# Deferred to first request so startup stays fast.
_novelty_detector = None

def _get_novelty():
    global _novelty_detector
    if _novelty_detector is None:
        from src.nlp import NoveltyDetector
        _novelty_detector = NoveltyDetector()
    return _novelty_detector


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'message': 'Application is running'})


@app.route('/api/statistics', methods=['POST'])
def calculate_statistics():
    try:
        data = request.json
        g1 = pd.Series(data.get('group1', []), dtype=float)
        g2 = pd.Series(data.get('group2', []), dtype=float)
        result = med_stats.t_test(g1, g2)
        clean = {
            k: (float(v) if isinstance(v, (np.floating, np.integer)) else
                bool(v)  if isinstance(v, np.bool_) else v)
            for k, v in result.items()
        }
        return jsonify({'status': 'success', 'result': clean})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/analysis/novelty', methods=['POST'])
def analyze_novelty():
    try:
        data = request.json
        query  = data.get('query', '')
        corpus = data.get('corpus', [])
        gap = _get_novelty().detect_research_gaps(corpus, query)
        return jsonify({
            'status':       'success',
            'gap_score':    float(gap['gap_score']),
            'is_novel':     bool(gap['is_novel']),
            'max_similarity': float(gap['max_similarity']),
            'similar_count':  int(gap['similar_count']),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/manuscript/generate', methods=['POST'])
def generate_manuscript():
    try:
        from src.papergen import ManuscriptGenerator
        data = request.json
        gen = ManuscriptGenerator(
            title=data.get('title', ''),
            authors=data.get('authors', []),
            institution=data.get('institution', ''),
        )
        abstract = gen.generate_abstract(
            background=data.get('background', ''),
            objective=data.get('objective', ''),
            methods=data.get('methods', ''),
            results=data.get('results', ''),
            conclusion=data.get('conclusion', ''),
        )
        return jsonify({'status': 'success', 'abstract': abstract})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
