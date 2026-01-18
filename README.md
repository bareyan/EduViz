# MathViz - 3Blue1Brown Style Educational Video Generator

Transform your math materials (PDFs, images) into beautiful, 3Blue1Brown-style animated videos with AI narration.

![MathViz Demo](https://via.placeholder.com/800x400?text=MathViz+Demo)

## Features

- 📄 **Smart Material Analysis**: Upload PDFs or images with math content
- 🎯 **Topic Extraction**: AI-powered detection of equations, theorems, and key concepts
- 🎬 **Manim Animations**: Beautiful 3Blue1Brown-style animations generated automatically
- 🎙️ **Voice Narration**: Natural-sounding AI voices (Edge TTS - free and high quality)
- 📹 **Chapter Support**: Videos divided into logical chapters (max 20 min each)
- ⚡ **Background Processing**: Generate videos without blocking the UI

## Tech Stack

### Backend
- **FastAPI**: Modern Python web framework
- **Manim**: Mathematical animation engine (3Blue1Brown's tool)
- **Edge TTS**: Microsoft's free, high-quality text-to-speech
- **PyMuPDF**: PDF text extraction
- **OpenAI** (optional): Enhanced content analysis

### Frontend
- **React 18**: Modern UI framework
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first styling
- **Vite**: Fast development server

## Prerequisites

- Python 3.10+
- Node.js 18+
- FFmpeg (for video processing)
- LaTeX (for Manim equation rendering)

### Installing FFmpeg

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows (using Chocolatey)
choco install ffmpeg
```

### Installing LaTeX (for Manim)

```bash
# Ubuntu/Debian
sudo apt install texlive-full

# macOS
brew install --cask mactex

# Windows
# Download and install MiKTeX from https://miktex.org/
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/mathviz.git
cd mathviz
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env and add your OpenAI API key (optional but recommended)

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

### 4. Access the Application

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Usage

1. **Upload Material**: Drag and drop a PDF or image with math content
2. **Review Analysis**: AI analyzes the content and suggests video topics
3. **Select Topics**: Choose which topics to generate videos for
4. **Customize**: Select voice, style, and video length preferences
5. **Generate**: Videos are generated in the background
6. **Download**: View and download your completed videos

## Project Structure

```
mathviz/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   └── services/
│   │       ├── analyzer.py       # Material analysis
│   │       ├── script_generator.py # Video script generation
│   │       ├── manim_scenes.py   # Manim animation code
│   │       ├── tts_engine.py     # Text-to-speech
│   │       ├── video_generator.py # Video composition
│   │       └── job_manager.py    # Background job tracking
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/                  # API client
│   │   ├── components/           # React components
│   │   ├── pages/               # Page components
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload` | Upload a PDF or image file |
| POST | `/analyze` | Analyze uploaded material |
| POST | `/generate` | Start video generation |
| GET | `/job/{job_id}` | Get generation job status |
| GET | `/video/{video_id}` | Download generated video |
| GET | `/voices` | List available TTS voices |

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for enhanced analysis | - |
| `HOST` | Server host | 0.0.0.0 |
| `PORT` | Server port | 8000 |
| `DEFAULT_MAX_VIDEO_LENGTH` | Max video length in minutes | 20 |
| `DEFAULT_VOICE` | Default TTS voice | en-US-GuyNeural |

### Available Voices

| Voice ID | Name | Gender |
|----------|------|--------|
| en-US-GuyNeural | Guy (US) | Male |
| en-US-JennyNeural | Jenny (US) | Female |
| en-GB-RyanNeural | Ryan (UK) | Male |
| en-GB-SoniaNeural | Sonia (UK) | Female |
| en-AU-WilliamNeural | William (AU) | Male |
| en-IN-PrabhatNeural | Prabhat (India) | Male |

## Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build
```

## Roadmap

- [ ] Support for more input formats (Word, LaTeX)
- [ ] Custom animation templates
- [ ] Multi-language support
- [ ] Collaborative editing
- [ ] Cloud storage integration
- [ ] Mobile app

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [3Blue1Brown](https://www.3blue1brown.com/) for inspiration and Manim
- [Manim Community](https://www.manim.community/) for the amazing animation library
- [Microsoft Edge TTS](https://azure.microsoft.com/en-us/services/cognitive-services/text-to-speech/) for high-quality voices

---

Made with ❤️ for math education
