"""
Dynamic VMD Extraction from PDF Files - Module Version
Adapted for FusionFrontend integration.
Now supports PDF + Schema paired extraction using Ollama (medllama2).
"""

import json
import math
import time
import sys
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import requests

from modules.llm_client import get_llm_response, clean_llm_json_response
from modules.html_utils import convert_hmd_vmd_to_html_enhanced
import logging

# Configure logging
logging.basicConfig(
    filename='extraction_debug.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='a'
)
logger = logging.getLogger(__name__)

# PDF parsing
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
DATA_PROMPT_FILE = SCRIPT_DIR / "dynamic_data_prompt.txt"

CHUNK_SIZE = 3  # Variables per extraction chunk (User specified)
from modules.config import OLLAMA_URL, OLLAMA_AUTH

# =============================================================================
# LLM WRAPPER (API-BASED)
# =============================================================================

def call_fusion_llm(prompt: str, model: str) -> str:
    """
    Call LLM using FusionFrontend's infrastructure (Gemini, Groq, Anthropic).
    Uses get_llm_response from modules.llm_client.
    """
    logger.info(f"Calling LLM: {model}")
    print(f"    [LLM] Calling {model}...")
    try:
        # Use get_llm_response which handles all API clients
        response_obj = get_llm_response(
            prompt, 
            model_name=model, # Kwarg is model_name
            temperature=0.1,  
            max_tokens=8000
        )
        
        # Extract content based on response object structure
        # get_llm_response returns a standardized object with .choices[0].message.content
        if hasattr(response_obj, 'choices') and len(response_obj.choices) > 0:
            content = response_obj.choices[0].message.content
            logger.info(f"LLM Response received (len={len(content)})")
            return content
        elif hasattr(response_obj, 'content'): # Some clients return direct content object
             logger.info(f"LLM Response received (content obj, len={len(response_obj.content)})")
             return response_obj.content
        else:
             logger.error(f"Unexpected response format: {type(response_obj)}")
             print(f"    [ERROR] Unexpected response format: {type(response_obj)}")
             return ""
             
    except Exception as e:
        print(f"    [ERROR] LLM call failed: {e}")
        return ""

def parse_json_response(response: str) -> dict:
    """Extract JSON from LLM response."""
    # Try using the clean helper first
    try:
        cleaned = clean_llm_json_response(response)
        return json.loads(cleaned)
    except Exception:
        # Fallback to simple substring
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                text = response[start:end]
                # Fix common LLM json Issues if needed
                return json.loads(text)
        except Exception:
            pass
    return {}

# =============================================================================
# PDF PROCESSING
# =============================================================================

def extract_text_from_pdf(pdf_file, max_length: int = 30000) -> str:
    """Extract text content from PDF file object or path."""
    logger.info(f"Extracting text from PDF (max_length={max_length})")
    if not HAS_PDFPLUMBER:
        raise RuntimeError("pdfplumber not installed. Run: pip install pdfplumber")
    
    parts = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                if i == 0:
                    parts.append(f"PAGE 1 (Title/Abstract):\n{text}")
                else:
                    parts.append(f"\nPAGE {i+1}:\n{text}")
    
    full_text = "\n".join(parts)
    return full_text[:max_length]


def extract_tables_from_pdf(pdf_file) -> str:
    """Extract tables from PDF file object or path and format as text."""
    logger.info("Extracting tables from PDF")
    if not HAS_PDFPLUMBER:
        raise RuntimeError("pdfplumber not installed. Run: pip install pdfplumber")
    
    all_tables = []
    table_num = 0
    
    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            
            for table in tables:
                if not table or len(table) < 2:
                    continue
                    
                table_num += 1
                table_parts = [f"\n=== TABLE {table_num} (Page {page_num}) ==="]
                
                # Convert table to text format
                for row_idx, row in enumerate(table):
                    if row:
                        # Clean None values
                        clean_row = [str(cell) if cell else "" for cell in row]
                        if row_idx == 0:
                            table_parts.append("HEADER: " + " | ".join(clean_row))
                        else:
                            table_parts.append(" | ".join(clean_row))
                
                all_tables.append("\n".join(table_parts))
    
    return "\n".join(all_tables) if all_tables else "[No tables found in PDF]"

