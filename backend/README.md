# EduViz Backend

The backend for EduViz is a robust FastAPI application responsible for content analysis, script generation, audio synthesis, and Manim animation rendering.

## Quick Start

### Prerequisites
- Python 3.12+
- FFmpeg (must be in system PATH)
- Manim (must be installable via pip or in system PATH)
- Google Cloud Project (for Vertex AI) OR API Key (for Gemini API)

### Local Development Setup

1.  **Navigate to the backend directory:**
    ```bash
    cd backend
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv .venv
    ```

3.  **Activate the virtual environment:**
    -   **Windows:**
        ```bash
        .venv\Scripts\activate
        ```
    -   **Linux/Mac:**
        ```bash
        source .venv/bin/activate
        ```

4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Configure Environment:**
    Copy the example environment file:
    ```bash
    cp .env.example .env
    ```
    
    Edit `.env` and configure your AI backend (see [Configuration](#configuration)).

6.  **Run the Server:**
    ```bash
    python -m uvicorn app.main:app --reload
    ```
    The API will be available at `http://localhost:8000`.

## Configuration

EduViz supports two AI backends. Choose one in your `.env` file.

### 1. Gemini API (Default - Easiest)
Best for local development and testing.
```ini
USE_VERTEX_AI=false
GEMINI_API_KEY=your_api_key_here  # Get from https://aistudio.google.com/app/apikey
```

### 2. Vertex AI (Enterprise)
Best for production and enterprise deployments.
```ini
USE_VERTEX_AI=true
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=us-central1
```
*Note: Requires `gcloud auth application-default login`.*

### Detailed Environment Variables
For a complete list of configuration options, including rate limiting, logging, and advanced settings, please refer to [`ENVIRONMENT.md`](ENVIRONMENT.md).

## Testing

We use `pytest` for testing.

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_animation_pipeline.py

# Run integration tests only
pytest -m integration
```

## API Documentation

-   **Swagger UI:** `http://localhost:8000/docs`
-   **ReDoc:** `http://localhost:8000/redoc`

### Key Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/upload` | Upload content file for analysis |
| `POST` | `/analyze` | Analyze content and extract topics |
| `POST` | `/generate` | Generate video from selected topics |
| `GET` | `/jobs/{job_id}` | Get job status and metadata |
| `GET` | `/jobs/{job_id}/sections` | Get detailed section information |
| `POST` | `/translate` | Translate video to another language |
| `GET` | `/health` | Health check endpoint |

## Development

-   **Linting:** `ruff check .`
-   **Type Checking:** `pyright`
-   **Formatting:** `black .`

Refer to the root `ARCHITECTURE.md` for architectural details and `ENVIRONMENT.md` for advanced configuration.
