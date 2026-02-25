"""
LLM client functions for interacting with various LLM APIs
"""
import time
from modules.config import *
from modules.parsers import clean_llm_json_response

# Model detection functions (is_gemini_model, is_claude_model, is_openai_model)
# are now in config.py and imported via "from modules.config import *"

def apply_llm_preset(preset_name, **override_params):
    """Apply a parameter preset and allow overrides"""
    if preset_name not in LLM_PRESETS:
        raise ValueError(f"Unknown preset: {preset_name}. Available: {list(LLM_PRESETS.keys())}")
    params = LLM_PRESETS[preset_name].copy()
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
                    response_mime_type="application/json",  # Force valid JSON output
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
    
    elif is_ollama_model(model_name):
        import requests
        import json
        
        headers = {'Content-Type': 'application/json'}
        if OLLAMA_AUTH:
            # If it doesn't start with Basic or Bearer, assume Bearer token
            if not (OLLAMA_AUTH.startswith("Basic ") or OLLAMA_AUTH.startswith("Bearer ")):
                headers['Authorization'] = f"Bearer {OLLAMA_AUTH}"
            else:
                headers['Authorization'] = OLLAMA_AUTH
                
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
            }
        }
        
        # In Ollama, max_tokens is often controlled via num_predict in options
        if max_tokens:
             payload["options"]["num_predict"] = max_tokens
             
        try:
            response = requests.post(OLLAMA_URL, headers=headers, json=payload, timeout=300)
            response.raise_for_status()
            result_json = response.json()
            response_text = result_json.get("response", "")
            
            class MockChoice:
                def __init__(self, content):
                    self.message = type('obj', (object,), {'content': content})
            
            class MockUsage:
                def __init__(self, prompt_tokens, completion_tokens):
                    self.prompt_tokens = prompt_tokens
                    self.completion_tokens = completion_tokens
                    self.total_tokens = prompt_tokens + completion_tokens
            
            class MockResponse:
                def __init__(self, content, usage):
                    self.choices = [MockChoice(content)]
                    self.usage = usage
            
            # Ollama provides prompt_eval_count and eval_count
            p_tokens = result_json.get("prompt_eval_count", int(len(prompt)/4))
            c_tokens = result_json.get("eval_count", int(len(response_text)/4))
            
            return MockResponse(response_text, MockUsage(p_tokens, c_tokens))
            
        except Exception as e:
            raise Exception(f"Ollama API error: {str(e)}")

    else:
        # Use Groq for non-Gemini, non-Claude models (includes Llama and OpenAI models via Groq)
        if not active_groq_client:
            raise Exception(f"Groq client not configured. Please set GROQ_API_KEY environment variable. Model requested: {model_name}")

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