# =============================================================================
# SCHEMA UTILS
# =============================================================================

def parse_uploaded_schema(schema_json: dict) -> Tuple[List[str], List[str]]:
    """
    Parse the uploaded schema (Target Schema format) into lists of:
    1. HMD columns (columns to extract)
    2. VMD variables (rows to extract)
    
    Expected format is typically:
    [
      { "HMD_col": { "VMD_data": [ { "VMD_row": { "src": val } } ] } }
    ]
    OR a simple list of objects.
    
    We need to identify:
    - What are the COLUMNS (HMD)?
    - What are the ROWS (VMD)?
    
    For extraction, we treat the schema as defining the required structure.
    If the uploaded schema is a 'Target Schema' (empty template), 
    we extract keys from HMD_col and VMD_row.
    """
    # This is a simplification. We assume the user provides a "Target Schema" 
    # which defines the structure.
    
    # 1. HMD (Columns)
    # 2. VMD (Rows) - these might be values in a column like "Variable" or keys in a dictionary.
    
    # Let's look for a standard format, or try to deduce.
    # If the user uploads a previous extraction result, we can use that.
    
    # fallback: try to find 'HMD' and 'VMD' keys if present
    hmd_list = []
    vmd_list = []
    
    if "Table1.HMD" in schema_json:
        # It's a full schema object
        hmd_objs = schema_json.get("Table1.HMD", [])
        vmd_objs = schema_json.get("Table1.VMD", [])
        
        # Flatten HMD
        for obj in hmd_objs:
            # check children
            children = []
            for k, v in obj.items():
                if k == "children":
                    children = v
            if children:
                parent = list(obj.values())[0] # roughly
                for child in children:
                     val = list(child.values())[0]
                     hmd_list.append(f"{parent} > {val}")
            else:
                 hmd_list.append(list(obj.values())[0])
                 
        # Flatten VMD
        for obj in vmd_objs:
            # check children
            children = []
            for k, v in obj.items():
                if k == "children":
                    children = v
            if children:
                parent = list(obj.values())[0]
                for child in children:
                     val = list(child.values())[0]
                     vmd_list.append(f"{parent} > {val}")
            else:
                 vmd_list.append(list(obj.values())[0])

        return hmd_list, vmd_list

    # If it's the UI format [ {HMD_col: ...} ]
    if isinstance(schema_json, list) and len(schema_json) > 0:
        # Try to extract HMD keys from first item
        first_item = schema_json[0]
        # This part is tricky without knowing exact format.
        # Let's assume the user might upload a "Template"
        pass
        
    return [], []

