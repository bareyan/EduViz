
import asyncio
import os
import sys

# Ensure backend module is found
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # Should be EduViz
sys.path.append(current_dir) 

from app.services.infrastructure.llm.prompting_engine.base_engine import PromptingEngine, PromptConfig
from app.services.pipeline.animation.generation.tools.generation import GenerationToolHandler
from app.services.pipeline.animation.generation.tools.code_manipulation import extract_code_from_response
from app.services.pipeline.animation.generation.validation.code_validator import CodeValidator

async def main():
    print("--- Starting Agentic Loop Test ---")
    
    # 1. Initialize Engine
    # Using a model that supports tools well, e.g., gemini-2.0-flash-exp or similar valid model
    # relying on default config or env vars
    engine = PromptingEngine()
    validator = CodeValidator()
    
    # 2. Initialize Handler
    handler = GenerationToolHandler(engine, validator)
    
    # 3. Define a Request
    section = {
        "title": "Introduction to Limits",
        "narration": "A limit tells us the value that a function approaches as that function's inputs get closer and closer to some number.",
        "content": "Visualizing the limit of (x^2 - 1) / (x - 1) as x approaches 1."
    }
    
    print(f"Request: {section['title']}")
    
    # 4. Run Generation
    # We enable thinking manually in the config passed to run_loop via generate
    # But GenerationToolHandler.generate creates its own config or uses defaults.
    # checking generation.py: it creates PromptConfig with enable_thinking=True (or I should check) which is fine.
    # Actually, let's verify if we need to pass specific config.
    
    # The handler's generate method uses:
    # config=PromptConfig(
    #     temperature=BASE_GENERATION_TEMPERATURE, # 0.7
    #     stop_sequences=["```"],
    #     max_tokens=4096,
    #     enable_thinking=True # Copied from my memory of the file, let's hope it's there or default
    # )
    
    result = await handler.generate(
        section=section,
        style="3b1b",
        target_duration=10.0
    )
    
    print("\n--- Generation Result ---")
    print(f"Success: {result.success}")
    print(f"Iterations: {result.iterations}")
    
    if result.feedback_history:
        print("\n--- Feedback History ---")
        for i, feedback in enumerate(result.feedback_history):
            print(f"[{i+1}] {feedback}")
            
    if result.code:
        print("\n--- Generated Code ---")
        print(result.code[:500] + "...\n(truncated)")
    else:
        print("\nNo code generated.")
        if result.error:
            print(f"Error: {result.error}")

if __name__ == "__main__":
    asyncio.run(main())
