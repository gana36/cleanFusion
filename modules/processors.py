"""
Multi-step LLM processing and orchestration functions
"""
import json
import time
import re
from typing import Dict, Any, Optional, Tuple, List
from modules.config import *
from modules.models import *
from modules.llm_client import *
from modules.pricing import *
import modules.parsers
from modules.parsers import clean_llm_json_response
from modules.prompts import PROMPT_TEMPLATES

# ============================================================================
# VALUE PARSING AND AGGREGATION UTILITIES
# ============================================================================

def extract_numeric_value(value_str: str) -> Tuple[Optional[float], Optional[float], str]:
    """
    Extract numeric values from various formats commonly found in medical/statistical tables.

    Returns:
        Tuple of (primary_value, secondary_value, format_type)
        - primary_value: Main numeric value (mean, count, etc.)
        - secondary_value: Secondary value (SD, percentage, etc.) or None
        - format_type: 'mean_sd', 'count_percent', 'comparison', 'simple', 'non_numeric'

    Examples:
        "74.0±8.1" -> (74.0, 8.1, 'mean_sd')
        "28(80.0)" -> (28.0, 80.0, 'count_percent')
        "<0.001" -> (0.001, None, 'comparison')
        "0.043" -> (0.043, None, 'simple')
        "Yes" -> (None, None, 'non_numeric')
    """
    if not value_str or not isinstance(value_str, str):
        return None, None, 'non_numeric'

    value_str = value_str.strip()

    # Pattern 1: Mean ± SD format (e.g., "74.0±8.1", "70.5±10.1", "22.7±4.6")
    mean_sd_pattern = r'^([\d.]+)\s*[±\+\-]\s*([\d.]+)$'
    match = re.match(mean_sd_pattern, value_str)
    if match:
        try:
            return float(match.group(1)), float(match.group(2)), 'mean_sd'
        except ValueError:
            pass

    # Pattern 2: Count with percentage (e.g., "28(80.0)", "189(50.1)", "32 (66.7)")
    count_percent_pattern = r'^([\d.]+)\s*\(\s*([\d.]+)\s*\)$'
    match = re.match(count_percent_pattern, value_str)
    if match:
        try:
            return float(match.group(1)), float(match.group(2)), 'count_percent'
        except ValueError:
            pass

    # Pattern 3: Comparison operators (e.g., "<0.001", ">0.05", "≤0.01")
    comparison_pattern = r'^[<>≤≥]\s*([\d.]+)$'
    match = re.match(comparison_pattern, value_str)
    if match:
        try:
            return float(match.group(1)), None, 'comparison'
        except ValueError:
            pass

    # Pattern 4: Simple numeric (e.g., "0.043", "123", "45.67")
    simple_pattern = r'^([\d.]+)$'
    match = re.match(simple_pattern, value_str)
    if match:
        try:
            return float(match.group(1)), None, 'simple'
        except ValueError:
            pass

    # Non-numeric value
    return None, None, 'non_numeric'


def is_numeric_value(value_str: str) -> bool:
    """Check if a value string contains numeric data."""
    primary, _, format_type = extract_numeric_value(value_str)
    return format_type != 'non_numeric'


def aggregate_values(value1: str, value2: str, strategy: str) -> str:
    """
    Aggregate two values based on the specified strategy.
    Only aggregates when BOTH values are present and numeric.

    Args:
        value1: First value (from source1/t1)
        value2: Second value (from source2/t2)
        strategy: 'average', 'range', or 'delimited'

    Returns:
        Aggregated value string, or None if aggregation should not be applied
    """
    # Handle empty values - return None to indicate no aggregation
    if not value1 and not value2:
        return None
    if not value1 or not value2:
        # Only one value present - don't aggregate, return None
        return None

    # For delimited strategy, always return both values
    if strategy == 'delimited':
        return f"{value1} | {value2}"

    # Extract numeric values
    primary1, secondary1, format1 = extract_numeric_value(value1)
    primary2, secondary2, format2 = extract_numeric_value(value2)

    # If either value is non-numeric, fall back to delimited
    if format1 == 'non_numeric' or format2 == 'non_numeric':
        return f"{value1} | {value2}"

    # Handle different format combinations
    if strategy == 'average':
        return _compute_average(primary1, secondary1, format1, primary2, secondary2, format2)
    elif strategy == 'range':
        return _compute_range(primary1, secondary1, format1, primary2, secondary2, format2)

    # Default to delimited
    return f"{value1} | {value2}"


def _compute_average(p1: float, s1: Optional[float], f1: str,
                     p2: float, s2: Optional[float], f2: str) -> str:
    """Compute average of two numeric values."""

    # Same format types
    if f1 == f2:
        if f1 == 'mean_sd':
            # Average the means, combine SDs using root mean square
            avg_mean = (p1 + p2) / 2
            if s1 is not None and s2 is not None:
                combined_sd = ((s1**2 + s2**2) / 2) ** 0.5
                return f"{avg_mean:.1f}±{combined_sd:.1f}"
            return f"{avg_mean:.1f}"

        elif f1 == 'count_percent':
            # Average both count and percentage
            avg_count = (p1 + p2) / 2
            if s1 is not None and s2 is not None:
                avg_percent = (s1 + s2) / 2
                return f"{avg_count:.0f}({avg_percent:.1f})"
            return f"{avg_count:.0f}"

        elif f1 in ['simple', 'comparison']:
            # Simple average
            avg = (p1 + p2) / 2
            # Preserve precision
            if avg == int(avg):
                return f"{int(avg)}"
            elif avg < 0.01:
                return f"{avg:.3f}"
            else:
                return f"{avg:.2f}"

    # Different format types - average the primary values
    avg = (p1 + p2) / 2
    if avg == int(avg):
        return f"{int(avg)}"
    elif avg < 0.01:
        return f"{avg:.3f}"
    else:
        return f"{avg:.2f}"


def _compute_range(p1: float, s1: Optional[float], f1: str,
                   p2: float, s2: Optional[float], f2: str) -> str:
    """Compute range of two numeric values."""

    # Same format types
    if f1 == f2:
        if f1 == 'mean_sd':
            # Show range of means
            min_val, max_val = min(p1, p2), max(p1, p2)
            return f"{min_val:.1f}-{max_val:.1f}"

        elif f1 == 'count_percent':
            # Show range of counts (and optionally percentages)
            min_count, max_count = min(p1, p2), max(p1, p2)
            if s1 is not None and s2 is not None:
                min_pct, max_pct = min(s1, s2), max(s1, s2)
                return f"{min_count:.0f}-{max_count:.0f} ({min_pct:.1f}-{max_pct:.1f})"
            return f"{min_count:.0f}-{max_count:.0f}"

        elif f1 in ['simple', 'comparison']:
            min_val, max_val = min(p1, p2), max(p1, p2)
            if min_val == int(min_val) and max_val == int(max_val):
                return f"{int(min_val)}-{int(max_val)}"
            elif min_val < 0.01 or max_val < 0.01:
                return f"{min_val:.3f}-{max_val:.3f}"
            else:
                return f"{min_val:.2f}-{max_val:.2f}"

    # Different format types - range of primary values
    min_val, max_val = min(p1, p2), max(p1, p2)
    if min_val == int(min_val) and max_val == int(max_val):
        return f"{int(min_val)}-{int(max_val)}"
    else:
        return f"{min_val:.2f}-{max_val:.2f}"


