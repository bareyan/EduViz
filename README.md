# EduViz

**AI-Powered Educational Video Generation Platform**

EduViz transforms educational content into professional animated videos using AI-driven narration and Manim-based mathematical visualizations.

## Documentation

-   **[Architecture Overview](ARCHITECTURE.md):** Detailed system design, layer descriptions, and the animation pipeline.
-   **[Backend Setup & API](backend/README.md):** Instructions for setting up the FastAPI backend, configuration detailed, and testing.
-   **[Frontend Setup](frontend/README.md):** Instructions for setting up the React frontend.
-   **[Environment Configuration](backend/ENVIRONMENT.md):** Detailed guide on environment variables and advanced settings.

## Overview

EduViz is a production-grade platform that automates educational video creation from source materials. The system leverages Google's Gemini AI for intelligent content analysis, script generation, and animation choreography, combined with Manim for mathematical visualizations and Gemini TTS for natural-sounding narration.

### Key Features

-   **Multi-Format Content Analysis** (PDFs, text, images)
-   **AI-Driven Script Generation** & **Intelligent Animation Generation**
-   **Natural Text-to-Speech** (Gemini TTS)
-   **Professional Video Assembly**
-   **Multi-Language Support** (50+ languages)
-   **Customizable Themes** (3Blue1Brown, Clean White, etc.)

## Quick Start

### Prerequisites
-   Docker and Docker Compose (Recommended)
-   OR Python 3.12+ / Node.js 18+ / FFmpeg / Manim (Local Dev)

### Using Docker (Simplest)

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd EduViz-main
    ```

2.  **Configure environment:**
    ```bash
    cd backend
    cp .env.example .env
    # Edit .env and add your GEMINI_API_KEY
    ```

3.  **Start with Docker Compose:**
    ```bash
    # Windows
    run.bat
    
    # Linux/Mac
    ./run.sh
    ```

4.  **Access:**
    -   Frontend: `http://localhost:3000`
    -   Backend API: `http://localhost:8000/docs`

For detailed local development setup, refer to the [Backend README](backend/README.md) and [Frontend README](frontend/README.md).

## Tech Stack

-   **Backend:** FastAPI, Python, Manim, Google Gemini, Gemini TTS, FFmpeg
-   **Frontend:** React, TypeScript, Vite, TailwindCSS
-   **Infrastructure:** Docker, Nginx

## Support

For issues, questions, or contributions, please refer to the specific component documentation or open an issue on GitHub.
