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
import ollama
# from groq import Groq
# from anthropic import Anthropic
from groq import Groq
from anthropic import Anthropic
from pydantic import BaseModel, ValidationError
from typing import List, Dict, Any, Optional
from docx import Document
from docx.table import Table as DocxTable
import io
import base64
# MongoDB imports removed - using local storage instead

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Install with: pip install python-dotenv")
    # Manual .env loading fallback
    import os
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        print(f"Loading .env manually from {env_path}")
        with open(env_path, "r") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    try:
                        key, value = line.strip().split("=", 1)
                        os.environ[key] = value
                    except ValueError:
                        pass


# Import Google Generative AI - Removed for local only
GEMINI_AVAILABLE = False
# try:
#     import google.generativeai as genai
#     GEMINI_AVAILABLE = True
# except ImportError:
#     GEMINI_AVAILABLE = False
#     print("Warning: Google Generative AI package not installed. Install with: pip install google-generativeai")

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
# --- Configuration ---
# API Keys removed - using Local Ollama
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
# OLLAMA_AUTH can be a Bearer token or Basic auth string (e.g. "Basic dXNlcjpwYXNz")
OLLAMA_AUTH = os.getenv("OLLAMA_AUTH")


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
    "max_tokens": 8000,        # Maximum tokens in response (increased for complex schemas - Gemini supports up to 8192)
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
# Using user's local models
# MODEL_MAP = {
#     "default": "Qwen2.5:14B",
#     "Qwen2.5:14B": "Qwen2.5:14B",
#     "qwen2.5:14b": "Qwen2.5:14B",
#     "gemma3:12b": "gemma3:12b",
#     "llama3.3:70b": "llama3.3:70b",
#     "llama3:8b": "llama3:8b",
#     "mistral:7b": "mistral:7b",
#     "deepseek-r1:32b": "deepseek-r1:32b",
#     # Legacy/Fallback mappings
#     "llama-3.1-8b-instant": "llama3:8b", 
# }

# --- Curated Models for UI Display ---
# Only these models will be shown in the dropdowns
UI_MODELS = [
    "Qwen2.5:14B",
    "gemma3:12b", 
    "llama3:8b",
    "mistral:7b",
    "deepseek-r1:32b",
    "llama3.3:70b"
]

# --- Model Detection Helper Functions ---
def is_gemini_model(model_name):
    return False

def is_claude_model(model_name):
    return False

def is_openai_model(model_name):
    return False
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
    "gemini-2.0-flash": "gemini-2.0-flash",
    "gemini-2.5-flash":"gemini-2.5-flash",
    "default": "Qwen2.5:14B",
    # "Qwen2.5:14B": "Qwen2.5:14B",
    # "qwen2.5:14b": "Qwen2.5:14B",
    # "gemma3:12b": "gemma3:12b",
    # "llama3.3:70b": "llama3.3:70b",
    # "llama3:8b": "llama3:8b",
    # "mistral:7b": "mistral:7b",
    # "deepseek-r1:32b": "deepseek-r1:32b",
    # # Legacy/Fallback mappings
    # "llama-3.1-8b-instant": "llama3:8b", 
}

# --- Model Detection Helper Functions ---
def is_gemini_model(model_name):
    """Check if model is a Gemini model"""
    if not model_name: return False
    return "gemini" in model_name.lower()

def is_claude_model(model_name):
    """Check if model is a Claude model"""
    if not model_name: return False
    return "claude" in model_name.lower()

def is_openai_model(model_name):
    """Check if model uses OpenAI router (typically via Groq in this project)"""
    if not model_name: return False
    return model_name.lower().startswith("openai/")

def is_ollama_model(model_name):
    """Check if model should be treated as an Ollama model"""
    if not model_name: return True
    # If explicitly gemini or claude, it's an API model
    if is_gemini_model(model_name) or is_claude_model(model_name):
        return False
    # If it's a known Groq model and we have a key, treat as non-ollama
    groq_models = ["llama-3.1", "qwen/qwen3", "deepseek-r1-distill", "openai/gpt-oss"]
    if GROQ_API_KEY and any(m in model_name.lower() for m in groq_models):
        return False
    # Everything else (or if missing Groq key) is Ollama
    return True
