''''
Cleaned Schema Fusion App with Fixed Connection Logic
'''

# Flask imports commented out - using FastAPI instead
# from flask import Flask, request, jsonify, render_template_string, render_template, Blueprint
import os
import json
import uuid
import datetime
import time
from groq import Groq
from anthropic import Anthropic
from pydantic import BaseModel, ValidationError
from typing import List, Dict, Any, Optional
from docx import Document
from docx.table import Table as DocxTable
import io
import base64
# MongoDB imports removed - using local storage instead

# Import Google Generative AI
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Warning: Google Generative AI package not installed. Install with: pip install google-generativeai")

# Flask app removed - this is now a helper module for FastAPI
# app = Flask(__name__)
# app.config['JSON_SORT_KEYS'] = False
# app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# --- Configuration ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# --- Local Storage Configuration ---
STORAGE_DIR = "fusion_data"
LOGS_DIR = os.path.join(STORAGE_DIR, "logs")
RESULTS_DIR = os.path.join(STORAGE_DIR, "results")
UPLOADS_DIR = os.path.join(STORAGE_DIR, "uploads")

# Create storage directories
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Initialize clients
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Initialize Anthropic
anthropic_client = None
if ANTHROPIC_API_KEY:
    try:
        anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
        # print("[OK] Anthropic API configured successfully")
        pass
    except Exception as e:
        # print(f"[WARNING] Anthropic API configuration failed: {str(e)}")
        pass
else:
    print("[WARNING] ANTHROPIC_API_KEY environment variable not set")

# --- Local Storage Functions ---
def save_to_json_file(data, filename, directory=RESULTS_DIR):
    """Save data to a JSON file"""
    try:
        filepath = os.path.join(directory, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        print(f"[OK] Data saved to {filepath}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save to {filepath}: {str(e)}")
        return False

def load_from_json_file(filename, directory=RESULTS_DIR):
    """Load data from a JSON file"""
    try:
        filepath = os.path.join(directory, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"[ERROR] Failed to load {filepath}: {str(e)}")
        return None

def log_activity(activity_data):
    """Log activity to a JSON file with timestamp"""
    try:
        timestamp = datetime.datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "activity": activity_data
        }

        # Generate log filename with date
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        log_filename = f"activity_log_{date_str}.json"
        log_filepath = os.path.join(LOGS_DIR, log_filename)

        # Load existing logs or create new list
        if os.path.exists(log_filepath):
            with open(log_filepath, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        else:
            logs = []

        # Add new log entry
        logs.append(log_entry)

        # Save updated logs
        with open(log_filepath, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False, default=str)

        return True
    except Exception as e:
        print(f"[ERROR] Failed to log activity: {str(e)}")
        return False

print("[OK] Local storage initialized successfully")
print(f"[INFO] Storage location: {os.path.abspath(STORAGE_DIR)}")


# Initialize Gemini
gemini_client = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_client = genai
        # print("[OK] Gemini API configured successfully")
    except Exception as e:
        # print(f"[WARNING]  Gemini API configuration failed: {str(e)}")
        GEMINI_AVAILABLE = False
elif GEMINI_AVAILABLE and not GEMINI_API_KEY:
    print("[WARNING]  GEMINI_API_KEY environment variable not set")
    GEMINI_AVAILABLE = False

# --- Model 1Configuration ---
# Default LLM parameters for fine-tuning model behavior
DEFAULT_LLM_PARAMS = {
    "max_tokens": 3000,        # Maximum tokens in response (increased for complex schemas)
    "temperature": 0.0,        # Randomness (0.0-2.0): 0.0 for maximum consistency in schema mapping
    "top_p": 0.1,             # Nucleus sampling (0.0-1.0): 0.1 for focused, deterministic token selection
    "frequency_penalty": 0.2,  # Reduces repetition (0.0-2.0): Helps avoid repeated mappings
    "presence_penalty": 0.1    # Encourages new topics (0.0-2.0): Helps explore all attributes
}

# Predefined parameter presets for different use cases
LLM_PRESETS = {
    "precise": {
        "temperature": 0.0,
        "top_p": 0.8,
        "frequency_penalty": 0.1,
        "presence_penalty": 0.0
    },
    "balanced": {
        "temperature": 0.3,
        "top_p": 0.9,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0
    },
    "creative": {
        "temperature": 0.7,
        "top_p": 1.0,
        "frequency_penalty": 0.2,
        "presence_penalty": 0.3
    },
    "schema_matching": {
        "temperature": 0.0,
        "top_p": 0.1,
        "frequency_penalty": 0.3,
        "presence_penalty": 0.2,
        "max_tokens": 3000
    },
    "deterministic_mapping": {
        "temperature": 0.0,
        "top_p": 0.05,
        "frequency_penalty": 0.4,
        "presence_penalty": 0.1,
        "max_tokens": 2500
    }
}

# --- Model map ---
MODEL_MAP = {
    # Groq models
    "llama-3.1-8b-instant": "llama-3.1-8b-instant",
    "qwen/qwen3-32b": "qwen/qwen3-32b",
    "deepseek-r1-distill-llama-70b": "deepseek-r1-distill-llama-70b",
    
    "openai/gpt-oss-20b": "openai/gpt-oss-20b",
    "openai/gpt-oss-120b": "openai/gpt-oss-120b",
    
    # Anthropic Claude models
    "claude-3-5-haiku-20241022": "claude-3-5-haiku-20241022",
    "claude-3-5-sonnet-20241022": "claude-3-5-sonnet-20241022", 
    # "claude-3-opus-20240229": "claude-3-opus-20240229",
    "claude-sonnet-4-20250514": "claude-sonnet-4-20250514",
    # "claude-opus-4-20241212": "claude-opus-4-20241212",
    
    # Gemini models
    "gemini-1.5-flash": "gemini-1.5-flash",
    "gemini-2.0-flash-exp": "gemini-2.0-flash",
    "gemini-2.5-flash":"gemini-2.5-flash"
}

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

# --- Prompt Templates ---


def is_gemini_model(model_name):
    """Check if the model is a Gemini model"""
    return model_name.startswith("gemini-")

def is_claude_model(model_name):
    """Check if the model is a Claude model"""
    return model_name.startswith("claude-")

def is_openai_model(model_name):
    """Check if the model is an OpenAI model"""
    return model_name.startswith("openai/")

def apply_llm_preset(preset_name, **override_params):
    """Apply a predefined parameter preset with optional overrides"""
    if preset_name not in LLM_PRESETS:
        print(f"[WARNING]  Unknown preset '{preset_name}'. Available: {list(LLM_PRESETS.keys())}")
        return DEFAULT_LLM_PARAMS.copy()
    
    # Start with defaults, apply preset, then apply any overrides
    params = DEFAULT_LLM_PARAMS.copy()
    params.update(LLM_PRESETS[preset_name])
    params.update(override_params)
    
    return params

def get_llm_response(prompt, model_name, max_tokens=None, temperature=None, top_p=None, frequency_penalty=None, presence_penalty=None, custom_clients=None):
    """Get LLM response from Groq, Gemini, or Anthropic based on model name with configurable parameters"""
    # Use default parameters if not specified
    max_tokens = max_tokens or DEFAULT_LLM_PARAMS["max_tokens"]
    temperature = temperature if temperature is not None else DEFAULT_LLM_PARAMS["temperature"]
    top_p = top_p if top_p is not None else DEFAULT_LLM_PARAMS["top_p"]
    frequency_penalty = frequency_penalty if frequency_penalty is not None else DEFAULT_LLM_PARAMS["frequency_penalty"]
    presence_penalty = presence_penalty if presence_penalty is not None else DEFAULT_LLM_PARAMS["presence_penalty"]

    # Use custom clients if provided, otherwise use global clients
    active_groq_client = client
    active_anthropic_client = anthropic_client
    active_gemini_client = gemini_client

    if custom_clients:
        active_groq_client = custom_clients.get('groq', client)
        active_anthropic_client = custom_clients.get('anthropic', anthropic_client)
        active_gemini_client = custom_clients.get('gemini', gemini_client)

    if is_gemini_model(model_name):
        if not active_gemini_client:
            raise Exception("Gemini client not configured. Please set GEMINI_API_KEY environment variable.")
        
        try:
            model = active_gemini_client.GenerativeModel(model_name)
            
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    top_p=top_p,
                )
            )
            
            # FIX: Check for blocked response more thoroughly
            if not response.candidates or len(response.candidates) == 0:
                raise Exception(f"No response candidates from {model_name}")
            
            candidate = response.candidates[0]
            
            # Check finish reason BEFORE trying to access text
            if hasattr(candidate, 'finish_reason'):
                finish_reason = candidate.finish_reason
                if finish_reason == 2:  # MAX_TOKENS
                    # For MAX_TOKENS, we might still have partial text
                    if candidate.content and candidate.content.parts:
                        partial_text = candidate.content.parts[0].text
                        if partial_text and partial_text.strip():
                            print(f"Warning: {model_name} hit max tokens, using partial response")
                            # Continue with partial response
                        else:
                            raise Exception(f"{model_name} hit max token limit with no usable output. Try increasing max_tokens or simplifying prompt.")
                    else:
                        raise Exception(f"{model_name} hit max token limit with no output")
                elif finish_reason == 3:  # SAFETY
                    raise Exception(f"{model_name} response blocked by safety filters")
                elif finish_reason not in [0, 1]:  # Not UNSPECIFIED or STOP
                    raise Exception(f"{model_name} stopped with finish_reason {finish_reason}")
            
            # Now safely access the text
            if not candidate.content or not candidate.content.parts:
                raise Exception(f"No content parts in {model_name} response")
            
            response_text = candidate.content.parts[0].text
            if not response_text or not response_text.strip():
                raise Exception(f"Empty response from {model_name}")
            
            # Check if response has usage_metadata (real Gemini response)
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                # Use real Gemini response with actual usage metadata
                class GeminiResponse:
                    def __init__(self, gemini_response, content):
                        self.choices = [MockChoice(content)]
                        self.usage_metadata = gemini_response.usage_metadata  # Real Gemini usage data
                        # Add fallback usage for compatibility
                        self.usage = MockUsage()

                class MockChoice:
                    def __init__(self, content):
                        self.message = type('obj', (object,), {'content': content})

                class MockUsage:
                    def __init__(self):
                        self.prompt_tokens = int(len(prompt) / 4)
                        self.completion_tokens = int(len(response_text) / 4)
                        self.total_tokens = self.prompt_tokens + self.completion_tokens

                return GeminiResponse(response, response_text)
            else:
                # Fallback: Create mock response object if no real usage data
                class MockChoice:
                    def __init__(self, content):
                        self.message = type('obj', (object,), {'content': content})

                class MockUsage:
                    def __init__(self):
                        self.prompt_tokens = int(len(prompt) / 4)
                        self.completion_tokens = int(len(response_text) / 4)
                        self.total_tokens = self.prompt_tokens + self.completion_tokens

                class MockUsageMetadata:
                    def __init__(self, prompt_text, response_text):
                        self.prompt_token_count = int(len(prompt_text) / 4)
                        self.candidates_token_count = int(len(response_text) / 4)
                        self.total_token_count = self.prompt_token_count + self.candidates_token_count

                class MockResponse:
                    def __init__(self, content):
                        self.choices = [MockChoice(content)]
                        self.usage = MockUsage()  # Keep for compatibility
                        self.usage_metadata = MockUsageMetadata(prompt, response_text)  # Add Gemini format

                return MockResponse(response_text)
            
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")
    
    elif is_claude_model(model_name):
        # Use Anthropic Claude models
        if not active_anthropic_client:
            raise Exception("Anthropic client not configured. Please set ANTHROPIC_API_KEY environment variable.")

        try:
            response = active_anthropic_client.messages.create(
                model=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                system="You are a precise JSON generator. Return only valid JSON.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
                # Note: Claude doesn't support frequency_penalty/presence_penalty
            )
            
            # Create a mock response object similar to Groq's structure for compatibility
            class MockChoice:
                def __init__(self, content):
                    self.message = type('obj', (object,), {'content': content})
            
            class MockUsage:
                def __init__(self, input_tokens, output_tokens):
                    self.prompt_tokens = input_tokens
                    self.completion_tokens = output_tokens
                    self.total_tokens = input_tokens + output_tokens
            
            class MockResponse:
                def __init__(self, content, usage):
                    self.choices = [MockChoice(content)]
                    self.usage = usage
            
            # Safely extract text content with proper null checks
            text_content = ""
            if response.content and len(response.content) > 0 and hasattr(response.content[0], 'text'):
                text_content = response.content[0].text or ""

            return MockResponse(
                text_content,
                MockUsage(response.usage.input_tokens, response.usage.output_tokens)
            )
            
        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")
    
    else:
        # Use Groq for non-Gemini, non-Claude models (includes Llama and OpenAI models via Groq)
        if not active_groq_client:
            raise Exception("Groq client not configured. Please set GROQ_API_KEY environment variable.")

        return active_groq_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a precise JSON generator. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty
        )