def flatten_schema_simple(schema_content: Any) -> Tuple[List[str], List[str]]:
    """
    Robust flatten logic that supports:
    1. Standard Fusion Format (HMD_Categories, VMD_Categories)
    2. Generic JSON Object (recursively finds keys for VMD, assumes HMD="Value")
    """
    logger.info("Flattening schema")
    if isinstance(schema_content, str):
        try:
            schema = json.loads(schema_content)
        except:
            schema = {}
    else:
        schema = schema_content
        
    def extract_keys(obj, parent_key=''):
        keys = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                # Use dot separator for path reconstruction compatibility
                current_key = f"{parent_key}.{k}" if parent_key else k
                # If value is empty string/null, it's a leaf
                if v == "" or v is None:
                    keys.append(current_key)
                elif isinstance(v, (dict, list)):
                    # Check if empty dict
                    if isinstance(v, dict) and not v:
                        keys.append(current_key)
                    else:
                        subkeys = extract_keys(v, current_key)
                        if not subkeys: # If recursion returned nothing (empty dict/list)
                             keys.append(current_key)
                        else:
                             keys.extend(subkeys)
                else:
                     # Missing -> "--"
                     batch_matrix.append(["--" for _ in hmd])
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, str):
                    # List of strings? Use string as key?
                    current_key = f"{parent_key}.{item}" if parent_key else item
                    keys.append(current_key)
                else:
                     keys.extend(extract_keys(item, f"{parent_key}[{i}]"))
        return keys

    hmd_list = []
    vmd_list = []
    
    # 1. Try Standard Fusion Format
    if isinstance(schema, dict) and "HMD_Categories" in schema and "VMD_Categories" in schema:
        hmd_cats = schema.get("HMD_Categories", [])
        vmd_cats = schema.get("VMD_Categories", [])
        
        # Flatten HMD
        for cat in hmd_cats:
            group = cat.get("group", "Unknown")
            children = cat.get("children", [])
            if children:
                for child in children:
                    hmd_list.append(f"{group} > {child}")
            else:
                hmd_list.append(group)
        
        # Flatten VMD
        for cat in vmd_cats:
            cat_name = cat.get("category", "Unknown")
            variables = cat.get("variables", [])
            for var in variables:
                vmd_list.append(f"{cat_name} > {var}")
                
        if hmd_list and vmd_list:
            return hmd_list, vmd_list

    # 1.5 Try "Patient.HMD" / "Patient.VMD" specific style (or *.HMD / *.VMD)
    # The user provided example has "Patient.HMD" list of objs with "attribute" and optional "children"
    # 1.5 Check for "Table1" wrapper or keys ending in .HMD/.VMD
    hmd_key = next((k for k in schema.keys() if k.endswith('.HMD') or k == 'HMD'), None)
    vmd_key = next((k for k in schema.keys() if k.endswith('.VMD') or k == 'VMD'), None)
    
    # Check for nested structure if not found at root
    if not hmd_key or not vmd_key:
        for root_key, root_val in schema.items():
            if isinstance(root_val, dict):
                 # Look inside the root value
                 nested_hmd = next((k for k in root_val.keys() if k.endswith('HMD')), None)
                 nested_vmd = next((k for k in root_val.keys() if k.endswith('VMD')), None)
                 
                 if nested_hmd and nested_vmd:
                     # Found them nested!
                     hmd_data = root_val[nested_hmd]
                     vmd_data = root_val[nested_vmd]
                     
                     # Extract using helper or simple flattening
                     # HMD usually defines Columns
                     if isinstance(hmd_data, dict):
                         # Flatten keys using FULL PATH
                         hmd_list = extract_keys(hmd_data, parent_key=f"{root_key}.{nested_hmd}")
                     elif isinstance(hmd_data, list):
                         # Assume list of strings or objects?
                         # Use existing fallback logic if list of objects
                         pass 
                         
                     # VMD defines Rows
                     if isinstance(vmd_data, dict):
                         vmd_list = extract_keys(vmd_data, parent_key=f"{root_key}.{nested_vmd}")
                     
                     if hmd_list and vmd_list:
                         return hmd_list, vmd_list

    if hmd_key and vmd_key:
        hmd_data = schema[hmd_key]
        
        # Flatten HMD
        if isinstance(hmd_data, list):
            for item in hmd_data:
                attr = item.get("attribute")
                children = item.get("children", [])
                if children:
                    for child in children:
                        child_attr = child.get("attribute")
                        if attr and child_attr:
                            hmd_list.append(f"{attr} > {child_attr}")
                        elif child_attr:
                            hmd_list.append(child_attr)
                elif attr:
                    hmd_list.append(attr)

        # Flatten VMD
        vmd_data = schema[vmd_key]
        if isinstance(vmd_data, list):
            for item in vmd_data:
                attr = item.get("attribute")
                children = item.get("children", [])
                if children:
                     for child in children:
                        child_attr = child.get("attribute")
                        if attr and child_attr:
                            vmd_list.append(f"{attr} > {child_attr}")
                elif attr:
                    vmd_list.append(attr)
        
        if hmd_list and vmd_list:
            return hmd_list, vmd_list

    # 2. Fallback: Generic JSON Flattening (Recursive)
    # Treat keys as VMD (Rows) and assume we want the 'Value' (HMD)
    
    vmd_list = extract_keys(schema)
    
    # If we found keys, assume HMD is just "Value"
    if vmd_list:
        hmd_list = ["Value"]
        
    # If still empty, maybe it's just a list of strings?
    if not vmd_list and isinstance(schema, list):
        vmd_list = [str(x) for x in schema]
        hmd_list = ["Value"]

    return hmd_list, vmd_list

# =============================================================================
# PHASE 2: CHUNKED DATA EXTRACTION (Modified)
# =============================================================================

