"""
Tool-based code generation with iterative validation

Handles the function calling loop for code generation:
1. Model generates code
2. Automatically validates (syntax, structure, imports, spatial)
3. Model sees validation results
4. Model applies fixes if needed
5. Re-validates after each fix
6. Returns when code passes all checks or max attempts reached

Single Responsibility: Execute tool-based generation loop with validation feedback.
"""

import asyncio
from typing import Dict, Any, Optional, Tuple

from .tools import ToolExecutor, MANIM_TOOLS, extract_code_from_response
from .code_helpers import clean_code


class ToolBasedGenerator:
    """
    Handles iterative code generation using function calling tools.
    
    The model:
    - Generates code
    - Calls validate_code to check it
    - Sees validation results (syntax, structure, imports, spatial)
    - Calls apply_fix to correct issues
    - Re-validates after each fix
    - Calls finalize_code when all checks pass
    """
    
    def __init__(self, client, cost_tracker):
        """
        Initialize tool-based generator.
        
        Args:
            client: Gemini client for API calls
            cost_tracker: Cost tracker instance
        """
        self.client = client
        self.cost_tracker = cost_tracker
        self.tool_executor = ToolExecutor()
    
    async def generate_with_validation(
        self,
        prompt: str,
        model: str,
        max_iterations: int = 5,
        config: Optional[Any] = None
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Generate code using function calling with iterative validation.
        
        Flow:
        1. Model generates code
        2. Model calls validate_code → sees validation results
        3. If invalid, model calls apply_fix → sees fix result
        4. Model calls validate_code again → sees new validation results
        5. Repeat steps 3-4 until valid or max_iterations
        6. Model calls finalize_code when satisfied
        
        Args:
            prompt: Code generation prompt
            model: Model name to use
            max_iterations: Maximum tool call iterations
            config: Generation config (optional)
            
        Returns:
            Tuple of (final_code, validation_dict) or (None, {}) on failure
        """
        print(f"[ToolGenerator] Starting generation with validation feedback (max {max_iterations} iterations)...")
        
        # System instruction that explains the workflow
        system_instruction = """You are a Manim code generator.

YOUR WORKFLOW:
1. Generate the Manim code for the prompt
2. Call create_code(code) to submit it
   → System validates and returns: {syntax, structure, imports, spatial}
3. READ the validation results carefully
4. If ANY check fails (valid=false):
   - Analyze the specific error messages
   - Call apply_fix(code, search, replace, reason) to correct it
   → System validates the fix and returns new validation results
5. READ the new validation results
6. Repeat step 4-5 until ALL checks pass (valid=true)
7. Stop when validation shows valid=true

IMPORTANT:
- ALWAYS call create_code first to submit your generated code
- Read validation feedback carefully - it shows exactly what's wrong
- Use exact search/replace in apply_fix (search must be unique)
- Keep applying fixes until all 4 checks pass

Available tools:
- create_code(code): Submit generated code and get validation results
- apply_fix(code, search, replace, reason): Fix code and get new validation results"""

        # Prepare conversation
        conversation = [system_instruction, prompt]
        
        current_code = None
        iteration = 0
        last_validation = {}
        
        while iteration < max_iterations:
            iteration += 1
            print(f"[ToolGenerator] Iteration {iteration}/{max_iterations}...")
            
            try:
                # Call model with tools enabled
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=model,
                    contents=conversation,
                    tools=MANIM_TOOLS,
                    config=config if iteration == 1 else None
                )
                
                self.cost_tracker.track_usage(response, model)
                
                # Process response
                if not hasattr(response.candidates[0].content, 'parts'):
                    print("[ToolGenerator] No response parts, stopping")
                    break
                
                for part in response.candidates[0].content.parts:
                    # Handle function call (create_code or apply_fix)
                    if hasattr(part, 'function_call') and part.function_call:
                        func_call = part.function_call
                        tool_name = func_call.name
                        
                        # Extract parameters
                        params = {}
                        if hasattr(func_call, 'args'):
                            params = dict(func_call.args)
                        
                        print(f"[ToolGenerator] Model called: {tool_name}")
                        
                        # Execute tool
                        tool_result = self.tool_executor.execute(tool_name, params)
                        
                        # Handle create_code tool
                        if tool_name == "create_code":
                            current_code = params.get("code", "")
                            last_validation = tool_result
                            is_valid = tool_result.get("valid", False)
                            
                            print(f"[ToolGenerator] Code created, validation: {'✓ PASS' if is_valid else '✗ FAIL'}")
                            
                            if not is_valid:
                                failures = []
                                if not tool_result["syntax"]["valid"]:
                                    failures.append(f"Syntax: {tool_result['syntax']['error_message']}")
                                if tool_result["structure"]["errors"]:
                                    failures.append(f"Structure: {tool_result['structure']['errors'][:2]}")
                                if tool_result["imports"]["missing_imports"]:
                                    failures.append(f"Missing: {tool_result['imports']['missing_imports']}")
                                if not tool_result["spatial"]["valid"]:
                                    spatial_errs = tool_result['spatial']['errors']
                                    failures.append(f"Spatial: {len(spatial_errs)} error(s)")
                                
                                for fail in failures:
                                    print(f"  ✗ {fail}")
                            else:
                                # Valid! We're done
                                print(f"[ToolGenerator] ✓ All checks passed, stopping")
                                return (current_code, last_validation)
                        
                        # Handle apply_fix tool
                        elif tool_name == "apply_fix":
                            if tool_result.get("success"):
                                # Get validation results from the fix
                                last_validation = tool_result["validation"]
                                is_valid = last_validation.get("valid", False)
                                
                                print(f"[ToolGenerator] Fix applied: {tool_result.get('reason', 'N/A')}")
                                print(f"[ToolGenerator] Auto-validation: {'✓ PASS' if is_valid else '✗ FAIL'}")
                                
                                # Extract code from params (it's in the function call)
                                current_code = params.get("code", "")
                                
                                # Apply the fix to get new code
                                from .tools import apply_search_replace
                                _, new_code, _ = apply_search_replace(
                                    current_code,
                                    params.get("search", ""),
                                    params.get("replace", "")
                                )
                                current_code = new_code
                                
                                if not is_valid:
                                    # Show what's still wrong
                                    failures = []
                                    if not last_validation["syntax"]["valid"]:
                                        failures.append(f"Syntax: {last_validation['syntax']['error_message']}")
                                    if last_validation["structure"]["errors"]:
                                        failures.append(f"Structure: {last_validation['structure']['errors'][:2]}")
                                    if last_validation["imports"]["missing_imports"]:
                                        failures.append(f"Missing: {last_validation['imports']['missing_imports']}")
                                    if not last_validation["spatial"]["valid"]:
                                        spatial_errs = last_validation['spatial']['errors']
                                        failures.append(f"Spatial: {len(spatial_errs)} error(s)")
                                    
                                    for fail in failures:
                                        print(f"  ✗ {fail}")
                                else:
                                    # Valid! We're done
                                    print(f"[ToolGenerator] ✓ All checks passed, stopping")
                                    return (current_code, last_validation)
                            else:
                                print(f"[ToolGenerator] ✗ Fix failed: {tool_result.get('error', 'Unknown')}")
                        
                        # Add to conversation history
                        conversation.append({
                            "role": "model",
                            "parts": [{"function_call": func_call}]
                        })
                        conversation.append({
                            "role": "user",
                            "parts": [{
                                "function_response": {
                                    "name": tool_name,
                                    "response": tool_result
                                }
                            }]
                        })
                        
                        break  # Continue to next iteration
                    
                    # Handle text response (fallback - shouldn't happen with tools)
                    elif hasattr(part, 'text') and part.text:
                        text = part.text
                        print(f"[ToolGenerator] Model returned text: {text[:100]}...")
                        
                        # Try to extract code
                        if "```python" in text or "```" in text:
                            code = extract_code_from_response(text)
                            code = clean_code(code)
                            
                            # Validate manually
                            validation = self.tool_executor.validator.validate(code)
                            if validation.valid:
                                print(f"[ToolGenerator] ✓ Extracted code is valid")
                                return (code, validation.to_dict())
                            else:
                                print(f"[ToolGenerator] ✗ Extracted code has issues")
                                current_code = code
                                last_validation = validation.to_dict()
                        break
                
            except asyncio.TimeoutError:
                print(f"[ToolGenerator] Iteration {iteration} timed out")
                break
            except Exception as e:
                print(f"[ToolGenerator] Error: {e}")
                break
        
        # Max iterations reached - return best code we have
        if current_code:
            validation = self.tool_executor.validator.validate(current_code)
            is_valid = validation.valid
            print(f"[ToolGenerator] Max iterations reached. Code valid: {is_valid}")
            return (current_code, validation.to_dict())
        
        print("[ToolGenerator] Failed to generate valid code")
        return (None, {})