def detect_schema_complexity(schema_data):
    """Auto-detect whether a schema is complex (hierarchical) or relational"""
    if not isinstance(schema_data, dict):
        return "relational"
    
    # Check for complex schema indicators
    for key, value in schema_data.items():
        if key.endswith('.HMD') or key.endswith('.VMD'):
            if isinstance(value, list) and value:
                # Check if any item has children
                for item in value:
                    if isinstance(item, dict) and 'children' in item:
                        return "complex"
                    # Check for nested structure in attribute names
                    if isinstance(item, dict):
                        for attr_key, attr_value in item.items():
                            if isinstance(attr_value, str) and '.' in attr_value:
                                return "complex"
    
    # Check for hierarchical structure in attribute names
    for key, value in schema_data.items():
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and '.' in item:
                    return "complex"
                elif isinstance(item, dict):
                    for attr_key, attr_value in item.items():
                        if isinstance(attr_value, str) and '.' in attr_value:
                            return "complex"
    
    return "relational"

# --- PROMPT TEMPLATES ---
PROMPT_TEMPLATES = {
    "complex": {
        "baseline": {
            "json_default": {
                "match": """Given are Schema1/Table 1 (source) and Schema2/Table 2 (target) in the [document, json file or images].
Identify the header attributes for the source and target schemas/tables.
Match the similar attributes between the source and target schemas/tables and output the matches in JSON structure:

{
 "matches": [{"source": "attribute_name1", "target": "attribute_name3"}]
}""",
                "merge": """Given are Schema1/Table 1 (source) and Schema2/Table 2 (target) in the [document, json file or images].
Identify the header attributes for the source and target schemas/tables.
Given are the following schemas and their match results:
Source Schema:
{source_schema_placeholder}
Target Schema:
{target_schema_placeholder}
Match Results:
{match_results_placeholder}
Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the match results provided above.

Create a new merged schema (Merged_Schema) from the matched attributes above.
Ensure the merged table includes all matching attributes and values from both source and target schemas.
Output the result in JSON format with the following structure:
{
  "HMD_Merged_Schema": [],
  "VMD_Merged_Schema": [],
  "Merged_Schema": [],
  "Merged_Data": []
}""",
                "instance_merge": """Given are Schema1/Table 1 (source) and Schema2/Table 2 (target) in the [document, json file or images].
Identify the header attributes for the source and target schemas/tables.
Given are the following schemas and their match results:
Source Schema:
{source_schema_placeholder}
Target Schema:
{target_schema_placeholder}
Match Results:
{match_results_placeholder}
Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the match results provided above.

Create a new merged schema (Merged_Schema) from the matched attributes above.
Ensure the merged table includes all matching attributes and values from both source and target schemas.
Output the result in JSON format with the following structure:
{
  "HMD_Merged_Schema": [],
  "VMD_Merged_Schema": [],
  "Merged_Schema": [],
  "Merged_Data": []
}"""
            }
        },
        "operator": {
            "json_default": {
                "match": """-----------------------------------------------------------
Complex Match Operator - Input(schema1 and schema2)
                       - Output(map M)
-----------------------------------------------------------

Convert schema 1 (Table 1) and schema 2(Table 2) into JSON while preserving its structure.
Analyze the data nodes in the JSON for each schema and identify child attributes for each header attribute based on the hierarchical structure within the data node.
For each schema/table, list:
1) Horizontal (HMD) attributes along with their child attributes, if any.
2) Vertical (VMD) attributes along with their child attributes, if applicable.
3) Do not invent any attribute names unless they are present in the original schema.
For each schema/table, follow the JSON structure outlined below.

{
  "Table1.HMD": [
    {
      "attribute1": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    },
    {
      "attribute2": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    }
   ],
    "Table1.VMD":[
    {
      "attribute1": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    },
    {
      "attribute2": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    }
}

Given the HMD source schema and HMD target schema from above.

Act as a schema matcher for hierarchical, non-relational schemas.
Your task is to identify semantic matches between a source schema and a target schema by analyzing their nested JSON structure.
Each schema is represented as a hierarchical JSON, where:
Keys represent attribute hierarchy
Values specify attribute name
Nested structures ("children") define sub-attributes defined as child_level#, where # is number of levels
Two attributes semantically match if and only if there exists an invertible function that maps all values from one attribute (including its sub-attributes) to the corresponding target attribute.
The set of all attribute names is called table schema or metadata. Metadata is a set of attributes of a table. Metadata can be stored in a row or in a column. A table with hierarchical metadata is a complex, non-relational table that, similar to a relational table, has metadata (i.e., attributes), but unlike a relational table it may be found not only in a row, but also in a column. It may also take several rows or columns. Such rows with metadata are called horizontal metadata (HMD).On the other hand, such columns with metadata are called vertical metadata (VMD)

Instructions:
I will first provide the source schema in a hierarchical JSON format.
Then, I will provide the target schema in the same format.
You must analyze the hierarchical relationships and identify semantic matches at all levels.
Sample input JSON for a table (Table1 or Source)  with separate JSON for HMD and VMD
{
  "Table1.HMD": [
    {
      "attribute1": "attribute1name"
    },
    {
      "attribute2": "attribute2name",
      "children": [
        {
          "child_level1attribute1": "child_level1attribute1name",
          "children": [
            {
              "child_level2attribute1": "child_level2attribute1name"
            }
          ]
        }
      ]
    }
  ]
}


{
  "Table1.VMD": [
    {
      "attribute1": "attribute1name"
    },
    {
      "attribute2": "attribute2name",
      "children": [
        {
          "child_level1attribute1": "child_level1attribute1name",
          "children": [
            {
              "child_level2attribute1": "child_level2attribute1name"
            }
          ]
        }
      ]
    }
  ]
}

Provide the output as a structured JSON, following the template
{
  {"HMD_matches": [
    {"source": "attribute1name", "target": "attribute1name"},
    {"source": "attribute2name", "target": ".attribute2name"},
    {"source": "attribute2name.child_level1attribute1name", "target":  "attribute2name.child_level1attribute1name"},
{"source": "attribute2name.child_level1attribute1name.child_level2attribute1name", "target": "attribute2name.child_level1attribute1name.child_level2attribute1name"}
  ]
  },
  {
  "VMD_matches": [
  {"source": "attribute1name", "target": "attribute1name"},
    {"source": "attribute2name", "target": ".attribute2name"},
    {"source": "attribute2name.child_level1attribute1name", "target":  "attribute2name.child_level1attribute1name"},
{"source": "attribute2name.child_level1attribute1name.child_level2attribute1name", "target": "attribute2name.child_level1attribute1name.child_level2attribute1name"}

  ]
}
}
If either HMD or VMD is not present return [] for respective keys.

Example Input (Source Schema):
{
  "Table1.HMD": [
    {
      "attribute1": "name"
    },
    {
      "attribute2": "birth_date",
      "children": [
        {
          "child_level1.attribute1": "date_of_birth",
          "children": [
            {
              "child_level2.attribute1": "dob_formatted"
            }
          ]
        }
      ]
    }
  ]
}

Example Input (Target Schema):

{
  "Table2.HMD": [
    {
      "attribute1": "full_name"
    },
    {
      "attribute2": "dob",
      "children": [
        {
          "child_level1.attribute1": "dob_field",
          "children": [
            {
              "child_level2.attribute1": "formatted_dob"
            }
          ]
        }
      ]
    }
  ]
}



Expected Output (Schema Matches):


{
  {
   "HMD_matches": [
    {"source": "name", "target": "full_name"},
    {"source": "birth_date", "target": "dob"},
    {"source": "birth_date.date_of_birth", "target": "dob.dob_field"},
    {"source": "birth_date.date_of_birth.dob_formatted", "target": "dob.dob_field.formatted_dob"}
  ]
  },
  {"VMD_matches":[]}
}

Please do not match schema if they are not semantically equivalent, check for abbreviate equivalent form, and then do not show matching if parent attributes are not related!


VALIDATION CHECKLIST:
✓ Return ONLY valid JSON (no explanations)
✓ Use exact attribute names from schemas (no modifications)
✓ Include "Table1.HMD."/"Table1.VMD." and "Table2.HMD."/"Table2.VMD." prefixes
✓ Return empty arrays [] if no valid matches exist""",

                "merge": """Given are Table 1 (source1) and Table 2 (source2) in the [document or json file].

Convert schema 1 (Table 1) and schema 2(Table 2) into JSON while preserving its structure.
Analyze the data nodes in the JSON for each schema and identify child attributes for each header attribute based on the hierarchical structure within the data node.
For each schema/table, list:
1) Horizontal (HMD) attributes along with their child attributes, if any.
2) Vertical (VMD) attributes along with their child attributes, if applicable.
3) Do not invent any attribute names unless they are present in the original schema.
For each schema/table, follow the JSON structure outlined below.

{
  "Table1.HMD": [
    {
      "attribute1": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    },
    {
      "attribute2": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    }
   ],
    "Table1.VMD":[
    {
      "attribute1": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    },
    {
      "attribute2": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    }
}

Given the HMD source1 schema and HMD target/source2 schema from above.


Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}


Create a new merged schema (Merged_Schema) from the matched attributes above.
Add all remaining HDM and VMD attributes and their children from source1 (Schema1/Table1) and source2 (Schema2/Table2) in the new merged schema (Merged_Schema).
Output them in JSON format in the following structure:

{
  "HMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
  "VMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
}

Using the merged schema (Merged_Schema), for each HMD attribute in the HMD_Merged_Schema,
go through all the VMD attributes in the VMD_Merged_Schema list and add the corresponding values from source and target tables.
If no values are available, add "".
If HMD attribute has children then skip the attribute and create a list only for the children.
Output them in JSON format in the following structure:
}
"Merged_Data":[
        {"HMD.attr_name.child_name": "value" {
                {"VMD.attr_name.child_name1","source1": "value", "source2":"value"},
                {"VMD.attr_name.child_name2","source1": "value", "source2":"value"}
        }
        ]
}

Create a new map schema (Map_Schema1) that includes only the source1 (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{
  "HMD_Map_Schema1": [{"source1": "Merged_Schema.attr_name", "source2":"Schema1.attr_name"}],
  "VMD_Map_Schema1": [{"source1": "Merged_Schema.attr_name", "source2":"Schema1.attr_name"}],
}

Create a new map schema (Map_Schema2) that includes only the source2 (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:
{
  "HMD_Map_Schema2": [{"source1": "Merged_Schema.attr_name", "source2":"Schema2.attr_name"}],
  "VMD_Map_Schema2": [{"source1": "Merged_Schema.attr_name", "source2":"Schema2.attr_name"}],
}


If no valid matches exist, return: {"Merged_Schema":[]}""",

                "instance_merge": """Given are Table 1 (source1) and Table 2 (source2) in the [document or json file].

Convert schema 1 (Table 1) and schema 2(Table 2) into JSON while preserving its structure.
Analyze the data nodes in the JSON for each schema and identify child attributes for each header attribute based on the hierarchical structure within the data node.
For each schema/table, list:
1) Horizontal (HMD) attributes along with their child attributes, if any.
2) Vertical (VMD) attributes along with their child attributes, if applicable.
3) Do not invent any attribute names unless they are present in the original schema.
For each schema/table, follow the JSON structure outlined below.

{
  "Table1.HMD": [
    {
      "attribute1": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    },
    {
      "attribute2": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    }
   ],
    "Table1.VMD":[
    {
      "attribute1": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    },
    {
      "attribute2": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    }
}

Given the HMD source1 schema and HMD target/source2 schema from above.


Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}


Create a new merged schema (Merged_Schema) from the matched attributes above.
Add all remaining HDM and VMD attributes and their children from source1 (Schema1/Table1) and source2 (Schema2/Table2) in the new merged schema (Merged_Schema).
Output them in JSON format in the following structure:

{
  "HMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
  "VMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
}

Using the merged schema (Merged_Schema), for each HMD attribute in the HMD_Merged_Schema,
go through all the VMD attributes in the VMD_Merged_Schema list and add the corresponding values from source and target tables.
If no values are available, add "".
If HMD attribute has children then skip the attribute and create a list only for the children.
Output them in JSON format in the following structure:
}
"Merged_Data":[
        {"HMD.attr_name.child_name": "value" {
                {"VMD.attr_name.child_name1","source1": "value", "source2":"value"},
                {"VMD.attr_name.child_name2","source1": "value", "source2":"value"}
        }
        ]
}

Create a new map schema (Map_Schema1) that includes only the source1 (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{
  "HMD_Map_Schema1": [{"source1": "Merged_Schema.attr_name", "source2":"Schema1.attr_name"}],
  "VMD_Map_Schema1": [{"source1": "Merged_Schema.attr_name", "source2":"Schema1.attr_name"}],
}

Create a new map schema (Map_Schema2) that includes only the source2 (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:
{
  "HMD_Map_Schema2": [{"source1": "Merged_Schema.attr_name", "source2":"Schema2.attr_name"}],
  "VMD_Map_Schema2": [{"source1": "Merged_Schema.attr_name", "source2":"Schema2.attr_name"}],
}


If no valid matches exist, return: {"HMD_Merged_Schema":[], "VMD_Merged_Schema":[], "Merged_Data":{}, "HMD_Map_Schema1":[], "VMD_Map_Schema1":[], "HMD_Map_Schema2":[], "VMD_Map_Schema2":[]}

VALIDATION CHECKLIST:
✓ Return ONLY valid JSON (no text outside JSON)
✓ Include all 7 required fields: HMD_Merged_Schema, VMD_Merged_Schema, Merged_Data, HMD_Map_Schema1, VMD_Map_Schema1, HMD_Map_Schema2, VMD_Map_Schema2
✓ Use proper JSON syntax (commas, brackets, quotes)
✓ Validate JSON before responding
            """
            },
            "kg_enhanced": {
                "match": """-----------------------------------------------------------
Knowledge Graph Enhanced Complex Match Operator - Input(schema1 and schema2)
                                                  - Output(map M)
-----------------------------------------------------------

Convert schema 1 (Table 1) and schema 2(Table 2) into JSON while preserving its structure.
Analyze the data nodes in the JSON for each schema and identify child attributes for each header attribute based on the hierarchical structure within the data node.
For each schema/table, list:
1) Horizontal (HMD) attributes along with their child attributes, if any.
2) Vertical (VMD) attributes along with their child attributes, if applicable.
3) Do not invent any attribute names unless they are present in the original schema.
For each schema/table, follow the JSON structure outlined below.

{
  "Table1.HMD": [
    {
      "attribute1": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    },
    {
      "attribute2": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    }
   ],
    "Table1.VMD":[
    {
      "attribute1": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    },
    {
      "attribute2": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    }
}

Given the HMD source schema and HMD target schema from above.

Act as an enhanced schema matcher for hierarchical, non-relational schemas with knowledge graph support.
Your task is to identify semantic matches between a source schema and a target schema by analyzing their nested JSON structure and leveraging external knowledge graphs for improved semantic understanding.

KNOWLEDGE GRAPH ENHANCEMENT:
Before performing matching, consider leveraging the following knowledge graphs and ontologies to understand semantic relationships:
1. DBpedia - For general domain knowledge and entity relationships
2. YAGO - For hierarchical taxonomies and semantic types
3. Wikidata - For structured data about entities and their properties
4. Schema.org - For web semantic markup and common data types
5. Domain-specific ontologies when applicable

For each attribute in both schemas:
- Look for synonyms, hypernyms, hyponyms, and related concepts
- Consider multilingual variations and alternative naming conventions
- Identify semantic type hierarchies (e.g., "age" and "years_old" both relate to temporal measurement)
- Use knowledge graph relationships to find indirect semantic connections

Each schema is represented as a hierarchical JSON, where:
Keys represent attribute hierarchy
Values specify attribute name
Nested structures ("children") define sub-attributes defined as child_level#, where # is number of levels
Two attributes semantically match if and only if there exists an invertible function that maps all values from one attribute (including its sub-attributes) to the corresponding target attribute, OR if they represent the same semantic concept according to knowledge graph relationships.

The set of all attribute names is called table schema or metadata. Metadata is a set of attributes of a table. Metadata can be stored in a row or in a column. A table with hierarchical metadata is a complex, non-relational table that, similar to a relational table, has metadata (i.e., attributes), but unlike a relational table it may be found not only in a row, but also in a column. It may also take several rows or columns. Such rows with metadata are called horizontal metadata (HMD).On the other hand, such columns with metadata are called vertical metadata (VMD)

Instructions:
I will first provide the source schema in a hierarchical JSON format.
Then, I will provide the target schema in the same format.
You must analyze the hierarchical relationships and identify semantic matches at all levels using knowledge graph insights when helpful.

Sample input JSON for a table (Table1 or Source) with separate JSON for HMD and VMD
{
  "Table1.HMD": [
    {
      "attribute1": "attribute1name"
    },
    {
      "attribute2": "attribute2name",
      "children": [
        {
          "child_level1attribute1": "child_level1attribute1name",
          "children": [
            {
              "child_level2attribute1": "child_level2attribute1name"
            }
          ]
        }
      ]
    }
  ]
}

{
  "Table1.VMD": [
    {
      "attribute1": "attribute1name"
    },
    {
      "attribute2": "attribute2name",
      "children": [
        {
          "child_level1attribute1": "child_level1attribute1name",
          "children": [
            {
              "child_level2attribute1": "child_level2attribute1name"
            }
          ]
        }
      ]
    }
  ]
}

Provide the output as a structured JSON, following the template
{
  {"HMD_matches": [
    {"source": "attribute1name", "target": "attribute1name"},
    {"source": "attribute2name", "target": ".attribute2name"},
    {"source": "attribute2name.child_level1attribute1name", "target":  "attribute2name.child_level1attribute1name"},
{"source": "attribute2name.child_level1attribute1name.child_level2attribute1name", "target": "attribute2name.child_level1attribute1name.child_level2attribute1name"}
  ]
  },
  {
  "VMD_matches": [
  {"source": "attribute1name", "target": "attribute1name"},
    {"source": "attribute2name", "target": ".attribute2name"},
    {"source": "attribute2name.child_level1attribute1name", "target":  "attribute2name.child_level1attribute1name"},
{"source": "attribute2name.child_level1attribute1name.child_level2attribute1name", "target": "attribute2name.child_level1attribute1name.child_level2attribute1name"}

  ]
}
}
If either HMD or VMD is not present return [] for respective keys.

Example Input (Source Schema):
{
  "Table1.HMD": [
    {
      "attribute1": "name"
    },
    {
      "attribute2": "birth_date",
      "children": [
        {
          "child_level1.attribute1": "date_of_birth",
          "children": [
            {
              "child_level2.attribute1": "dob_formatted"
            }
          ]
        }
      ]
    }
  ]
}

Example Input (Target Schema):

{
  "Table2.HMD": [
    {
      "attribute1": "full_name"
    },
    {
      "attribute2": "dob",
      "children": [
        {
          "child_level1.attribute1": "dob_field",
          "children": [
            {
              "child_level2.attribute1": "formatted_dob"
            }
          ]
        }
      ]
    }
  ]
}

Expected Output (Schema Matches):
{
  {
   "HMD_matches": [
    {"source": "name", "target": "full_name"},
    {"source": "birth_date", "target": "dob"},
    {"source": "birth_date.date_of_birth", "target": "dob.dob_field"},
    {"source": "birth_date.date_of_birth.dob_formatted", "target": "dob.dob_field.formatted_dob"}
  ]
  },
  {
  "VMD_matches": []
}
}""",
                "merge": """Given are Table 1 (source1) and Table 2 (source2) in the [document or json file].

Convert schema 1 (Table 1) and schema 2(Table 2) into JSON while preserving its structure.
Analyze the data nodes in the JSON for each schema and identify child attributes for each header attribute based on the hierarchical structure within the data node.
For each schema/table, list:
1) Horizontal (HMD) attributes along with their child attributes, if any.
2) Vertical (VMD) attributes along with their child attributes, if applicable.
3) Do not invent any attribute names unless they are present in the original schema.
For each schema/table, follow the JSON structure outlined below.

{
  "Table1.HMD": [
    {
      "attribute1": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    },
    {
      "attribute2": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    }
   ],
    "Table1.VMD":[
    {
      "attribute1": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    },
    {
      "attribute2": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    }
}

Given the HMD source1 schema and HMD target/source2 schema from above.


Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}


Create a new merged schema (Merged_Schema) from the matched attributes above.
Add all remaining HDM and VMD attributes and their children from source1 (Schema1/Table1) and source2 (Schema2/Table2) in the new merged schema (Merged_Schema).
Output them in JSON format in the following structure:

{
  "HMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
  "VMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
}

Using the merged schema (Merged_Schema), for each HMD attribute in the HMD_Merged_Schema,
go through all the VMD attributes in the VMD_Merged_Schema list and add the corresponding values from source and target tables.
If no values are available, add "".
If HMD attribute has children then skip the attribute and create a list only for the children.
Output them in JSON format in the following structure:
}
"Merged_Data":[
        {"HMD.attr_name.child_name": "value" {
                {"VMD.attr_name.child_name1","source1": "value", "source2":"value"},
                {"VMD.attr_name.child_name2","source1": "value", "source2":"value"}
        }
        ]
}

Create a new map schema (Map_Schema1) that includes only the source1 (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{
  "HMD_Map_Schema1": [{"source1": "Merged_Schema.attr_name", "source2":"Schema1.attr_name"}],
  "VMD_Map_Schema1": [{"source1": "Merged_Schema.attr_name", "source2":"Schema1.attr_name"}],
}

Create a new map schema (Map_Schema2) that includes only the source2 (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:
{
  "HMD_Map_Schema2": [{"source1": "Merged_Schema.attr_name", "source2":"Schema2.attr_name"}],
  "VMD_Map_Schema2": [{"source1": "Merged_Schema.attr_name", "source2":"Schema2.attr_name"}],
}


If no valid matches exist, return: {"Merged_Schema":[]}""",
                "instance_merge": """Given are Table 1 (source1) and Table 2 (source2) in the [document or json file].

Convert schema 1 (Table 1) and schema 2(Table 2) into JSON while preserving its structure.
Analyze the data nodes in the JSON for each schema and identify child attributes for each header attribute based on the hierarchical structure within the data node.
For each schema/table, list:
1) Horizontal (HMD) attributes along with their child attributes, if any.
2) Vertical (VMD) attributes along with their child attributes, if applicable.
3) Do not invent any attribute names unless they are present in the original schema.
For each schema/table, follow the JSON structure outlined below.

{
  "Table1.HMD": [
    {
      "attribute1": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    },
    {
      "attribute2": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    }
   ],
    "Table1.VMD":[
    {
      "attribute1": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    },
    {
      "attribute2": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    }
}

Given the HMD source1 schema and HMD target/source2 schema from above.


Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}


Create a new merged schema (Merged_Schema) from the matched attributes above.
Add all remaining HDM and VMD attributes and their children from source1 (Schema1/Table1) and source2 (Schema2/Table2) in the new merged schema (Merged_Schema).
Output them in JSON format in the following structure:

{
  "HMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
  "VMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
}

Using the merged schema (Merged_Schema), for each HMD attribute in the HMD_Merged_Schema,
go through all the VMD attributes in the VMD_Merged_Schema list and add the corresponding values from source and target tables.
If no values are available, add "".
If HMD attribute has children then skip the attribute and create a list only for the children.
Output them in JSON format in the following structure:
}
"Merged_Data":[
        {"HMD.attr_name.child_name": "value" {
                {"VMD.attr_name.child_name1","source1": "value", "source2":"value"},
                {"VMD.attr_name.child_name2","source1": "value", "source2":"value"}
        }
        ]
}

Create a new map schema (Map_Schema1) that includes only the source1 (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{
  "HMD_Map_Schema1": [{"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}],
  "VMD_Map_Schema1": [{"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}],
}

Create a new map schema (Map_Schema2) that includes only the source2 (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "HMD_Map_Schema2": [{"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}],
  "VMD_Map_Schema2": [{"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}],
}

If no valid matches exist, return: {"HMD_Merged_Schema":[], "VMD_Merged_Schema":[], "Merged_Data":{}, "HMD_Map_Schema1":[], "VMD_Map_Schema1":[], "HMD_Map_Schema2":[], "VMD_Map_Schema2":[]}

VALIDATION CHECKLIST:
✓ Return ONLY valid JSON (no text outside JSON)
✓ Include all 7 required fields: HMD_Merged_Schema, VMD_Merged_Schema, Merged_Data, HMD_Map_Schema1, VMD_Map_Schema1, HMD_Map_Schema2, VMD_Map_Schema2
✓ Use proper JSON syntax (commas, brackets, quotes)
✓ Validate JSON before responding
            """
            },
            "multi_step": {
                "match": """-----------------------------------------------------------
Multi-Step Complex Match Operator - Input(schema1 and schema2)
                                   - Output(map M)
                         Using 3-Round Ensemble Approach
-----------------------------------------------------------

Convert schema 1 (Table 1) and schema 2(Table 2) into JSON while preserving its structure.
Analyze the data nodes in the JSON for each schema and identify child attributes for each header attribute based on the hierarchical structure within the data node.
For each schema/table, list:
1) Horizontal (HMD) attributes along with their child attributes, if any.
2) Vertical (VMD) attributes along with their child attributes, if applicable.
3) Do not invent any attribute names unless they are present in the original schema.
For each schema/table, follow the JSON structure outlined below.

{
  "Table1.HMD": [
    {
      "attribute1": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    },
    {
      "attribute2": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    }
   ],
    "Table1.VMD":[
    {
      "attribute1": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    },
    {
      "attribute2": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    }
}

Given the HMD source schema and HMD target schema from above.

Act as a schema matcher for hierarchical, non-relational schemas.
Your task is to identify semantic matches between a source schema and a target schema by analyzing their nested JSON structure.

MULTI-STEP APPROACH INSTRUCTIONS:
- This is one of three independent matching attempts
- Use your best judgment and reasoning for this specific attempt
- Consider different semantic perspectives and matching strategies
- Focus on finding accurate and meaningful matches
- Be thorough in your analysis

Each schema is represented as a hierarchical JSON, where:
Keys represent attribute hierarchy
Values specify attribute name
Nested structures ("children") define sub-attributes defined as child_level#, where # is number of levels
Two attributes semantically match if and only if there exists an invertible function that maps all values from one attribute (including its sub-attributes) to the corresponding target attribute.

The set of all attribute names is called table schema or metadata. Metadata is a set of attributes of a table. Metadata can be stored in a row or in a column. A table with hierarchical metadata is a complex, non-relational table that, similar to a relational table, has metadata (i.e., attributes), but unlike a relational table it may be found not only in a row, but also in a column. It may also take several rows or columns. Such rows with metadata are called horizontal metadata (HMD).On the other hand, such columns with metadata are called vertical metadata (VMD)

Instructions:
I will first provide the source schema in a hierarchical JSON format.
Then, I will provide the target schema in the same format.
You must analyze the hierarchical relationships and identify semantic matches at all levels.

Sample input JSON for a table (Table1 or Source) with separate JSON for HMD and VMD
{
  "Table1.HMD": [
    {
      "attribute1": "attribute1name"
    },
    {
      "attribute2": "attribute2name",
      "children": [
        {
          "child_level1attribute1": "child_level1attribute1name",
          "children": [
            {
              "child_level2attribute1": "child_level2attribute1name"
            }
          ]
        }
      ]
    }
  ]
}

{
  "Table1.VMD": [
    {
      "attribute1": "attribute1name"
    },
    {
      "attribute2": "attribute2name",
      "children": [
        {
          "child_level1attribute1": "child_level1attribute1name",
          "children": [
            {
              "child_level2attribute1": "child_level2attribute1name"
            }
          ]
        }
      ]
    }
  ]
}

Provide the output as a structured JSON, following the template
{
  {"HMD_matches": [
    {"source": "attribute1name", "target": "attribute1name"},
    {"source": "attribute2name", "target": ".attribute2name"},
    {"source": "attribute2name.child_level1attribute1name", "target":  "attribute2name.child_level1attribute1name"},
{"source": "attribute2name.child_level1attribute1name.child_level2attribute1name", "target": "attribute2name.child_level1attribute1name.child_level2attribute1name"}
  ]
  },
  {
  "VMD_matches": [
  {"source": "attribute1name", "target": "attribute1name"},
    {"source": "attribute2name", "target": ".attribute2name"},
    {"source": "attribute2name.child_level1attribute1name", "target":  "attribute2name.child_level1attribute1name"},
{"source": "attribute2name.child_level1attribute1name.child_level2attribute1name", "target": "attribute2name.child_level1attribute1name.child_level2attribute1name"}

  ]
}
}
If either HMD or VMD is not present return [] for respective keys.""",

                "merge": """Given are the following schemas and their match results:

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Match Results:
{match_results_placeholder}

Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the match results provided above.

MULTI-STEP APPROACH INSTRUCTIONS:
- This is one of three independent merging attempts
- Use your best judgment for this specific merge attempt
- Consider different merging strategies and perspectives
- Focus on creating a comprehensive and accurate merged schema

Create a new merged schema (Merged_Schema) from the matched attributes above.
Add all remaining HDM and VMD attributes and their children from source1 (Schema1/Table1) and source2 (Schema2/Table2) in the new merged schema (Merged_Schema).
Output them in JSON format in the following structure:

{
  "HMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
  "VMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
}

Using the merged schema (Merged_Schema), for each HMD attribute in the HMD_Merged_Schema,
go through all the VMD attributes in the VMD_Merged_Schema list and add the corresponding values from source and target tables.
If no values are available, add "".
If HMD attribute has children then skip the attribute and create a list only for the children.
Output them in JSON format in the following structure:
}
"Merged_Data":[
        {"HMD.attr_name.child_name": "value" {
                {"VMD.attr_name.child_name1","source1": "value", "source2":"value"},
                {"VMD.attr_name.child_name2","source1": "value", "source2":"value"}
        }
        ]
}

Create a new map schema (Map_Schema1) that includes only the source1 (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{
  "HMD_Map_Schema1": [{"source1": "Merged_Schema.attr_name", "source2":"Schema1.attr_name"}],
  "VMD_Map_Schema1": [{"source1": "Merged_Schema.attr_name", "source2":"Schema1.attr_name"}],
}

Create a new map schema (Map_Schema2) that includes only the source2 (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:
{
  "HMD_Map_Schema2": [{"source1": "Merged_Schema.attr_name", "source2":"Schema2.attr_name"}],
  "VMD_Map_Schema2": [{"source1": "Merged_Schema.attr_name", "source2":"Schema2.attr_name"}],
}

If no valid matches exist, return: {"Merged_Schema":[]}""",

                "instance_merge": """Given are the following schemas and their match results:

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Match Results:
{match_results_placeholder}

Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the match results provided above.

MULTI-STEP APPROACH INSTRUCTIONS:
- This is one of three independent instance merging attempts
- Use your best judgment for this specific instance merge attempt
- Consider different instance merging strategies and perspectives
- Focus on creating accurate merged data instances

Create a new merged schema (Merged_Schema) from the matched attributes above.
Add all remaining HDM and VMD attributes and their children from source1 (Schema1/Table1) and source2 (Schema2/Table2) in the new merged schema (Merged_Schema).
Output them in JSON format in the following structure:

{
  "HMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
  "VMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
}

Using the merged schema (Merged_Schema), for each HMD attribute in the HMD_Merged_Schema,
go through all the VMD attributes in the VMD_Merged_Schema list and add the corresponding values from source and target tables.
If no values are available, add "".
If HMD attribute has children then skip the attribute and create a list only for the children.
Output them in JSON format in the following structure:
}
"Merged_Data":[
        {"HMD.attr_name.child_name": "value" {
                {"VMD.attr_name.child_name1","source1": "value", "source2":"value"},
                {"VMD.attr_name.child_name2","source1": "value", "source2":"value"}
        }
        ]
}

Create a new map schema (Map_Schema1) that includes only the source1 (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{
  "HMD_Map_Schema1": [{"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}],
  "VMD_Map_Schema1": [{"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}],
}

Create a new map schema (Map_Schema2) that includes only the source2 (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "HMD_Map_Schema2": [{"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}],
  "VMD_Map_Schema2": [{"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}],
}

If no valid matches exist, return: {"HMD_Merged_Schema":[], "VMD_Merged_Schema":[], "Merged_Data":{}, "HMD_Map_Schema1":[], "VMD_Map_Schema1":[], "HMD_Map_Schema2":[], "VMD_Map_Schema2":[]}

VALIDATION CHECKLIST:
✓ Return ONLY valid JSON (no text outside JSON)
✓ Include all 7 required fields: HMD_Merged_Schema, VMD_Merged_Schema, Merged_Data, HMD_Map_Schema1, VMD_Map_Schema1, HMD_Map_Schema2, VMD_Map_Schema2
✓ Use proper JSON syntax (commas, brackets, quotes)
✓ Validate JSON before responding
            """,

                "ensemble": """You are an ensemble aggregator for multi-step schema processing results.

You have been given 3 independent responses for the same schema operation. Your task is to analyze these responses and create a single, high-quality merged result that combines the best aspects of all three responses.

ENSEMBLE AGGREGATION INSTRUCTIONS:
1. Compare the three responses carefully
2. Look for consensus across responses - matches/mappings that appear in multiple responses are likely correct
3. Use majority voting where applicable
4. For merge operations, combine unique valid entries from all responses
5. Maintain the exact same JSON structure as the individual responses
6. Ensure completeness - don't lose valid information from any response
7. Prioritize quality and accuracy over quantity

INPUT: Three independent responses labeled Response1, Response2, and Response3

Response1:
{response1}

Response2:
{response2}

Response3:
{response3}

OUTPUT: A single aggregated response following the exact same JSON structure as the input responses.

For matching operations, output:
{
  "HMD_matches": [...],
  "VMD_matches": [...]
}

For merge/instance_merge operations, output:
{
  "HMD_Merged_Schema": [...],
  "VMD_Merged_Schema": [...],
  "Merged_Data": [...],
  "HMD_Map_Schema1": [...],
  "VMD_Map_Schema1": [...],
  "HMD_Map_Schema2": [...],
  "VMD_Map_Schema2": [...]
}

Apply ensemble logic to create the best possible aggregated result."""
            }
        },
        "schema": {
            "json_default": {
                "merge": """Given are sources (Schema1/Table1) and target (Schema2/Table2) in the [document or json file].

Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source schema (Table1) and a target schema (Table2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Create a new merged schema from the matched attributes above.
Add all remaining HMD and VMD attributes and their children from source1 (Schema1/Table1) and source2 (Schema2/Table2) in the new merged schema (Merged_Schema).
Output them in JSON format in the following structure:

{
  "HMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
  "VMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
  "Merged_Data": [...],
  "HMD_Map_Schema1": [...],
  "VMD_Map_Schema1": [...],
  "HMD_Map_Schema2": [...],
  "VMD_Map_Schema2": [...]
}

If no valid matches exist, return: {"Merged_Schema":[]}"""
            },
            "multi_step": {
                "merge": """Given are the following schemas and their match results:

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Match Results:
{match_results_placeholder}

MULTI-STEP SCHEMA MERGE INSTRUCTIONS:
- This is one of three independent schema merging attempts
- Use your best judgment for this specific schema merge attempt
- Consider different merging strategies and perspectives
- Focus on creating accurate merged schema structures

Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the match results provided above.

Create a new merged schema from the matched attributes above.
Add all remaining HMD and VMD attributes and their children from source1 (Schema1/Table1) and source2 (Schema2/Table2) in the new merged schema (Merged_Schema).
Output them in JSON format in the following structure:

{
  "HMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
  "VMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
  "Merged_Data": [...],
  "HMD_Map_Schema1": [...],
  "VMD_Map_Schema1": [...],
  "HMD_Map_Schema2": [...],
  "VMD_Map_Schema2": [...]
}

If no valid matches exist, return: {"Merged_Schema":[]}"""
            }
        },
        "instance": {
            "json_default": {
                "merge": """Given are sources (Schema1/Table1) and target (Schema2/Table2) in the [document or json file].

Act as an instance merger for hierarchical, non-relational schemas.
Your task is to merge the actual data instances that are matched between the source schema (Table1) and a target schema (Table2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Create a new merged schema from the matched attributes above and merge the actual data instances.
Focus on combining the data values from both schemas, not just the structure.
Output them in JSON format in the following structure:

{
  "HMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
  "VMD_Merged_Schema": ["attr_name", "attr_name.children.attr_name"],
  "Merged_Data": [...],
  "HMD_Map_Schema1": [...],
  "VMD_Map_Schema1": [...],
  "HMD_Map_Schema2": [...],
  "VMD_Map_Schema2": [...]
}

If no valid matches exist, return: {"Merged_Schema":[]}"""
            }
        }
    },
    "relational": {
        "baseline": {
            "json_default": {
                "match": """Given are Schema1/Table 1 (source) and Schema2/Table 2 (target) in the [document, json file or images].
Identify the header attributes for the source and target schemas/tables.
Match the similar attributes between the source and target schemas/tables and output the matches in JSON structure:

{
 "matches": [{"source": "attribute_name1", "target": "attribute_name3"}]
}""",
                "merge": """Given are Schema1/Table 1 (source) and Schema2/Table 2 (target) in the [document, json file or images].
Identify the header attributes for the source and target schemas/tables.
Given are the following schemas and their match results:
Source Schema:
{source_schema_placeholder}
Target Schema:
{target_schema_placeholder}
Match Results:
{match_results_placeholder}
Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the match results provided above.

Create a new merged schema (Merged_Schema) from the matched attributes above.
Ensure the merged table includes all matching attributes and values from both source and target schemas.
Output the result in JSON format with the following structure:
{
  "HMD_Merged_Schema": [],
  "VMD_Merged_Schema": [],
  "Merged_Schema": [],
  "Merged_Data": []
}"""
            }
        },
        "operator": {
            "json_default": {
                "match": """Given are Table 1 (source) and Table 2 (target) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as a schema matcher for relational schemas.
Your task is to identify semantic matches between header attributes in a source schema (Table1) and a target schema (Table2) based on strict invertible transformations.
Two header attributes semantically match if and only if there exists an invertible function that maps all values of one attribute to the corresponding values of the other.

Instructions:
I will first input the header attribute names from the source schema.
Then, I will input the header attribute names from the target schema.
You must determine semantic matches between the source and target attributes.
Provide the output in JSON format as a mapping of matched attributes in the following structure:

{
"matches": [
{"source": "Table1.attr_name", "target": "Table2.attr_name"},
{"source": "Table1.attr_name", "target": "Table2.attr_name"}
]
}

If no valid matches exist, return: {"matches": []}""",
                "merge": """Given are sources (Schema1/Table1) and target (Schema2/Table2) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as a schema merger for relational schemas.
Your task is to merge the attributes that are matched between the source schema (Table1) and a target schema (Table2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Create a new merged schema from the matched attributes above and all remaining attributes in source (Schema1/Table1) and target (Schema2/Table2).
Add the attribute values in the "Merged_Data" and if no values are available, add "".
If the matched attributes from source and target have similar or the same valules, add source value and target value.
Also add the non-matched rows from both source and target tables.
Output them in JSON format in the following structure:

{ "Merged_Schema": ["attr_name", "attr_name"], "Merged_Data":["attr_name.value", { "source": "attr_name.value", "target":"attr_name.value"}] }

Create a new map schema (Map_Schema1) that includes only the source (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema1": [ {"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}]}

Create a new map schema (Map_Schema2) that includes only the target (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema2": [ {"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}]}

If no valid matches exist, return: {"Merged_Schema":[]}""",
                "instance_merge": """Given are sources (Schema1/Table1) and target (Schema2/Table2) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as a schema merger for relational schemas.
Your task is to merge the attributes that are matched between the source schema (Table1) and a target schema (Table2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Create a new merged schema from the matched attributes above and all remaining attributes in source (Schema1/Table1) and target (Schema2/Table2).
Add the attribute values in the "Merged_Data" and if no values are available, add "".
If the matched attributes from source and target have similar or the same valules, add source value and target value.
Also add the non-matched rows from both source and target tables.
Output them in JSON format in the following structure:

{ "Merged_Schema": ["attr_name", "attr_name"], "Merged_Data":["attr_name.value", { "source": "attr_name.value", "target":"attr_name.value"}] }

Create a new map schema (Map_Schema1) that includes only the source (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema1": [ {"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}]}

Create a new map schema (Map_Schema2) that includes only the target (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema2": [ {"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}]}

If no valid matches exist, return: {"Merged_Schema":[]}"""
            },
            "kg_enhanced": {
                "match": """Given are Table 1 (source) and Table 2 (target) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as an enhanced schema matcher for relational schemas with knowledge graph support.
Your task is to identify semantic matches between header attributes in a source schema (Table1) and a target schema (Table2) based on strict invertible transformations and enhanced by knowledge graph relationships.

KNOWLEDGE GRAPH ENHANCEMENT:
Before performing matching, consider leveraging the following knowledge graphs and ontologies to understand semantic relationships:
1. DBpedia - For general domain knowledge and entity relationships
2. YAGO - For hierarchical taxonomies and semantic types
3. Wikidata - For structured data about entities and their properties
4. Schema.org - For web semantic markup and common data types
5. Domain-specific ontologies when applicable

For each attribute in both schemas:
- Look for synonyms, hypernyms, hyponyms, and related concepts
- Consider multilingual variations and alternative naming conventions
- Identify semantic type hierarchies (e.g., "age" and "years_old" both relate to temporal measurement)
- Use knowledge graph relationships to find indirect semantic connections

Two header attributes semantically match if and only if there exists an invertible function that maps all values of one attribute to the corresponding values of the other, OR if they represent the same semantic concept according to knowledge graph relationships.

Instructions:
I will first input the header attribute names from the source schema.
Then, I will input the header attribute names from the target schema.
You must determine semantic matches between the source and target attributes using knowledge graph insights when helpful.
Provide the output in JSON format as a mapping of matched attributes in the following structure:

{
"matches": [
{"source": "Table1.attr_name", "target": "Table2.attr_name"},
{"source": "Table1.attr_name", "target": "Table2.attr_name"}
]
}

If no valid matches exist, return: {"matches": []}""",
                "merge": """Given are sources (Schema1/Table1) and target (Schema2/Table2) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as a schema merger for relational schemas.
Your task is to merge the attributes that are matched between the source schema (Table1) and a target schema (Table2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Create a new merged schema from the matched attributes above and all remaining attributes in source (Schema1/Table1) and target (Schema2/Table2).
Add the attribute values in the "Merged_Data" and if no values are available, add "".
If the matched attributes from source and target have similar or the same valules, add source value and target value.
Also add the non-matched rows from both source and target tables.
Output them in JSON format in the following structure:

{ "Merged_Schema": ["attr_name", "attr_name"], "Merged_Data":["attr_name.value", { "source": "attr_name.value", "target":"attr_name.value"}] }

Create a new map schema (Map_Schema1) that includes only the source (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema1": [ {"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}]}

Create a new map schema (Map_Schema2) that includes only the target (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema2": [ {"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}]}

If no valid matches exist, return: {"Merged_Schema":[]}""",
                "instance_merge": """Given are sources (Schema1/Table1) and target (Schema2/Table2) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as a schema merger for relational schemas.
Your task is to merge the attributes that are matched between the source schema (Table1) and a target schema (Table2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Create a new merged schema from the matched attributes above and all remaining attributes in source (Schema1/Table1) and target (Schema2/Table2).
Add the attribute values in the "Merged_Data" and if no values are available, add "".
If the matched attributes from source and target have similar or the same valules, add source value and target value.
Also add the non-matched rows from both source and target tables.
Output them in JSON format in the following structure:

{ "Merged_Schema": ["attr_name", "attr_name"], "Merged_Data":["attr_name.value", { "source": "attr_name.value", "target":"attr_name.value"}] }

Create a new map schema (Map_Schema1) that includes only the source (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema1": [ {"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}]}

Create a new map schema (Map_Schema2) that includes only the target (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema2": [ {"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}]}

If no valid matches exist, return: {"Merged_Schema":[]}"""
            },
            "multi_step": {
                "match": """Given are Table 1 (source) and Table 2 (target) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as a schema matcher for relational schemas.
Your task is to identify semantic matches between header attributes in a source schema (Table1) and a target schema (Table2) based on strict invertible transformations.

MULTI-STEP APPROACH INSTRUCTIONS:
- This is one of three independent matching attempts
- Use your best judgment and reasoning for this specific attempt
- Consider different semantic perspectives and matching strategies
- Focus on finding accurate and meaningful matches
- Be thorough in your analysis

Two header attributes semantically match if and only if there exists an invertible function that maps all values of one attribute to the corresponding values of the other.

Instructions:
I will first input the header attribute names from the source schema.
Then, I will input the header attribute names from the target schema.
You must determine semantic matches between the source and target attributes.
Provide the output in JSON format as a mapping of matched attributes in the following structure:

{
"matches": [
{"source": "Table1.attr_name", "target": "Table2.attr_name"},
{"source": "Table1.attr_name", "target": "Table2.attr_name"}
]
}

If no valid matches exist, return: {"matches": []}""",
                "merge": """Given are sources (Schema1/Table1) and target (Schema2/Table2) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as a schema merger for relational schemas.
Your task is to merge the attributes that are matched between the source schema (Table1) and a target schema (Table2) using the following match results:

MULTI-STEP APPROACH INSTRUCTIONS:
- This is one of three independent merging attempts
- Use your best judgment for this specific merge attempt
- Consider different merging strategies and perspectives
- Focus on creating a comprehensive and accurate merged schema

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Create a new merged schema from the matched attributes above and all remaining attributes in source (Schema1/Table1) and target (Schema2/Table2).
Add the attribute values in the "Merged_Data" and if no values are available, add "".
If the matched attributes from source and target have similar or the same valules, add source value and target value.
Also add the non-matched rows from both source and target tables.
Output them in JSON format in the following structure:

{ "Merged_Schema": ["attr_name", "attr_name"], "Merged_Data":["attr_name.value", { "source": "attr_name.value", "target":"attr_name.value"}] }

Create a new map schema (Map_Schema1) that includes only the source (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema1": [ {"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}]}

Create a new map schema (Map_Schema2) that includes only the target (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema2": [ {"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}]}

If no valid matches exist, return: {"Merged_Schema":[]}""",
                "instance_merge": """Given are sources (Schema1/Table1) and target (Schema2/Table2) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as a schema merger for relational schemas.
Your task is to merge the attributes that are matched between the source schema (Table1) and a target schema (Table2) using the following match results:

MULTI-STEP APPROACH INSTRUCTIONS:
- This is one of three independent instance merging attempts
- Use your best judgment for this specific instance merge attempt
- Consider different instance merging strategies and perspectives
- Focus on creating accurate merged data instances

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Create a new merged schema from the matched attributes above and all remaining attributes in source (Schema1/Table1) and target (Schema2/Table2).
Add the attribute values in the "Merged_Data" and if no values are available, add "".
If the matched attributes from source and target have similar or the same valules, add source value and target value.
Also add the non-matched rows from both source and target tables.
Output them in JSON format in the following structure:

{ "Merged_Schema": ["attr_name", "attr_name"], "Merged_Data":["attr_name.value", { "source": "attr_name.value", "target":"attr_name.value"}] }

Create a new map schema (Map_Schema1) that includes only the source (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema1": [ {"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}]}

Create a new map schema (Map_Schema2) that includes only the target (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema2": [ {"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}]}

If no valid matches exist, return: {"Merged_Schema":[]}""",
                "ensemble": """You are an ensemble aggregator for multi-step schema processing results.

You have been given 3 independent responses for the same schema operation. Your task is to analyze these responses and create a single, high-quality merged result that combines the best aspects of all three responses.

ENSEMBLE AGGREGATION INSTRUCTIONS:
1. Compare the three responses carefully
2. Look for consensus across responses - matches/mappings that appear in multiple responses are likely correct
3. Use majority voting where applicable
4. For merge operations, combine unique valid entries from all responses
5. Maintain the exact same JSON structure as the individual responses
6. Ensure completeness - don't lose valid information from any response
7. Prioritize quality and accuracy over quantity

INPUT: Three independent responses labeled Response1, Response2, and Response3

Response1:
{response1}

Response2:
{response2}

Response3:
{response3}

OUTPUT: A single aggregated response following the exact same JSON structure as the input responses.

For matching operations, output:
{
  "matches": [...]
}

For merge/instance_merge operations, output:
{
  "Merged_Schema": [...],
  "Merged_Data": [...],
  "Map_Schema1": [...],
  "Map_Schema2": [...]
}

Apply ensemble logic to create the best possible aggregated result."""
            }
        }
    }
}