def apply_merge_value_strategy(result_data: Dict[str, Any], strategy: str) -> Dict[str, Any]:
    """
    Apply merge value strategy to the Merged_Data in the result.

    This function post-processes the LLM output to aggregate values
    based on the user's selected strategy (average, range, or delimited).

    Args:
        result_data: The result dictionary containing Merged_Data
        strategy: 'average', 'range', or 'delimited'

    Returns:
        Modified result_data with aggregated values
    """
    if strategy == 'delimited':
        # Default behavior - no aggregation needed
        return result_data

    if 'Merged_Data' not in result_data:
        return result_data

    merged_data = result_data.get('Merged_Data', [])

    # Handle list format (complex schemas)
    if isinstance(merged_data, list):
        for hmd_entry in merged_data:
            if not isinstance(hmd_entry, dict):
                continue

            for hmd_col, hmd_content in hmd_entry.items():
                if not isinstance(hmd_content, dict):
                    continue

                vmd_data = hmd_content.get('VMD_data', [])
                if not isinstance(vmd_data, list):
                    continue

                for vmd_entry in vmd_data:
                    if not isinstance(vmd_entry, dict):
                        continue

                    for vmd_row, vmd_values in vmd_entry.items():
                        if not isinstance(vmd_values, dict):
                            continue

                        source1_val = vmd_values.get('source1', '')
                        source2_val = vmd_values.get('source2', '')

                        # Apply aggregation strategy
                        aggregated = aggregate_values(source1_val, source2_val, strategy)

                        # Store aggregated value
                        vmd_values['aggregated'] = aggregated
                        vmd_values['strategy'] = strategy

    # Handle dict format (relational schemas)
    elif isinstance(merged_data, dict):
        for key, value in merged_data.items():
            if isinstance(value, dict) and 'source' in value and 'target' in value:
                source_val = value.get('source', '')
                target_val = value.get('target', '')
                aggregated = aggregate_values(source_val, target_val, strategy)
                value['aggregated'] = aggregated
                value['strategy'] = strategy

    result_data['Merged_Data'] = merged_data
    result_data['merge_value_strategy'] = strategy

    return result_data

def process_multi_step(source_schema, target_schema, schema_type, operation_type, llm_model="llama-3.1-8b-instant", 
                      max_tokens=None, temperature=None, top_p=None, frequency_penalty=None, presence_penalty=None, pre_approved_match_result=None,
                      use_merge_multi_step=False, merge_value_strategy="delimited"):
    """Multi-step processing: For MATCH: 3 independent match calls + ensemble. For MERGE: Should receive match results."""

    # If this is a merge operation, we shouldn't be doing multi-step here
    if operation_type in ["merge", "instance_merge"]:
        print(f"[WARNING] Multi-step {operation_type} should receive match results, falling back to normal merge")
        return process_with_llm_enhanced(source_schema, target_schema, schema_type, "operator", operation_type, llm_model,
                                       max_tokens, temperature, top_p, frequency_penalty, presence_penalty,
                                       use_merge_multi_step=use_merge_multi_step, match_operation="operator", matching_method="json_default",
                                       pre_approved_match_result=pre_approved_match_result, merge_value_strategy=merge_value_strategy)

    print(f"[MULTI] Starting multi-step {operation_type} processing (3 calls + 1 ensemble)")
    
    # Generate unique ID for tracking
    script_id = str(uuid.uuid4())
    timestamp = datetime.datetime.now().isoformat()
    
    # Track timing for all steps
    total_start_time = time.time()
    
    responses = []
    individual_times = []
    
    # Step 1-3: Make 3 independent calls using operator prompts
    for step in range(1, 4):
        print(f"   Step {step}/3: Independent {operation_type} call")
        step_start_time = time.time()
        
        # Add cooldown between calls to avoid rate limiting
        if step > 1:
            cooldown_time = 1.0  # 1 second cooldown between calls
            print(f"   [WAIT]  Cooldown: {cooldown_time}s before next call")
            time.sleep(cooldown_time)
        
        try:
            # Use operator processing type for individual calls - MATCH ONLY
            result = process_with_llm_enhanced(source_schema, target_schema, schema_type, "operator", operation_type, llm_model,
                                             max_tokens, temperature, top_p, frequency_penalty, presence_penalty,
                                             use_merge_multi_step=False, match_operation="operator", matching_method="json_default")
            
            step_end_time = time.time()
            step_time = step_end_time - step_start_time
            individual_times.append(step_time)
            
            if result["success"]:
                responses.append(result["raw_response"])
                print(f"   [OK] Step {step} completed in {step_time:.2f}s")
            else:
                print(f"   ❌ Step {step} failed: {result.get('error', 'Unknown error')}")
                # Continue with other steps even if one fails
                responses.append("{}")
                
        except Exception as e:
            print(f"   ❌ Step {step} failed with exception: {str(e)}")
            responses.append("{}")
            individual_times.append(0.0)
    
    # For multi-step match: NO ensemble, just return the 3 independent results
    total_time = time.time() - total_start_time
    print(f"[DONE] Multi-step {operation_type} processing completed in {total_time:.2f}s total")
    print(f"   📊 Collected {len(responses)} independent {operation_type} results")

    # Parse all responses to JSON objects for storage
    parsed_responses = []
    valid_count = 0
    for i, response in enumerate(responses):
        if response and response != "{}":
            try:
                parsed_result = json.loads(clean_llm_json_response(response))
                parsed_responses.append(parsed_result)
                valid_count += 1
                print(f"   ✓ Response {i+1}: Valid {operation_type} result")
            except json.JSONDecodeError as e:
                print(f"   ⚠ Response {i+1}: Failed to parse - {str(e)}")
                parsed_responses.append({})
        else:
            print(f"   ✗ Response {i+1}: Empty or invalid response")
            parsed_responses.append({})

    if valid_count == 0:
        return {
            "success": False,
            "error": f"Multi-step {operation_type} processing failed: All responses were invalid"
        }

    try:
        # Create result data structure with the 3 individual responses
        result_data = {
            "multi_step_results": parsed_responses,
            "valid_responses_count": valid_count,
            "total_responses_count": len(responses)
        }

        # Add aggregated summary for compatibility (use first valid response as main result)
        main_result = next((resp for resp in parsed_responses if resp), {})
        if main_result:
            result_data.update(main_result)

        # Generate pipeline description for multi-step
        pipeline_description = generate_pipeline_description(
            operation_type=operation_type,
            match_operation="operator",  # Multi-step uses operator by default
            matching_method="json_default",  # Multi-step uses json_default by default
            matching_llm=llm_model,
            merge_operation=None,  # Multi-step match doesn't have merge
            merge_method=None,
            merge_llm=None,
            processing_type="multi_step"
        )

        # Calculate metrics
        metrics_data = {
            "script_id": script_id,
            "timestamp": timestamp,
            "llm_model": llm_model,
            "schema_type": "complex" if schema_type == "complex" else "relational",
            "processing_type": "multi_step",
            "operation_type": operation_type,
            "total_generation_time": round(total_time, 4),
            "preprocessing_time": 0.0,
            "match_generation_time": round(sum(individual_times), 4) if operation_type == "match" else 0.0,
            "merge_generation_time": round(sum(individual_times), 4) if operation_type == "merge" else 0.0,
            "multi_step_times": individual_times,
            "valid_responses_count": valid_count,
            "total_responses_count": len(responses),
            "pipeline_description": pipeline_description
        }
        # Add token information - sum from all individual calls (note: responses are raw strings, no usage info)
        # For multi-step, we estimate total tokens since individual API responses aren't stored
        total_prompt_chars = sum(len(source_schema) + len(target_schema) for _ in responses)
        total_response_chars = sum(len(str(resp)) for resp in responses)

        # Estimate tokens using provider-specific methods
        estimated_prompt_tokens = estimate_tokens_by_provider(source_schema + target_schema, llm_model) * len(responses)
        estimated_completion_tokens = sum(estimate_tokens_by_provider(str(resp), llm_model) for resp in responses)

        prompt_tokens = estimated_prompt_tokens
        completion_tokens = estimated_completion_tokens
        total_tokens = prompt_tokens + completion_tokens

        metrics_data.update({
            "input_prompt_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "tokens_per_second": round(completion_tokens / total_time, 2) if total_time > 0 else 0,
            "api_call_cost": calculate_api_cost(llm_model, prompt_tokens, completion_tokens)
        })

        # Add match counts (aggregate from all responses)
        if operation_type == "match":
            if schema_type == "complex":
                total_hmd = sum(len(resp.get('HMD_matches', [])) for resp in parsed_responses if resp)
                total_vmd = sum(len(resp.get('VMD_matches', [])) for resp in parsed_responses if resp)
                metrics_data["hmd_matches"] = total_hmd
                metrics_data["vmd_matches"] = total_vmd
                metrics_data["total_matches"] = total_hmd + total_vmd
            else:
                total_matches = sum(len(resp.get('column_matches', [])) for resp in parsed_responses if resp)
                metrics_data["total_matches"] = total_matches
        else:  # merge or instance_merge
            metrics_data["total_matches"] = 0

        return {
            "success": True,
            "data": result_data,
            "metrics": metrics_data,
            "raw_response": str(parsed_responses),  # All responses as string
            "match_result": None,
            "multi_step_results": parsed_responses  # Store all 3 individual results
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Multi-step processing failed: {str(e)}",
            "raw_response": str(responses)
        }

