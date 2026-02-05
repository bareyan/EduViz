"""
Manual PDF payload test (no pytest).

Usage:
  python test_pdf_payload.py /path/to/file.pdf
"""

import sys
import asyncio
from pathlib import Path
import traceback
import base64

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from app.services.infrastructure.llm import PromptingEngine, PromptConfig


def _build_pdf_part(engine: PromptingEngine, pdf_path: Path):
    pdf_bytes = pdf_path.read_bytes()
    try:
        return engine.types.Part.from_data(
            data=pdf_bytes,
            mime_type="application/pdf",
        )
    except Exception:
        try:
            return engine.types.Part.from_bytes(
                data=pdf_bytes,
                mime_type="application/pdf",
            )
        except Exception:
            return None


def _build_image_part(engine: PromptingEngine, pdf_path: Path):
    """Render first page to PNG bytes and build image Part."""
    if not fitz:
        return None
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            return None
        page = doc[0]
        pix = page.get_pixmap(alpha=False)
        png_bytes = pix.tobytes("png")
        doc.close()
    except Exception:
        return None

    try:
        return engine.types.Part.from_data(
            data=png_bytes,
            mime_type="image/png",
        )
    except Exception:
        try:
            return engine.types.Part.from_bytes(
                data=png_bytes,
                mime_type="image/png",
            )
        except Exception:
            return None


def build_contents(engine: PromptingEngine, prompt: str, pdf_path: Path):
    pdf_part = _build_pdf_part(engine, pdf_path)
    if pdf_part is None:
        print("Failed to build PDF Part attachment.")
        return None

    # Gemini PDF processing expects the attachment first, then the prompt string.
    return [pdf_part, prompt]


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python test_pdf_payload.py /path/to/file.pdf [--no-pdf]")
        return 1

    no_pdf = False
    args = sys.argv[1:]
    if args[-1] == "--no-pdf":
        no_pdf = True
        args = args[:-1]

    pdf_path = Path(args[0]).expanduser().resolve()
    if not no_pdf and not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return 1

    engine = PromptingEngine("analysis")
    prompt = (
        "Analyze the attached PDF and return a JSON object with keys: "
        "summary, main_subject, key_concepts."
    )
    contents = None
    if not no_pdf:
        contents = build_contents(engine, prompt, pdf_path)
        if contents is None:
            print("No contents payload; aborting.")
            return 1

    config = PromptConfig(
        temperature=0.2,
        max_output_tokens=1024,
        timeout=60.0,
        response_format="json",
    )

    print("\n=== Payload Debug ===")
    print("Using PDF:", not no_pdf)
    if contents:
        print("Contents type:", type(contents))
        print("Contents len:", len(contents))
        for i, c in enumerate(contents):
            print(f"  Item {i} type:", type(c))
            if hasattr(c, "parts"):
                print("    parts len:", len(getattr(c, "parts", [])))
    else:
        print("Contents: None (prompt-only)")

    try:
        result = asyncio.run(
            engine.generate(
                prompt=prompt,
                config=config,
                contents=contents,
            )
        )
    except Exception:
        print("\n=== Exception during generate (PDF) ===")
        traceback.print_exc()
        result = None

    # If PDF attempt fails due to attachment issues, retry with image (first page)
    if not no_pdf and (result is None or not result.get("success")):
        print("\nPDF attempt failed; retrying with first-page image...")
        image_part = _build_image_part(engine, pdf_path)
        if image_part:
            try:
                text_part = engine.types.Part.from_text(text=prompt)
                content = engine.types.Content(role="user", parts=[text_part, image_part])
                image_contents = [content]
            except Exception as e:
                print(f"Failed to build Content with image: {e}")
                image_contents = None
            if image_contents:
                try:
                    result = asyncio.run(
                        engine.generate(
                            prompt=prompt,
                            config=config,
                            contents=image_contents,
                        )
                    )
                except Exception:
                    print("\n=== Exception during generate (image) ===")
                    traceback.print_exc()
                    result = None
        else:
            print("Could not build image part (PyMuPDF missing or render failed).")

    print("Success:", result.get("success") if result else None)
    print("Error:", result.get("error") if result else None)
    print("Response:\n", result.get("response") if result else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