# --- Pydantic Models for Response Validation ---
class MatchResult(BaseModel):
    matches: List[Dict[str, str]]

class MergeResult(BaseModel):
    Merged_Schema: List[str]
    Merged_Data: Optional[List[Dict[str, Any]]] = []
    Map_Schema1: Optional[List[Dict[str, str]]] = []
    Map_Schema2: Optional[List[Dict[str, str]]] = []

class ComplexInstanceMergeResult(BaseModel):
    HMD_Merged_Schema: List[Dict[str, Any]] = []
    VMD_Merged_Schema: List[Dict[str, Any]] = []
    Merged_Data: Dict[str, Any] = {}
    HMD_Map_Schema1: List[Dict[str, str]] = []
    VMD_Map_Schema1: List[Dict[str, str]] = []
    HMD_Map_Schema2: List[Dict[str, str]] = []
    VMD_Map_Schema2: List[Dict[str, str]] = []
    
    class Config:
        extra = "forbid"  # Prevent extra fields

class ProcessingMetrics(BaseModel):
    script_id: str
    timestamp: str
    llm_model: str
    schema_type: str
    processing_type: str
    operation_type: str
    total_generation_time: float
    input_prompt_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0
    total_tokens: Optional[int] = 0
    tokens_per_second: Optional[float] = 0.0
    api_call_cost: Optional[float] = 0.0
    preprocessing_time: Optional[float] = 0.0
    hmd_matches: Optional[int] = 0
    vmd_matches: Optional[int] = 0
    total_matches: Optional[int] = 0
    match_generation_time: Optional[float] = 0.0
    merge_generation_time: Optional[float] = 0.0

    # Detailed metrics for separate match and merge steps
    match_input_tokens: Optional[int] = None
    match_output_tokens: Optional[int] = None
    merge_input_tokens: Optional[int] = None
    merge_output_tokens: Optional[int] = None
    match_api_cost: Optional[float] = None
    merge_api_cost: Optional[float] = None
    matching_llm_used: Optional[str] = None
    merge_llm_used: Optional[str] = None
    pipeline_description: Optional[str] = None

