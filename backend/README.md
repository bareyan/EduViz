# EduViz Backend - Quick Start

## AI Backend Setup

EduViz supports two AI backends:

### 1. Gemini API (Default - Easiest)

```bash
# Get API key from https://aistudio.google.com/app/apikey
echo "USE_VERTEX_AI=false" >> .env
echo "GEMINI_API_KEY=your_key_here" >> .env

pip install google-generativeai
python -m uvicorn app.main:app --reload
```

### 2. Vertex AI (Enterprise)

```bash
# Setup GCP project and enable Vertex AI API
echo "USE_VERTEX_AI=true" >> .env
echo "GCP_PROJECT_ID=your-project-id" >> .env
echo "GCP_LOCATION=us-central1" >> .env

# Authenticate
gcloud auth application-default login

pip install google-cloud-aiplatform
python -m uvicorn app.main:app --reload
```

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Optional: review advanced knobs
# cp .env.advanced.example .env.advanced

# Edit .env with your settings (see above)
nano .env

# Run server
python -m uvicorn app.main:app --reload
```

## Documentation

- Full setup guide: [docs/VERTEX_AI_SETUP.md](../docs/VERTEX_AI_SETUP.md)
- Model configuration: [app/config/models.py](app/config/models.py)
- Environment strategy: [ENVIRONMENT.md](ENVIRONMENT.md)
- Advanced env knobs: [.env.advanced.example](.env.advanced.example)

## Switching Backends

Change `USE_VERTEX_AI` in `.env`:
- `false` → Gemini API (needs `GEMINI_API_KEY`)
- `true` → Vertex AI (needs `GCP_PROJECT_ID`)

No code changes required!