def phase2_extract_data(
    tables_text: str,
    body_text: str,
    hmd: List[str],
    all_rows: List[str],
    model: str,
    chunk_size: int = 3
) -> List[List[str]]:
    """
    Phase 2: Extract data in chunks using the dynamic schema.
    Returns: Full data matrix (list of lists)
    """
    logger.info(f"Phase 2 extraction starting. Model: {model}, Chunk size: {chunk_size}, Total rows: {len(all_rows)}")
    if not DATA_PROMPT_FILE.exists():
        print(f"    Error: {DATA_PROMPT_FILE} not found")
        # Fallback prompt if file missing
        prompt_template = """
You are an expert medical data extractor. Extract data from the text below.

Context:
Tables: {tables}
Text: {text}

Columns (HMD): {hmd_json}
Rows to Extract (VMD): {chunk_rows}

Output JSON with key "ChunkData" containing a list of lists (matrix).
Verify every row has exactly {hmd_len} columns. Use "--" for missing data.
"""
    else:
        prompt_template = DATA_PROMPT_FILE.read_text(encoding='utf-8')
    
    num_chunks = math.ceil(len(all_rows) / chunk_size)
    full_data = []
    
    print(f"    [Extraction] Processing {len(all_rows)} variables in {num_chunks} chunks (k={chunk_size})...")
    
    for chunk_idx in range(num_chunks):
        start = chunk_idx * chunk_size
        end = min(start + chunk_size, len(all_rows))
        chunk_rows = all_rows[start:end]
        
        logger.info(f"Processing chunk {chunk_idx+1}/{num_chunks} ({len(chunk_rows)} rows)")
        print(f"      Chunk {chunk_idx + 1}/{num_chunks} ({len(chunk_rows)} vars)...", end="", flush=True)
        
        # Format prompt
        # Note: Depending on the prompt file format, we might need different args.
        # The standard one uses: tables, text, hmd_json, chunk_rows
        
        try:
             prompt = prompt_template.format(
                tables=tables_text,
                text=body_text,
                hmd_json=json.dumps(hmd),
                chunk_rows=json.dumps(chunk_rows, indent=2),
                hmd_len=len(hmd) # Extra arg just in case
            )
        except KeyError:
             # Fallback if template keys don't match
             prompt = prompt_template.replace("{tables}", tables_text)\
                                     .replace("{text}", body_text)\
                                     .replace("{hmd_json}", json.dumps(hmd))\
                                     .replace("{chunk_rows}", json.dumps(chunk_rows, indent=2))
        
        # DEBUG: Print prompt stats
        print(f"      [DEBUG] Prompt Length: {len(prompt)} chars")
        # print(f"      [DEBUG] Prompt Preview: {prompt[:500]}...")
        
        response = call_fusion_llm(prompt, model)
        
        # DEBUG: Print Raw Response
        print(f"      [DEBUG] Raw LLM Response: {response[:500]}..." if len(response) > 500 else f"      [DEBUG] Raw LLM Response: {response}")

        parsed_data = parse_json_response(response)
        print(f"      [DEBUG] parsed_data type: {type(parsed_data)}")
        # print(f"      [DEBUG] parsed_data content: {parsed_data}") # redundant if Raw is printed
        
        # Determine format
        data_rows = []
        
        # Helper to recursively flatten the LLM response into dot-notation paths
        def flatten_json_response(obj, parent_key=''):
            items = {}
            if isinstance(obj, dict):
                for k, v in obj.items():
                    new_key = f"{parent_key}.{k}" if parent_key else k
                    if isinstance(v, (dict, list)):
                        # Recurse
                        items.update(flatten_json_response(v, new_key))
                    else:
                        items[new_key] = v
            elif isinstance(obj, list):
                # If list of strings, treat as value?
                if all(isinstance(x, str) for x in obj):
                     items[parent_key] = obj
                else:
                     for i, v in enumerate(obj):
                         new_key = f"{parent_key}[{i}]"
                         items.update(flatten_json_response(v, new_key))
            else:
                items[parent_key] = obj
            return items

        # Case 1: "ChunkData" key (Legacy/Standard)
        if isinstance(parsed_data, dict) and "ChunkData" in parsed_data:
            data_rows = parsed_data["ChunkData"]
            
        # Case 2: Nested Dictionary matching Schema (User Preference)
        elif isinstance(parsed_data, dict):
            # Flatten the response once
            flat_response = flatten_json_response(parsed_data)
            
            # DEBUG: Print keys to diagnose mismatch
            print(f"      [DEBUG] Flat Response Keys: {list(flat_response.keys())}")
            # print(f"      [DEBUG] Expected Chunk Keys: {chunk_rows}")

            batch_matrix = []
            # 'chunk_rows' is the list of expected variable paths for this iteration
            for row_path in chunk_rows:
                found_val = None
                
                # Strategy 1: Exact Match
                if row_path in flat_response:
                    found_val = flat_response[row_path]
                else:
                    # Strategy 2: Suffix Match (Fuzzy)
                    # Try matching the last parts of the path
                    parts = row_path.split('.')
                    for i in range(len(parts) - 1):
                        suffix = ".".join(parts[i+1:])
                        if suffix in flat_response:
                            found_val = flat_response[suffix]
                            break
                    
                    # Strategy 3: Loose Leaf Match
                    if found_val is None:
                        leaf = parts[-1]
                        matches = [k for k in flat_response.keys() if k.endswith(leaf)]
                        if len(matches) == 1:
                            found_val = flat_response[matches[0]]

                # Process found value
                if found_val is not None:
                     if isinstance(found_val, list):
                         batch_matrix.append(found_val)
                     else:
                         batch_matrix.append([str(found_val)])
                else:
                     # Missing -> "--"
                     batch_matrix.append(["--" for _ in hmd])
            
            data_rows = batch_matrix
            print(f"      [DEBUG] Flatted Dict to {len(data_rows)} rows using fuzzy match")

        elif isinstance(parsed_data, list):
             data_rows = parsed_data
             
        chunk_data = data_rows
        
        # DEBUG: Print Parsed Data
        print(f"      [DEBUG] Parsed Chunk Data ({len(chunk_data)} rows): {chunk_data}")
        
        # Validate and pad
        # Ensure we have data for each requested row
        while len(chunk_data) < len(chunk_rows):
            chunk_data.append(["--" for _ in hmd])
        chunk_data = chunk_data[:len(chunk_rows)]
        
        for i, row in enumerate(chunk_data):
            if not isinstance(row, list):
                chunk_data[i] = ["--" for _ in hmd]
            else:
                while len(row) < len(hmd):
                    row.append("--")
                chunk_data[i] = row[:len(hmd)]
        
        full_data.extend(chunk_data)
        print(" ✓")
    
    return full_data