def process_multi_step_merge_with_responses(source_schema, target_schema, schema_type, operation_type, llm_model,
                                          replicated_responses, max_tokens=None, temperature=None, top_p=None,
                                          frequency_penalty=None, presence_penalty=None, merge_value_strategy="delimited"):
    """Process multi-step merge using replicated match responses for ensemble processing"""

    print("[AUTO] Starting multi-step merge processing with replicated match responses")

    # Generate unique ID for tracking
    script_id = str(uuid.uuid4())
    timestamp = datetime.datetime.now().isoformat()

    # Track timing for merge processing
    total_start_time = time.time()

    print(f"[INFO] Using {len(replicated_responses)} replicated responses for ensemble merge")

    # Step: Ensemble aggregation using replicated responses
    print("   Step 1/1: Ensemble merge aggregation")

    ensemble_start_time = time.time()

    try:
        # Get the ensemble prompt for merge operations
        ensemble_prompt = PROMPT_TEMPLATES["complex"]["operator"]["multi_step"]["ensemble"]

        # Format the ensemble prompt with the 3 replicated responses
        try:
            if ensemble_prompt is None:
                return {"success": False, "error": "Ensemble prompt is None for replicated responses"}
            formatted_prompt = ensemble_prompt.replace("{response1}", replicated_responses[0] if len(replicated_responses) > 0 else "{}")
            formatted_prompt = formatted_prompt.replace("{response2}", replicated_responses[1] if len(replicated_responses) > 1 else "{}")
            formatted_prompt = formatted_prompt.replace("{response3}", replicated_responses[2] if len(replicated_responses) > 2 else "{}")
        except Exception as e:
            return {"success": False, "error": f"Error formatting replicated ensemble prompt: {str(e)}"}

        # Make the ensemble call
        ensemble_response = get_llm_response(formatted_prompt, llm_model, max_tokens=max_tokens, temperature=temperature,
                                           top_p=top_p, frequency_penalty=frequency_penalty, presence_penalty=presence_penalty, custom_clients=custom_clients)

        ensemble_end_time = time.time()
        ensemble_time = ensemble_end_time - ensemble_start_time
        total_time = time.time() - total_start_time

        print(f"   [OK] Ensemble merge aggregation completed in {ensemble_time:.2f}s")
        print(f"[DONE] Multi-step merge processing completed in {total_time:.2f}s total")

        # Parse the ensemble response
        raw_response = ensemble_response.choices[0].message.content.strip()
        cleaned_response = clean_llm_json_response(raw_response)

    except Exception as e:
        print(f"   [ERROR] Ensemble merge call failed: {str(e)}")
        return {
            "success": False,
            "error": f"Multi-step merge ensemble processing failed: {str(e)}"
        }

    try:
        result_data = json.loads(cleaned_response)

        # Add missing keys for merge operations
        if 'Merged_Schema' not in result_data:
            result_data['Merged_Schema'] = []
        if 'Merged_Data' not in result_data:
            result_data['Merged_Data'] = []
        if 'Map_Schema1' not in result_data:
            result_data['Map_Schema1'] = []
        if 'Map_Schema2' not in result_data:
            result_data['Map_Schema2'] = []

        # Repair Merged_Data structure for complex instance merges
        if schema_type == "complex" and operation_type == "instance_merge":
            print("[VALIDATION] Repairing Merged_Data structure for multi-step complex instance merge...")
            result_data = repair_merged_data_structure(result_data)
            print("[VALIDATION] Repairing mapping schemas...")
            result_data = repair_mapping_schema(result_data)

        # Calculate metrics
        metrics_data = {
            "script_id": script_id,
            "operation_type": operation_type,
            "llm_model": llm_model,
            "merge_time": total_time,
            "ensemble_time": ensemble_time,
            "processing_steps": 1,
            "timestamp": timestamp,
            "replicated_responses_count": len(replicated_responses)
        }

        # Add token usage using accurate provider-specific extraction
        prompt_tokens, completion_tokens = extract_token_usage(ensemble_response, llm_model)
        total_tokens = prompt_tokens + completion_tokens

        if total_tokens > 0:

            metrics_data.update({
                "input_prompt_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "tokens_per_second": round(completion_tokens / total_time, 2) if total_time > 0 else 0,
                "api_call_cost": calculate_api_cost(llm_model, prompt_tokens, completion_tokens)
            })

        # Set match count to 0 for merge operations
        metrics_data["total_matches"] = 0

        # Apply merge value strategy for merge operations
        if merge_value_strategy != 'delimited':
            print(f"[POST-PROCESS] Applying merge value strategy: {merge_value_strategy}")
            result_data = apply_merge_value_strategy(result_data, merge_value_strategy)

        return {
            "success": True,
            "data": result_data,
            "metrics": metrics_data,
            "raw_response": raw_response,
            "match_result": None,
            "replicated_responses": replicated_responses  # Include replicated responses for debugging
        }

    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"JSON parsing error in ensemble merge result: {str(e)}",
            "raw_response": raw_response
        }

