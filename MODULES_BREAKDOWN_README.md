# Fusion Helpers Modular Breakdown Documentation

## Overview
The monolithic `fusion_helpers.py` (4398 lines) has been broken down into **8 focused modules** for better maintainability and reduced memory usage.

## New Structure

```
sender/
├── modules/
│   ├── __init__.py              # Module initialization
│   ├── config.py                # Configuration & API clients (214 lines)
│   ├── pricing.py               # Cost calculation & metrics (265 lines)
│   ├── models.py                # Pydantic data models (165 lines)
│   ├── llm_client.py            # LLM API interactions (182 lines)
│   ├── prompts.py               # Prompt templates (242 lines)
│   ├── parsers.py               # DOCX/JSON parsing (407 lines)
│   ├── processors.py            # Multi-step LLM processing (865 lines)
│   └── html_utils.py            # HTML generation & rendering (267 lines)
├── fusion_helpers.py            # Main entry point (76 lines)
└── fusion_helpers_backup.py     # Original backup (4398 lines)
```

## Module Breakdown

### 1. **config.py** (214 lines)
**Purpose:** Configuration, API keys, client initialization, and storage functions

**Contents:**
- API Keys: `GROQ_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`
- Storage paths: `STORAGE_DIR`, `LOGS_DIR`, `RESULTS_DIR`, `UPLOADS_DIR`
- Client initialization: `client` (Groq), `anthropic_client`, `gemini_client`
- LLM parameters: `DEFAULT_LLM_PARAMS`, `LLM_PRESETS`
- Model mapping: `MODEL_MAP`
- Storage functions: `save_to_json_file()`, `load_from_json_file()`, `log_activity()`

**Key Functions:**
```python
- save_to_json_file(data, filename, directory)
- load_from_json_file(filename, directory)
- log_activity(activity_data)
```

---

### 2. **pricing.py** (265 lines)
**Purpose:** API cost calculation, token estimation, and usage tracking

**Contents:**
- Pricing configuration for different models
- Token counting and estimation
- Cost calculation per request
- Pipeline description generation
- Response storage with metrics

**Key Functions:**
```python
- get_model_pricing(model_name) -> dict
- calculate_api_cost(model_name, input_tokens, output_tokens) -> float
- extract_token_usage(response, model_name) -> dict
- estimate_tokens_by_provider(text, model_name) -> int
- format_cost_display(cost) -> str
- generate_pipeline_description(...) -> str
- store_llm_response_to_local_storage(...)
```

---

### 3. **models.py** (165 lines)
**Purpose:** Pydantic data models for type validation and structure

**Contents:**
- Response validation models
- Data structure definitions

**Key Classes:**
```python
class MatchResult(BaseModel):
    # Schema matching results

class MergeResult(BaseModel):
    # Schema merge results

class ComplexInstanceMergeResult(BaseModel):
    # Complex merge results with nested data

class ProcessingMetrics(BaseModel):
    # Processing metrics and timing
```

---

### 4. **llm_client.py** (182 lines)
**Purpose:** LLM API interactions and response handling

**Contents:**
- Model detection utilities
- LLM preset application
- Unified API calling interface
- Schema complexity detection

**Key Functions:**
```python
- is_gemini_model(model_name) -> bool
- is_claude_model(model_name) -> bool
- is_openai_model(model_name) -> bool
- apply_llm_preset(preset_name, **override_params) -> dict
- get_llm_response(prompt, model_name, ...) -> dict
- detect_schema_complexity(schema_data) -> str
```

**Supported Models:**
- Groq: Llama, Qwen, DeepSeek, OpenAI OSS
- Anthropic: Claude 3.5 Haiku, Sonnet, Sonnet 4
- Google: Gemini 1.5/2.0/2.5 Flash

---

### 5. **prompts.py** (242 lines)
**Purpose:** LLM prompt templates for different operations

**Contents:**
- Schema matching prompts
- Schema merge prompts
- Instance merge prompts
- Multi-step operation prompts

**Key Templates:**
- Baseline matching
- Operator-based matching
- Schema fusion
- Instance data merging

---

### 6. **parsers.py** (407 lines)
**Purpose:** DOCX/JSON parsing and schema structure handling

**Contents:**
- DOCX table parsing
- JSON schema parsing
- HMD (Horizontal Metadata) building
- VMD (Vertical Metadata) building
- Schema structure detection

**Key Functions:**
```python
- parse_docx_file(file_content) -> dict
- parse_json_input(json_text) -> dict
- convert_docx_to_hmd_vmd_enhanced(raw_rows, table_name) -> dict
- build_hierarchical_hmd_fixed(header_rows) -> list
- build_two_level_hmd_fixed(header_rows) -> list
- build_three_level_hmd_fixed(header_rows) -> list
- build_single_level_hmd(header_row) -> list
- build_hierarchical_vmd_structure(data_rows) -> list
- detect_vmd_category_pattern(current_row, all_rows) -> str
- normalize_vmd_structure(vmd_structure) -> list
- extract_hmd_vmd_from_schema(schema_data) -> dict
```

---

### 7. **processors.py** (865 lines)
**Purpose:** Multi-step LLM processing and schema operations

**Contents:**
- Multi-step matching workflows
- Multi-step merge workflows
- Enhanced LLM processing with retries
- Response cleaning and validation