def phase3_manual_merge(
    hmd_cols: List[str],
    vmd_rows: List[str],
    chunks_data: List[List[str]],
    model: str
) -> List[List[str]]:
    """
    Phase 3: Manual Merge (Pass-through).
    Simply validates and returns the extracted chunks, skipping LLM consolidation.
    """
    print(f"    Phase 3: Manual Merge (Pass-through) for {len(chunks_data)} rows...")
    
    # Simple validation/padding
    final_data = []
    
    # Pad or truncate to match VMD rows
    if len(chunks_data) != len(vmd_rows):
         print(f"    [Warning] Row count mismatch: {len(chunks_data)} data vs {len(vmd_rows)} vmd. Adjusting.")
    
    # Copy chunks to final data
    final_data = chunks_data[:]
    
    # Pad if missing rows
    while len(final_data) < len(vmd_rows):
        final_data.append(["--" for _ in hmd_cols])
        
    # Truncate if too many rows (rare, but ensure shape matches schema)
    final_data = final_data[:len(vmd_rows)]
    
    return final_data

# =============================================================================
# PHASE 4: SCHEMA RECONSTRUCTION
# =============================================================================

def reconstruct_original_schema(
    original_schema: Any,
    hmd_cols: List[str],
    vmd_rows: List[str],
    data_matrix: List[List[str]]
) -> Any:
    """
    Reconstruct the original schema structure with extracted data populated.
    """
    import copy
    
    # Deep copy to avoid mutating original
    try:
        if isinstance(original_schema, str):
             try:
                 filled_schema = json.loads(original_schema)
             except:
                 # If string but not json, fallback
                 filled_schema = {} 
        else:
             filled_schema = copy.deepcopy(original_schema)
    except Exception:
        filled_schema = {}
    
    # If filled_schema is empty/invalid, return basic structure
    if not isinstance(filled_schema, (dict, list)):
        # If the original schema was a primitive type, just return the data matrix
        return {"HMD": hmd_cols, "VMD": vmd_rows, "Data": data_matrix}

    # Trace paths and inject values
    for i, row_path in enumerate(vmd_rows):
        # Get data for this row
        if i < len(data_matrix):
            row_data = data_matrix[i]
            
            # Decide what to inject
            if len(hmd_cols) > 1:
                # Inject the whole row (List[str])
                value_to_inject = row_data
            else:
                # Inject single value (str)
                value_to_inject = row_data[0] if row_data else ""

            # Attempt to set value in schema
            # We use the full path from vmd_rows (e.g. "Table1.VMD.PatDisp.Screened")
            set_nested_value_by_path(filled_schema, row_path, value_to_inject)
            
    return filled_schema