def process_with_llm_enhanced(source_schema, target_schema, schema_type, processing_type, operation_type, llm_model="llama-3.1-8b-instant",
                            max_tokens=None, temperature=None, top_p=None, frequency_penalty=None, presence_penalty=None, use_merge_multi_step=False,
                            match_operation="baseline", matching_method="json_default", merge_method=None, matching_llm=None, merge_llm=None, user_api_keys=None,
                            merge_value_strategy="delimited", pre_approved_match_result=None, previous_match_metrics=None):
    """Enhanced LLM processing with hierarchical output and metrics and configurable parameters"""


    # Set default merge_method if not provided
    if merge_method is None:
        merge_method = matching_method

    # Set default LLM models if not provided
    if matching_llm is None:
        matching_llm = llm_model
    if merge_llm is None:
        merge_llm = matching_llm

    # Auto-optimize parameters for schema matching tasks
    if operation_type == "match" and (temperature is None and top_p is None):
        print("[AUTO] Auto-applying schema_matching preset for optimal mapping decisions")
        optimized_params = apply_llm_preset("schema_matching")
        max_tokens = max_tokens or optimized_params["max_tokens"]
        temperature = optimized_params["temperature"]
        top_p = optimized_params["top_p"]
        frequency_penalty = optimized_params["frequency_penalty"]
        presence_penalty = optimized_params["presence_penalty"]
    else:
        # Use default parameters if not specified
        max_tokens = max_tokens or DEFAULT_LLM_PARAMS["max_tokens"]
        temperature = temperature if temperature is not None else DEFAULT_LLM_PARAMS["temperature"]
        top_p = top_p if top_p is not None else DEFAULT_LLM_PARAMS["top_p"]
        frequency_penalty = frequency_penalty if frequency_penalty is not None else DEFAULT_LLM_PARAMS["frequency_penalty"]
        presence_penalty = presence_penalty if presence_penalty is not None else DEFAULT_LLM_PARAMS["presence_penalty"]

    # Initialize LLM clients with user-provided API keys if available
    user_api_keys = user_api_keys or {}
    active_groq_client = client
    active_anthropic_client = anthropic_client
    active_gemini_client = gemini_client

    if user_api_keys.get('groq'):
        try:
            active_groq_client = Groq(api_key=user_api_keys['groq'])
            print("[INFO] Using user-provided Groq API key")
        except Exception as e:
            print(f"[WARNING] Failed to initialize user Groq client: {e}")
            active_groq_client = client

    if user_api_keys.get('anthropic'):
        try:
            active_anthropic_client = Anthropic(api_key=user_api_keys['anthropic'])
            print("[INFO] Using user-provided Anthropic API key")
        except Exception as e:
            print(f"[WARNING] Failed to initialize user Anthropic client: {e}")
            active_anthropic_client = anthropic_client

    if user_api_keys.get('gemini') and GEMINI_AVAILABLE:
        try:
            import google.generativeai as genai
            genai.configure(api_key=user_api_keys['gemini'])
            active_gemini_client = genai
            print("[INFO] Using user-provided Gemini API key")
        except Exception as e:
            print(f"[WARNING] Failed to initialize user Gemini client: {e}")
            active_gemini_client = gemini_client

    # Create custom clients dictionary for passing to get_llm_response
    custom_clients = {
        'groq': active_groq_client,
        'anthropic': active_anthropic_client,
        'gemini': active_gemini_client
    }

    # Check if the appropriate client is available
    if is_gemini_model(llm_model) and not active_gemini_client:
        return {"success": False, "error": "Gemini API not configured. Please set GEMINI_API_KEY environment variable."}
    elif is_claude_model(llm_model) and not active_anthropic_client:
        return {"success": False, "error": "Anthropic API not configured. Please set ANTHROPIC_API_KEY environment variable."}
    elif not is_gemini_model(llm_model) and not is_claude_model(llm_model) and not active_groq_client:
        return {"success": False, "error": "Groq API not configured. Please set GROQ_API_KEY environment variable."}
    custom_clients = {}
    # Generate unique ID for tracking
    script_id = str(uuid.uuid4())
    timestamp = datetime.datetime.now().isoformat()
    
    # Preprocessing time start
    preprocess_start = time.time()
    
    try:
        source_data = json.loads(source_schema)
        target_data = json.loads(target_schema)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON schema: {str(e)}"}
    
    # Determine the actual schema type (complex vs relational)
    actual_schema_type = "complex" if schema_type == "complex" else "relational"
    
    # Get the appropriate prompt template
    if actual_schema_type not in PROMPT_TEMPLATES:
        return {"success": False, "error": f"Unsupported schema type: {actual_schema_type}"}
    
    # Handle multi-step processing separately
    if processing_type == "multi_step":
        return process_multi_step(source_schema, target_schema, schema_type, operation_type, llm_model,
                                max_tokens, temperature, top_p, frequency_penalty, presence_penalty, pre_approved_match_result,
                                use_merge_multi_step, merge_value_strategy)
    
    if match_operation not in PROMPT_TEMPLATES[actual_schema_type]:
        return {"success": False, "error": f"Unsupported match operation: {match_operation}"}

    if matching_method not in PROMPT_TEMPLATES[actual_schema_type][match_operation]:
        return {"success": False, "error": f"Unsupported matching method: {matching_method}"}

    # For merge operations, use merge_method; for match operations, use matching_method
    template_method = merge_method if operation_type in ["merge", "instance_merge"] else matching_method

    if operation_type not in PROMPT_TEMPLATES[actual_schema_type][match_operation][template_method]:
        return {"success": False, "error": f"Unsupported operation type: {operation_type} for method: {template_method}"}

    prompt_template = PROMPT_TEMPLATES[actual_schema_type][match_operation][template_method][operation_type]

    # Debug: Check if prompt_template exists
    if not prompt_template:
        error_msg = f"No prompt template found for: schema_type={actual_schema_type}, match_operation={match_operation}, template_method={template_method}, operation_type={operation_type}"
        print(f"[ERROR] {error_msg}")
        return {"success": False, "error": error_msg}
    
    # Prepare schema data for the prompt
    if actual_schema_type == "complex":
        source_hmd, source_vmd = extract_hmd_vmd_from_schema(source_data)
        target_hmd, target_vmd = extract_hmd_vmd_from_schema(target_data)

        # DEBUG: Log extracted VMD data
        print(f"[DEBUG] Extracted source VMD for LLM ({len(source_vmd)} items): {source_vmd[:5] if len(source_vmd) > 5 else source_vmd}")
        print(f"[DEBUG] Extracted target VMD for LLM ({len(target_vmd)} items): {target_vmd[:5] if len(target_vmd) > 5 else target_vmd}")

        # Wrap HMD/VMD in proper JSON structure expected by the prompt template
        source_schema_formatted = json.dumps({
            "Table1.HMD": source_hmd,
            "Table1.VMD": source_vmd
        }, indent=2)

        target_schema_formatted = json.dumps({
            "Table2.HMD": target_hmd,
            "Table2.VMD": target_vmd
        }, indent=2)

        # Format the prompt with actual schema data
        if operation_type == "match":
            prompt = f"""{prompt_template}

Source Schema (Table1):
{source_schema_formatted}

Target Schema (Table2):
{target_schema_formatted}

Return only the JSON object."""

            # DEBUG: Log prompt snippet to verify VMD is included
            print(f"[DEBUG] Prompt includes {len(source_vmd)} source VMD and {len(target_vmd)} target VMD items")
        else:  # merge or instance_merge
            prompt = f"""{prompt_template}

Source Schema (Table1):
{source_schema_formatted}

Target Schema (Table2):
{target_schema_formatted}

Return only the JSON object."""
    else:  # relational
        if operation_type == "match":
            prompt = f"""{prompt_template}

Source Schema: {source_schema}
Target Schema: {target_schema}

Return only the JSON object."""
        else:  # merge or instance_merge
            prompt = f"""{prompt_template}

Source Schema: {source_schema}
Target Schema: {target_schema}

Return only the JSON object."""
    
    preprocess_time = time.time() - preprocess_start
    
    # Start timing for LLM processing
    start_time = time.time()
    
    try:
        # For merge operations, we need to first perform matching
        match_result = None
        match_response = None
        match_generation_time = 0.0

        # HITL: Use pre-approved match result if provided
        if pre_approved_match_result:
            print(f"[HITL] Using pre-approved match result (user-edited)")
            match_result = pre_approved_match_result
            match_generation_time = 0.0  # No LLM call needed
        elif operation_type in ["merge", "instance_merge"]:
            # First, perform matching using the corresponding match prompt
            print(f"🔍 Performing {operation_type} operation - will first run matching step")
            match_prompt_template = PROMPT_TEMPLATES[actual_schema_type][match_operation][matching_method]["match"]

            if actual_schema_type == "complex":
                match_prompt = f"""{match_prompt_template}

Source Schema (Table1):
{source_schema_formatted}

Target Schema (Table2):
{target_schema_formatted}

Return only the JSON object."""
            else:
                match_prompt = f"""{match_prompt_template}

Source Schema: {source_schema}
Target Schema: {target_schema}

Return only the JSON object."""
            
            # Perform matching using the specified matching LLM
            match_start = time.time()
            # print(f"[DEBUG] Calling get_llm_response for matching with LLM: {matching_llm}")
            match_response = get_llm_response(match_prompt, matching_llm, max_tokens=max_tokens, temperature=temperature,
                                            top_p=top_p, frequency_penalty=frequency_penalty, presence_penalty=presence_penalty, custom_clients=custom_clients)
            match_end = time.time()
            match_generation_time = match_end - match_start

            # print(f"[DEBUG] Match response type: {type(match_response)}")
            # print(f"[DEBUG] Match response attributes: {[attr for attr in dir(match_response) if not attr.startswith('_')]}")

            # Parse match result
            try:
                if hasattr(match_response, 'choices') and match_response.choices:
                    match_raw_response = match_response.choices[0].message.content.strip()
                elif hasattr(match_response, 'content'):
                    match_raw_response = match_response.content.strip()
                elif hasattr(match_response, 'text'):
                    match_raw_response = match_response.text.strip()
                else:
                    match_raw_response = str(match_response).strip()

                # print(f"[DEBUG] Match raw response (first 200 chars): {match_raw_response[:200]}...")
                match_cleaned_response = clean_llm_json_response(match_raw_response)
            except Exception as e:
                print(f"[ERROR] Failed to parse match response: {str(e)}")
                match_raw_response = ""
                match_cleaned_response = ""
            
            if not match_result:
                try:
                    if match_cleaned_response:
                        match_result = json.loads(match_cleaned_response)
                        print(f"[OK] Match step completed for {operation_type}. Found matches: HMD={len(match_result.get('HMD_matches', []))}, VMD={len(match_result.get('VMD_matches', []))}")
                    else:
                        print(f"[ERROR] Empty match response - cannot proceed with merge")
                        match_result = None

                except json.JSONDecodeError as e:
                    print(f"[ERROR] Failed to parse match result JSON: {str(e)}")
                    # print(f"[DEBUG] Raw match response: {match_raw_response[:500]}...")
                    match_result = None
            
            # CRITICAL FIX: If merge step uses multi-step but match step was not multi-step,
            # replicate the single match result 3 times for multi-step merge ensemble
            if match_result and use_merge_multi_step and processing_type != "multi_step":
                print(f"[AUTO] Replicating single match result 3 times for multi-step merge ensemble")
                # Create 3 copies of the match result for ensemble processing
                replicated_responses = [
                    json.dumps(match_result, indent=2),
                    json.dumps(match_result, indent=2),
                    json.dumps(match_result, indent=2)
                ]
                # Call multi-step merge processing with replicated responses
                return process_multi_step_merge_with_responses(
                    source_schema, target_schema, schema_type, operation_type, llm_model,
                    replicated_responses, max_tokens, temperature, top_p, frequency_penalty, presence_penalty,
                    merge_value_strategy
                )

            # Update the merge prompt to include match results
            # print(f"[DEBUG] match_result exists: {bool(match_result)}")
            # print(f"[DEBUG] actual_schema_type: {actual_schema_type}")
            # print(f"[DEBUG] operation_type: {operation_type}")
            if match_result:
                    if actual_schema_type == "complex":
                        # Use the new placeholder-based prompt for complex schemas (both merge and instance_merge)
                        if not prompt_template:
                            return {"success": False, "error": f"No prompt template found for complex {operation_type}"}

                        try:
                            if prompt_template is None:
                                return {"success": False, "error": "Prompt template is None"}
                            prompt = prompt_template.replace(
                                "{match_results_placeholder}",
                                json.dumps(match_result, indent=2)
                            ).replace(
                                "{source_schema_placeholder}",
                                json.dumps(source_data, indent=2)
                            ).replace(
                                "{target_schema_placeholder}",
                                json.dumps(target_data, indent=2)
                            )
                        except Exception as e:
                            return {"success": False, "error": f"Error processing template: {str(e)}"}
                        # print(f"[DEBUG] Template after replacement length: {len(prompt)}")
                        # print(f"[DEBUG] Match results keys: {list(match_result.keys())}")
                    else:
                        # Use placeholder-based prompt for relational schemas too
                        # print(f"[DEBUG] Entering relational schema branch")
                        # print(f"[DEBUG] Match result has 'matches' key: {'matches' in match_result}")
                        if "matches" in match_result:
                            # print(f"[DEBUG] Updating {operation_type} prompt for relational schema")
                            try:
                                if prompt_template is None:
                                    return {"success": False, "error": "Prompt template is None for relational schema"}
                                if source_schema is None:
                                    return {"success": False, "error": "Source schema is None"}
                                if target_schema is None:
                                    return {"success": False, "error": "Target schema is None"}
                                prompt = prompt_template.replace(
                                    "{match_results_placeholder}",
                                    json.dumps(match_result, indent=2)
                                ).replace(
                                    "{source_schema_placeholder}",
                                    source_schema
                                ).replace(
                                    "{target_schema_placeholder}",
                                    target_schema
                                )
                            except Exception as e:
                                return {"success": False, "error": f"Error processing relational template: {str(e)}"}
                            prompt += "\n\nReturn only the JSON object."
                            # print(f"[DEBUG] Match results keys: {list(match_result.keys())}")
        
        # Debug: Log the actual prompt being sent to LLM
        # print(f"[DEBUG] Final prompt being sent to {llm_model}:")
        # print(f"[DEBUG] Prompt length: {len(prompt)} characters")
        # print(f"[DEBUG] First 500 chars: {prompt[:500]}...")
        # print(f"[DEBUG] Last 500 chars: ...{prompt[-500:]}")

        # Now perform the main operation using the appropriate LLM
        # Use matching_llm for match operations, merge_llm for merge/instance_merge operations
        operation_llm = matching_llm if operation_type == "match" else merge_llm
        response = get_llm_response(prompt, operation_llm, max_tokens=max_tokens, temperature=temperature,
                                  top_p=top_p, frequency_penalty=frequency_penalty, presence_penalty=presence_penalty, custom_clients=custom_clients)
        
        # End timing
        end_time = time.time()
        total_time = end_time - start_time
        
        raw_response = response.choices[0].message.content.strip()
        cleaned_response = clean_llm_json_response(raw_response)
        
        try:
            result_data = json.loads(cleaned_response)

            # Ensure proper structure based on operation type
            if operation_type == "match":
                if actual_schema_type == "complex":
                    if 'HMD_matches' not in result_data:
                        result_data['HMD_matches'] = []
                    if 'VMD_matches' not in result_data:
                        result_data['VMD_matches'] = []
                else:
                    if 'column_matches' not in result_data:
                        result_data['column_matches'] = []
            else:  # merge or instance_merge
                if 'Merged_Schema' not in result_data:
                    result_data['Merged_Schema'] = []
                if 'Merged_Data' not in result_data:
                    result_data['Merged_Data'] = []
                if 'Map_Schema1' not in result_data:
                    result_data['Map_Schema1'] = []
                if 'Map_Schema2' not in result_data:
                    result_data['Map_Schema2'] = []

                # Repair Merged_Data structure for complex instance merges
                if actual_schema_type == "complex" and operation_type == "instance_merge":
                    print("[VALIDATION] Repairing Merged_Data structure for complex instance merge...")
                    result_data = repair_merged_data_structure(result_data)
                    print("[VALIDATION] Repairing mapping schemas...")
                    result_data = repair_mapping_schema(result_data)
            
            # Calculate metrics
            metrics_data = {
                "script_id": script_id,
                "timestamp": timestamp,
                "llm_model": llm_model,
                "schema_type": actual_schema_type,
                "processing_type": processing_type,
                "operation_type": operation_type,
                "total_generation_time": round(total_time, 4),
                "preprocessing_time": round(preprocess_time, 4),
                "match_generation_time": round(match_generation_time, 4) if match_generation_time > 0 else 0.0,
                "merge_generation_time": round(total_time - match_generation_time, 4) if match_generation_time > 0 else 0.0,
            }
            
            # Extract token usage using provider-specific methods for main operation
            operation_llm_used = matching_llm if operation_type == "match" else merge_llm
            prompt_tokens, completion_tokens = extract_token_usage(response, operation_llm_used)

            # Calculate separate costs for match and merge operations
            # This fires when:
            #   (a) a live match was done internally (match_response is set), OR
            #   (b) HITL path used pre_approved_match_result (skipped match LLM, match_response=None)
            if operation_type in ['merge', 'instance_merge'] and (match_response or pre_approved_match_result):
                # Extract match step token usage if a live match was performed
                if match_response:
                    match_prompt_tokens, match_completion_tokens = extract_token_usage(match_response, matching_llm)
                else:
                    # HITL path: match was skipped, use metrics passed from the frontend's saved match run
                    if previous_match_metrics:
                        match_prompt_tokens = previous_match_metrics.get('input_prompt_tokens', 0) or previous_match_metrics.get('match_input_tokens', 0)
                        match_completion_tokens = previous_match_metrics.get('output_tokens', 0) or previous_match_metrics.get('match_output_tokens', 0)
                        # Also carry over the match LLM name and time if the caller didn't set them
                        if not matching_llm:
                            matching_llm = previous_match_metrics.get('llm_model') or previous_match_metrics.get('matching_llm_used', matching_llm)
                        # Override match_generation_time with the real value from the match run
                        match_generation_time = previous_match_metrics.get('total_generation_time', 0)
                        print(f"[HITL-METRICS] Restored match metrics from frontend: input={match_prompt_tokens}, output={match_completion_tokens}, time={match_generation_time}s")
                    else:
                        match_prompt_tokens, match_completion_tokens = 0, 0

                # Calculate separate costs
                match_cost = calculate_api_cost(matching_llm, match_prompt_tokens, match_completion_tokens)
                merge_cost = calculate_api_cost(merge_llm, prompt_tokens, completion_tokens)
                total_api_cost = match_cost + merge_cost
                print("There are no previous match results",previous_match_metrics)
                # Total tokens
                total_prompt_tokens = prompt_tokens + match_prompt_tokens
                total_completion_tokens = completion_tokens + match_completion_tokens

                # Add separate cost metrics
                metrics_data.update({
                    "match_api_cost": match_cost,
                    "merge_api_cost": merge_cost,
                    "match_input_tokens": match_prompt_tokens,
                    "match_output_tokens": match_completion_tokens,
                    "merge_input_tokens": prompt_tokens,
                    "merge_output_tokens": completion_tokens,
                    "matching_llm_used": matching_llm,
                    "merge_llm_used": merge_llm
                })
            else:
                # Single operation (match only)
                total_prompt_tokens = prompt_tokens
                total_completion_tokens = completion_tokens
                total_api_cost = calculate_api_cost(operation_llm_used, total_prompt_tokens, total_completion_tokens)

                # Add single operation metrics
                metrics_data.update({
                    "match_api_cost": total_api_cost if operation_type == "match" else 0.0,
                    "merge_api_cost": 0.0,
                    "matching_llm_used": operation_llm_used if operation_type == "match" else None,
                    "merge_llm_used": None
                })

            # Generate pipeline description
            pipeline_description = generate_pipeline_description(
                operation_type=operation_type,
                match_operation=match_operation,
                matching_method=matching_method,
                matching_llm=matching_llm,
                merge_operation=match_operation if operation_type in ['merge', 'instance_merge'] else None,
                merge_method=merge_method,
                merge_llm=merge_llm,
                processing_type=processing_type
            )

            # Add common metrics for both cases
            metrics_data.update({
                "total_tokens": total_prompt_tokens + total_completion_tokens,
                "input_prompt_tokens": total_prompt_tokens,
                "output_tokens": total_completion_tokens,
                "tokens_per_second": round(total_completion_tokens / total_time, 2) if total_time > 0 else 0,
                "api_call_cost": total_api_cost,
                "pipeline_description": pipeline_description
            })
            
            # Add match counts
            def count_real_matches(matches):
                """Count only non-empty matches (exclude where both source and target are empty strings)"""
                return sum(1 for m in matches if m.get('source', '') or m.get('target', ''))

            if operation_type == "match":
                if actual_schema_type == "complex":
                    metrics_data["hmd_matches"] = count_real_matches(result_data.get('HMD_matches', []))
                    metrics_data["vmd_matches"] = count_real_matches(result_data.get('VMD_matches', []))
                    metrics_data["total_matches"] = metrics_data["hmd_matches"] + metrics_data["vmd_matches"]
                else:
                    metrics_data["total_matches"] = len(result_data.get('column_matches', []))
            else:  # merge or instance_merge
                # For merge operations, use the match result for counts
                if match_result:
                    if actual_schema_type == "complex":
                        metrics_data["hmd_matches"] = count_real_matches(match_result.get('HMD_matches', []))
                        metrics_data["vmd_matches"] = count_real_matches(match_result.get('VMD_matches', []))
                        metrics_data["total_matches"] = metrics_data["hmd_matches"] + metrics_data["vmd_matches"]
                    else:
                        metrics_data["total_matches"] = len(match_result.get('matches', []))
                else:
                    metrics_data["total_matches"] = 0
            
            # Apply merge value strategy for merge operations
            print(f"[DEBUG] operation_type={operation_type}, merge_value_strategy={merge_value_strategy}")
            if operation_type in ["merge", "instance_merge"] and merge_value_strategy != 'delimited':
                print(f"[POST-PROCESS] Applying merge value strategy: {merge_value_strategy}")
                result_data = apply_merge_value_strategy(result_data, merge_value_strategy)
            else:
                print(f"[DEBUG] Skipping aggregation: operation={operation_type}, strategy={merge_value_strategy}")

            # Validate metrics using Pydantic
            validated_metrics = ProcessingMetrics(**metrics_data)

            return {
                "success": True,
                "data": result_data,
                "metrics": validated_metrics.model_dump(),
                "raw_response": raw_response,
                "match_result": match_result if match_result else None
            }
            
        except json.JSONDecodeError as e:
            # Save raw response to file for debugging
            import time as time_module
            import os
            timestamp = time_module.strftime("%Y%m%d_%H%M%S")
            debug_filename = f"llm_response_debug_{timestamp}.txt"
            try:
                with open(debug_filename, 'w', encoding='utf-8') as f:
                    f.write("=" * 80 + "\n")
                    f.write("LLM RESPONSE DEBUG - JSON PARSING FAILED\n")
                    f.write("=" * 80 + "\n\n")
                    f.write(f"Error: {str(e)}\n")
                    f.write(f"Response Length: {len(raw_response)} characters\n")
                    f.write(f"Response Lines: {raw_response.count(chr(10)) + 1}\n\n")
                    f.write("-" * 80 + "\n")
                    f.write("RAW RESPONSE (first 2000 chars):\n")
                    f.write("-" * 80 + "\n")
                    f.write(raw_response[:2000] + "\n\n")
                    f.write("-" * 80 + "\n")
                    f.write("RAW RESPONSE (last 2000 chars):\n")
                    f.write("-" * 80 + "\n")
                    f.write(raw_response[-2000:] + "\n\n")
                    f.write("-" * 80 + "\n")
                    f.write("FULL RAW RESPONSE:\n")
                    f.write("-" * 80 + "\n")
                    f.write(raw_response)
                    f.write("\n\n" + "=" * 80 + "\n")
                    f.write("END OF DEBUG FILE\n")
                    f.write("=" * 80 + "\n")
                print(f"[DEBUG] Saved raw LLM response to: {os.path.abspath(debug_filename)}")
            except Exception as write_err:
                print(f"[DEBUG] Failed to write debug file: {write_err}")
            
            return {
                "success": False, 
                "error": f"JSON parsing error: {str(e)}",
                "raw_response": raw_response
            }
            
    except Exception as e:
        return {
            "success": False, 
            "error": f"LLM API error: {str(e)}"
        }

