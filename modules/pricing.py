"""
Pricing and cost calculation functions for LLM API calls
"""
import datetime
import uuid
import json
from modules.config import *
# Model detection functions (is_gemini_model, is_claude_model, is_openai_model)
# are imported from modules.config via "from modules.config import *"

# --- Pricing Configuration (USD per million tokens) ---
# Updated with accurate 2025 API pricing from official sources
MODEL_PRICING = {
    # Groq models - Official 2025 pricing from groq.com/pricing
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},  # Official Groq pricing
    "qwen/qwen3-32b": {"input": 0.18, "output": 0.18},  # Groq uniform pricing for Qwen models
    "deepseek-r1-distill-llama-70b": {"input": 0.59, "output": 0.79},  # Groq Llama 3.3 70B pricing
    "openai/gpt-oss-20b": {"input": 0.18, "output": 0.18},  # Groq uniform pricing tier
    "openai/gpt-oss-120b": {"input": 0.59, "output": 0.79},  # Groq higher tier pricing

    # Anthropic Claude models - Official 2025 pricing from claude.com/pricing
    "claude-3-5-haiku-20241022": {"input": 0.25, "output": 1.25},  # Official Claude 3.5 Haiku
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},  # Official Claude 3.5 Sonnet
    # "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},  # Official Claude 3 Opus
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},  # Official Claude Sonnet 4
    # "claude-opus-4-20241212": {"input": 15.00, "output": 75.00},  # Official Claude Opus 4

    # Gemini models - Official 2025 pricing from ai.google.dev/gemini-api/docs/pricing
    "gemini-1.5-flash": {"input": 0.15, "output": 0.60},  # Official Gemini 1.5 Flash pricing
    "gemini-2.0-flash-exp": {"input": 0.10, "output": 0.40},  # Currently free in API
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},  # Official unified pricing (2025 update)
}

def get_model_pricing(model_name):
    """Get pricing information for a specific model"""
    return MODEL_PRICING.get(model_name, {"input": 0.05, "output": 0.10})  # Default fallback

def calculate_api_cost(model_name, input_tokens, output_tokens):
    """Calculate API cost based on model-specific pricing"""
    pricing = get_model_pricing(model_name)
    input_cost = (input_tokens / 1000000) * pricing["input"]
    output_cost = (output_tokens / 1000000) * pricing["output"]
    return input_cost + output_cost

def extract_token_usage(response, model_name):
    """
    Extract accurate token usage from API response based on provider-specific methods

    Returns: tuple (input_tokens, output_tokens)
    """
    try:
        # print(f"[DEBUG] Extracting tokens for model: {model_name}")
        # print(f"[DEBUG] Response type: {type(response)}")
        # print(f"[DEBUG] Response has usage: {hasattr(response, 'usage')}")
        # print(f"[DEBUG] Response has usage_metadata: {hasattr(response, 'usage_metadata')}")

        # Prioritize native formats for each model type

        # 1. Gemini models - prioritize usage_metadata (native Gemini format)
        if is_gemini_model(model_name) and hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage_meta = response.usage_metadata
            # print(f"[DEBUG] Usage_metadata object type: {type(usage_meta)}")
            # print(f"[DEBUG] Usage_metadata attributes: {dir(usage_meta)}")
            if hasattr(usage_meta, 'prompt_token_count') and hasattr(usage_meta, 'candidates_token_count'):
                input_tokens = usage_meta.prompt_token_count
                output_tokens = usage_meta.candidates_token_count
                # print(f"[DEBUG] Gemini native tokens: input={input_tokens}, output={output_tokens}")
                return input_tokens, output_tokens

        # 2. Claude models - prioritize input_tokens/output_tokens (native Claude format)
        if is_claude_model(model_name) and hasattr(response, 'usage') and response.usage:
            usage = response.usage
            # print(f"[DEBUG] Usage object type: {type(usage)}")
            # print(f"[DEBUG] Usage attributes: {dir(usage)}")
            if hasattr(usage, 'input_tokens') and hasattr(usage, 'output_tokens'):
                input_tokens = usage.input_tokens
                output_tokens = usage.output_tokens
                # print(f"[DEBUG] Claude native tokens: input={input_tokens}, output={output_tokens}")

                return input_tokens, output_tokens

        # 3. OpenAI/Groq models - use prompt_tokens/completion_tokens (OpenAI format)
        if hasattr(response, 'usage') and response.usage:
            usage = response.usage
            # print(f"[DEBUG] Usage object type: {type(usage)}")
            # print(f"[DEBUG] Usage attributes: {dir(usage)}")
            if hasattr(usage, 'prompt_tokens') and hasattr(usage, 'completion_tokens'):
                input_tokens = usage.prompt_tokens
                output_tokens = usage.completion_tokens
                if is_openai_model(model_name):
                    # print(f"[DEBUG] OpenAI native tokens: input={input_tokens}, output={output_tokens}")
                    pass
                else:
                    # print(f"[DEBUG] Groq/other tokens: input={input_tokens}, output={output_tokens}")
                    pass
                return input_tokens, output_tokens

        # Fallback: return 0, 0 if no usage information found
        # print(f"[WARNING] No token usage information found for model: {model_name}")
        # print(f"[DEBUG] Available response attributes: {[attr for attr in dir(response) if not attr.startswith('_')]}")
        return 0, 0

    except Exception as e:
        # print(f"[ERROR] Failed to extract token usage for model {model_name}: {str(e)}")
        # print(f"[DEBUG] Exception details: {e.__class__.__name__}: {str(e)}")
        return 0, 0

