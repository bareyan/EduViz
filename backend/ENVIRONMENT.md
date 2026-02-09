# Environment Configuration

This backend uses a two-tier environment strategy:

1. `.env.example`: minimal, commonly edited variables.
2. `.env.advanced.example`: optional tuning knobs for production optimization.

## Recommended Workflow

1. Copy minimal template:
   - `cp .env.example .env`
2. Set backend credentials (`GEMINI_API_KEY` or Vertex config).
3. Only add advanced variables if you have a clear operational reason.

## Minimal Variables

- `USE_VERTEX_AI`
- `GEMINI_API_KEY`
- `GCP_PROJECT_ID`
- `GCP_LOCATION`
- `STARTUP_STRICT_RUNTIME_CHECKS`
- `MAX_UPLOAD_SIZE`
- `AUTH_ENABLED`
- `AUTH_PASSWORD`

## Advanced Variables (Optional)

See `.env.advanced.example` for:
- Retention/cleanup windows
- Logging volume/rotation
- LLM logging options
- Rate limiting and request-size caps
- Auth session controls (`AUTH_SECRET`, `AUTH_SESSION_MAX_AGE_SECONDS`, `AUTH_COOKIE_SECURE`, `AUTH_OPEN_PATHS`)
- Cache size tuning
- Optional PDF slicing behavior (`ENABLE_SECTION_PDF_SLICES`, `SECTION_PDF_SLICE_MIN_PAGES`)

## Why This Split

- Keeps default setup simple and less error-prone.
- Avoids "config sprawl" for new developers.
- Preserves full control for production tuning.
