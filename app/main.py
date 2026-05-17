"""Medical Research Analysis Web Application"""

from flask import Flask, render_template, request, jsonify
import logging

from src.config.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)
import sys
import os
import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.statistics import MedicalStatistics
from src.visualization import MedicalVisualizer
from src.nlp import NoveltyDetector

app = Flask(__name__)

med_stats = MedicalStatistics()
visualizer = MedicalVisualizer()

# NoveltyDetector loads a sentence-transformer model (~80MB).
# Loaded lazily on first request to keep startup fast.
_novelty_detector = None
_rag_pipeline = None
_agent = None


def get_novelty_detector():
    global _novelty_detector
    if _novelty_detector is None:
        _novelty_detector = NoveltyDetector()
    return _novelty_detector


def get_rag():
    global _rag_pipeline
    if _rag_pipeline is None:
        from src.rag.pipeline import RAGPipeline
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline


def get_agent():
    global _agent
    if _agent is None:
        from src.agent.medical_agent import MedicalAgent
        _agent = MedicalAgent()
    return _agent


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/statistics', methods=['POST'])
def calculate_statistics():
    try:
        data = request.json
        group1 = pd.Series(data.get('group1', []), dtype=float)
        group2 = pd.Series(data.get('group2', []), dtype=float)

        result = med_stats.t_test(group1, group2)

        # Convert numpy scalars to plain Python for JSON serialisation
        clean = {k: (float(v) if isinstance(v, (np.floating, np.integer)) else
                     bool(v) if isinstance(v, (np.bool_,)) else v)
                 for k, v in result.items()}

        return jsonify({'status': 'success', 'result': clean})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/analysis/novelty', methods=['POST'])
def analyze_novelty():
    try:
        data = request.json
        query = data.get('query', '')
        corpus = data.get('corpus', [])

        detector = get_novelty_detector()
        gap_analysis = detector.detect_research_gaps(corpus, query)

        return jsonify({
            'status': 'success',
            'gap_score': float(gap_analysis['gap_score']),
            'is_novel': bool(gap_analysis['is_novel']),
            'max_similarity': float(gap_analysis['max_similarity']),
            'similar_count': int(gap_analysis['similar_count']),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/manuscript/generate', methods=['POST'])
def generate_manuscript():
    try:
        from src.papergen import ManuscriptGenerator

        data = request.json
        gen = ManuscriptGenerator(
            title=data.get('title', 'Research Title'),
            authors=data.get('authors', []),
            institution=data.get('institution', '')
        )

        abstract = gen.generate_abstract(
            background=data.get('background', ''),
            objective=data.get('objective', ''),
            methods=data.get('methods', ''),
            results=data.get('results', ''),
            conclusion=data.get('conclusion', '')
        )

        return jsonify({'status': 'success', 'abstract': abstract})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'message': 'Application is running'})


# ---------------------------------------------------------------------------
# RAG / Paper Learning endpoints
# ---------------------------------------------------------------------------

