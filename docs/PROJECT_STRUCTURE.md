# Medical Research Paper Automated Analysis Environment

## 📁 Project Structure

```
Medical-Agent/
│
├── 📚 learning/              # 🎓 LEARNING & EXPLORATION AREA
│   ├── notebooks/
│   │   ├── 01_data_exploration.ipynb
│   │   ├── 02_statistical_analysis.ipynb
│   │   ├── 03_visualization.ipynb
│   │   └── 04_manuscript_generation.ipynb
│   └── tutorials/            # Tutorial notebooks and guides
│
├── 🚀 app/                   # 💼 PRODUCTION APPLICATION AREA
│   ├── main.py              # Flask web application
│   ├── api/                 # REST API endpoints
│   ├── config/              # Configuration files
│   │   └── settings.py
│   └── templates/           # HTML templates
│
├── 📖 examples/             # 💡 WORKING EXAMPLES
│   ├── 01_statistics_example.py
│   ├── 02_data_management_example.py
│   └── 03_novelty_detection_example.py
│
├── 📚 docs/                 # Documentation
│   └── ARCHITECTURE.md
│
├── 📂 data/                 # Research data and datasets
│   └── sample_data/
│
├── 📦 src/                  # Core library code
│   ├── statistics/
│   ├── visualization/
│   ├── database/
│   ├── nlp/
│   └── papergen/
│
├── requirements.txt         # Python dependencies
└── README.md               # Project documentation
```

## 🎓 Learning Area (`/learning`)

**Purpose**: Interactive exploration, experimentation, and learning

**Contents**:
- **Jupyter Notebooks** (`/notebooks/`): Interactive analysis notebooks for:
  - Data exploration and visualization
  - Statistical analysis demonstrations
  - Publication-ready visualization creation
  - Automated manuscript generation
  
**How to Use**:
```bash
jupyter lab --notebook-dir=learning/notebooks
```

**Best for**:
- Data exploration and analysis
- Learning statistical methods
- Creating new analysis pipelines
- Experimenting with different approaches
- Visualizing and understanding results

---

## 💼 Production Area (`/app`)

**Purpose**: Stable, production-ready application code

**Contents**:
- **Web Application** (`main.py`): Flask-based REST API
- **API Endpoints** (`/api/`): Statistical analysis, novelty detection, manuscript generation
- **Configuration** (`/config/`): Environment-specific settings
- **Templates** (`/templates/`): HTML UI components

**How to Use**:
```bash
cd app
python main.py
```

**API Endpoints**:
- `POST /api/statistics` - Calculate statistics
- `POST /api/analysis/novelty` - Analyze research novelty
- `POST /api/manuscript/generate` - Generate manuscript sections
- `GET /health` - Health check

---

## 💡 Examples (`/examples`)

**Purpose**: Practical working examples for each module

**Files**:
1. `01_statistics_example.py` - Medical statistics usage
2. `02_data_management_example.py` - Data cleaning and database operations
3. `03_novelty_detection_example.py` - Research novelty analysis

**How to Use**:
```bash
# Run any example
python examples/01_statistics_example.py
```

---

## 📂 Core Library (`/src`)

**Purpose**: Reusable modules shared between learning and production areas

**Modules**:

### `statistics/`
- `MedicalStatistics`: Statistical tests (t-test, ANOVA, chi-square, etc.)
- `SurvivalAnalysis`: Kaplan-Meier curves, survival analysis

### `visualization/`
- `MedicalVisualizer`: Publication-ready charts and plots

### `database/`
- `MedicalDatabase`: SQLite database operations
- `DataCleaner`: Data cleaning and preprocessing

### `nlp/`
- `NoveltyDetector`: Research gap and novelty detection
- `KeywordExtractor`: Extract medical terminology
- `TextAnalyzer`: Readability metrics

### `papergen/`
- `ManuscriptGenerator`: Automated manuscript sections
- `CitationFormatter`: Citation formatting (APA, MLA, Chicago)

---

## 🔄 Workflow

### For Learning/Experimentation:
1. Open learning area in VS Code
2. Launch Jupyter Lab: `jupyter lab --notebook-dir=learning/notebooks`
3. Work through notebooks interactively
4. Test new ideas and approaches

### For Production Use:
1. Open app area in VS Code
2. Run Flask server: `python app/main.py`
3. Access web interface at `http://localhost:5000`
4. Use REST API endpoints for automation

### For Examples/Reference:
1. Open examples folder
2. Run any example: `python examples/XX_example.py`
3. Study code patterns and usage
4. Adapt to your specific needs

---

## 🚀 Getting Started

### Installation
```bash
pip install -r requirements.txt
```

### Start Learning (Notebooks)
```bash
jupyter lab --notebook-dir=learning/notebooks
```

### Start Application (Production)
```bash
cd app
python main.py
```

### Run Examples
```bash
python examples/01_statistics_example.py
```

---

## 📝 File Organization Guidelines

**Use Learning Area for**:
- ✅ Exploring new datasets
- ✅ Testing new statistical methods
- ✅ Creating visualizations
- ✅ Prototyping new analyses
- ✅ Learning and experimentation

**Use Production Area for**:
- ✅ Stable, tested code
- ✅ API endpoints
- ✅ Web application
- ✅ Configuration management
- ✅ Deployment-ready code

**Use Examples for**:
- ✅ Code templates
- ✅ Usage demonstrations
- ✅ Reference implementations
- ✅ Learning patterns

---

## 🎯 Key Features

- **Medical Statistics**: Comprehensive statistical tests
- **Data Management**: Database operations, cleaning, handling missing values
- **Visualization**: Publication-ready medical graphs
- **Novelty Detection**: AI-powered research gap identification
- **Manuscript Generation**: Automated paper structure and content
- **Web Application**: REST API for integration

---

## 📚 Documentation

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture information.

---

## 📞 Support

For issues, questions, or contributions, please refer to the documentation and examples.