def estimate_tokens_by_provider(text, model_name):
    """Estimate token count based on provider-specific rules"""
    if is_gemini_model(model_name):
        # Gemini: 1 token ≈ 4 characters
        return int(len(text) / 4)
    elif is_claude_model(model_name):
        # Claude: roughly 1 token ≈ 3.3 characters (similar to GPT)
        return int(len(text) / 3.3)
    else:
        # Groq/OpenAI models: roughly 1 token ≈ 3.3 characters
        return int(len(text) / 3.3)

def generate_pipeline_description(operation_type, match_operation=None, matching_method=None, matching_llm=None,
                                merge_operation=None, merge_method=None, merge_llm=None, processing_type=None):
    """Generate a comprehensive pipeline description string with explicit labels"""

    # Helper function to get LLM display name
    def get_llm_display_name(llm_model):
        if not llm_model:
            return "Auto-select"
        if llm_model.startswith('claude'):
            return f"Claude {llm_model.split('-')[1].title()} {llm_model.split('-')[2].title()}"
        elif llm_model.startswith('gemini'):
            return f"Gemini {llm_model.replace('gemini-', '').replace('-', ' ').title()}"
        elif llm_model.startswith('llama'):
            return f"Llama {llm_model.replace('llama-', '').replace('-', ' ').title()}"
        elif 'qwen' in llm_model:
            return f"Qwen {llm_model.split('/')[-1].replace('qwen', '').replace('-', ' ').title()}"
        elif 'deepseek' in llm_model:
            return f"DeepSeek {llm_model.split('/')[-1].replace('deepseek-', '').title()}"
        elif llm_model.startswith('gpt-'):
            return f"GPT {llm_model.replace('gpt-', '').replace('-', ' ').title()}"
        elif llm_model.startswith('openai/gpt'):
            return f"GPT {llm_model.replace('openai/gpt-', '').replace('-', ' ').title()}"
        else:
            return llm_model.replace('-', ' ').title()

    # Helper function to get method display name
    def get_method_display_name(method):
        method_names = {
            'json_default': 'JSON',
            'kg_enhanced': 'Knowledge Graph',
            'baseline': 'Baseline',
            'multi_step': 'Multi-Step',
            'loss_less': 'Loss-Less'
        }
        return method_names.get(method, method.replace('_', ' ').title() if method else 'JSON')

    # Helper function to get operation display name
    def get_operation_display_name(operation):
        operation_names = {
            'operator': 'Operator',
            'baseline': 'Baseline',
            'merge': 'Schema Merge',
            'instance_merge': 'Instance Merge'
        }
        return operation_names.get(operation, operation.replace('_', ' ').title() if operation else 'Operator')

    # Build explicit pipeline description
    description_parts = []

    # Add processing type prefix if multi-step
    prefix = "Multi-Step " if processing_type == 'multi_step' else ""

    # Always include match information (all pipelines have a match component)
    match_op = get_operation_display_name(match_operation or 'operator')
    match_method = get_method_display_name(matching_method or 'json_default')
    match_llm = get_llm_display_name(matching_llm or 'Auto-select')

    match_desc = f"{prefix}Match Operator: {match_op}, Match Method: {match_method}, LLM used for matching: {match_llm}"
    description_parts.append(match_desc)

    # Add merge information if it's a merge operation
    if operation_type in ['merge', 'instance_merge']:
        merge_op = get_operation_display_name(merge_operation or operation_type)
        merge_method_name = get_method_display_name(merge_method or matching_method or 'json_default')
        merge_llm_name = get_llm_display_name(merge_llm or matching_llm or 'Auto-select')

        merge_desc = f"Merge Operator: {merge_op}, Merge Method: {merge_method_name}, LLM used for merging: {merge_llm_name}"
        description_parts.append(merge_desc)

    return ", ".join(description_parts)

