"""
Example: Testing LLM Request/Response Logging

This script demonstrates the LLM logging functionality by making
test API calls and showing the logged output.
"""

import os
import sys

# Ensure backend module is found
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Set up environment for testing
os.environ["LLM_LOG_CONSOLE"] = "true"
os.environ["LLM_LOG_MAX_PROMPT_LENGTH"] = "200"
os.environ["LLM_LOG_MAX_RESPONSE_LENGTH"] = "500"

from app.core.logging import setup_logging
from app.services.infrastructure.llm.gemini.client import UnifiedGeminiClient, GenerationConfig

def main():
    print("=" * 60)
    print("LLM Request/Response Logging Test")
    print("=" * 60)
    print()
    
    # Set up logging
    setup_logging(level="INFO", use_json=False)
    
    # Create client
    print("🔧 Initializing UnifiedGeminiClient...")
    client = UnifiedGeminiClient()
    print("✅ Client initialized with automatic logging enabled!\n")
    
    # Test 1: Simple request
    print("-" * 60)
    print("Test 1: Simple Text Generation")
    print("-" * 60)
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="What is the capital of France? Answer in one sentence.",
            config=GenerationConfig(
                temperature=0.7,
                max_output_tokens=100
            )
        )
        print(f"\n📝 Response: {response.text}\n")
    except Exception as e:
        print(f"❌ Error: {e}\n")
    
    # Test 2: Longer prompt (to test truncation)
    print("-" * 60)
    print("Test 2: Long Prompt (Testing Truncation)")
    print("-" * 60)
    
    long_prompt = """
    Please explain the concept of machine learning in detail, including:
    1. What is machine learning?
    2. What are the main types of machine learning?
    3. How does supervised learning work?
    4. What are some real-world applications?
    5. What are the challenges in implementing ML systems?
    
    This is a longer prompt to demonstrate the truncation feature of the logger.
    The logger should truncate the prompt to the configured max length and show
    how many total characters were in the original prompt.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=long_prompt.strip(),
            config=GenerationConfig(temperature=0.5)
        )
        print(f"\n📝 Response (first 200 chars): {response.text[:200]}...\n")
    except Exception as e:
        print(f"❌ Error: {e}\n")
    
    # Test 3: Request with error (simulate with invalid model)
    print("-" * 60)
    print("Test 3: Error Handling")
    print("-" * 60)
    
    try:
        response = client.models.generate_content(
            model="invalid-model-name-12345",
            contents="This should fail"
        )
    except Exception as e:
        print(f"❌ Expected error occurred: {type(e).__name__}\n")
        print("✅ Error was logged successfully!\n")
    
    print("=" * 60)
    print("Test Complete!")
    print("=" * 60)
    print()
    print("📊 Check the logs above to see:")
    print("  • Request logging (model, prompt length, config)")
    print("  • Response logging (duration, response length)")
    print("  • Error logging (when requests fail)")
    print()
    print("💡 Tips:")
    print("  - Set LLM_LOG_FILE to save logs to a file")
    print("  - Adjust LLM_LOG_MAX_PROMPT_LENGTH for more/less detail")
    print("  - Use LLM_LOG_CONSOLE=false to disable console output")
    print()

if __name__ == "__main__":
    main()