def createEnhancedTable(data, type, matchData):
    """Create enhanced table with proper column counting"""
    html = '<div style="border: 2px solid #333; background: white; overflow: hidden;">'
    hmd_data = None
    vmd_data = None
    vmd_header = ''
    
    for key, value in data.items():
        if key.endswith('.HMD'):
            hmd_data = value
        elif key.endswith('.VMD'):
            vmd_data = value
        elif key.endswith('.VMD_HEADER') and isinstance(value, str):
            vmd_header = value
    
    if not hmd_data or not vmd_data:
        return '<p>Invalid table structure</p>'

    html += '<table style="width: 100%; border-collapse: collapse; font-size: 14px; font-weight: bold;">'
    
    # Build headers
    header_html = build_preview_headers_with_vmd(hmd_data, vmd_header)
    html += '<thead>' + ''.join(header_html) + '</thead>'
    
    html += '<tbody>'
    
    column_count = count_columns_from_hmd_fixed(hmd_data)
    
    # Enhanced VMD rendering with hierarchy support  
    # Get table data for this table
    table_data_values = None
    for key, value in data.items():
        if key.endswith('.Data'):
            table_data_values = value
            break
    
    html += render_vmd_rows_with_hierarchy(vmd_data, type, matchData, column_count, table_data_values)
    
    html += '</tbody></table></div>'
    return html