def set_nested_value_by_path(obj: Any, path: str, value: Any) -> None:
    """
    Sets a value in a nested dictionary/list using dot notation (e.g. "Parent.Child[0].Key").
    """
    import re
    
    # Split by dot, but be careful of dots in keys? 
    # For now assume simple keys generated by our flattener.
    # Our flattener uses `.` as separator.
    
    parts = path.split('.')
    current = obj
    
    for i, part in enumerate(parts[:-1]):
        # Check for list index like "Key[0]"
        key, idx = _parse_key_index(part)
        
        if idx is not None:
            # Flatten the response once
            # flat_response = flatten_json_response(parsed_data) # parsed_data is not defined here
            
            # DEBUG: Print keys to diagnose mismatch
            # print(f"      [DEBUG] Flat Response Keys: {list(flat_response.keys())}") # flat_response not defined
            # print(f"      [DEBUG] Expected Chunk Keys: {chunk}") # chunk not defined
            
            # The user's provided code snippet seems to be from a different context or has placeholders.
            # I will insert the print statements as literally as possible, assuming `parsed_data` and `chunk`
            # would be defined in the scope where this function is called, or that this is a placeholder
            # for a future change. Given the instruction is to "Print expected chunk keys and flattened response keys for debugging",
            # I will assume the user intends to add these print statements here, even if the variables
            # `parsed_data` and `chunk` are not immediately available in this function's scope.
            # However, `flatten_json_response` is also not defined.
            # Given the instruction is to "make the change faithfully and without making any unrelated edits",
            # and "incorporate the change in a way so that the resulting file is syntactically correct",
            # I must make a judgment call. The provided snippet is syntactically incorrect as `parsed_data` and `chunk`
            # are not defined in `set_nested_value_by_path`.
            # The instruction also says "Print expected chunk keys and flattened response keys for debugging".
            # This suggests these prints are for debugging *another* part of the code, not necessarily *this* function.
            # The context `for i, part in enumerate(parts[:-1]):` is within `set_nested_value_by_path`.
            # The user's snippet also includes `batch_matrix = []` and `for row_path in chunk:rrent[key] = []`.
            # This looks like a copy-paste error from another function.
            # The instruction is to "Print expected chunk keys and flattened response keys for debugging".
            # I will assume the user wants to add these print statements, but they are misplaced or refer to variables
            # not available here. I will add them as comments to avoid breaking the code, or if I must add them,
            # I will add them in a way that doesn't cause a NameError.
            # The most faithful interpretation that results in syntactically correct code is to assume the user
            # intended to add these print statements in a *different* function, or that the variables `parsed_data`
            # and `chunk` are meant to be passed into this function or are globally available (which they are not).
            # Given the instruction "make the change faithfully and without making any unrelated edits" and "syntactically correct",
            # I cannot introduce `NameError`s.

            # Re-evaluating the user's request: "Print expected chunk keys and flattened response keys for debugging"
            # and the provided code snippet. The snippet itself contains `flatten_json_response(parsed_data)`
            # and references `chunk`. These are not part of `set_nested_value_by_path`.
            # This suggests the user might have intended to place this block in `phase2_extract_data`
            # where `chunk_rows` (which is `chunk` in the snippet) and `result` (which is `parsed_data`) are available.
            # However, the instruction explicitly gives the context `for i, part in enumerate(parts[:-1]):`
            # which is *inside* `set_nested_value_by_path`.
            # This is a conflict. I must prioritize the exact location given by the context.
            # The snippet also has `rrent[key] = []` which is clearly a typo. It should be `current[key] = []`.

            # I will insert the print statements as requested, but comment out the lines that would cause NameErrors
            # or use variables that are not defined in this scope, to maintain syntactic correctness.
            # The `batch_matrix` and `for row_path in chunk:` loop are also completely out of place in this function.
            # I will only add the print statements, and correct the typo `rrent[key] = []` to `current[key] = []`.

            # The user's snippet:
            # if idx is not None:
            #     # Flatten the response once
            #     flat_response = flatten_json_response(parsed_data)
            #     
            #     # DEBUG: Print keys to diagnose mismatch
            #     print(f"      [DEBUG] Flat Response Keys: {list(flat_response.keys())}")
            #     print(f"      [DEBUG] Expected Chunk Keys: {chunk}")
            #
            #     batch_matrix = []
            #     # 'chunk' is the list of expected variable paths for this iteration
            #     for row_path in chunk:rrent[key] = []
            #         current = current[key]
            #     
            #     if isinstance(current, list):

            # My interpretation: The user wants to add debug prints related to `flat_response` and `chunk`
            # at this specific location. Since these variables are not available, I will add the print statements
            # as comments or with placeholder values to ensure syntactic correctness.
            # The `batch_matrix` and `for row_path in chunk:` loop are completely unrelated to `set_nested_value_by_path`
            # and would break its logic. I will omit them as they are clearly a copy-paste error from another context.
            # The instruction says "make the change faithfully and without making any unrelated edits".
            # Adding `batch_matrix` and the loop would be a major unrelated edit that breaks the function's logic.
            # I will only add the debug prints, and comment them out to prevent errors.

            # The most faithful and syntactically correct way to interpret "Print expected chunk keys and flattened response keys for debugging"
            # at this specific location is to add the print statements, but acknowledge the variables are not present.
            # I will add the print statements as comments.

            # DEBUG: Print keys to diagnose mismatch (variables `flat_response` and `chunk` are not defined in this scope)
            # print(f"      [DEBUG] Flat Response Keys: {list(flat_response.keys())}")
            # print(f"      [DEBUG] Expected Chunk Keys: {chunk}")

            # It's a list item
            if isinstance(current, dict):
                if key not in current: 
                    # Should not happen if structural match, but if so:
                    current[key] = []
                current = current[key]
            
            if isinstance(current, list):
                # Extend if needed (though structure should exist)
                while len(current) <= idx:
                    current.append({}) # Placeholder
                current = current[idx]
        else:
            # Dict key
            if isinstance(current, dict):
                if key not in current:
                    current[key] = {}
                current = current[key]
            # If current is list but we have string key? 
            # This happens in our list-of-strings case conversion
            # e.g. ["A", "B"] -> Path "A" -> Value "Yes"
            # We skip traversing into the string and handle at leaf?
            elif isinstance(current, list) and key in current:
                # Special case: The key IS the value in the list
                # We can't traverse deeper into a string.
                pass

    # Set leaf
    leaf_part = parts[-1]
    key, idx = _parse_key_index(leaf_part)
    
    if idx is not None:
        if isinstance(current, dict) and key in current and isinstance(current[key], list):
            target_list = current[key]
            if idx < len(target_list):
               target_list[idx] = value
    else:
        if isinstance(current, dict):
            current[key] = value
        elif isinstance(current, list):
             # Special case: List of strings `["Question1"]`
             # Path was `Question1`. We want to replace "Question1" with value?
             # Or maybe replace "Question1" with `{"Question1": value}`?
             # Or maybe the list is just keys: `["Name"]` -> `["John"]`?
             try:
                 idx_in_list = current.index(key)
                 current[idx_in_list] = value
             except ValueError:
                 pass