def extract_hmd_vmd_from_schema(schema_data):
    """Extract HMD and VMD arrays from schema data for LLM processing"""
    hmd_data = []
    vmd_data = []
    
    for key, value in schema_data.items():
        if key.endswith('.HMD') and isinstance(value, list):
            hmd_data.extend(value)
        elif key.endswith('.VMD') and isinstance(value, list):
            # FIXED: Return VMD in the same hierarchical format as HMD
            # The LLM prompt expects both HMD and VMD in structured format with attribute1, children
            vmd_data.extend(value)  # Pass raw hierarchical VMD, not flattened strings
    
    return hmd_data, vmd_data

def _create_vmd_for_llm_matching(vmd_list):
    """Create VMD list with hierarchical paths for LLM matching"""
    vmd_for_matching = []
    
    for obj in vmd_list:
        if isinstance(obj, dict):
            # Check for structured VMD hierarchy (user's format)
            if 'children' in obj and isinstance(obj.get('children'), list):
                parent_text = None
                for key, value in obj.items():
                    if key.startswith('attribute') and isinstance(value, str) and value.strip():
                        parent_text = value.strip()
                        break
                
                if parent_text:
                    # Add parent category for matching
                    vmd_for_matching.append(parent_text)
                    
                    children = obj.get('children', [])
                    if children:
                        for child_obj in children:
                            if isinstance(child_obj, dict):
                                # Extract child names from all child_level1.attributeX keys in this object
                                child_attributes = []
                                for child_key, child_value in child_obj.items():
                                    if child_key.startswith('child_level1.') and isinstance(child_value, str) and child_value.strip():
                                        child_attributes.append((child_key, child_value.strip()))
                                
                                # Sort by attribute order (attribute1, attribute2, etc.)
                                child_attributes.sort(key=lambda x: x[0])
                                
                                # Add each child name and hierarchical path
                                for _, child_name in child_attributes:
                                    # Add child name alone for matching
                                    vmd_for_matching.append(child_name)
                                    # Add hierarchical path for matching
                                    vmd_for_matching.append(f"{parent_text}.{child_name}")
            else:
                # Legacy format - extract string values
                for v in obj.values():
                    if isinstance(v, str) and v:
                        vmd_for_matching.append(v)
        elif isinstance(obj, str) and obj:
            vmd_for_matching.append(obj)
    
    return vmd_for_matching