def flatten_hmd_and_rowheader(hmd_list):
    """Flatten HMD objects while preserving JSON order and handling complex hierarchies"""
    hmd_out = []
    row_header = None

    if not isinstance(hmd_list, list):
        return [], None

    max_depth = 1
    for obj in hmd_list:
        if not isinstance(obj, dict):
            continue
        children = obj.get("children", [])
        if isinstance(children, list) and children:
            max_depth = max(max_depth, 2)

    for obj in hmd_list:
        if not isinstance(obj, dict):
            continue

        parent = None
        is_attribute1 = False
        for k, v in obj.items():
            if k.startswith("attribute") and isinstance(v, str):
                parent = v.strip()
                if k == "attribute1":
                    is_attribute1 = True
                break

        children = obj.get("children", [])
        
        if is_attribute1:
            if row_header is None:
                row_header = parent
            
            if isinstance(children, list) and children:
                for child in children:
                    if isinstance(child, dict):
                        for _, grade in child.items():
                            if isinstance(grade, str) and grade.strip():
                                hmd_out.append(f"{parent}.{grade.strip()}" if parent else grade.strip())
            
        elif isinstance(children, list) and children:
            # Handle complex children structure (like Table2's Treatment Group)
            for child in children:
                if isinstance(child, dict):
                    # Extract all child_level1.attributeX values from this child object
                    child_attributes = []
                    for child_key, child_value in child.items():
                        if child_key.startswith("child_level1.") and isinstance(child_value, str) and child_value.strip():
                            child_attributes.append((child_key, child_value.strip()))
                    
                    # Sort by attribute order (attribute1, attribute2, etc.)
                    child_attributes.sort(key=lambda x: x[0])
                    
                    # Add each child column as a separate item
                    for _, child_value in child_attributes:
                        if parent:
                            hmd_out.append(f"{parent}.{child_value}")
                        else:
                            hmd_out.append(child_value)
        else:
            if parent:
                hmd_out.append({
                    "text": parent,
                    "is_childless": True,
                    "rowspan": max_depth,
                    "colspan": 1
                })

    return hmd_out, row_header

