# Project Architecture

## Overview

The Medical Research Paper Automated Analysis Environment is organized with **clear separation** between learning/exploration and production/application code.

## Architecture Layers

### 1. Presentation Layer
- **Location**: `/app/templates/`
- **Purpose**: Web UI for the application
- **Technology**: HTML, CSS, JavaScript

### 2. API Layer
- **Location**: `/app/api/`
- **Purpose**: REST endpoints for client-server communication
- **Technology**: Flask

### 3. Application Layer
- **Location**: `/app/`
- **Purpose**: Business logic and application orchestration
- **Files**: `main.py`, configuration management

### 4. Library Layer
- **Location**: `/src/`
- **Purpose**: Core reusable modules
- **Modules**: Statistics, Visualization, Database, NLP, Paper Generation

### 5. Data Layer
- **Location**: `/data/`
- **Purpose**: Data storage and management
- **Technology**: SQLite, CSV, JSON

### 6. Learning & Experimentation Layer
- **Location**: `/learning/`
- **Purpose**: Jupyter notebooks for exploration
- **Technology**: Jupyter Lab, Python

### 7. Examples & Reference Layer
- **Location**: `/examples/`
- **Purpose**: Practical working examples
- **Files**: Python scripts demonstrating usage

## Key Principles

### Separation of Concerns
- **Learning** workspace: Interactive exploration (notebooks)
- **Production** workspace: Stable application code
- **Examples**: Reference implementations
- **Library**: Shared utilities used by both

### Dependencies
```
Examples, Learning → Library → Database, NLP, Visualization, Statistics
    ↓
Production App → Library (same)
```

### Configuration Management
- Environment-specific settings in `/app/config/`
- `.env` file for sensitive data
- Development, testing, production modes

## Data Flow

### Research Analysis Workflow
```
Data Input
    ↓
Data Cleaning (DataCleaner)
    ↓
Statistical Analysis (MedicalStatistics)
    ↓
Visualization (MedicalVisualizer)
    ↓
Novelty Detection (NoveltyDetector)
    ↓
Manuscript Generation (ManuscriptGenerator)
    ↓
Output (Web/Export)
```

## File Organization Strategy

### Learning (`/learning/notebooks/`)
- **01_data_exploration.ipynb**: Load and explore medical data
- **02_statistical_analysis.ipynb**: Perform statistical tests
- **03_visualization.ipynb**: Create publication-ready charts
- **04_manuscript_generation.ipynb**: Generate paper sections

### Production (`/app/`)
- **main.py**: Flask application entry point
- **config/settings.py**: Configuration management
- **api/**: REST API endpoints
- **templates/**: HTML UI

### Examples (`/examples/`)
- **01_statistics_example.py**: Statistical methods usage
- **02_data_management_example.py**: Database and cleaning
- **03_novelty_detection_example.py**: Research novelty analysis

### Library (`/src/`)
- **statistics/**: Medical statistical functions
- **visualization/**: Chart and plot generation
- **database/**: Data management and cleaning
- **nlp/**: Text analysis and novelty detection
- **papergen/**: Manuscript generation

## Module Interfaces

### MedicalStatistics
```python
from src.statistics import MedicalStatistics

stats = MedicalStatistics()
result = stats.t_test(group1, group2)
result = stats.correlation(x, y)
```

### MedicalVisualizer
```python
from src.visualization import MedicalVisualizer

visualizer = MedicalVisualizer()
fig = visualizer.distribution_plot(data, title="Distribution")
fig = visualizer.box_plot(data, x="group", y="value")
```

### MedicalDatabase
```python
from src.database import MedicalDatabase

db = MedicalDatabase("path/to/db.sqlite")
db.insert_data("table_name", dataframe)
result = db.query("SELECT * FROM table_name")
```

### NoveltyDetector
```python
from src.nlp import NoveltyDetector

detector = NoveltyDetector()
gap_analysis = detector.detect_research_gaps(corpus, new_research)
similar = detector.find_similar_research(query, corpus)
```

### ManuscriptGenerator
```python
from src.papergen import ManuscriptGenerator

gen = ManuscriptGenerator(title, authors, institution)
abstract = gen.generate_abstract(...)
introduction = gen.generate_introduction(...)
manuscript = gen.generate_full_manuscript(sections)
```

## Deployment Architecture

### Development
- Single machine with Jupyter Lab and Flask
- SQLite database for data storage
- No external dependencies

### Production
- Flask application running on server
- SQLite or PostgreSQL database
- Optional: Docker containerization
- Optional: Load balancer and multiple app instances

## Environment Variables

```env
FLASK_ENV=production
SECRET_KEY=your-secret-key
DATABASE_PATH=path/to/database.sqlite
SENTENCE_MODEL=all-MiniLM-L6-v2
```

## Best Practices

1. **Keep Learning and Production Separate**
   - Don't import production code in notebooks unnecessarily
   - Use examples as integration tests

2. **Library First**
   - Add new functionality to library first
   - Use library in both learning and production

3. **Configuration Management**
   - Store all settings in config
   - Use environment variables for secrets

4. **Testing**
   - Use examples as integration tests
   - Add unit tests in separate test/ directory (future)

5. **Documentation**
   - Keep docs in sync with code
   - Include docstrings in all modules
   - Provide examples for new features

## Future Enhancements

- [ ] Add REST API documentation (Swagger)
- [ ] Add authentication and authorization
- [ ] Add unit and integration tests
- [ ] Add Docker containerization
- [ ] Add database migrations
- [ ] Add caching layer
- [ ] Add task queue for long-running operations