def repair_merged_data_structure(result_data, source_schemas=None):
    """
    Repair and validate Merged_Data structure for ComplexInstanceMergeResult
    Handles incomplete/truncated LLM responses and reconstructs missing data
    """
    if not isinstance(result_data, dict):
        return result_data

    # Check if this is a complex instance merge result
    if 'HMD_Merged_Schema' not in result_data or 'VMD_Merged_Schema' not in result_data:
        return result_data

    hmd_schema = result_data.get('HMD_Merged_Schema', [])
    vmd_schema = result_data.get('VMD_Merged_Schema', [])
    merged_data = result_data.get('Merged_Data', [])

    # If Merged_Data is empty or not a list, reconstruct it
    if not isinstance(merged_data, list) or len(merged_data) == 0:
        print("[REPAIR] Merged_Data is empty, reconstructing from schemas...")
        merged_data = []

        # Create structure for each HMD column
        for hmd_col in hmd_schema:
            vmd_data = []
            for vmd_row in vmd_schema:
                vmd_data.append({
                    vmd_row: {
                        "source1": "",
                        "source2": ""
                    }
                })
            merged_data.append({
                hmd_col: {
                    "VMD_data": vmd_data
                }
            })

        result_data['Merged_Data'] = merged_data
        print(f"[REPAIR] Reconstructed Merged_Data with {len(merged_data)} HMD columns and {len(vmd_schema)} VMD rows")
        return result_data

    # Validate and repair existing Merged_Data structure
    print("[REPAIR] Validating existing Merged_Data structure...")
    repaired_data = []

    for idx, hmd_entry in enumerate(merged_data):
        if not isinstance(hmd_entry, dict):
            print(f"[REPAIR] Entry {idx} is not a dict, skipping...")
            continue

        for hmd_col, hmd_content in hmd_entry.items():
            # Check if hmd_content has VMD_data
            if not isinstance(hmd_content, dict):
                print(f"[REPAIR] {hmd_col} content is not a dict, creating structure...")
                vmd_data = []
                for vmd_row in vmd_schema:
                    vmd_data.append({
                        vmd_row: {
                            "source1": "",
                            "source2": ""
                        }
                    })
                repaired_data.append({
                    hmd_col: {
                        "VMD_data": vmd_data
                    }
                })
                continue

            vmd_data = hmd_content.get('VMD_data', [])

            # Validate VMD_data structure
            if not isinstance(vmd_data, list):
                print(f"[REPAIR] {hmd_col} VMD_data is not a list, creating structure...")
                vmd_data = []
                for vmd_row in vmd_schema:
                    vmd_data.append({
                        vmd_row: {
                            "source1": "",
                            "source2": ""
                        }
                    })
            else:
                # Repair incomplete VMD entries
                repaired_vmd = []
                existing_vmd_rows = set()

                for vmd_entry in vmd_data:
                    if not isinstance(vmd_entry, dict):
                        continue

                    for vmd_row, vmd_values in vmd_entry.items():
                        existing_vmd_rows.add(vmd_row)

                        # Ensure proper structure with source1/source2
                        if not isinstance(vmd_values, dict):
                            vmd_values = {"source1": "", "source2": ""}
                        else:
                            if 'source1' not in vmd_values:
                                vmd_values['source1'] = ""
                            if 'source2' not in vmd_values:
                                vmd_values['source2'] = ""

                        repaired_vmd.append({
                            vmd_row: vmd_values
                        })

                # Add missing VMD rows
                for vmd_row in vmd_schema:
                    if vmd_row not in existing_vmd_rows:
                        print(f"[REPAIR] Adding missing VMD row: {vmd_row} to {hmd_col}")
                        repaired_vmd.append({
                            vmd_row: {
                                "source1": "",
                                "source2": ""
                            }
                        })

                vmd_data = repaired_vmd

            repaired_data.append({
                hmd_col: {
                    "VMD_data": vmd_data
                }
            })

    # Ensure all HMD columns are present
    existing_hmd_cols = set()
    for entry in repaired_data:
        for hmd_col in entry.keys():
            existing_hmd_cols.add(hmd_col)

    for hmd_col in hmd_schema:
        if hmd_col not in existing_hmd_cols:
            print(f"[REPAIR] Adding missing HMD column: {hmd_col}")
            vmd_data = []
            for vmd_row in vmd_schema:
                vmd_data.append({
                    vmd_row: {
                        "source1": "",
                        "source2": ""
                    }
                })
            repaired_data.append({
                hmd_col: {
                    "VMD_data": vmd_data
                }
            })

    result_data['Merged_Data'] = repaired_data
    print(f"[REPAIR] Validation complete. Merged_Data has {len(repaired_data)} HMD entries")
    return result_data