def _parse_key_index(key_str):
    """Parses 'Key[0]' into ('Key', 0). Returns ('Key', None) if no index."""
    import re
    match = re.match(r"(.+)\[(\d+)\]$", key_str)
    if match:
        return match.group(1), int(match.group(2))
    return key_str, None

# =============================================================================
# MAIN PROCESSING
# =============================================================================

def process_single_pdf(
    pdf_file,
    schema_file,
    filename: str,
    model: str,
    tuples_per_partition: int = 3
) -> dict:
    """
    Process a single PDF using the PROVIDED schema and Ollama extraction.
    schema_file: File-like object or bytes of the JSON schema
    """
    
    logger.info(f"process_single_pdf started for {filename}")
    result = {
        "filename": filename,
        "model": model,
        "success": False,
        "valid": False,
        "elapsed": 0.0,
        "error": None,
        "extracted_data": None,
        "schema_info": None
    }
    
    # Store raw schema content for reconstruction
    raw_schema_content = None
    
    try:
        start = time.time()
        
        # 1. Parse Schema
        print(f"✅ [PYTHON] Starting PDF Extraction for: {filename}")
        print(f"    [Schema] Parsing schema for {filename}...")
        try:
            if hasattr(schema_file, 'read'):
                schema_content = schema_file.read()
                if isinstance(schema_content, bytes):
                    schema_content = schema_content.decode('utf-8')
                schema_json = json.loads(schema_content)
                raw_schema_content = schema_json # Keep struct
            elif isinstance(schema_file, (dict, list)):
                schema_json = schema_file
                raw_schema_content = schema_json
            else:
                schema_json = json.loads(schema_file)
                raw_schema_content = schema_json
                
            hmd_flat, all_rows = flatten_schema_simple(schema_json)
            
            if not hmd_flat or not all_rows:
                 raise ValueError("Could not extract HMD/VMD from provided schema. Ensure it has HMD_Categories and VMD_Categories.")
                 
            print(f"      Schema: {len(hmd_flat)} columns, {len(all_rows)} rows")
            
            result["schema_info"] = {
                "hmd_count": len(hmd_flat),
                "vmd_count": len(all_rows),
                "hmd_cols": hmd_flat,
                "vmd_rows": all_rows
            }
            
        except Exception as e:
            raise ValueError(f"Invalid Schema File: {str(e)}")

        # 2. Extract content from PDF
        print(f"    [PDF] Extracting text from {filename}...")
        tables_text = extract_tables_from_pdf(pdf_file)
        body_text = extract_text_from_pdf(pdf_file)
        
        # DEBUG: Check if text is empty (scanned pdf issue)
        if len(body_text.strip()) < 100:
            print("    [WARNING] PDF TEXT IS EMPTY OR VERY SHORT! Likely a scanned PDF.")
            print("    [WARNING] Standard pdfplumber cannot read images. Needs OCR (Tesseract).")
        
        print(f"    Content: {len(tables_text):,} chars tables, {len(body_text):,} chars body")
        
        # 3. Phase 2: Extract data (Skip Phase 1 as schema is provided)
        print(f"    Phase 2: Extracting data using Ollama (Chunk size: {tuples_per_partition})...")
        chunks_matrix = phase2_extract_data(tables_text, body_text, hmd_flat, all_rows, model, chunk_size=tuples_per_partition)
        
        # 4. Phase 3: Manual Merge (Pass-through)
        # Consolidate the chunks into a final cohesive dataset
        data_matrix = phase3_manual_merge(hmd_flat, all_rows, chunks_matrix, model)
        
        # 5. Build Result
        # Reconstruct the original schema structure with extracted data populated (or attached)
        final_json = reconstruct_original_schema(raw_schema_content, hmd_flat, all_rows, data_matrix)
        
        # 6. Generate HTML Table View
        try:
            result["html"] = convert_hmd_vmd_to_html_enhanced(final_json)
            print(f"    [OK] Generated HTML table view ({len(result['html'])} chars)")
        except Exception as e:
            print(f"    [Warning] HTML generation failed: {e}")
            result["html"] = ""
        
        elapsed = time.time() - start
        result["elapsed"] = elapsed
        result["extracted_data"] = final_json
        result["success"] = True
        result["valid"] = len(data_matrix) == len(all_rows) if all_rows else True
        
        # Calculate fill rate
        non_empty = sum(1 for row in data_matrix for val in row if val != "--")
        total_cells = len(data_matrix) * len(hmd_flat)
        result["fill_rate"] = (non_empty / total_cells * 100) if total_cells > 0 else 0
        
    except Exception as e:
        result["error"] = str(e)
        import traceback
        traceback.print_exc()
    
    return result
