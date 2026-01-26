"""
Constants configuration

Constants, API settings, and CORS configuration.
"""

# API settings
API_TITLE = "MathViz API"
API_DESCRIPTION = "Generate 3Blue1Brown-style educational videos from any material"
API_VERSION = "1.0.0"

# CORS origins
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001", 
    "http://localhost:5173",
]

# File upload settings
ALLOWED_MIME_TYPES = [
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "text/plain",
    "text/x-tex",
    "application/x-tex",
    "application/x-latex",
]

ALLOWED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tex", ".txt"]

__all__ = [
    "API_TITLE",
    "API_DESCRIPTION",
    "API_VERSION",
    "CORS_ORIGINS",
    "ALLOWED_MIME_TYPES",
    "ALLOWED_EXTENSIONS",
]