def repair_mapping_schema(result_data):
    """
    Repair and validate HMD/VMD mapping schemas
    Ensures all merged schema attributes have corresponding mappings
    """
    if not isinstance(result_data, dict):
        return result_data

    # Check if this has mapping data
    if 'HMD_Merged_Schema' not in result_data or 'VMD_Merged_Schema' not in result_data:
        return result_data

    hmd_merged = result_data.get('HMD_Merged_Schema', [])
    vmd_merged = result_data.get('VMD_Merged_Schema', [])

    # Repair HMD_Map_Schema1 and HMD_Map_Schema2
    for map_key in ['HMD_Map_Schema1', 'HMD_Map_Schema2']:
        if map_key in result_data:
            existing_mappings = result_data[map_key]
            if not isinstance(existing_mappings, list):
                existing_mappings = []

            # Get existing mapped attributes
            mapped_attrs = set()
            for mapping in existing_mappings:
                if isinstance(mapping, dict):
                    source1 = mapping.get('source1', '').replace('Merged_Schema.', '').replace('HMD_Merged_Schema.', '')
                    if source1:
                        mapped_attrs.add(source1)

            # Add missing mappings
            schema_num = '1' if '1' in map_key else '2'
            for hmd_attr in hmd_merged:
                if hmd_attr not in mapped_attrs:
                    print(f"[REPAIR] Adding missing {map_key} mapping for: {hmd_attr}")
                    existing_mappings.append({
                        "source1": f"Merged_Schema.{hmd_attr}",
                        "source2": f"Schema{schema_num}.{hmd_attr}"
                    })

            result_data[map_key] = existing_mappings

    # Repair VMD_Map_Schema1 and VMD_Map_Schema2
    for map_key in ['VMD_Map_Schema1', 'VMD_Map_Schema2']:
        if map_key in result_data:
            existing_mappings = result_data[map_key]
            if not isinstance(existing_mappings, list):
                existing_mappings = []

            # Get existing mapped attributes
            mapped_attrs = set()
            for mapping in existing_mappings:
                if isinstance(mapping, dict):
                    source1 = mapping.get('source1', '').replace('Merged_Schema.', '').replace('VMD_Merged_Schema.', '')
                    if source1:
                        mapped_attrs.add(source1)

            # Add missing mappings
            schema_num = '1' if '1' in map_key else '2'
            for vmd_attr in vmd_merged:
                if vmd_attr not in mapped_attrs:
                    print(f"[REPAIR] Adding missing {map_key} mapping for: {vmd_attr}")
                    existing_mappings.append({
                        "source1": f"Merged_Schema.{vmd_attr}",
                        "source2": f"Schema{schema_num}.{vmd_attr}"
                    })

            result_data[map_key] = existing_mappings

    print(f"[REPAIR] Mapping schemas validated and repaired")
    return result_data

