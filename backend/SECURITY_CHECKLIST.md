# Backend Security Checklist

Use this checklist before production deploys.

## Runtime & Infrastructure
- [ ] `STARTUP_STRICT_RUNTIME_CHECKS=true` in production.
- [ ] `ffmpeg`, `ffprobe`, and `manim` are installed in the runtime image.
- [ ] `uploads/` and `outputs/` are writable by the app user.
- [ ] Output cleanup is enabled and tuned for retention requirements.

## API Protection
- [ ] Rate limiting is enabled (`RATE_LIMIT_ENABLED=true`).
- [ ] Request-size cap is set (`MAX_REQUEST_BODY_BYTES`) for non-upload endpoints.
- [ ] Upload size cap is set (`MAX_UPLOAD_SIZE`) and tested.
- [ ] CORS origins are locked down (no wildcard in production).

## Logging & Secrets
- [ ] LLM response logging is capped (`LLM_LOG_MAX_RESPONSE_LENGTH`).
- [ ] Log rotation is enabled (`LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`).
- [ ] API keys and tokens are never logged in plaintext.

## Failure Isolation & Recovery
- [ ] Background tasks are idempotent and report failure status to job metadata.
- [ ] Health endpoint checks runtime/tool availability.
- [ ] Restart behavior for interrupted jobs is tested.
- [ ] Disk space alerting is configured.

## Verification
- [ ] Run test suite: `python -m pytest .\\tests\\`
- [ ] Run at least one end-to-end generation in the target environment.
- [ ] Run one translation and one high-quality recompilation in the target environment.
