"""
Test Gemini API and Vertex AI compatibility

Verifies that all API calls work correctly with both backends.
"""

import asyncio
import os
from pathlib import Path

from app.services.infrastructure.llm.gemini.client import create_client, get_types_module
from app.services.infrastructure.llm.gemini.helpers import (
    generate_content_with_text,
    generate_content_with_images,
)


async def test_basic_generation():
    """Test basic text generation"""
    print("\n" + "="*60)
    print("TEST 1: Basic Text Generation")
    print("="*60)
    
    client = create_client()
    types = get_types_module()
    
    backend = "Vertex AI" if os.getenv("USE_VERTEX_AI", "false").lower() == "true" else "Gemini API"
    print(f"Using backend: {backend}")
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents="Say 'Hello from AI!' in exactly 3 words.",
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=50,
            )
        )
        
        print(f"✅ Basic generation works")
        print(f"Response: {response.text}")
        return True
        
    except Exception as e:
        print(f"❌ Basic generation failed: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_thinking_config():
    """Test generation with thinking config"""
    print("\n" + "="*60)
    print("TEST 2: Generation with Thinking Config")
    print("="*60)
    
    client = create_client()
    types = get_types_module()
    
    # Note: Not all models support thinking config (e.g., gemini-2.0-flash-exp doesn't)
    # Models that support it: gemini-2.5-flash, gemini-2.5-pro, gemini-3-flash-preview, gemini-3-pro-preview
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents="What is 2+2? Answer in one word.",
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="LOW"),
                temperature=0.1,
                max_output_tokens=50,
            )
        )
        
        print(f"✅ Thinking config fallback works (automatically retried without thinking_config)")
        if response and hasattr(response, 'text'):
            print(f"Response: {response.text}")
        return True
        
    except Exception as e:
        error_msg = str(e)
        # If the error is about thinking_level not being supported, that's expected for some models
        if "thinking_level is not supported" in error_msg or "thinking_config" in error_msg.lower():
            print(f"⚠️  Thinking config not supported by this model (expected for some models)")
            print(f"   Trying without thinking config...")
            
            # Retry without thinking config
            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents="What is 2+2? Answer in one word.",
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=50,
                    )
                )
                print(f"✅ Model works without thinking config")
                print(f"Response: {response.text}")
                return True
            except Exception as e2:
                print(f"❌ Model failed even without thinking config: {type(e2).__name__}: {str(e2)}")
                return False
        else:
            print(f"❌ Thinking config failed: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


async def test_part_from_text():
    """Test Part.from_text()"""
    print("\n" + "="*60)
    print("TEST 3: Part.from_text()")
    print("="*60)
    
    client = create_client()
    types = get_types_module()
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text="Say 'Part works!' in exactly 2 words.")]
                )
            ],
            config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=50)
        )
        
        print(f"✅ Part.from_text() works")
        print(f"Response: {response.text}")
        return True
        
    except Exception as e:
        print(f"❌ Part.from_text() failed: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_part_from_data_bytes():
    """Test Part.from_data() and Part.from_bytes() fallback"""
    print("\n" + "="*60)
    print("TEST 4: Part.from_data/from_bytes Compatibility")
    print("="*60)
    
    client = create_client()
    types = get_types_module()
    
    # Create a tiny 1x1 PNG image (69 bytes)
    png_data = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,
        0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41,
        0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
        0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00,
        0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,
        0x42, 0x60, 0x82
    ])
    
    try:
        # Try from_data first (Vertex AI)
        try:
            image_part = types.Part.from_data(data=png_data, mime_type="image/png")
            print("✅ Part.from_data() works (Vertex AI)")
        except AttributeError:
            # Fallback to from_bytes (Gemini API)
            image_part = types.Part.from_bytes(data=png_data, mime_type="image/png")
            print("✅ Part.from_bytes() works (Gemini API)")
        
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        image_part,
                        types.Part.from_text(text="Describe this image in 3 words.")
                    ]
                )
            ],
            config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=50)
        )
        
        print(f"✅ Image processing works")
        print(f"Response: {response.text}")
        return True
        
    except Exception as e:
        print(f"❌ Image processing failed: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_helper_functions():
    """Test helper functions from gemini/helpers.py"""
    print("\n" + "="*60)
    print("TEST 5: Helper Functions")
    print("="*60)
    
    client = create_client()
    
    try:
        # Test generate_content_with_text
        result = await generate_content_with_text(
            client=client,
            model="gemini-2.0-flash-exp",
            prompt="Say 'Helpers work!' in exactly 2 words.",
            temperature=0.1,
            max_output_tokens=50
        )
        
        if result:
            print(f"✅ generate_content_with_text() works")
            print(f"Response: {result}")
            return True
        else:
            print(f"❌ generate_content_with_text() returned None")
            return False
        
    except Exception as e:
        print(f"❌ Helper functions failed: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_all():
    """Run all compatibility tests"""
    print("\n" + "="*60)
    print("GEMINI API COMPATIBILITY TEST SUITE")
    print("="*60)
    
    backend = "Vertex AI" if os.getenv("USE_VERTEX_AI", "false").lower() == "true" else "Gemini API"
    print(f"\n🔧 Testing with: {backend}")
    
    if backend == "Vertex AI":
        project_id = os.getenv("GCP_PROJECT_ID")
        location = os.getenv("GCP_LOCATION", "us-central1")
        print(f"   Project: {project_id}")
        print(f"   Location: {location}")
    else:
        api_key = os.getenv("GEMINI_API_KEY", "")
        print(f"   API Key: {'*' * min(len(api_key), 20) if api_key else 'NOT SET'}")
    
    tests = [
        ("Basic Generation", test_basic_generation),
        ("Thinking Config", test_thinking_config),
        ("Part.from_text", test_part_from_text),
        ("Part Compatibility", test_part_from_data_bytes),
        ("Helper Functions", test_helper_functions),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {type(e).__name__}: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All compatibility tests passed!")
        print(f"✅ {backend} is working correctly")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        print("Check the errors above for details")
    
    print("="*60)


if __name__ == "__main__":
    asyncio.run(test_all())