@app.route('/api/papers/ingest', methods=['POST'])
def ingest_paper():
    """Ingest a single PDF into the vector store.

    Body: {"pdf_path": "/absolute/path/to/paper.pdf"}
    """
    try:
        data = request.json
        pdf_path = data.get('pdf_path', '')
        if not pdf_path:
            return jsonify({'status': 'error', 'message': 'pdf_path is required'}), 400

        rag = get_rag()
        result = rag.ingest_pdf(pdf_path)
        return jsonify({'status': 'success', 'result': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/papers/ingest_directory', methods=['POST'])
def ingest_directory():
    """Ingest all PDFs in a directory.

    Body: {"directory": "/path/to/pdfs"}  (optional; defaults to data/papers/)
    """
    try:
        data = request.json or {}
        directory = data.get('directory')

        rag = get_rag()
        results = rag.ingest_directory(directory)
        return jsonify({'status': 'success', 'results': results})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/papers/ask', methods=['POST'])
def ask_papers():
    """Ask a question answered from indexed papers (RAG).

    Body: {"question": "...", "filename": "paper.pdf"  (optional filter)}
    """
    try:
        data = request.json
        question = data.get('question', '')
        if not question:
            return jsonify({'status': 'error', 'message': 'question is required'}), 400

        filename = data.get('filename')
        rag = get_rag()
        result = rag.ask(question, filename_filter=filename)
        return jsonify({'status': 'success', **result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/papers/summarize', methods=['POST'])
def summarize_paper():
    """Summarise an indexed paper with Claude.

    Body: {"filename": "paper.pdf"}
    """
    try:
        data = request.json
        filename = data.get('filename', '')
        if not filename:
            return jsonify({'status': 'error', 'message': 'filename is required'}), 400

        rag = get_rag()
        summary = rag.summarize(filename)
        return jsonify({'status': 'success', 'summary': summary})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/papers/status', methods=['GET'])
def papers_status():
    """Return index stats: total chunks and list of indexed papers."""
    try:
        rag = get_rag()
        return jsonify({'status': 'success', **rag.status()})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


# ---------------------------------------------------------------------------
# Self-learning Agent endpoints
# ---------------------------------------------------------------------------

@app.route('/api/agent/learn', methods=['POST'])
def agent_learn():
    """Teach the agent a new paper.

    Body: {"pdf_path": "/path/to/paper.pdf"}
    Or:   {"directory": "/path/to/folder"}  to ingest all PDFs in a folder
    """
    try:
        data = request.json or {}
        agent = get_agent()

        if 'directory' in data:
            results = agent.learn_directory(data['directory'])
            return jsonify({'status': 'success', 'results': results})

        pdf_path = data.get('pdf_path', '')
        if not pdf_path:
            return jsonify({'status': 'error', 'message': 'pdf_path or directory is required'}), 400

        result = agent.learn(pdf_path)
        return jsonify({'status': 'success', 'result': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/agent/ask', methods=['POST'])
def agent_ask():
    """Ask the agent a question — answered from everything it has learned.

    Body: {"question": "...", "filename": "paper.pdf"  (optional)}
    """
    try:
        data = request.json
        question = data.get('question', '')
        if not question:
            return jsonify({'status': 'error', 'message': 'question is required'}), 400

        agent = get_agent()
        result = agent.ask(question, filename_filter=data.get('filename'))
        return jsonify({'status': 'success', **result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/agent/summarize', methods=['POST'])
def agent_summarize():
    """Return or generate a cached paper summary.

    Body: {"filename": "paper.pdf", "force": false}
    """
    try:
        data = request.json
        filename = data.get('filename', '')
        if not filename:
            return jsonify({'status': 'error', 'message': 'filename is required'}), 400

        agent = get_agent()
        summary = agent.summarize(filename, force=bool(data.get('force', False)))
        return jsonify({'status': 'success', 'summary': summary})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/agent/synthesize', methods=['POST'])
def agent_synthesize():
    """Generate cross-paper insights across all indexed papers."""
    try:
        agent = get_agent()
        insight = agent.synthesize_insights()
        return jsonify({'status': 'success', 'insight': insight})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/agent/status', methods=['GET'])
def agent_status():
    """Return full agent status: index size, interaction count, follow-ups."""
    try:
        agent = get_agent()
        return jsonify({'status': 'success', **agent.status()})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/agent/history', methods=['GET'])
def agent_history():
    """Return the full Q&A interaction history."""
    try:
        agent = get_agent()
        return jsonify({'status': 'success', 'history': agent.get_history()})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/agent/follow_ups', methods=['GET'])
def agent_follow_ups():
    """Return open follow-up questions the agent has flagged."""
    try:
        agent = get_agent()
        return jsonify({'status': 'success', 'follow_ups': agent.get_follow_ups()})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
