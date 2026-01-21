# 🚀 ManimagAin Quick Reference - Micromamba Setup

## Start the Server

```bash
# From the project root
./start_server.sh

# OR manually
cd backend
micromamba run -n manim uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Server Access

- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:3000 (if running)

## Useful Commands

```bash
# Check micromamba environment
micromamba env list

# Install packages in manim env
micromamba run -n manim pip install <package>
```