# --- DOCX Processing ---
def parse_docx_file(file_content):
    """Parse DOCX file and extract tables as structured data"""
    try:
        doc = Document(io.BytesIO(file_content))
        tables_data = {}
        
        for i, table in enumerate(doc.tables):
            table_name = f"Table{i+1}"
            
            raw_rows = []
            for row in table.rows:
                row_data = []
                for cell in row.cells:
                    cell_text = cell.text.strip()
                    row_data.append(cell_text if cell_text else "")
                raw_rows.append(row_data)
            
            table_structure = convert_docx_to_hmd_vmd_enhanced(raw_rows, table_name)
            tables_data.update(table_structure)
            
        return {
            "success": True,
            "data": tables_data,
            "html": convert_hmd_vmd_to_html_enhanced(tables_data)
        }
    except Exception as e:
        return {"success": False, "error": f"DOCX parsing error: {str(e)}"}

def convert_docx_to_hmd_vmd_enhanced(raw_rows, table_name):
    """Convert DOCX table to HMD/VMD structure with VMD hierarchy support"""
    result = {f"{table_name}.HMD": [], f"{table_name}.VMD": []}
    if not raw_rows:
        return result

    rows = [[(c or "").strip() for c in r] for r in raw_rows]

    while rows and not any(rows[0]):
        rows.pop(0)
    if not rows:
        return result

    header_rows = [rows[0]]
    data_start = 1

    for i in range(1, len(rows)):
        row = rows[i]
        nonempty = [c for c in row if c]
        if not nonempty:
            data_start = i + 1
            break
        if (len(row) > 0 and not row[0]) and sum(1 for c in row if c) >= 2:
            header_rows.append(row)
            data_start = i + 1
        else:
            data_start = i
            break

    is_complex = len(header_rows) >= 2

    if is_complex:
        hmd_data = build_hierarchical_hmd_fixed(header_rows)
    else:
        hmd_data = [c for c in header_rows[0] if c]

    # Enhanced VMD processing with hierarchy detection
    data_rows = rows[data_start:]
    vmd_data = build_hierarchical_vmd_structure(data_rows)

    if not vmd_data:
        hmd_data = [c for c in rows[0] if c]
        vmd_data = [r[0] for r in rows[1:] if r and r[0]]

    result[f"{table_name}.HMD"] = hmd_data
    result[f"{table_name}.VMD"] = vmd_data
    return result

def build_hierarchical_hmd_fixed(header_rows):
    """Build hierarchical HMD structure with fixed dot notation"""
    if not header_rows:
        return []
    
    cleaned_headers = []
    for row in header_rows:
        cleaned_row = [cell.strip() for cell in row]
        if any(cleaned_row):
            cleaned_headers.append(cleaned_row)
    
    if len(cleaned_headers) == 1:
        return build_single_level_hmd(cleaned_headers[0])
    elif len(cleaned_headers) == 2:
        return build_two_level_hmd_fixed(cleaned_headers)
    else:
        return build_three_level_hmd_fixed(cleaned_headers)

def build_two_level_hmd_fixed(header_rows):
    """Build two-level hierarchy with proper column mapping"""
    if len(header_rows) < 2:
        return build_single_level_hmd(header_rows[0])
    
    hmd = []
    row1, row2 = header_rows[0], header_rows[1]
    
    for i, cell in enumerate(row2):
        if cell:
            grade = cell
            treatment_for_this_column = None
            for j in range(i, -1, -1):
                if j < len(row1) and row1[j]:
                    treatment_for_this_column = row1[j]
                    break
            if treatment_for_this_column:
                full_path = f"{treatment_for_this_column}.{grade}"
                hmd.append(full_path)
    
    return hmd

def build_three_level_hmd_fixed(header_rows):
    """Build three-level hierarchy with proper column mapping"""
    if len(header_rows) < 3:
        return build_two_level_hmd_fixed(header_rows[:2])
    
    hmd = []
    row1, row2, row3 = header_rows[0], header_rows[1], header_rows[2]
    
    main_category = None
    for cell in row1:
        if cell:
            main_category = cell
            break
    if not main_category:
        return []
    
    for i, cell in enumerate(row3):
        if cell:
            grade = cell
            treatment_for_this_column = None
            for j in range(i, -1, -1):
                if j < len(row2) and row2[j]:
                    treatment_for_this_column = row2[j]
                    break
            if treatment_for_this_column:
                full_path = f"{main_category}.{treatment_for_this_column}.{grade}"
                hmd.append(full_path)
    
    return hmd

def build_single_level_hmd(header_row):
    """Build simple single-level hierarchy"""
    hmd = []
    for cell in header_row:
        if cell:
            hmd.append(cell)
    return hmd

def build_hierarchical_vmd_structure(data_rows):
    """Build hierarchical VMD structure to handle both flat and nested row patterns"""
    if not data_rows:
        return []
    
    vmd_structure = []
    current_category = None
    
    for row in data_rows:
        if not row or not row[0]:  # Skip empty rows
            continue
            
        first_col = row[0].strip()
        if not first_col:
            continue
            
        # Detect if this is a category header or data row
        # Category headers typically:
        # 1. Have text in first column but empty/minimal data in other columns
        # 2. Often end with patterns like "- no. (%)", "- years", etc.
        # 3. Are followed by indented sub-items
        
        is_category = detect_vmd_category_pattern(row, data_rows)
        
        if is_category:
            # This is a category header
            current_category = first_col
            vmd_structure.append({
                "text": current_category,
                "is_category": True,
                "children": []
            })
        else:
            # This is a data row
            if current_category and vmd_structure and vmd_structure[-1].get("is_category"):
                # Add as child to current category
                full_path = f"{current_category}.{first_col}"
                vmd_structure[-1]["children"].append(first_col)
                # Also add the full path for matching purposes
                vmd_structure.append(full_path)
            else:
                # Standalone row (flat structure)
                vmd_structure.append(first_col)
                current_category = None
    
    # Convert to mixed format that supports both hierarchical and flat
    return normalize_vmd_structure(vmd_structure)

def detect_vmd_category_pattern(current_row, all_rows):
    """Detect if a row is a category header based on patterns"""
    if not current_row or not current_row[0]:
        return False
    
    first_col = current_row[0].strip()
    
    # Pattern 1: Ends with category indicators
    category_indicators = [
        "- no. (%)", "- years", "- no.(%)", "(%)", 
        "- no", "index", "mass", "- years"
    ]
    
    if any(first_col.lower().endswith(indicator.lower()) for indicator in category_indicators):
        return True
    
    # Pattern 2: Has data in first column but minimal/no data in other columns
    # and the next rows seem to be sub-items (indented or related)
    non_empty_data_cols = sum(1 for cell in current_row[1:] if cell and cell.strip())
    
    if non_empty_data_cols <= 1:  # Category rows typically have little data
        # Check if next few rows look like sub-items
        current_idx = None
        for i, row in enumerate(all_rows):
            if row == current_row:
                current_idx = i
                break
        
        if current_idx is not None and current_idx + 1 < len(all_rows):
            next_row = all_rows[current_idx + 1]
            if next_row and next_row[0]:
                next_first_col = next_row[0].strip()
                # Check if next row looks like a sub-item
                if (len(next_first_col) < len(first_col) and 
                    not any(next_first_col.lower().endswith(ind.lower()) for ind in category_indicators)):
                    return True
    
    # Pattern 3: Title-case or specific formatting patterns
    if (first_col.istitle() and len(first_col.split()) <= 3 and 
        not first_col[0].islower()):
        return True
    
    return False

def normalize_vmd_structure(vmd_structure):
    """Normalize VMD structure to handle both flat and hierarchical formats"""
    normalized = []
    
    for item in vmd_structure:
        if isinstance(item, dict) and item.get("is_category"):
            # Add category as hierarchical object
            category_obj = {
                "text": item["text"],
                "is_vmd_category": True,
                "children": item.get("children", []),
                "rowspan": len(item.get("children", [])) if item.get("children") else 1
            }
            normalized.append(category_obj)
        elif isinstance(item, str):
            # Add as simple string (could be flat or hierarchical path)
            normalized.append(item)
    
    # If no hierarchical structure detected, fall back to flat
    if not any(isinstance(item, dict) for item in normalized):
        # Pure flat structure - convert all to simple strings
        flat_items = []
        for item in vmd_structure:
            if isinstance(item, dict):
                flat_items.append(item.get("text", str(item)))
            else:
                flat_items.append(str(item))
        return flat_items
    
    return normalized