def format_cost_display(cost):
    """Format cost for display with appropriate precision"""
    if cost == 0:
        return "$0.00"
    elif cost < 0.000001:
        return f"${cost:.8f}"
    elif cost < 0.0001:
        return f"${cost:.6f}"
    elif cost < 0.01:
        return f"${cost:.4f}"
    else:
        return f"${cost:.2f}"

def store_llm_response_to_local_storage(request_data, response_data, metrics_data, raw_response, match_result=None, multi_step_results=None):
    """Store LLM response data to local JSON storage"""
    try:
        session_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().isoformat()

        document = {
            "session_id": session_id,
            "timestamp": timestamp,
            "request_data": {
                "source_schema": request_data.get('sourceSchema', ''),
                "target_schema": request_data.get('targetSchema', ''),
                "schema_type": request_data.get('schemaType', ''),
                "processing_type": request_data.get('processingType', ''),
                "operation_type": request_data.get('operationType', ''),
                "llm_model": request_data.get('llmModel', ''),
                "parameters": request_data.get('parameters', {})
            },
            "response_data": response_data,
            "metrics": {
                "timestamp": metrics_data.get('timestamp', ''),
                "llm_model": metrics_data.get('llm_model', ''),
                "schema_type": metrics_data.get('schema_type', ''),
                "processing_type": metrics_data.get('processing_type', ''),
                "operation_type": metrics_data.get('operation_type', ''),
                "total_generation_time": metrics_data.get('total_generation_time', 0.0),
                "input_prompt_tokens": metrics_data.get('input_prompt_tokens', 0),
                "output_tokens": metrics_data.get('output_tokens', 0),
                "total_tokens": metrics_data.get('total_tokens', 0),
                "tokens_per_second": metrics_data.get('tokens_per_second', 0.0),
                "api_call_cost": metrics_data.get('api_call_cost', 0.0),
                "preprocessing_time": metrics_data.get('preprocessing_time', 0.0),
                "hmd_matches": metrics_data.get('hmd_matches', 0),
                "vmd_matches": metrics_data.get('vmd_matches', 0),
                "total_matches": metrics_data.get('total_matches', 0),
                "match_generation_time": metrics_data.get('match_generation_time', 0.0),
                "merge_generation_time": metrics_data.get('merge_generation_time', 0.0),
                "pipeline_description": metrics_data.get('pipeline_description', '')
            },
            "raw_response": raw_response,
            "match_result": match_result,
            "multi_step_results": multi_step_results,
            "intermediate_results": {
                "match_result": match_result,
                "processing_type": metrics_data.get('processing_type', ''),
                "operation_type": metrics_data.get('operation_type', '')
            },
            "success": response_data is not None
        }

        # Generate filename with timestamp and session ID
        filename = f"llm_response_{timestamp.replace(':', '-').replace('.', '_')}_{session_id[:8]}.json"

        # Save to results directory
        success = save_to_json_file(document, filename, RESULTS_DIR)

        if success:
            print(f"[OK] LLM response data stored locally with session ID: {session_id}")
            return True
        else:
            print(f"[WARNING] Failed to store LLM response data locally")
            return False

    except Exception as e:
        print(f"[WARNING] Failed to store data to local storage: {str(e)}")
        return False

# Keep the old function name for compatibility but redirect to local storage
def store_llm_response_to_mongodb(request_data, response_data, metrics_data, raw_response, match_result=None, multi_step_results=None):
    """Compatibility wrapper - now stores to local storage instead of MongoDB"""
    return store_llm_response_to_local_storage(request_data, response_data, metrics_data, raw_response, match_result, multi_step_results)