def clean_llm_json_response(response):
    """Clean and extract JSON from LLM response with enhanced malformed JSON handling.
    
    This function handles common LLM response issues including:
    - Multiple JSON objects in response (takes the first complete one)
    - Extra text before/after JSON
    - Markdown code blocks
    - Trailing commas and other malformations
    """
    response = response.strip()

    # Remove markdown code blocks
    if '```json' in response:
        start = response.find('```json') + 7
        end = response.find('```', start)
        if end > start:
            response = response[start:end].strip()
    elif '```' in response:
        start = response.find('```') + 3
        end = response.find('```', start)
        if end > start:
            response = response[start:end].strip()

    # Find the first JSON object by balancing braces
    json_start = response.find('{')
    
    if json_start < 0:
        return '{"HMD_matches": [], "VMD_matches": []}'
    
    # Use brace balancing to find the end of the first complete JSON object
    brace_count = 0
    in_string = False
    escape_next = False
    json_end = -1
    
    for i, char in enumerate(response[json_start:], start=json_start):
        if escape_next:
            escape_next = False
            continue
            
        if char == '\\' and in_string:
            escape_next = True
            continue
            
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
            
        if in_string:
            continue
            
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                json_end = i + 1
                break
    
    if json_end > json_start:
        json_content = response[json_start:json_end]

        # Fix common JSON malformation issues
        json_content = json_content.replace('}\n  ]', '}]')  # Fix array ending
        json_content = json_content.replace('}\n]', '}]')    # Fix array ending
        json_content = json_content.replace(',\n}', '\n}')   # Fix trailing comma
        json_content = json_content.replace(',}', '}')       # Fix trailing comma
        json_content = json_content.replace(',]', ']')       # Fix trailing comma in array
        
        # Try to parse and validate the JSON
        try:
            import json
            parsed = json.loads(json_content)
            return json_content
        except json.JSONDecodeError as e:
            print(f"[DEBUG] JSON validation failed after brace balancing: {e}")
            # Fall back to trying to fix more issues
            
            # Try to find and fix truncated arrays
            json_content = _fix_truncated_json(json_content)
            
            try:
                json.loads(json_content)
                return json_content
            except json.JSONDecodeError:
                pass
    
    # Fallback: use rfind but warn about potential issues
    json_end_fallback = response.rfind('}') + 1
    if json_start >= 0 and json_end_fallback > json_start:
        json_content = response[json_start:json_end_fallback]
        
        # Fix common JSON malformation issues
        json_content = json_content.replace('}\n  ]', '}]')
        json_content = json_content.replace('}\n]', '}]')
        json_content = json_content.replace(',\n}', '\n}')
        json_content = json_content.replace(',}', '}')
        json_content = json_content.replace(',]', ']')
        
        return json_content

    return '{"HMD_matches": [], "VMD_matches": []}'


def _fix_truncated_json(json_content):
    """Attempt to fix truncated or malformed JSON by closing unclosed brackets/braces."""
    import re
    
    # Count unclosed braces and brackets
    open_braces = json_content.count('{') - json_content.count('}')
    open_brackets = json_content.count('[') - json_content.count(']')
    
    # Remove any incomplete key-value pairs at the end (e.g., "key": or "key":  ")
    # Remove trailing incomplete strings
    json_content = re.sub(r',\s*"[^"]*":\s*"?[^"]*$', '', json_content)
    json_content = re.sub(r',\s*"[^"]*":\s*$', '', json_content)
    
    # Recount after cleanup
    open_braces = json_content.count('{') - json_content.count('}')
    open_brackets = json_content.count('[') - json_content.count(']')
    
    # Close any unclosed brackets first, then braces
    json_content = json_content.rstrip()
    if json_content.endswith(','):
        json_content = json_content[:-1]
    
    json_content += ']' * open_brackets
    json_content += '}' * open_braces
    
    return json_content