def render_vmd_rows_with_hierarchy(vmd_data, type, matchData, column_count, table_data=None):
    """Render VMD rows as flat table like the original clean image"""
    if not vmd_data:
        return ''
    
    html = ''
    data_row_index = 0  # Track position in data array
    
    for index, item in enumerate(vmd_data):
        if isinstance(item, dict) and item.get("is_vmd_category"):
            # This is a hierarchical category with children
            category_text = item["text"]
            children = item.get("children", [])
            
            # Render category row first
            is_matched = isRowMatched(category_text, matchData) if matchData else False
            row_class = 'matched-row' if is_matched else ''
            row_id = f'{type}-vmd-category-{index}'
            
            html += f'<tr class="{row_class}" id="{row_id}" data-row="{category_text}">'
            
            # Category cell styling - bold and clean
            bg_color = 'white'
            escaped_name = category_text.replace('"', '&quot;')
            html += f'<td class="vmd-cell" style="border: 1px solid #333; padding: 4px; text-align: left; font-weight: bold; background: {bg_color};">'
            html += f'<span class="row-label" data-row-label="{escaped_name}">{category_text}</span>'
            html += '</td>'
            
            # Category row - no data (empty cells)
            for i in range(column_count):
                html += f'<td style="border: 1px solid #333; padding: 4px; background: white; text-align: center; font-weight: bold;" data-cell-value=""></td>'
            
            html += '</tr>'
            data_row_index += 1  # Skip the empty data row for category
            
            # Render children as separate rows with slight indentation
            for child_index, child in enumerate(children):
                child_matched = isRowMatched(child, matchData) if matchData else False
                child_row_class = 'matched-row' if child_matched else ''
                child_row_id = f'{type}-vmd-child-{index}-{child_index}'
                
                html += f'<tr class="{child_row_class}" id="{child_row_id}" data-row="{child}">'
                
                # Child cell with slight indentation
                child_bg = 'white'
                escaped_child = child.replace('"', '&quot;')
                html += f'<td class="vmd-cell" style="border: 1px solid #333; padding: 4px 4px 4px 12px; text-align: left; font-weight: normal; background: {child_bg};">'
                html += f'<span class="row-label" data-row-label="{escaped_child}">{child}</span>'
                html += '</td>'
                
                # Child data cells
                for i in range(column_count):
                    cell_value = ""
                    if table_data and data_row_index < len(table_data):
                        row_data = table_data[data_row_index]
                        if isinstance(row_data, list) and i < len(row_data):
                            cell_value = row_data[i] or ""
                    
                    # Apply color coding based on table type
                    if type == 'source' and cell_value:
                        cell_content = f'<span style="color: #8B4513; font-weight: bold;">{cell_value}</span>'
                    elif type == 'target' and cell_value:
                        cell_content = f'<span style="color: #800080; font-weight: bold;">{cell_value}</span>'
                    else:
                        cell_content = cell_value if cell_value else ''
                    
                    html += f'<td style="border: 1px solid #333; padding: 4px; background: white; text-align: center; font-weight: bold;" data-cell-value="{cell_value}">{cell_content}</td>'
                
                html += '</tr>'
                data_row_index += 1  # Move to next data row for next child
        
        elif isinstance(item, str):
            # Handle hierarchical paths - skip if already rendered as child
            if "." in item:
                # This might be a hierarchical path like "Category.Child"
                parts = item.split(".", 1)
                if len(parts) == 2:
                    # Check if this is already handled by a category above
                    parent_category = parts[0]
                    child_name = parts[1]
                    
                    # Look for parent category in previous items
                    found_parent = False
                    for prev_item in vmd_data[:index]:
                        if (isinstance(prev_item, dict) and 
                            prev_item.get("is_vmd_category") and 
                            prev_item["text"] == parent_category):
                            found_parent = True
                            break
                    
                    if found_parent:
                        # This child is already rendered under its parent category
                        continue
            
            # Render as flat item
            is_matched = isRowMatched(item, matchData) if matchData else False
            row_class = 'matched-row' if is_matched else ''
            row_id = f'{type}-vmd-{index}'
            
            html += f'<tr class="{row_class}" id="{row_id}" data-row="{item}">'
            
            bg_color = 'white'
            escaped_name = item.replace('"', '&quot;')
            html += f'<td class="vmd-cell" style="border: 1px solid #333; padding: 4px; text-align: left; font-weight: bold; background: {bg_color};">'
            html += f'<span class="row-label" data-row-label="{escaped_name}">{item}</span>'
            html += '</td>'
            
            # Add data cells
            for i in range(column_count):
                cell_value = ""
                if table_data and data_row_index < len(table_data):
                    row_data = table_data[data_row_index]
                    if isinstance(row_data, list) and i < len(row_data):
                        cell_value = row_data[i] or ""
                
                # Apply color coding based on table type
                if type == 'source' and cell_value:
                    cell_content = f'<span style="color: #8B4513; font-weight: bold;">{cell_value}</span>'
                elif type == 'target' and cell_value:
                    cell_content = f'<span style="color: #800080; font-weight: bold;">{cell_value}</span>'
                else:
                    cell_content = cell_value if cell_value else ''
                
                html += f'<td style="border: 1px solid #333; padding: 4px; background: white; text-align: center; font-weight: bold;" data-cell-value="{cell_value}">{cell_content}</td>'
            
            html += '</tr>'
            data_row_index += 1  # Move to next data row
    
    return html

# --- LLM Processing ---
def process_multi_step(source_schema, target_schema, schema_type, operation_type, llm_model="llama-3.1-8b-instant", 
                      max_tokens=None, temperature=None, top_p=None, frequency_penalty=None, presence_penalty=None):
    """Multi-step processing: For MATCH: 3 independent match calls + ensemble. For MERGE: Should receive match results."""

    # If this is a merge operation, we shouldn't be doing multi-step here
    if operation_type == "merge":
        print("[WARNING] Multi-step merge should receive match results, falling back to normal merge")
        return process_with_llm_enhanced(source_schema, target_schema, schema_type, "operator", operation_type, llm_model,
                                       max_tokens, temperature, top_p, frequency_penalty, presence_penalty,
                                       use_merge_multi_step=False, match_operation="operator", matching_method="json_default")

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
                                          frequency_penalty=None, presence_penalty=None):
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
                            match_operation="baseline", matching_method="json_default", merge_method=None, matching_llm=None, merge_llm=None, user_api_keys=None):
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
                                max_tokens, temperature, top_p, frequency_penalty, presence_penalty)
    
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
        
        # Format the prompt with actual schema data
        if operation_type == "match":
            prompt = f"""{prompt_template}

Source HMD: {source_hmd}
Source VMD: {source_vmd}
Target HMD: {target_hmd}
Target VMD: {target_vmd}

Return only the JSON object."""
        else:  # merge or instance_merge
            prompt = f"""{prompt_template}

Source HMD: {source_hmd}
Source VMD: {source_vmd}
Target HMD: {target_hmd}
Target VMD: {target_vmd}

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
        
        if operation_type in ["merge", "instance_merge"]:
            # First, perform matching using the corresponding match prompt
            print(f"🔍 Performing {operation_type} operation - will first run matching step")
            match_prompt_template = PROMPT_TEMPLATES[actual_schema_type][match_operation][matching_method]["match"]
            
            if actual_schema_type == "complex":
                match_prompt = f"""{match_prompt_template}

Source HMD: {source_hmd}
Source VMD: {source_vmd}
Target HMD: {target_hmd}
Target VMD: {target_vmd}

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
            
            try:
                if match_cleaned_response:
                    match_result = json.loads(match_cleaned_response)
                    print(f"[OK] Match step completed for {operation_type}. Found matches: HMD={len(match_result.get('HMD_matches', []))}, VMD={len(match_result.get('VMD_matches', []))}")

                    # CRITICAL FIX: If merge step uses multi-step but match step was not multi-step,
                    # replicate the single match result 3 times for multi-step merge ensemble
                    if use_merge_multi_step and processing_type != "multi_step":
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
                            replicated_responses, max_tokens, temperature, top_p, frequency_penalty, presence_penalty
                        )
                else:
                    print(f"[ERROR] Empty match response - cannot proceed with merge")
                    match_result = None

            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to parse match result JSON: {str(e)}")
                # print(f"[DEBUG] Raw match response: {match_raw_response[:500]}...")
                match_result = None

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
            if match_response and operation_type in ['merge', 'instance_merge']:
                # Extract match step token usage (even if match_result parsing failed)
                match_prompt_tokens, match_completion_tokens = extract_token_usage(match_response, matching_llm)

                # Calculate separate costs
                match_cost = calculate_api_cost(matching_llm, match_prompt_tokens, match_completion_tokens)
                merge_cost = calculate_api_cost(merge_llm, prompt_tokens, completion_tokens)
                total_api_cost = match_cost + merge_cost

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
            if operation_type == "match":
                if actual_schema_type == "complex":
                    metrics_data["hmd_matches"] = len(result_data.get('HMD_matches', []))
                    metrics_data["vmd_matches"] = len(result_data.get('VMD_matches', []))
                    metrics_data["total_matches"] = metrics_data["hmd_matches"] + metrics_data["vmd_matches"]
                else:
                    metrics_data["total_matches"] = len(result_data.get('column_matches', []))
            else:  # merge or instance_merge
                # For merge operations, use the match result for counts
                if match_result:
                    if actual_schema_type == "complex":
                        metrics_data["hmd_matches"] = len(match_result.get('HMD_matches', []))
                        metrics_data["vmd_matches"] = len(match_result.get('VMD_matches', []))
                        metrics_data["total_matches"] = metrics_data["hmd_matches"] + metrics_data["vmd_matches"]
                    else:
                        metrics_data["total_matches"] = len(match_result.get('matches', []))
                else:
                    metrics_data["total_matches"] = 0
            
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
            # For VMD, we need to include hierarchical paths for LLM matching
            vmd_for_llm = _create_vmd_for_llm_matching(value)
            vmd_data.extend(vmd_for_llm)
    
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

def clean_llm_json_response(response):
    """Clean and extract JSON from LLM response with enhanced malformed JSON handling"""
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
    
    # Extract JSON content
    json_start = response.find('{')
    json_end = response.rfind('}') + 1
    
    if json_start >= 0 and json_end > json_start:
        json_content = response[json_start:json_end]
        
        # Fix common JSON malformation issues
        json_content = json_content.replace('}\n  ]', '}]')  # Fix array ending
        json_content = json_content.replace('}\n]', '}]')    # Fix array ending
        json_content = json_content.replace(',\n}', '\n}')   # Fix trailing comma
        json_content = json_content.replace(',}', '}')       # Fix trailing comma
        json_content = json_content.replace(',]', ']')       # Fix trailing comma in array
        
        return json_content
    
    return '{"HMD_matches": [], "VMD_matches": []}'

# --- HTML Conversion ---

def convert_hmd_vmd_to_html_enhanced(data):
    """Enhanced HTML conversion with data display"""
    html_parts = []
    
    tables = {}
    for key, value in data.items():
        if '.' in key:
            table_name, data_type = key.split('.', 1)
            if table_name not in tables:
                tables[table_name] = {}
            tables[table_name][data_type] = value
    
    for table_name, table_data in tables.items():
        html_parts.append(f'<div class="table-container"><h3>{table_name}</h3>')
        html_parts.append('<table class="hmd-vmd-table">')

        if 'HMD' in table_data and table_data['HMD']:
            html_parts.append('<thead>')
            vmd_label = table_data.get('VMD_HEADER', '')
            header_html = build_preview_headers_with_vmd(table_data['HMD'], vmd_label)
            html_parts.extend(header_html)
            html_parts.append('</thead>')

        if 'VMD' in table_data and table_data['VMD']:
            html_parts.append('<tbody>')
            col_count = count_columns_from_hmd_fixed(table_data.get('HMD', []))
            
            vmd_data = table_data['VMD']
            if isinstance(vmd_data, list) and vmd_data and isinstance(vmd_data[0], dict):
                vmd_data = _flatten_vmd_objects(vmd_data)
            
            # NEW: Get the data array for this table
            table_data_values = None
            for key, value in data.items():
                if key.startswith(table_name + '.') and key.endswith('.Data'):
                    table_data_values = value
                    break
            
            # Render VMD rows using the same logic as createEnhancedTable
            html_parts.append(render_vmd_rows_with_hierarchy(vmd_data, 'preview', None, col_count, table_data_values))
            html_parts.append('</tbody>')
        
        html_parts.append('</table></div>')
    
    return ''.join(html_parts)

def count_columns_from_hmd_fixed(hmd_data):
    """Fixed column counting that properly handles childless parents"""
    if not hmd_data:
        return 0
    
    count = 0
    for item in hmd_data:
        if isinstance(item, dict) and item.get("is_childless"):
            count += item.get("colspan", 1)
        elif isinstance(item, str):
            count += 1
        else:
            count += 1
    
    return count