**Key Functions:**
```python
- process_multi_step(source_schema, target_schema, ...) -> dict
- process_multi_step_merge_with_responses(...) -> dict
- process_with_llm_enhanced(source_schema, target_schema, ...) -> dict
- clean_llm_json_response(response) -> dict
```

**Operations:**
- `baseline`: Simple schema matching
- `operator`: Advanced operator-based matching
- `merge`: Schema structure merging
- `instance_merge`: Data instance merging

---

### 8. **html_utils.py** (267 lines)
**Purpose:** HTML table generation and rendering

**Contents:**
- Enhanced table creation
- HMD/VMD flattening for display
- Row rendering with hierarchy
- HTML conversion utilities
- Column counting
- Preview header building

**Key Functions:**
```python
- createEnhancedTable(data, type, matchData) -> str
- flatten_hmd_and_rowheader(hmd_list) -> list
- render_vmd_rows_with_hierarchy(vmd_data, ...) -> str
- convert_hmd_vmd_to_html_enhanced(data) -> str
- count_columns_from_hmd_fixed(hmd_data) -> int
- build_preview_headers_with_vmd(hmd_data, vmd_header_label) -> str
- parse_hmd_structure_correctly(hmd_data) -> dict
- isRowMatched(rowName, matchData) -> bool
- create_merged_schema_table(merge_result_data) -> str
```

---

## Main Entry Point

### **fusion_helpers.py** (76 lines)
**Purpose:** Import aggregator for backward compatibility

**What it does:**
- Imports all functions from modules
- Re-exports everything for backward compatibility
- Maintains the same interface as before
- Prints initialization status

**Usage:**
```python
# Old way (still works!)
from fusion_helpers import *

# New way (more explicit)
from modules.config import GROQ_API_KEY
from modules.parsers import parse_docx_file
from modules.processors import process_with_llm_enhanced
```

---

## Benefits

### 1. **Dramatic Size Reduction**
| File | Old Size | New Size | Reduction |
|------|----------|----------|-----------|
| fusion_helpers.py | 4398 lines | 76 lines | **98.3%** |
| Largest module | N/A | 865 lines | Isolated |
| Average module | N/A | 288 lines | Manageable |

### 2. **Memory Efficiency**
- **Before**: Always load 4398 lines
- **After**: Load only needed modules (76-865 lines each)
- **Claude Code**: Can focus on specific modules instead of entire file

### 3. **Better Organization**
- Clear separation of concerns
- Easy to find specific functionality
- Logical grouping by purpose

### 4. **Easier Maintenance**
- Edit one module without affecting others
- Reduce risk of breaking changes
- Simpler code reviews

### 5. **Import Flexibility**
```python
# Import everything (backward compatible)
from fusion_helpers import *

# Import specific module
from modules.parsers import parse_docx_file

# Import specific functions
from modules.pricing import calculate_api_cost, format_cost_display
```

---

## How to Use

### Editing a Module
```bash
# Edit configuration
edit modules/config.py

# Edit parsing logic
edit modules/parsers.py

# Edit LLM processing
edit modules/processors.py
```

### Adding New Functionality
1. Add function to appropriate module
2. Update `fusion_helpers.py` `__all__` list if needed
3. Module is automatically available via `from fusion_helpers import *`

### Testing Specific Module
```python
# Test only the parsers module
from modules.parsers import parse_docx_file
result = parse_docx_file(file_content)
```

---

## Import Dependencies

**Module dependency chain:**
```
config.py (no dependencies)
  ↓
models.py (uses: config)
  ↓
llm_client.py (uses: config)
  ↓
pricing.py (uses: config, llm_client)
  ↓
prompts.py (uses: config)
  ↓
parsers.py (uses: config, models)
  ↓
processors.py (uses: all above)
  ↓
html_utils.py (uses: config, parsers)
```

---

## Rollback Instructions

If you need to revert to the monolithic version:

```bash
cd sender
cp fusion_helpers_backup.py fusion_helpers.py
```

---

## Testing

### Test Import
```python
python -c "from fusion_helpers import *; print('[OK] Import successful')"
```

### Test Specific Module
```python
python -c "from modules.config import client; print('[OK] Config loaded')"
python -c "from modules.parsers import parse_docx_file; print('[OK] Parsers loaded')"
```

### Run Application
```bash
python main_fast.py
# or
uvicorn main_fast:app --reload --port 8000
```

---

## Troubleshooting

### ModuleNotFoundError
- Ensure `modules/` directory exists
- Check `modules/__init__.py` is present
- Verify Python path includes sender directory

### Circular Import Errors
- Modules are designed to avoid circular imports
- Import order in fusion_helpers.py is optimized
- Don't import fusion_helpers.py inside module files

### Missing Functions
- Check function is in correct module
- Verify it's listed in `__all__` if using `import *`
- Use explicit import: `from modules.X import function_name`

---

## Performance Comparison

**Context/Memory Usage:**

| Task | Old | New | Improvement |
|------|-----|-----|-------------|
| Edit config | 4398 lines | 214 lines | **95%** less |
| Edit parsers | 4398 lines | 407 lines | **91%** less |
| Edit processors | 4398 lines | 865 lines | **80%** less |
| Edit HTML utils | 4398 lines | 267 lines | **94%** less |
| View main file | 4398 lines | 76 lines | **98%** less |

---

## Notes

- All original functionality preserved
- No changes to API or function signatures
- Backward compatible with existing code
- Module structure follows Python best practices
- Each module is independently testable
