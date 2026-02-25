"""
Modular Schema Fusion Helper - Main Entry Point

This file imports all functionality from modular components for backward compatibility.
All heavy logic has been broken down into smaller, maintainable modules.
"""

# Import all configuration, clients, and constants
from modules.config import *

# Import pricing and cost calculation functions
from modules.pricing import *

# Import Pydantic models
from modules.models import *

# Import LLM client functions
from modules.llm_client import *

# Import prompt templates
from modules.prompts import *

# Import parser functions
from modules.parsers import *

# Import processor functions
from modules.processors import *

# Import HTML utility functions
from modules.html_utils import *

# Export all for backward compatibility
__all__ = [
    # From config
    'GROQ_API_KEY', 'GEMINI_API_KEY', 'ANTHROPIC_API_KEY',
    'STORAGE_DIR', 'LOGS_DIR', 'RESULTS_DIR', 'UPLOADS_DIR',
    'client', 'anthropic_client', 'gemini_client', 'GEMINI_AVAILABLE',
    'DEFAULT_LLM_PARAMS', 'LLM_PRESETS', 'MODEL_MAP',
    'save_to_json_file', 'load_from_json_file', 'log_activity',

    # From pricing
    'get_model_pricing', 'calculate_api_cost', 'extract_token_usage',
    'estimate_tokens_by_provider', 'format_cost_display',
    'generate_pipeline_description',
    'store_llm_response_to_local_storage', 'store_llm_response_to_mongodb',

    # From prompts
    'PROMPT_TEMPLATES',

    # From models
    'MatchResult', 'MergeResult', 'ComplexInstanceMergeResult', 'ProcessingMetrics',

    # From llm_client
    'is_gemini_model', 'is_claude_model', 'is_openai_model',
    'apply_llm_preset', 'get_llm_response', 'detect_schema_complexity',

    # From parsers
    'parse_docx_file', 'convert_docx_to_hmd_vmd_enhanced',
    'build_hierarchical_hmd_fixed', 'build_two_level_hmd_fixed',
    'build_three_level_hmd_fixed', 'build_single_level_hmd',
    'build_hierarchical_vmd_structure', 'detect_vmd_category_pattern',
    'normalize_vmd_structure', 'extract_hmd_vmd_from_schema',
    'parse_json_input',

    # From processors
    'process_multi_step', 'process_multi_step_merge_with_responses',
    'process_with_llm_enhanced', 'clean_llm_json_response',
    'repair_merged_data_structure', 'repair_mapping_schema',

    # From html_utils
    'createEnhancedTable', 'flatten_hmd_and_rowheader',
    'render_vmd_rows_with_hierarchy', 'convert_hmd_vmd_to_html_enhanced',
    'count_columns_from_hmd_fixed', 'build_preview_headers_with_vmd',
    'parse_hmd_structure_correctly', 'isRowMatched',
    'create_merged_schema_table',
]

print("[OK] Modular fusion_helpers loaded successfully")
print(f"[INFO] Modules: config, pricing, models, llm_client, prompts, parsers, processors, html_utils")