def build_preview_headers_with_vmd(hmd_data, vmd_header_label=""):
    """Build preview headers with VMD support"""
    if not hmd_data:
        return []

    hierarchical_items = []
    childless_parents = []
    
    for item in hmd_data:
        if isinstance(item, dict) and item.get("is_childless"):
            childless_parents.append(item)
        elif isinstance(item, str):
            hierarchical_items.append(item)

    has_hierarchy = any('.' in item for item in hierarchical_items)
    
    if not has_hierarchy:
        headers = ['<tr>']
        safe_label = (vmd_header_label or "").strip()
        
        headers.append(
            f'<th class="hmd-header level-0" '
            f'style="border: 1px solid #333; padding: 4px; background: #2E7D32; '
            f'color: white; text-align: left;">{safe_label}</th>'
        )
        
        for item in hierarchical_items:
            headers.append(
                f'<th class="hmd-header level-0" data-header="{item}" '
                f'style="border: 1px solid #333; padding: 4px; background: #2E7D32; '
                f'color: white; text-align: center;">{item}</th>'
            )
        
        for item in childless_parents:
            colspan = item.get("colspan", 1)
            text = item.get("text", "")
            headers.append(
                f'<th class="hmd-header level-0" data-header="{text}" colspan="{colspan}" '
                f'style="border: 1px solid #333; padding: 4px; background: #2E7D32; '
                f'color: white; text-align: center;">{text}</th>'
            )
        
        headers.append('</tr>')
        return headers

    structure = parse_hmd_structure_correctly(hierarchical_items)
    max_levels = structure['levels']
    
    headers = []
    for level in range(max_levels):
        headers.append('<tr>')
        
        if level == 0:
            safe_label = (vmd_header_label or "").strip()
            headers.append(
                f'<th class="hmd-header level-0" rowspan="{max_levels}" '
                f'style="border: 1px solid #333; padding: 4px; background: #2E7D32; '
                f'color: white; text-align: left;">{safe_label}</th>'
            )
            
            processed = set()
            for item in hierarchical_items:
                if item in processed:
                    continue
                    
                parts = item.split('.')
                current_part = parts[0]
                
                colspan = 1
                j = hierarchical_items.index(item) + 1
                while j < len(hierarchical_items):
                    next_item = hierarchical_items[j]
                    if next_item.split('.')[0] == current_part:
                        processed.add(next_item)
                        colspan += 1
                        j += 1
                    else:
                        break
                
                processed.add(item)
                headers.append(
                    f'<th class="hmd-header level-0" data-header="{current_part}" colspan="{colspan}" '
                    f'style="border: 1px solid #333; padding: 4px; background: #2E7D32; '
                    f'color: white; text-align: center;">{current_part}</th>'
                )
            
            for item in childless_parents:
                text = item.get("text", "")
                headers.append(
                    f'<th class="hmd-header level-0" data-header="{text}" rowspan="{max_levels}" '
                    f'style="border: 1px solid #333; padding: 4px; background: #2E7D32; '
                    f'color: white; text-align: center;">{text}</th>'
                )
        else:
            for item in hierarchical_items:
                parts = item.split('.')
                if level < len(parts):
                    part = parts[level]
                    bg_color = '#4CAF50' if level == 1 else '#81C784'
                    # Use full hierarchical path as data-header for sub-levels
                    full_path = '.'.join(parts[:level+1])
                    headers.append(
                        f'<th class="hmd-header level-{level}" data-header="{full_path}" '
                        f'style="border: 1px solid #333; padding: 4px; background: {bg_color}; '
                        f'color: white; text-align: center;">{part}</th>'
                    )
        
        headers.append('</tr>')
    
    return headers

def parse_hmd_structure_correctly(hmd_data):
    """Parse HMD data into a structure that preserves column alignment"""
    structure = {
        'levels': 0,
        'columns': []
    }
    
    max_levels = max(len(str(item).split('.')) for item in hmd_data)
    structure['levels'] = max_levels
    
    for item in hmd_data:
        parts = str(item).split('.')
        column = {
            'parts': parts,
            'full_path': str(item)
        }
        structure['columns'].append(column)
    
    return structure

def _flatten_vmd_objects(vmd_list):
    """Flatten VMD objects with support for structured hierarchy (user's JSON format)"""
    if not isinstance(vmd_list, list):
        return []
    
    result = []
    
    for vmd_obj in vmd_list:
        if not isinstance(vmd_obj, dict):
            if isinstance(vmd_obj, str) and vmd_obj.strip():
                result.append(vmd_obj.strip())
            continue
        
        # Check if this is already a processed VMD category
        if vmd_obj.get("is_vmd_category"):
            result.append(vmd_obj)
            continue
            
        # Check if this has the new hierarchical structure
        if 'children' not in vmd_obj:
            # Legacy format - extract any string values
            for v in vmd_obj.values():
                if isinstance(v, str) and v.strip():
                    result.append(v.strip())
            continue
            
        # Extract parent name from attributeX
        parent_name = None
        for key, value in vmd_obj.items():
            if key.startswith('attribute') and isinstance(value, str) and value.strip():
                parent_name = value.strip()
                break
        
        if not parent_name:
            continue  # Skip if no parent name found
            
        # Extract children
        children_array = vmd_obj.get('children', [])
        if not isinstance(children_array, list):
            # No children, treat as flat
            result.append(parent_name)
            continue
            
        # Process children to extract child names
        child_names = []
        for child_dict in children_array:
            if isinstance(child_dict, dict):
                # Extract all child_level1.attributeX values
                child_attrs = []
                for k, v in child_dict.items():
                    if k.startswith('child_level1.') and isinstance(v, str) and v.strip():
                        child_attrs.append((k, v.strip()))
                
                # Sort and add to child names
                child_attrs.sort()
                for _, name in child_attrs:
                    child_names.append(name)
        
        # Create VMD category object
        if child_names:
            vmd_category = {
                "text": parent_name,
                "is_vmd_category": True,
                "children": child_names,
                "rowspan": len(child_names) + 1
            }
            result.append(vmd_category)
        else:
            # No children found, add as flat item
            result.append(parent_name)
    
    return result

# --- JSON Input Processing ---
def parse_json_input(json_text):
    """Parse JSON input and convert to display format"""
    try:
        data = json.loads(json_text)

        if isinstance(data, dict) and any(
            isinstance(k, str) and (k.endswith('.HMD') or k.endswith('.VMD'))
            for k in data.keys()
        ):
            normalized = {}

            for k, v in data.items():
                if k.endswith('.HMD') and isinstance(v, list) and v and isinstance(v[0], dict):
                    hmd_flat, row_header = flatten_hmd_and_rowheader(v)
                    normalized[k] = hmd_flat
                    if row_header:
                        normalized[k.replace('.HMD', '.VMD_HEADER')] = row_header

                elif k.endswith('.VMD') and isinstance(v, list) and v and isinstance(v[0], dict):
                    normalized[k] = _flatten_vmd_objects(v)

                else:
                    normalized[k] = v

            return {
                "success": True,
                "data": normalized,
                "html": convert_hmd_vmd_to_html_enhanced(normalized)
            }

        # Simple JSON handling
        if isinstance(data, list) and data and all(isinstance(x, dict) and "name" in x for x in data):
            cols = [str(x.get("name", "")).strip() for x in data if x.get("name")]
            simple = {"SimpleTable.HMD": cols, "SimpleTable.VMD": []}
            return {"success": True, "data": simple, "html": convert_hmd_vmd_to_html_enhanced(simple)}

        if isinstance(data, list) and data and isinstance(data[0], dict):
            cols = list(data[0].keys())
            for row in data[1:]:
                for k in row.keys():
                    if k not in cols:
                        cols.append(k)
            simple = {"SimpleTable.HMD": cols, "SimpleTable.VMD": [f"Row_{i+1}" for i in range(len(data))]}
            return {"success": True, "data": simple, "html": convert_hmd_vmd_to_html_enhanced(simple)}

        if isinstance(data, dict) and data and all(isinstance(v, list) for v in data.values()):
            cols = list(data.keys())
            max_len = max((len(v) for v in data.values()), default=0)
            simple = {"SimpleTable.HMD": cols, "SimpleTable.VMD": [f"Row_{i+1}" for i in range(max_len)]}
            return {"success": True, "data": simple, "html": convert_hmd_vmd_to_html_enhanced(simple)}

        if isinstance(data, list) and all(isinstance(x, str) for x in data):
            simple = {"SimpleTable.HMD": data, "SimpleTable.VMD": []}
            return {"success": True, "data": simple, "html": convert_hmd_vmd_to_html_enhanced(simple)}

        simple = {"SimpleTable.HMD": [], "SimpleTable.VMD": []}
        return {"success": True, "data": simple, "html": convert_hmd_vmd_to_html_enhanced(simple)}

    except Exception as e:
        return {"success": False, "error": f"JSON parsing error: {str(e)}"}

def isRowMatched(rowName, matchData):
    """Check if row is matched in VMD_matches"""
    if not matchData or not isinstance(matchData, dict):
        return False
    vmd_matches = matchData.get('VMD_matches', [])
    if not isinstance(vmd_matches, list):
        return False
    
    row_lower = str(rowName).lower().strip()
    for match in vmd_matches:
        if isinstance(match, dict):
            source = str(match.get('source', '')).lower().strip()
            target = str(match.get('target', '')).lower().strip()
            if row_lower == source or row_lower == target:
                return True
    return False

def create_merged_schema_table(merge_result_data):
    """Create a table structure from HMD_Merged_Schema and VMD_Merged_Schema"""
    if not merge_result_data:
        return {}
    
    # Support both old and new JSON structure formats
    hmd_merged = merge_result_data.get('HMD_Merged_Schema', [])
    vmd_merged = merge_result_data.get('VMD_Merged_Schema', [])
    
    # Check for new nested format
    if not hmd_merged and not vmd_merged and 'Merged_Schema' in merge_result_data:
        nested_schema = merge_result_data['Merged_Schema']
        hmd_merged = nested_schema.get('HMD_Merged_Schema', [])
        vmd_merged = nested_schema.get('VMD_Merged_Schema', [])
    
    if not hmd_merged and not vmd_merged:
        return {}
    
    # Process HMD - handle both object format and string format
    processed_hmd = []
    for item in hmd_merged:
        if isinstance(item, dict):
            # Handle object format from LLM: {"attribute1": "Bleeding.(n=35)", "children": []}
            # Extract the attribute value from attributeX keys
            attribute_value = None
            for key, value in item.items():
                if key.startswith('attribute') and isinstance(value, str):
                    attribute_value = value.strip()
                    break
            
            if attribute_value:
                if '.' in attribute_value:
                    # Handle hierarchy like "Bleeding.(n=35)" -> parent: "Bleeding", child: "(n=35)"
                    parts = attribute_value.split('.', 1)
                    parent = parts[0].strip()
                    child = parts[1].strip()
                    
                    # Check if parent already exists
                    parent_found = False
                    for existing in processed_hmd:
                        if isinstance(existing, dict) and existing.get('attribute1') == parent:
                            if 'children' not in existing:
                                existing['children'] = []
                            existing['children'].append({'child_level1.attribute1': child})
                            parent_found = True
                            break
                    
                    if not parent_found:
                        # Create new parent with child
                        processed_hmd.append({
                            'attribute1': parent,
                            'children': [{'child_level1.attribute1': child}]
                        })
                else:
                    # Simple item without hierarchy
                    processed_hmd.append({'attribute1': attribute_value})
        elif isinstance(item, str):
            # Handle string format: "Bleeding.(n=35)"
            if '.' in item:
                # Handle hierarchy like "Bleeding.(n=35)" -> parent: "Bleeding", child: "(n=35)"
                parts = item.split('.', 1)
                parent = parts[0].strip()
                child = parts[1].strip()
                
                # Check if parent already exists
                parent_found = False
                for existing in processed_hmd:
                    if isinstance(existing, dict) and existing.get('attribute1') == parent:
                        if 'children' not in existing:
                            existing['children'] = []
                        existing['children'].append({'child_level1.attribute1': child})
                        parent_found = True
                        break
                
                if not parent_found:
                    # Create new parent with child
                    processed_hmd.append({
                        'attribute1': parent,
                        'children': [{'child_level1.attribute1': child}]
                    })
            else:
                # Simple item without hierarchy
                processed_hmd.append({'attribute1': str(item)})
    
    # Process VMD - handle both object format and string format
    processed_vmd = []
    for item in vmd_merged:
        if isinstance(item, dict):
            # Handle object format from LLM: {"attribute1": "Age, mean±SD,y", "children": []}
            # Extract the attribute value from attributeX keys
            attribute_value = None
            for key, value in item.items():
                if key.startswith('attribute') and isinstance(value, str):
                    attribute_value = value.strip()
                    break
            
            if attribute_value:
                processed_vmd.append(attribute_value)
        elif isinstance(item, str):
            processed_vmd.append(str(item))
    
    # Create the merged table structure
    merged_table = {
        'MergedTable.HMD': processed_hmd,
        'MergedTable.VMD': processed_vmd,
        'MergedTable.VMD_HEADER': 'Merged Attributes'
    }
    
    return merged_table

# --- Blueprint for /fuze prefix ---

# --- Routes ---
# Register Blueprint after all route definitions

