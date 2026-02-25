# C:\Users\saiga\OneDrive\Documents\First_SEM_FSU\Project_Colorectal\Dataset_Preparation\Automation_Sigmoid\Summer25\Claudecode_Fusion_Frontend\Breakdown\sender_backup

'''
FastAPI Version - Reuses ALL functionality from main_local.py
This approach imports all helper functions to preserve 100% functionality
'''

from fastapi import FastAPI, Request, UploadFile, File, Form, Depends, HTTPException, status, Response
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.concurrency import run_in_threadpool
import secrets
import os
import uuid
import json
import tempfile
from datetime import datetime, timedelta
from typing import List, Optional
from pathlib import Path
from modules.dynamic_pdf import process_single_pdf

# Create FastAPI app
app = FastAPI(title="Enhanced Schema Fusion App - FastAPI")

# HTTP Basic Authentication with session invalidation
security = HTTPBasic()

# Simple credentials (change these to your desired username/password)
VALID_USERNAME = "scbc"
VALID_PASSWORD = "moffitt"

# Session storage (in-memory, resets on server restart)
active_sessions = {}

class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to invalidate cached credentials on page reload"""
    async def dispatch(self, request: Request, call_next):
        # Skip auth for static files
        if request.url.path.startswith("/static") or request.url.path.startswith("/fuze/static"):
            return await call_next(request)

        # Removed the logic that forced a 401 to make the user re-login every time
        response = await call_next(request)
        return response

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify HTTP Basic Auth credentials"""
    # Debug logging
    print(f"[AUTH] Attempting login - Username: '{credentials.username}' (len={len(credentials.username)})")
    print(f"[AUTH] Expected username: '{VALID_USERNAME}' (len={len(VALID_USERNAME)})")
    print(f"[AUTH] Password length: {len(credentials.password)}, Expected: {len(VALID_PASSWORD)}")

    correct_username = secrets.compare_digest(credentials.username.encode("utf8"), VALID_USERNAME.encode("utf8"))
    correct_password = secrets.compare_digest(credentials.password.encode("utf8"), VALID_PASSWORD.encode("utf8"))

    print(f"[AUTH] Username match: {correct_username}, Password match: {correct_password}")

    if not (correct_username and correct_password):
        print(f"[AUTH] ❌ Authentication FAILED")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": 'Basic realm="FusionApp"'},
        )

    print(f"[AUTH] ✅ Authentication SUCCESS for user: {credentials.username}")
    return credentials.username

# Add authentication middleware FIRST (before CORS)
app.add_middleware(AuthMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates - use absolute path to avoid directory issues
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
# Also mount at /fuze/static for compatibility with server deployment
app.mount("/fuze/static", StaticFiles(directory=STATIC_DIR), name="fuze_static")



# ============================================================================
# Import ALL functionality from fusion_helpers.py
# ============================================================================
try:
    from fusion_helpers import *
    print("[OK] Successfully loaded all functions from fusion_helpers.py")
except Exception as e:
    print(f"[ERROR] Failed to load fusion_helpers.py: {e}")
    print("[INFO] Make sure fusion_helpers.py exists in the same directory")
    # Set defaults if import fails
    parse_docx_file = None
    parse_json_input = None
    process_with_llm_enhanced = None
    store_llm_response_to_mongodb = lambda *args, **kwargs: None
    load_from_json_file = None
    client = None

# Import partition utility functions
try:
    from modules.partition_utils import calculate_partition_stats, get_data_row_count_from_schema, create_partitioned_schemas, slice_hierarchical_vmd
    from modules.llm_client import detect_schema_complexity
    print("[OK] Successfully loaded partition utilities")
except Exception as e:
    print(f"[WARNING] Failed to load partition utilities: {e}")
    calculate_partition_stats = None
    get_data_row_count_from_schema = None
    create_partitioned_schemas = None
    detect_schema_complexity = None
    gemini_client = None
    anthropic_client = None
    MODEL_MAP = {}
    LOGS_DIR = 'logs'
    RESULTS_DIR = 'results'
    STORAGE_DIR = 'fusion_data'
    UPLOADS_DIR = 'uploads'
    GEMINI_AVAILABLE = False

# ============================================================================
# FastAPI Routes
# ============================================================================


@app.get("/")
async def root():
    return RedirectResponse(url="/fuze/")

@app.get("/fuze/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/fuze/tool", response_class=HTMLResponse)
async def tool(request: Request, mode: str = "fusion"):
    return templates.TemplateResponse("tool.html", {"request": request, "mode": mode})

# @app.post("/fuze/upload")
# async def upload_file(file: UploadFile = File(...), type: str = Form(...)):
# @app.get("/fuze/", response_class=HTMLResponse)
# async def index(request: Request, username: str = Depends(verify_credentials)):
#     return templates.TemplateResponse("index.html", {"request": request})

@app.post("/fuze/upload")
async def upload_file(file: UploadFile = File(...), type: str = Form(...), username: str = Depends(verify_credentials)):
    try:
        from modules.profiler import calculate_schema_profile, format_profile_for_display

        file_content = await file.read()
        filename = file.filename.lower()
        json_text = None

        if filename.endswith('.docx'):
            result = parse_docx_file(file_content) if parse_docx_file else {'success': False, 'error': 'Function not available'}
        elif filename.endswith('.json'):
            try:
                json_text = file_content.decode('utf-8')
                import json as json_module

                # Step 1: Use parse_json_input to generate preview HTML (uses flattened data)
                result = parse_json_input(json_text) if parse_json_input else {'success': False, 'error': 'Function not available'}

                if not result.get('success'):
                    return JSONResponse(result)

                # Step 2: Parse and preserve original hierarchical structure for partitioning
                try:
                    original_data = json_module.loads(json_text)
                    # Override data with hierarchical structure (keep HTML from parse_json_input)
                    result['data'] = original_data

                    print(f"[DEBUG] JSON file uploaded:")
                    print(f"[DEBUG]   - Preview HTML: {len(result.get('html', '')) if result.get('html') else 0} chars")
                    print(f"[DEBUG]   - Data structure: hierarchical (preserved for partitioning)")
                    print(f"[DEBUG]   - HMD keys in data: {[k for k in original_data.keys() if '.HMD' in k]}")

                except json_module.JSONDecodeError as e:
                    print(f"[WARNING] Could not preserve hierarchical structure: {e}")

            except UnicodeDecodeError:
                return JSONResponse({'success': False, 'error': 'Invalid file encoding'})
        elif filename.endswith('.txt'):
            try:
                json_text = file_content.decode('utf-8')
                # Parse JSON directly to preserve hierarchical structure
                import json as json_module
                try:
                    json_data = json_module.loads(json_text)
                    result = {'success': True, 'data': json_data}
                    print(f"[DEBUG] TXT file parsed as JSON, preserving original structure")

                    # Add profile for preview display (doesn't modify original data)
                    try:
                        from modules.profiler import calculate_schema_profile, format_profile_for_display
                        profile = calculate_schema_profile(json_data, json_text)
                        result['profile'] = format_profile_for_display(profile)
                        print(f"[DEBUG] Profile calculated successfully")
                    except Exception as e:
                        print(f"[WARNING] Profile calculation failed: {e}")
                        result['profile'] = None

                except json_module.JSONDecodeError as e:
                    # Fall back to parse_json_input if not valid JSON
                    result = parse_json_input(json_text) if parse_json_input else {'success': False, 'error': 'Function not available'}
            except UnicodeDecodeError:
                return JSONResponse({'success': False, 'error': 'Invalid text file encoding'})
        else:
            return JSONResponse({'success': False, 'error': 'Unsupported file type'})

        # Add profile information if parsing was successful
        if result.get('success') and result.get('data'):
            profile = calculate_schema_profile(result['data'], json_text)
            result['profile'] = format_profile_for_display(profile)

        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({'success': False, 'error': f'File processing error: {str(e)}'})

@app.post("/fuze/predict")
async def predict_automated(request: Request):
    try:
        from modules.automated_fusion import extract_combined_features, predict_best_paths
        
        data = await request.json()
        source_data = data.get('source_schema')
        target_data = data.get('target_schema')
        backend = data.get('backend', 'rf')
        mode = data.get('mode', 'merge')
        
        if not source_data or not target_data:
            return JSONResponse({'success': False, 'error': 'Missing schema data'})
            
        # Extract features
        features = extract_combined_features(source_data, target_data)
        
        # Predict best paths
        predictions = predict_best_paths(
            backend=backend,
            mode=mode,
            schema_type=features['schema_type'],
            input_tokens=features['input_prompt_tokens']
        )
        
        return JSONResponse({
            'success': True,
            'extraction': features,
            'prediction': predictions
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({'success': False, 'error': f'Prediction error: {str(e)}'})

@app.post("/fuze/parse-text")
async def parse_text(request: Request, username: str = Depends(verify_credentials)):
    try:
        from modules.profiler import calculate_schema_profile, format_profile_for_display

        data = await request.json()
        text = data.get('text', '')
        if not text.strip():
            return JSONResponse({'success': False, 'error': 'Empty text provided'})
        result = parse_json_input(text) if parse_json_input else {'success': False, 'error': 'Function not available'}

        # Add profile information if parsing was successful
        if result.get('success') and result.get('data'):
            profile = calculate_schema_profile(result['data'], text)
            result['profile'] = format_profile_for_display(profile)

        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({'success': False, 'error': f'Text parsing error: {str(e)}'})

@app.get("/fuze/models")
async def get_models():
    """Get available LLM models from configuration"""
    try:
        # Import MODEL_MAP and UI_MODELS
        import modules.config as config
        
        # Get full map
        model_map = getattr(config, 'MODEL_MAP', {})
        
        # Get curated list for UI if available
        ui_models = getattr(config, 'UI_MODELS', None)
        
        # Prepare response models
        if ui_models:
            # Create a dict of {Display Name: Model ID} for only the curated models
            # Only include models that actually exist in the map to be safe, 
            # or just trust UI_MODELS if they are direct keys
            models_to_return = {}
            for m in ui_models:
                # If m is in MODEL_MAP, use it. If not, assume it's valid as-is.
                # In config.py: "Qwen2.5:14B": "Qwen2.5:14B"
                if m in model_map:
                    models_to_return[m] = model_map[m]
                else:
                    # Fallback if config has a typo or just a list of IDs
                    models_to_return[m] = m
                    
            return JSONResponse({
                'success': True, 
                'models': models_to_return,
                'default': model_map.get('default', '')
            })
            
        # Fallback to full map if UI_MODELS is not defined
        return JSONResponse({
            'success': True, 
            'models': model_map,
            'default': model_map.get('default', '')
        })
    except Exception as e:
        return JSONResponse({'success': False, 'error': f'Failed to fetch models: {str(e)}'})

def extract_vmd_keys_from_merged_data(merged_data):
    """
    Extract unique VMD keys from the actual Merged_Data structure.
    This ensures VMD_Merged_Schema matches the keys actually used in the data,
    fixing the mismatch where LLM may generate inconsistent schema keys.
    
    Args:
        merged_data: List of HMD column objects with VMD_data arrays
        
    Returns:
        List of unique VMD keys in the order they appear
    """
    vmd_keys = []
    seen_keys = set()
    
    if not merged_data or not isinstance(merged_data, list):
        return vmd_keys
    
    # Iterate through each HMD column entry
    for hmd_entry in merged_data:
        if not isinstance(hmd_entry, dict):
            continue
            
        # Get the HMD column data (value of the first key)
        for hmd_key, hmd_data in hmd_entry.items():
            if not isinstance(hmd_data, dict):
                continue
                
            vmd_data_list = hmd_data.get('VMD_data', [])
            if not isinstance(vmd_data_list, list):
                continue
                
            # Extract VMD keys from VMD_data array
            for vmd_entry in vmd_data_list:
                if not isinstance(vmd_entry, dict):
                    continue
                    
                for vmd_key in vmd_entry.keys():
                    if vmd_key not in seen_keys:
                        seen_keys.add(vmd_key)
                        vmd_keys.append(vmd_key)
    
    print(f"[EXTRACT] Extracted {len(vmd_keys)} unique VMD keys from Merged_Data")
    return vmd_keys


def convert_partition_merge_to_ui_format(partition_merged_data, hmd_merged_schema):
    """
    Convert partition merge format to UI-expected format.
    
    Partition merge returns:
    {"VMD_row": {"source": [val1, val2, ...], "target": [val1, val2, ...]}}
    
    UI expects:
    [{"HMD_col": {"VMD_data": [{"VMD_row": {"source1": val, "source2": val}}]}}]
    """
    if not partition_merged_data or not hmd_merged_schema:
        return []
    
    ui_format = []
    
    # For each HMD column, create an entry with VMD_data
    for col_idx, hmd_col in enumerate(hmd_merged_schema):
        vmd_data_list = []
        
        # For each VMD row in the partition merged data
        for vmd_row, values in partition_merged_data.items():
            source_array = values.get('source', [])
            target_array = values.get('target', [])
            
            # Get value at this column index
            source_val = source_array[col_idx] if col_idx < len(source_array) else ''
            target_val = target_array[col_idx] if col_idx < len(target_array) else ''
            
            # Create VMD_data entry
            vmd_data_list.append({
                vmd_row: {
                    'source1': source_val,
                    'source2': target_val
                }
            })
        
        ui_format.append({
            hmd_col: {
                'VMD_data': vmd_data_list
            }
        })
    
    print(f"[FORMAT] Converted partition merge format to UI format: {len(ui_format)} HMD columns")
    return ui_format

@app.post("/fuze/create-partitions")
async def create_partitions(request: Request, username: str = Depends(verify_credentials)):
    """Create partition analysis when table partition method is selected"""
    try:
        data = await request.json()
        source_schema = data.get('sourceSchema', '')
        target_schema = data.get('targetSchema', '')
        merge_method = data.get('mergeMethod', '')

        print(f"[DEBUG] Create partitions endpoint called with method: {merge_method}")

        if not all([source_schema, target_schema]):
            return JSONResponse({'success': False, 'error': 'Source and target schemas are required'})

        if merge_method not in ['table_partition_horizontal', 'table_partition_vertical']:
            return JSONResponse({'success': False, 'error': 'Invalid partition method'})

        # Parse schemas - preserve original hierarchical structure
        import json

        # Parse the JSON directly without any transformation
        if isinstance(source_schema, str):
            source_data = json.loads(source_schema)
        else:
            source_data = source_schema

        if isinstance(target_schema, str):
            target_data = json.loads(target_schema)
        else:
            target_data = target_schema

        print(f"[DEBUG] Source schema keys: {list(source_data.keys()) if isinstance(source_data, dict) else 'Not a dict'}")
        print(f"[DEBUG] Target schema keys: {list(target_data.keys()) if isinstance(target_data, dict) else 'Not a dict'}")

        # Verify HMD structure is hierarchical
        if 'Table1.HMD' in source_data:
            hmd_sample = source_data['Table1.HMD']
            if isinstance(hmd_sample, list) and len(hmd_sample) > 0:
                print(f"[DEBUG] Source HMD structure type: {type(hmd_sample[0])}")
                if isinstance(hmd_sample[0], dict):
                    print(f"[DEBUG] Source HMD is hierarchical with keys: {list(hmd_sample[0].keys())}")
                else:
                    print(f"[WARNING] Source HMD appears to be flattened: {hmd_sample[0]}")

        # Get data row counts
        source_data_rows = get_data_row_count_from_schema(source_data) if get_data_row_count_from_schema else 0
        target_data_rows = get_data_row_count_from_schema(target_data) if get_data_row_count_from_schema else 0

        print(f"[DEBUG] Source data rows: {source_data_rows}, Target data rows: {target_data_rows}")

        if not calculate_partition_stats or not create_partitioned_schemas:
            return JSONResponse({'success': False, 'error': 'Partition utilities not available'})

        # Calculate partition stats
        partition_stats = calculate_partition_stats(source_data_rows, target_data_rows)
        print(f"[DEBUG] Partition stats calculated: {partition_stats}")

        # Create partitioned schemas
        print("[DEBUG] Creating partitioned schemas...")
        partitioned_data = create_partitioned_schemas(source_data, target_data, partition_stats)
        print(f"[DEBUG] Partitioned data created. Source partitions: {len(partitioned_data.get('source_partitions', []))}, Target partitions: {len(partitioned_data.get('target_partitions', []))}")

        # Write partition analysis to timestamped text file
        import datetime
        import os
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        partition_output_file = f"partition_analysis_{timestamp}.txt"
        print(f"[DEBUG] Writing partition analysis to: {partition_output_file}")

        with open(partition_output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("PARTITION ANALYSIS REPORT\n")
            f.write("=" * 80 + "\n\n")

            # Write partition statistics
            f.write("PARTITION STATISTICS\n")
            f.write("-" * 80 + "\n")
            f.write(f"Number of Partitions: {partition_stats['partitions']}\n")
            f.write(f"Source Table Data Rows: {partition_stats['table1_data_rows']}\n")
            f.write(f"Source Table Partition Size: {partition_stats['table1_partition_size']}\n")
            f.write(f"Source Table Remainder: {partition_stats['table1_rest']}\n")
            f.write(f"Target Table Data Rows: {partition_stats['table2_data_rows']}\n")
            f.write(f"Target Table Partition Size: {partition_stats['table2_partition_size']}\n")
            f.write(f"Target Table Remainder: {partition_stats['table2_rest']}\n")
            f.write("\n")

            # Write source partitions
            f.write("SOURCE TABLE PARTITIONS\n")
            f.write("-" * 80 + "\n")
            source_partitions = partitioned_data.get('source_partitions', [])
            for i, partition in enumerate(source_partitions):
                f.write(f"\nPartition {partition['partition_id']}:\n")
                f.write(f"  Table Name: {partition['table_name']}\n")
                f.write(f"  Row Range: {partition['start_row']}-{partition['end_row']} (total: {partition['row_count']} rows)\n")
                f.write(f"  Is Remainder: {partition['is_remainder']}\n")
                f.write("\n")

                # Write HMD
                hmd_key = f"{partition['table_name']}.HMD"
                if hmd_key in partition['schema']:
                    hmd = partition['schema'][hmd_key]
                    f.write(f"  HMD (Horizontal Metadata):\n")
                    import json
                    f.write(f"    {json.dumps(hmd, indent=4)}\n")
                    f.write("\n")

                # Write VMD (hierarchical, sliced)
                vmd_key = f"{partition['table_name']}.VMD"
                if vmd_key in partition['schema']:
                    vmd = partition['schema'][vmd_key]
                    f.write(f"  VMD (Vertical Metadata - Sliced):\n")
                    f.write(f"    {json.dumps(vmd, indent=4)}\n")
                    f.write("\n")

                # Show sample data (first 3 rows)
                data_key = f"{partition['table_name']}.Data"
                if data_key in partition['schema']:
                    data_rows = partition['schema'][data_key]
                    f.write(f"  Sample Data (first 3 rows):\n")
                    for j, row in enumerate(data_rows[:3]):
                        f.write(f"    Row {partition['start_row'] + j}: {str(row)[:100]}...\n")

            f.write("\n")

            # Write target partitions
            f.write("TARGET TABLE PARTITIONS\n")
            f.write("-" * 80 + "\n")
            target_partitions = partitioned_data.get('target_partitions', [])
            for i, partition in enumerate(target_partitions):
                f.write(f"\nPartition {partition['partition_id']}:\n")
                f.write(f"  Table Name: {partition['table_name']}\n")
                f.write(f"  Row Range: {partition['start_row']}-{partition['end_row']} (total: {partition['row_count']} rows)\n")
                f.write(f"  Is Remainder: {partition['is_remainder']}\n")
                f.write("\n")

                # Write HMD
                hmd_key = f"{partition['table_name']}.HMD"
                if hmd_key in partition['schema']:
                    hmd = partition['schema'][hmd_key]
                    f.write(f"  HMD (Horizontal Metadata):\n")
                    f.write(f"    {json.dumps(hmd, indent=4)}\n")
                    f.write("\n")

                # Write VMD (hierarchical, sliced)
                vmd_key = f"{partition['table_name']}.VMD"
                if vmd_key in partition['schema']:
                    vmd = partition['schema'][vmd_key]
                    f.write(f"  VMD (Vertical Metadata - Sliced):\n")
                    f.write(f"    {json.dumps(vmd, indent=4)}\n")
                    f.write("\n")

                # Show sample data (first 3 rows)
                data_key = f"{partition['table_name']}.Data"
                if data_key in partition['schema']:
                    data_rows = partition['schema'][data_key]
                    f.write(f"  Sample Data (first 3 rows):\n")
                    for j, row in enumerate(data_rows[:3]):
                        f.write(f"    Row {partition['start_row'] + j}: {str(row)[:100]}...\n")

            f.write("\n")
            f.write("=" * 80 + "\n")
            f.write("END OF PARTITION ANALYSIS\n")
            f.write("=" * 80 + "\n")

        abs_path = os.path.abspath(partition_output_file)
        print(f"[INFO] Partition analysis written to: {abs_path}")
        print(f"[INFO] File exists: {os.path.exists(abs_path)}, Size: {os.path.getsize(abs_path) if os.path.exists(abs_path) else 0} bytes")

        return JSONResponse({
            'success': True,
            'partition_stats': partition_stats,
            'partition_file': partition_output_file,
            'partitions': {
                'source_partitions': partitioned_data.get('source_partitions', []),
                'target_partitions': partitioned_data.get('target_partitions', [])
            },
            'source_partitions_count': len(partitioned_data.get('source_partitions', [])),
            'target_partitions_count': len(partitioned_data.get('target_partitions', []))
        })

    except Exception as e:
        print(f"[ERROR] Failed to create partitions: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({'success': False, 'error': f'Partition creation error: {str(e)}'})

@app.post("/fuze/merge-partitions")
async def merge_partitions(request: Request, username: str = Depends(verify_credentials)):
    """Merge all partitions and stack results - Phase 4 of partition HITL workflow"""
    try:
        data = await request.json()
        source_schema = data.get('sourceSchema', '')
        target_schema = data.get('targetSchema', '')
        approved_merged_schema = data.get('approvedMergedSchema', {})
        partition_info = data.get('partitionInfo', {})
        merge_llm = data.get('mergeLLM', 'gemini-1.5-flash')
        matching_llm = data.get('matchingLLM', merge_llm)  # Matching LLM from Phase 1
        parameters = data.get('parameters', {})
        match_result = data.get('matchResult', {})  # Phase 1 schema mapping for precise key alignment
        phase_metrics = data.get('phaseMetrics', {})  # Metrics from Phase 1 (match) and Phase 2 (schema merge)

        print(f"[PARTITION-MERGE] Starting Phase 4: Merging {len(partition_info.get('source_partitions', []))} partitions")
        if match_result:
            print(f"[PARTITION-MERGE] Using schema mapping: {len(match_result.get('VMD_matches', []))} VMD matches, {len(match_result.get('HMD_matches', []))} HMD matches")
        if phase_metrics:
            print(f"[PARTITION-MERGE] Received phase metrics - Match: {phase_metrics.get('match') is not None}, SchemaMerge: {phase_metrics.get('schemaMerge') is not None}")

        # Parse schemas
        import json
        source_data = json.loads(source_schema) if isinstance(source_schema, str) else source_schema
        target_data = json.loads(target_schema) if isinstance(target_schema, str) else target_schema

        source_partitions = partition_info.get('source_partitions', [])
        target_partitions = partition_info.get('target_partitions', [])

        # Extract merged schema arrays
        hmd_schema = approved_merged_schema.get('HMD_Merged_Schema', [])
        vmd_schema = approved_merged_schema.get('VMD_Merged_Schema', [])

        # Extract ORIGINAL source and target VMD lists (for correct per-table VMD derivation)
        # These have different orders than the merged schema!
        original_source_vmd_raw = source_data.get('Table1.VMD', [])
        original_target_vmd_raw = target_data.get('Table2.VMD', [])
        original_source_vmd = extract_vmd_from_raw(original_source_vmd_raw)
        original_target_vmd = extract_vmd_from_raw(original_target_vmd_raw)
        print(f"[PARTITION-MERGE] Original source VMD: {original_source_vmd}")
        print(f"[PARTITION-MERGE] Original target VMD: {original_target_vmd}")

        actual_merged_schema = {
            "HMD_Merged_Schema": hmd_schema,
            "VMD_Merged_Schema": vmd_schema
        }

        print(f"[PARTITION-MERGE] Using merged schema - HMD: {len(hmd_schema)}, VMD: {len(vmd_schema)}")

        # Load instance merge prompt
        import os
        prompt_file_path = os.path.join(os.path.dirname(__file__), 'instancelevelMergeOperatorv2.txt')
        with open(prompt_file_path, 'r', encoding='utf-8') as f:
            merge_prompt_base = f.read()

        # Merge all partitions
        from modules.llm_client import get_llm_response
        from modules.processors import clean_llm_json_response
        import time

        partition_merge_results = []

        for i in range(len(source_partitions)):
            print(f"\n{'='*80}")
            print(f"[PARTITION-MERGE] Processing partition {i+1}/{len(source_partitions)}")
            print(f"{'='*80}")

            source_partition_schema = source_partitions[i]['schema']
            target_partition_schema = target_partitions[i]['schema']
            
            # DEBUG: Log partition data being sent to LLM
            print(f"\n[DEBUG-PARTITION-{i+1}] === SOURCE PARTITION DATA ===")
            print(f"[DEBUG-PARTITION-{i+1}] Rows: {source_partitions[i]['start_row']}-{source_partitions[i]['end_row']}")
            print(f"[DEBUG-PARTITION-{i+1}] Source schema keys: {list(source_partition_schema.keys())}")
            
            # Try both key formats
            source_hmd_key = 'Table1.HMD' if 'Table1.HMD' in source_partition_schema else 'HMD'
            source_vmd_key = 'Table1.VMD' if 'Table1.VMD' in source_partition_schema else 'VMD'
            source_data_key = 'Table1.Data' if 'Table1.Data' in source_partition_schema else 'Data'
            
            if source_hmd_key in source_partition_schema:
                print(f"[DEBUG-PARTITION-{i+1}] Source HMD ({source_hmd_key}): {source_partition_schema.get(source_hmd_key, [])}")
            if source_vmd_key in source_partition_schema:
                print(f"[DEBUG-PARTITION-{i+1}] Source VMD ({source_vmd_key}): {source_partition_schema.get(source_vmd_key, [])}")
            if source_data_key in source_partition_schema:
                source_data = source_partition_schema.get(source_data_key, [])
                print(f"[DEBUG-PARTITION-{i+1}] Source Data rows: {len(source_data)}")
                for row_idx, row in enumerate(source_data[:3]):
                    print(f"[DEBUG-PARTITION-{i+1}]   Row {row_idx}: {row}")
            
            print(f"\n[DEBUG-PARTITION-{i+1}] === TARGET PARTITION DATA ===")
            print(f"[DEBUG-PARTITION-{i+1}] Rows: {target_partitions[i]['start_row']}-{target_partitions[i]['end_row']}")
            print(f"[DEBUG-PARTITION-{i+1}] Target schema keys: {list(target_partition_schema.keys())}")
            
            # Try both key formats for target
            target_hmd_key = 'Table2.HMD' if 'Table2.HMD' in target_partition_schema else 'HMD'
            target_vmd_key = 'Table2.VMD' if 'Table2.VMD' in target_partition_schema else 'VMD'
            target_data_key = 'Table2.Data' if 'Table2.Data' in target_partition_schema else 'Data'
            
            if target_hmd_key in target_partition_schema:
                print(f"[DEBUG-PARTITION-{i+1}] Target HMD ({target_hmd_key}): {target_partition_schema.get(target_hmd_key, [])}")
            if target_vmd_key in target_partition_schema:
                print(f"[DEBUG-PARTITION-{i+1}] Target VMD ({target_vmd_key}): {target_partition_schema.get(target_vmd_key, [])}")
            if target_data_key in target_partition_schema:
                target_data = target_partition_schema.get(target_data_key, [])
                print(f"[DEBUG-PARTITION-{i+1}] Target Data rows: {len(target_data)}")
                for row_idx, row in enumerate(target_data[:3]):
                    print(f"[DEBUG-PARTITION-{i+1}]   Row {row_idx}: {row}")

            # Extract VMD list from partitions for explicit prompting
            # Try VMD first, then VMD_HEADER as fallback
            source_vmd_raw = source_partition_schema.get('Table1.VMD', [])
            if not source_vmd_raw:
                source_vmd_raw = source_partition_schema.get('Table1.VMD_HEADER', [])
            target_vmd_raw = target_partition_schema.get('Table2.VMD', [])
            if not target_vmd_raw:
                target_vmd_raw = target_partition_schema.get('Table2.VMD_HEADER', [])
            
            # Extract VMD using same logic as HMD (combining parent.child)
            source_vmd_list = extract_vmd_from_raw(source_vmd_raw)
            target_vmd_list = extract_vmd_from_raw(target_vmd_raw)
            
            # FALLBACK: If partition VMD is empty, derive from ORIGINAL table VMD using row indices
            # IMPORTANT: Source and Target have DIFFERENT VMD orders - use original VMD lists, not merged!
            if not source_vmd_list:
                source_start = source_partitions[i]['start_row']
                source_end = source_partitions[i]['end_row']
                # Get VMD names from ORIGINAL source table (not merged schema!)
                source_vmd_list = original_source_vmd[source_start:source_end] if source_start < len(original_source_vmd) else []
                print(f"[DEBUG-PARTITION-{i+1}] Derived source VMD from ORIGINAL source (rows {source_start}-{source_end}): {source_vmd_list}")
            
            if not target_vmd_list:
                target_start = target_partitions[i]['start_row']
                target_end = target_partitions[i]['end_row']
                # Get VMD names from ORIGINAL target table (not merged schema!)
                target_vmd_list = original_target_vmd[target_start:target_end] if target_start < len(original_target_vmd) else []
                print(f"[DEBUG-PARTITION-{i+1}] Derived target VMD from ORIGINAL target (rows {target_start}-{target_end}): {target_vmd_list}")
            
            print(f"[DEBUG-PARTITION-{i+1}] Final source VMD: {source_vmd_list}")
            print(f"[DEBUG-PARTITION-{i+1}] Final target VMD: {target_vmd_list}")

            # Extract HMD columns from partitions
            source_hmd_raw = source_partition_schema.get('Table1.HMD', [])
            target_hmd_raw = target_partition_schema.get('Table2.HMD', [])
            
            # Debug: show raw HMD data structure
            print(f"[DEBUG-PARTITION-{i+1}] Raw source HMD type: {type(source_hmd_raw).__name__}, len: {len(source_hmd_raw) if hasattr(source_hmd_raw, '__len__') else 'N/A'}")
            if source_hmd_raw:
                print(f"[DEBUG-PARTITION-{i+1}] Raw source HMD first item: {source_hmd_raw[0] if isinstance(source_hmd_raw, list) and source_hmd_raw else source_hmd_raw}")
            
            source_hmd_list = extract_hmd_from_raw(source_hmd_raw)
            target_hmd_list = extract_hmd_from_raw(target_hmd_raw)
            print(f"[DEBUG-PARTITION-{i+1}] Extracted source HMD: {source_hmd_list}")
            print(f"[DEBUG-PARTITION-{i+1}] Extracted target HMD: {target_hmd_list}")

            # Construct merge prompt with DICT-BASED output format
            # REPLACED LLM CALL WITH DETERMINISTIC LOGIC
            
            # Helper to get value
            def safe_get_cell(data, r, c):
                try:
                    if r < len(data) and c < len(data[r]):
                        return str(data[r][c])
                    return ""
                except:
                    return ""

            # Helper to check if string is a number (for VMD matching)
            def is_same_row(name1, name2):
                if not name1 or not name2: return False
                return str(name1).strip().lower() == str(name2).strip().lower()

            merged_data_part = {}
            
            # --- PROCESS SOURCE ---
            s_data = source_partition_schema.get('Table1.Data', []) or source_partition_schema.get('Data', [])
            if not s_data and 'data' in source_partitions[i]: 
                 s_data = source_partitions[i]['data']
            
            # Iterate through Source VMD (Rows) available in this partition
            for r_idx, vmd_name in enumerate(source_vmd_list):
                if not vmd_name: continue
                # Use vmd_name as key (paritition-specific)
                row_key = vmd_name
                
                if row_key not in merged_data_part: 
                    merged_data_part[row_key] = {'source': {}, 'target': {}}
                
                # Iterate through Source HMD (Columns)
                for c_idx, hmd_name in enumerate(source_hmd_list):
                    val = safe_get_cell(s_data, r_idx, c_idx)
                    merged_data_part[row_key]['source'][hmd_name] = val

            # --- PROCESS TARGET ---
            t_data = target_partition_schema.get('Table2.Data', []) or target_partition_schema.get('Data', [])
            if not t_data and 'data' in target_partitions[i]:
                t_data = target_partitions[i]['data']

            # Iterate through Target VMD (Rows) available in this partition
            for r_idx, vmd_name in enumerate(target_vmd_list):
                if not vmd_name: continue
                row_key = vmd_name
                
                if row_key not in merged_data_part:
                    merged_data_part[row_key] = {'source': {}, 'target': {}}
                
                # Iterate through Target HMD (Columns)
                for c_idx, hmd_name in enumerate(target_hmd_list):
                     val = safe_get_cell(t_data, r_idx, c_idx)
                     merged_data_part[row_key]['target'][hmd_name] = val
            
            print(f"[PARTITION-MERGE] Deterministic Merge - {len(merged_data_part)} VMD rows processed")
            
            # Structure result exactly as LLM output for compatibility
            merge_result_data = {"Merged_Data": merged_data_part}
            
            # Add to results list
            partition_merge_results.append({
                'partition_id': i,
                'success': True,
                'data': merge_result_data,
                'merge_time': 0.01,
                'input_tokens': 0,
                'output_tokens': 0,
                'cost': 0.0,
                'source_hmd': source_hmd_list,
                'target_hmd': target_hmd_list
            })


#             merge_prompt = f"""{merge_prompt_base}

# CRITICAL: USE DICT FORMAT FOR OUTPUT (with HMD column names as keys, NOT arrays!)

# THIS PARTITION'S DATA:
# - Source Table1 VMD rows: {json.dumps(source_vmd_list)}
# - Source Table1 HMD columns: {json.dumps(source_hmd_list)}
# - Target Table2 VMD rows: {json.dumps(target_vmd_list)}
# - Target Table2 HMD columns: {json.dumps(target_hmd_list)}

# INSTRUCTIONS:
# 1. Output ALL VMD rows from BOTH source AND target partitions (union of both lists)
# 2. If a VMD row exists in target but not source, include it with empty source: {{}}
# 3. If a VMD row exists in source but not target, include it with empty target: {{}}
# 4. Use the EXACT VMD name from the partition as the key
# 5. For "source", create a dict with Table1's HMD column names as keys and data values from Table1.Data
# 6. For "target", create a dict with Table2's HMD column names as keys and data values from Table2.Data

# TABLE1 (Source):
# {json.dumps(source_partition_schema, indent=2)}

# TABLE2 (Target):
# {json.dumps(target_partition_schema, indent=2)}

# REQUIRED OUTPUT FORMAT (DICT-BASED - NOT ARRAYS):
# {{
#   "Merged_Data": {{
#     "{source_vmd_list[0] if source_vmd_list else '<VMD_row_name>'}": {{
#       "source": {{
#         "{source_hmd_list[0] if source_hmd_list else '<HMD_col1>'}": "<value1>",
#         "{source_hmd_list[1] if len(source_hmd_list) > 1 else '<HMD_col2>'}": "<value2>"
#       }},
#       "target": {{
#         "{target_hmd_list[0] if target_hmd_list else '<HMD_col1>'}": "<value1>",
#         "{target_hmd_list[1] if len(target_hmd_list) > 1 else '<HMD_col2>'}": "<value2>"
#       }}
#     }}
#   }}
# }}

# Return ONLY the JSON with actual data values extracted from Table1.Data and Table2.Data."""

#             # Call LLM for merge
#             start_time = time.time()
#             try:
#                 merge_response = get_llm_response(
#                     merge_prompt, merge_llm,
#                     max_tokens=parameters.get('maxTokens'),
#                     temperature=parameters.get('temperature'),
#                     top_p=parameters.get('topP'),
#                     frequency_penalty=parameters.get('frequencyPenalty'),
#                     presence_penalty=parameters.get('presencePenalty')
#                 )

#                 # Parse response
#                 if hasattr(merge_response, 'choices') and merge_response.choices:
#                     raw_response = merge_response.choices[0].message.content.strip()
#                 elif hasattr(merge_response, 'content'):
#                     raw_response = merge_response.content.strip()
#                 else:
#                     raw_response = str(merge_response).strip()

#                 # DEBUG: Log raw LLM response
#                 print(f"\n[DEBUG-PARTITION-{i+1}] === LLM RAW RESPONSE ===")
#                 print(f"[DEBUG-PARTITION-{i+1}] Response length: {len(raw_response)} chars")
#                 print(f"[DEBUG-PARTITION-{i+1}] First 500 chars: {raw_response[:500]}")
                
#                 cleaned_response = clean_llm_json_response(raw_response)
#                 merge_result_data = json.loads(cleaned_response)
                
#                 # DEBUG: Log parsed LLM response structure
#                 print(f"\n[DEBUG-PARTITION-{i+1}] === PARSED LLM RESPONSE ===")
#                 if 'Merged_Data' in merge_result_data:
#                     merged_data = merge_result_data['Merged_Data']
#                     print(f"[DEBUG-PARTITION-{i+1}] Merged_Data type: {type(merged_data).__name__}")
#                     if isinstance(merged_data, dict):
#                         print(f"[DEBUG-PARTITION-{i+1}] Merged_Data keys: {list(merged_data.keys())}")
#                         for vmd_key in list(merged_data.keys())[:3]:  # Show first 3
#                             vmd_data = merged_data[vmd_key]
#                             # Handle both dict format (new) and list format (legacy)
#                             source_val = vmd_data.get('source', {})
#                             target_val = vmd_data.get('target', {})
#                             if isinstance(source_val, dict):
#                                 print(f"[DEBUG-PARTITION-{i+1}]   {vmd_key}: source={dict(list(source_val.items())[:3])}, target={dict(list(target_val.items())[:3])}")
#                             else:
#                                 print(f"[DEBUG-PARTITION-{i+1}]   {vmd_key}: source={source_val[:3] if source_val else []}, target={target_val[:3] if target_val else []}")
#                     elif isinstance(merged_data, list):
#                         print(f"[DEBUG-PARTITION-{i+1}] Merged_Data is a list with {len(merged_data)} items")
#                 else:
#                     print(f"[DEBUG-PARTITION-{i+1}] No Merged_Data key found. Keys: {list(merge_result_data.keys())}")

#                 end_time = time.time()
#                 merge_time = end_time - start_time

#                 # Extract token usage using pricing module (handles Gemini, Claude, OpenAI formats)
#                 from modules.pricing import extract_token_usage, calculate_api_cost
#                 input_tokens, output_tokens = extract_token_usage(merge_response, merge_llm)
#                 partition_cost = calculate_api_cost(merge_llm, input_tokens, output_tokens)

#                 # Extract HMD from partition schemas for smart stacking
#                 source_hmd = extract_hmd_list(source_partition_schema)
#                 target_hmd = extract_hmd_list(target_partition_schema)

#                 partition_merge_results.append({
#                     'partition_id': i,
#                     'success': True,
#                     'data': merge_result_data,
#                     'merge_time': merge_time,
#                     'input_tokens': input_tokens,
#                     'output_tokens': output_tokens,
#                     'cost': partition_cost,
#                     'source_hmd': source_hmd,  # Partition's own source HMD for index mapping
#                     'target_hmd': target_hmd   # Partition's own target HMD for index mapping
#                 })

#                 print(f"\n[PARTITION-MERGE] Partition {i+1} merged in {merge_time:.2f}s (tokens: {input_tokens}+{output_tokens}, cost: ${partition_cost:.6f})")

#             except Exception as e:
#                 print(f"[ERROR] Failed to merge partition {i}: {str(e)}")
#                 partition_merge_results.append({
#                     'partition_id': i,
#                     'success': False,
#                     'error': str(e)
#                 })


        # Stack all partition results into single Merged_Data
        print(f"[PARTITION-MERGE] Stacking {len(partition_merge_results)} partition results")
        stacked_result = stack_partition_results(partition_merge_results, hmd_schema, vmd_schema, match_result)

        # Calculate aggregate metrics for displayMetrics compatibility
        total_merge_time = sum(r.get('merge_time', 0) for r in partition_merge_results if r.get('success'))
        total_input_tokens = sum(r.get('input_tokens', 0) for r in partition_merge_results if r.get('success'))
        total_output_tokens = sum(r.get('output_tokens', 0) for r in partition_merge_results if r.get('success'))
        total_cost = sum(r.get('cost', 0) for r in partition_merge_results if r.get('success'))
        successful_count = sum(1 for r in partition_merge_results if r.get('success'))
        
        # Extract metrics from Phase 1 (match) and Phase 2 (schema merge) if available
        match_metrics = phase_metrics.get('match', {}) if phase_metrics else {}
        schema_merge_metrics = phase_metrics.get('schemaMerge', {}) if phase_metrics else {}
        
        # Phase 1 (Match) metrics
        match_time = match_metrics.get('total_generation_time', 0) or 0
        match_input_tokens = match_metrics.get('input_tokens', 0) or match_metrics.get('input_prompt_tokens', 0) or 0
        match_output_tokens = match_metrics.get('output_tokens', 0) or 0
        match_cost = match_metrics.get('api_call_cost', 0) or 0
        match_llm = match_metrics.get('llm_model', matching_llm)
        
        # Phase 2 (Schema Merge) metrics  
        schema_merge_time = schema_merge_metrics.get('total_generation_time', 0) or 0
        schema_merge_input_tokens = schema_merge_metrics.get('input_tokens', 0) or schema_merge_metrics.get('merge_input_tokens', 0) or 0
        schema_merge_output_tokens = schema_merge_metrics.get('output_tokens', 0) or schema_merge_metrics.get('merge_output_tokens', 0) or 0
        schema_merge_cost = schema_merge_metrics.get('api_call_cost', 0) or 0
        
        # Phase 4 (Partition Merge) metrics
        partition_merge_time = total_merge_time
        partition_input_tokens = total_input_tokens
        partition_output_tokens = total_output_tokens
        partition_cost = total_cost
        
        # Aggregate all phases
        total_time_all_phases = match_time + schema_merge_time + partition_merge_time
        total_input_all_phases = match_input_tokens + schema_merge_input_tokens + partition_input_tokens
        total_output_all_phases = match_output_tokens + schema_merge_output_tokens + partition_output_tokens
        total_cost_all_phases = match_cost + schema_merge_cost + partition_cost
        
        # Calculate tokens per second across all phases
        tokens_per_second = (total_input_all_phases + total_output_all_phases) / total_time_all_phases if total_time_all_phases > 0 else 0
        
        # Extract match counts from match_result (passed from Phase 1)
        hmd_matches = len(match_result.get('HMD_matches', [])) if match_result else 0
        vmd_matches = len(match_result.get('VMD_matches', [])) if match_result else 0
        total_matches = hmd_matches + vmd_matches
        
        print(f"[PARTITION-MERGE] Aggregated metrics: Match={match_time:.2f}s, SchemaMerge={schema_merge_time:.2f}s, PartitionMerge={partition_merge_time:.2f}s, Total={total_time_all_phases:.2f}s")

        return JSONResponse({
            'success': True,
            'data': stacked_result,
            'metrics': {
                # Standard metrics expected by displayMetrics
                'operation_type': 'partition_pipeline',  # Special type for 3-phase display
                'schema_type': 'complex',  # Show HMD/VMD matches section
                'pipeline_description': f'Partition-Based Merge ({successful_count} partitions)',
                'total_generation_time': round(total_time_all_phases, 4),  # All phases combined
                'tokens_per_second': round(tokens_per_second, 1),
                'input_prompt_tokens': total_input_all_phases,
                'input_tokens': total_input_all_phases,
                'output_tokens': total_output_all_phases,
                'api_call_cost': total_cost_all_phases,  # All phases combined
                'llm_model': merge_llm,
                
                # Per-phase LLM info
                'matching_llm_used': match_llm,
                'merge_llm_used': merge_llm,  # For Phase 2 schema merge
                'partition_llm_used': merge_llm,  # For Phase 4 partition merge
                
                # Phase 1 (Match) metrics
                'match_generation_time': round(match_time, 4),
                'match_input_tokens': match_input_tokens,
                'match_output_tokens': match_output_tokens,
                'match_api_cost': match_cost,
                
                # Phase 2 (Schema Merge) metrics - SEPARATE
                'schema_merge_generation_time': round(schema_merge_time, 4),
                'schema_merge_input_tokens': schema_merge_input_tokens,
                'schema_merge_output_tokens': schema_merge_output_tokens,
                'schema_merge_api_cost': schema_merge_cost,
                
                # Phase 4 (Partition Merge) metrics - SEPARATE
                'partition_merge_generation_time': round(partition_merge_time, 4),
                'partition_merge_input_tokens': partition_input_tokens,
                'partition_merge_output_tokens': partition_output_tokens,
                'partition_merge_api_cost': partition_cost,
                
                # Match counts
                'hmd_matches': hmd_matches,
                'vmd_matches': vmd_matches,
                'total_matches': total_matches,
                
                # Partition-specific info
                'total_partitions': len(partition_merge_results),
                'successful_partitions': successful_count,
                'failed_partitions': sum(1 for r in partition_merge_results if not r.get('success'))
            },
            'partition_results': partition_merge_results
        })

    except Exception as e:
        print(f"[ERROR] Failed to merge partitions: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({'success': False, 'error': f'Partition merge error: {str(e)}'})

def extract_vmd_from_raw(vmd_data):
    """Extract flat list of VMD row names from raw VMD data.
    
    Uses same parent.child combining logic as HMD extraction.
    """
    vmd_list = []
    
    if isinstance(vmd_data, dict):
        attr_key = next((k for k in vmd_data.keys() if k.startswith('attribute')), None)
        parent_name = vmd_data.get(attr_key, '') if attr_key else ''
        
        if 'children' in vmd_data and vmd_data['children']:
            for child in vmd_data['children']:
                child_key = next((k for k in child.keys() if 'attribute' in k), None)
                child_name = child.get(child_key, '') if child_key else ''
                if parent_name and child_name:
                    vmd_list.append(f"{parent_name}.{child_name}")
                elif parent_name:
                    vmd_list.append(parent_name)
                elif child_name:
                    vmd_list.append(child_name)
        elif parent_name:
            vmd_list.append(parent_name)
    
    elif isinstance(vmd_data, list):
        for item in vmd_data:
            if isinstance(item, str):
                if item:
                    vmd_list.append(item)
            elif isinstance(item, dict):
                attr_key = next((k for k in item.keys() if k.startswith('attribute')), None)
                parent_name = item.get(attr_key, '') if attr_key else ''
                
                if 'children' in item and item['children']:
                    for child in item['children']:
                        child_key = next((k for k in child.keys() if 'attribute' in k), None)
                        child_name = child.get(child_key, '') if child_key else ''
                        if parent_name and child_name:
                            vmd_list.append(f"{parent_name}.{child_name}")
                        elif parent_name:
                            vmd_list.append(parent_name)
                        elif child_name:
                            vmd_list.append(child_name)
                elif parent_name:
                    vmd_list.append(parent_name)
    
    return vmd_list

def extract_hmd_from_raw(hmd_data):
    """Extract flat list of HMD column names from raw HMD data.
    
    Combines parent and child attributes like 'Bleeding.(n=35)' to match merged schema format.
    """
    hmd_list = []
    
    if isinstance(hmd_data, dict):
        # Single hierarchical entry
        attr_key = next((k for k in hmd_data.keys() if k.startswith('attribute')), None)
        parent_name = hmd_data.get(attr_key, '') if attr_key else ''
        
        if 'children' in hmd_data and hmd_data['children']:
            for child in hmd_data['children']:
                child_key = next((k for k in child.keys() if 'attribute' in k), None)
                child_name = child.get(child_key, '') if child_key else ''
                # Combine parent.child
                if parent_name and child_name:
                    hmd_list.append(f"{parent_name}.{child_name}")
                elif parent_name:
                    hmd_list.append(parent_name)
                elif child_name:
                    hmd_list.append(child_name)
        elif parent_name:
            hmd_list.append(parent_name)
    
    elif isinstance(hmd_data, list):
        for item in hmd_data:
            if isinstance(item, str):
                if item:  # Skip empty strings
                    hmd_list.append(item)
            elif isinstance(item, dict):
                attr_key = next((k for k in item.keys() if k.startswith('attribute')), None)
                parent_name = item.get(attr_key, '') if attr_key else ''
                
                if 'children' in item and item['children']:
                    for child in item['children']:
                        child_key = next((k for k in child.keys() if 'attribute' in k), None)
                        child_name = child.get(child_key, '') if child_key else ''
                        # Combine parent.child
                        if parent_name and child_name:
                            hmd_list.append(f"{parent_name}.{child_name}")
                        elif parent_name:
                            hmd_list.append(parent_name)
                        elif child_name:
                            hmd_list.append(child_name)
                elif parent_name:
                    hmd_list.append(parent_name)
    
    return hmd_list

def extract_hmd_list(partition_schema):
    """Extract flat list of HMD column names from partition schema."""
    hmd_data = partition_schema.get('HMD', [])
    hmd_list = []
    
    if isinstance(hmd_data, dict):
        # Hierarchical format: {attribute1: "Parent", children: [...]}
        attr_key = next((k for k in hmd_data.keys() if k.startswith('attribute')), None)
        if attr_key:
            hmd_list.append(hmd_data[attr_key])
        if 'children' in hmd_data and isinstance(hmd_data['children'], list):
            for child in hmd_data['children']:
                child_key = next((k for k in child.keys() if 'attribute' in k), None)
                if child_key:
                    hmd_list.append(child[child_key])
    elif isinstance(hmd_data, list):
        for item in hmd_data:
            if isinstance(item, str):
                hmd_list.append(item)
            elif isinstance(item, dict):
                attr_key = next((k for k in item.keys() if k.startswith('attribute')), None)
                if attr_key:
                    hmd_list.append(item[attr_key])
                if 'children' in item and isinstance(item['children'], list):
                    for child in item['children']:
                        child_key = next((k for k in child.keys() if 'attribute' in k), None)
                        if child_key:
                            hmd_list.append(child[child_key])
    
    return hmd_list

def stack_partition_results(partition_results, hmd_schema, vmd_schema, match_result=None):
    """Stack all partition Merged_Data into a single structure using smart HMD mapping.
    
    This function uses each partition's own HMD context to correctly map array indices
    to the merged schema columns, preventing overwrites between partitions.
    
    Args:
        partition_results: List of partition merge results, each containing:
            - data: LLM output with Merged_Data
            - source_hmd: Partition's source table HMD columns
            - target_hmd: Partition's target table HMD columns
        hmd_schema: Merged HMD schema (target column order)
        vmd_schema: Merged VMD schema (target row order)
        match_result: Phase 1 schema mapping (optional)
    """
    print(f"[STACK] Smart stacking partition results for {len(hmd_schema)} HMD cols x {len(vmd_schema)} VMD rows")
    print(f"[STACK] Processing {len(partition_results)} partitions")
    print(f"[STACK] Merged HMD columns: {hmd_schema}")

    # Build HMD name to index mapping for merged schema
    hmd_to_merged_idx = {hmd: i for i, hmd in enumerate(hmd_schema)}
    
    # Initialize the final data structure: {vmd_name: {merged_hmd_idx: {source: val, target: val}}}
    final_data = {}
    for vmd in vmd_schema:
        final_data[vmd] = {}
        for hmd_idx in range(len(hmd_schema)):
            final_data[vmd][hmd_idx] = {"source": "", "target": ""}
    
    # Build VMD mapping from match_result if available
    vmd_mapping = {}
    if match_result and match_result.get('VMD_matches'):
        for match in match_result.get('VMD_matches', []):
            source_vmd = match.get('source', '')
            target_vmd = match.get('target', '')
            if source_vmd and target_vmd:
                vmd_mapping[source_vmd] = target_vmd
                vmd_mapping[target_vmd] = source_vmd
    
    # Build HMD mapping from match_result if available
    hmd_mapping = {}
    if match_result and match_result.get('HMD_matches'):
        for match in match_result.get('HMD_matches', []):
            source_hmd = match.get('source', '')
            target_hmd = match.get('target', '')
            if source_hmd and target_hmd:
                hmd_mapping[source_hmd] = target_hmd
                hmd_mapping[target_hmd] = source_hmd

    print(f"[STACK] VMD mapping: {vmd_mapping}")
    print(f"[STACK] HMD mapping: {hmd_mapping}")

    # Process each partition
    for partition_result in partition_results:
        if not partition_result.get('success'):
            print(f"[STACK] Skipping failed partition {partition_result.get('partition_id')}")
            continue

        partition_id = partition_result.get('partition_id', 0)
        partition_data = partition_result.get('data', {})
        merged_data = partition_data.get('Merged_Data', {})
        source_hmd = partition_result.get('source_hmd', [])
        target_hmd = partition_result.get('target_hmd', [])
        
        print(f"\n[STACK] Partition {partition_id}: source_hmd={source_hmd}, target_hmd={target_hmd}")

        if not isinstance(merged_data, dict):
            print(f"[STACK] Partition {partition_id} has non-dict Merged_Data, skipping")
            continue

        # Process each VMD row from the partition
        for vmd_row, values in merged_data.items():
            if not isinstance(values, dict):
                continue
                
            # Find the corresponding VMD in the merged schema
            merged_vmd = vmd_row
            if vmd_row not in final_data:
                # Try to find via mapping
                if vmd_row in vmd_mapping and vmd_mapping[vmd_row] in final_data:
                    merged_vmd = vmd_mapping[vmd_row]
                else:
                    # Try fuzzy match
                    for schema_vmd in vmd_schema:
                        if vmd_row.strip().lower() == schema_vmd.strip().lower():
                            merged_vmd = schema_vmd
                            break
                        elif vmd_row.strip() in schema_vmd or schema_vmd in vmd_row.strip():
                            merged_vmd = schema_vmd
                            break
            
            if merged_vmd not in final_data:
                print(f"[STACK] VMD '{vmd_row}' not found in merged schema, skipping")
                continue

            source_data = values.get('source', {})
            target_data = values.get('target', {})
            
            # Handle DICT format (new format with HMD column names as keys)
            if isinstance(source_data, dict):
                print(f"[STACK] Processing source as DICT format with {len(source_data)} HMD keys")
                for hmd_col, val in source_data.items():
                    if not val or not str(val).strip():
                        continue
                    
                    # Find the merged schema index for this HMD column
                    merged_idx = None
                    if hmd_col in hmd_to_merged_idx:
                        merged_idx = hmd_to_merged_idx[hmd_col]
                    elif hmd_col in hmd_mapping and hmd_mapping[hmd_col] in hmd_to_merged_idx:
                        merged_idx = hmd_to_merged_idx[hmd_mapping[hmd_col]]
                    else:
                        # Try fuzzy match
                        for merged_hmd, idx in hmd_to_merged_idx.items():
                            if hmd_col.strip().lower() in merged_hmd.lower() or merged_hmd.lower() in hmd_col.strip().lower():
                                merged_idx = idx
                                break
                    
                    if merged_idx is not None and merged_idx < len(hmd_schema):
                        if not final_data[merged_vmd][merged_idx]["source"]:
                            final_data[merged_vmd][merged_idx]["source"] = val
                            print(f"[STACK-SET] source: {merged_vmd}|{hmd_schema[merged_idx]} = '{val}' (hmd_key='{hmd_col}')")
                        else:
                            print(f"[STACK-SKIP] source: {merged_vmd}|{hmd_schema[merged_idx]} already set, skipping '{val}'")
            
            # Handle ARRAY format (legacy format for backward compatibility)
            elif isinstance(source_data, list):
                print(f"[STACK] Processing source as ARRAY format with {len(source_data)} elements")
                for i, val in enumerate(source_data):
                    if not val or not str(val).strip():
                        continue
                    partition_hmd_col = source_hmd[i] if i < len(source_hmd) else None
                    merged_idx = None
                    if partition_hmd_col and partition_hmd_col in hmd_to_merged_idx:
                        merged_idx = hmd_to_merged_idx[partition_hmd_col]
                    elif partition_hmd_col and partition_hmd_col in hmd_mapping and hmd_mapping[partition_hmd_col] in hmd_to_merged_idx:
                        merged_idx = hmd_to_merged_idx[hmd_mapping[partition_hmd_col]]
                    else:
                        merged_idx = i if i < len(hmd_schema) else None
                    
                    if merged_idx is not None and merged_idx < len(hmd_schema):
                        if not final_data[merged_vmd][merged_idx]["source"]:
                            final_data[merged_vmd][merged_idx]["source"] = val
                            print(f"[STACK-SET] source: {merged_vmd}|{hmd_schema[merged_idx]} = '{val}' (array idx {i})")
            
            # Handle DICT format for target
            if isinstance(target_data, dict):
                print(f"[STACK] Processing target as DICT format with {len(target_data)} HMD keys")
                for hmd_col, val in target_data.items():
                    if not val or not str(val).strip():
                        continue
                    
                    merged_idx = None
                    if hmd_col in hmd_to_merged_idx:
                        merged_idx = hmd_to_merged_idx[hmd_col]
                    elif hmd_col in hmd_mapping and hmd_mapping[hmd_col] in hmd_to_merged_idx:
                        merged_idx = hmd_to_merged_idx[hmd_mapping[hmd_col]]
                    else:
                        for merged_hmd, idx in hmd_to_merged_idx.items():
                            if hmd_col.strip().lower() in merged_hmd.lower() or merged_hmd.lower() in hmd_col.strip().lower():
                                merged_idx = idx
                                break
                    
                    if merged_idx is not None and merged_idx < len(hmd_schema):
                        if not final_data[merged_vmd][merged_idx]["target"]:
                            final_data[merged_vmd][merged_idx]["target"] = val
                            print(f"[STACK-SET] target: {merged_vmd}|{hmd_schema[merged_idx]} = '{val}' (hmd_key='{hmd_col}')")
                        else:
                            print(f"[STACK-SKIP] target: {merged_vmd}|{hmd_schema[merged_idx]} already set, skipping '{val}'")
            
            # Handle ARRAY format for target (legacy)
            elif isinstance(target_data, list):
                print(f"[STACK] Processing target as ARRAY format with {len(target_data)} elements")
                for i, val in enumerate(target_data):
                    if not val or not str(val).strip():
                        continue
                    partition_hmd_col = target_hmd[i] if i < len(target_hmd) else None
                    merged_idx = None
                    if partition_hmd_col and partition_hmd_col in hmd_to_merged_idx:
                        merged_idx = hmd_to_merged_idx[partition_hmd_col]
                    elif partition_hmd_col and partition_hmd_col in hmd_mapping and hmd_mapping[partition_hmd_col] in hmd_to_merged_idx:
                        merged_idx = hmd_to_merged_idx[hmd_mapping[partition_hmd_col]]
                    else:
                        merged_idx = i if i < len(hmd_schema) else None
                    
                    if merged_idx is not None and merged_idx < len(hmd_schema):
                        if not final_data[merged_vmd][merged_idx]["target"]:
                            final_data[merged_vmd][merged_idx]["target"] = val
                            print(f"[STACK-SET] target: {merged_vmd}|{hmd_schema[merged_idx]} = '{val}' (array idx {i})")

    # Convert to UI format
    stacked_merged_data = []
    for hmd_idx, hmd_col in enumerate(hmd_schema):
        vmd_data_list = []
        for vmd_row in vmd_schema:
            cell_data = final_data.get(vmd_row, {}).get(hmd_idx, {"source": "", "target": ""})
            vmd_data_list.append({
                vmd_row: {
                    "source1": cell_data["source"],
                    "source2": cell_data["target"]
                }
            })
        stacked_merged_data.append({
            hmd_col: {
                "VMD_data": vmd_data_list
            }
        })
    
    result = {
        "HMD_Merged_Schema": hmd_schema,
        "VMD_Merged_Schema": vmd_schema,
        "Merged_Data": stacked_merged_data,
        "stacked_from_partitions": len([r for r in partition_results if r.get('success')])
    }
    
    # DEBUG: Log final stacked output structure
    print(f"\n{'='*80}")
    print(f"[STACK-FINAL] === FINAL STACKED OUTPUT ===")
    print(f"{'='*80}")
    print(f"[STACK-FINAL] HMD_Merged_Schema: {hmd_schema}")
    print(f"[STACK-FINAL] VMD_Merged_Schema: {vmd_schema}")
    print(f"[STACK-FINAL] Merged_Data has {len(stacked_merged_data)} HMD entries")
    
    # Show sample of each HMD column's data
    for hmd_entry in stacked_merged_data[:5]:
        for hmd_col, hmd_data in hmd_entry.items():
            vmd_data_list = hmd_data.get('VMD_data', [])
            print(f"\n[STACK-FINAL] HMD '{hmd_col}':")
            for vmd_entry in vmd_data_list:
                for vmd_row, cell_data in vmd_entry.items():
                    s1 = cell_data.get('source1', '')
                    s2 = cell_data.get('source2', '')
                    if s1 or s2:
                        print(f"[STACK-FINAL]   {vmd_row}: t1='{s1}' t2='{s2}'")
    
    print(f"[STACK] Smart stacking complete: {len(stacked_merged_data)} HMD columns")
    return result


@app.post("/fuze/process")
async def process_schemas(request: Request, username: str = Depends(verify_credentials)):
    try:
        data = await request.json()
        source_schema = data.get('sourceSchema', '')
        target_schema = data.get('targetSchema', '')
        schema_type = data.get('schemaType', '')
        processing_type = data.get('processingType', '')
        operation_type = data.get('operationType', '')
        llm_model = data.get('llmModel', 'llama-3.1-8b-instant')
        parameters = data.get('parameters', {})
        use_merge_multi_step = data.get('useMergeMultiStep', False)

        flexible_config = data.get('flexibleConfig', {})
        match_operation = flexible_config.get('matchOperation', 'baseline')
        matching_method = flexible_config.get('schemaMatchingType', 'json_default')
        merge_method = flexible_config.get('mergeMethod', matching_method)
        matching_llm = flexible_config.get('matchingLLM', llm_model)
        merge_llm = flexible_config.get('mergeLLM', matching_llm)
        merge_value_strategy = flexible_config.get('mergeValueStrategy', 'delimited')
        user_api_keys = data.get('apiKeys', {})
        
        # Human-in-the-Loop (HITL) parameters
        match_only = data.get('matchOnly', False)  # If True, run only match step and return for user approval
        pre_approved_match_result = data.get('preApprovedMatchResult', None)  # User-approved/edited match results

        print(f"[DEBUG] Process endpoint called")
        print(f"[DEBUG] merge_method received: '{merge_method}' (type: {type(merge_method).__name__})")
        print(f"[DEBUG] operation_type: '{operation_type}'")
        print(f"[HITL] matchOnly: {match_only}, preApprovedMatchResult provided: {pre_approved_match_result is not None}")

        if not all([source_schema, target_schema, schema_type, processing_type, operation_type]):
            return JSONResponse({'success': False, 'error': 'All fields are required'})

        if not process_with_llm_enhanced:
            return JSONResponse({'success': False, 'error': 'Processing function not available'})

        # Check if partition method is selected - special handling required
        if merge_method in ['table_partition_horizontal', 'table_partition_vertical'] and operation_type == 'instance_merge':
            print(f"[PARTITION] Partition-based instance merge detected")
            print(f"[PARTITION] Step 1: Running schema merge operation (match + merge) on full tables")

            # Step 1: Run schema merge (automatically runs match internally, then merge)
            schema_merge_response = process_with_llm_enhanced(source_schema, target_schema, schema_type, processing_type, 'merge', merge_llm,
                                             max_tokens=parameters.get('maxTokens'),
                                             temperature=parameters.get('temperature'),
                                             top_p=parameters.get('topP'),
                                             frequency_penalty=parameters.get('frequencyPenalty'),
                                             presence_penalty=parameters.get('presencePenalty'),
                                             use_merge_multi_step=use_merge_multi_step,
                                             match_operation=match_operation,
                                             matching_method=matching_method,
                                             merge_method='json_default',  # Use JSON default for schema merge
                                             matching_llm=matching_llm,
                                             merge_llm=merge_llm,
                                             user_api_keys=user_api_keys,
                                             merge_value_strategy=merge_value_strategy)

            if not schema_merge_response.get('success'):
                return JSONResponse({'success': False, 'error': f"Schema merge operation failed: {schema_merge_response.get('error')}"})

            merged_schema = schema_merge_response.get('data')
            match_result_data = schema_merge_response.get('match_result')  # Get match results from schema merge response
            print(f"[PARTITION] Step 1 completed: Schema merge result obtained")
            print(f"[PARTITION] Merged schema keys: {list(merged_schema.keys()) if isinstance(merged_schema, dict) else 'Not a dict'}")

            # Step 2: Create partitions
            print(f"[PARTITION] Step 2: Creating partitions")
            import json
            source_data = json.loads(source_schema) if isinstance(source_schema, str) else source_schema
            target_data = json.loads(target_schema) if isinstance(target_schema, str) else target_schema

            source_data_rows = get_data_row_count_from_schema(source_data) if get_data_row_count_from_schema else 0
            target_data_rows = get_data_row_count_from_schema(target_data) if get_data_row_count_from_schema else 0

            partition_stats = calculate_partition_stats(source_data_rows, target_data_rows) if calculate_partition_stats else None

            if not partition_stats:
                return JSONResponse({'success': False, 'error': 'Failed to calculate partition stats'})

            partitioned_data = create_partitioned_schemas(source_data, target_data, partition_stats) if create_partitioned_schemas else None

            if not partitioned_data:
                return JSONResponse({'success': False, 'error': 'Failed to create partitioned schemas'})

            source_partitions = partitioned_data.get('source_partitions', [])
            target_partitions = partitioned_data.get('target_partitions', [])
            print(f"[PARTITION] Step 2 completed: Created {len(source_partitions)} partition pairs")

            # Step 3: Run instance merge on each partition pair using the merged schema
            print(f"[PARTITION] Step 3: Running instance merge on each partition pair using merged schema")
            partition_merge_results = []

            # Import necessary functions
            from modules.llm_client import get_llm_response
            from modules.processors import clean_llm_json_response
            import time
            import os

            # Load the custom instance-level merge prompt
            prompt_file_path = os.path.join(os.path.dirname(__file__), 'instancelevelMergeOperatorv2.txt')
            try:
                with open(prompt_file_path, 'r', encoding='utf-8') as f:
                    merge_prompt_base = f.read()
                print(f"[PARTITION] Loaded custom merge prompt from: {prompt_file_path}")
            except Exception as e:
                print(f"[ERROR] Failed to load instance merge prompt: {e}")
                return JSONResponse({'success': False, 'error': f'Failed to load merge prompt: {str(e)}'})

            # Extract only the merged schema arrays from the full schema merge result
            # Handle BOTH old format (Merged_Schema, etc.) and new format (HMD_Merged_Schema, etc.)
            hmd_schema = merged_schema.get('HMD_Merged_Schema', [])
            vmd_schema = merged_schema.get('VMD_Merged_Schema', [])
            
            # Fallback: Try to extract from Merged_Schema if HMD/VMD arrays are empty
            if not hmd_schema and not vmd_schema:
                # Old format might have Merged_Schema as a dict with HMD/VMD keys
                old_merged = merged_schema.get('Merged_Schema', {})
                if isinstance(old_merged, dict):
                    hmd_schema = old_merged.get('HMD_Merged_Schema', []) or old_merged.get('HMD', [])
                    vmd_schema = old_merged.get('VMD_Merged_Schema', []) or old_merged.get('VMD', [])
                elif isinstance(old_merged, list):
                    # If Merged_Schema is a list, it might be the merged attributes
                    hmd_schema = old_merged
            
            # Fallback: Try Merged_Data which might contain the schema info
            if not hmd_schema and not vmd_schema:
                merged_data = merged_schema.get('Merged_Data', [])
                if isinstance(merged_data, list) and merged_data:
                    # Extract unique HMD keys from Merged_Data entries
                    for item in merged_data:
                        if isinstance(item, dict):
                            hmd_schema.extend(list(item.keys()))
                    hmd_schema = list(dict.fromkeys(hmd_schema))  # Remove duplicates while preserving order
            
            actual_merged_schema = {
                "HMD_Merged_Schema": hmd_schema,
                "VMD_Merged_Schema": vmd_schema
            }
            print(f"[PARTITION] Extracted merged schema - HMD items: {len(actual_merged_schema['HMD_Merged_Schema'])}, VMD items: {len(actual_merged_schema['VMD_Merged_Schema'])}")

            # EARLY VALIDATION: Stop if merged schema is empty to avoid wasting API calls
            if not actual_merged_schema['HMD_Merged_Schema'] and not actual_merged_schema['VMD_Merged_Schema']:
                print(f"[PARTITION] ERROR: Merged schema is empty! Available keys in response: {list(merged_schema.keys())}")
                print(f"[PARTITION] STOPPING EARLY to avoid wasting API calls on partition merge")
                return JSONResponse({
                    'success': False, 
                    'error': 'Schema merge succeeded but merged schema is empty. This may indicate an incompatible schema format. Please use regular JSON (Default) merge method instead of Table Partition.',
                    'debug_info': {
                        'available_keys': list(merged_schema.keys()) if isinstance(merged_schema, dict) else 'Not a dict',
                        'sample_data': str(merged_schema)[:500] if merged_schema else 'None'
                    }
                })

            # Debug: Print first few items to verify structure
            if actual_merged_schema['HMD_Merged_Schema']:
                print(f"[PARTITION] Sample HMD items: {actual_merged_schema['HMD_Merged_Schema'][:3]}")
            if actual_merged_schema['VMD_Merged_Schema']:
                print(f"[PARTITION] Sample VMD items: {actual_merged_schema['VMD_Merged_Schema'][:3]}")

            # Initialize custom clients for API keys
            custom_clients = {}
            if user_api_keys and user_api_keys.get('groq'):
                from groq import Groq
                custom_clients['groq'] = Groq(api_key=user_api_keys['groq'])
            if user_api_keys and user_api_keys.get('anthropic'):
                from anthropic import Anthropic
                custom_clients['anthropic'] = Anthropic(api_key=user_api_keys['anthropic'])

            for i in range(len(source_partitions)):
                print(f"[PARTITION] Processing partition pair {i+1}/{len(source_partitions)}")

                source_partition_schema = source_partitions[i]['schema']
                target_partition_schema = target_partitions[i]['schema']

                # Construct merge prompt with clearer data structure
                merge_prompt = f"""{merge_prompt_base}

MERGED SCHEMA (from Schema Merge operation):
{json.dumps(actual_merged_schema, indent=2)}

TABLE1 (Source Partition - rows {source_partitions[i]['start_row']}-{source_partitions[i]['end_row']}):
{json.dumps(source_partition_schema, indent=2)}

TABLE2 (Target Partition - rows {target_partitions[i]['start_row']}-{target_partitions[i]['end_row']}):
{json.dumps(target_partition_schema, indent=2)}

Remember: Extract ACTUAL DATA VALUES from Table1.Data and Table2.Data arrays, NOT the HMD column names.
Return only the JSON in the Merged_Data format specified in the instructions above."""

                # Call LLM for merge
                start_time = time.time()
                try:
                    merge_response = get_llm_response(
                        merge_prompt, merge_llm,
                        max_tokens=parameters.get('maxTokens'),
                        temperature=parameters.get('temperature'),
                        top_p=parameters.get('topP'),
                        frequency_penalty=parameters.get('frequencyPenalty'),
                        presence_penalty=parameters.get('presencePenalty'),
                        custom_clients=custom_clients
                    )

                    # Parse response
                    if hasattr(merge_response, 'choices') and merge_response.choices:
                        raw_response = merge_response.choices[0].message.content.strip()
                    elif hasattr(merge_response, 'content'):
                        raw_response = merge_response.content.strip()
                    else:
                        raw_response = str(merge_response).strip()

                    cleaned_response = clean_llm_json_response(raw_response)
                    merge_result_data = json.loads(cleaned_response)

                    end_time = time.time()
                    merge_time = end_time - start_time

                    partition_merge_results.append({
                        'partition_id': i,
                        'source_rows': f"{source_partitions[i]['start_row']}-{source_partitions[i]['end_row']}",
                        'target_rows': f"{target_partitions[i]['start_row']}-{target_partitions[i]['end_row']}",
                        'success': True,
                        'data': merge_result_data,
                        'merge_time': merge_time
                    })

                    print(f"[PARTITION] Partition {i+1} merge completed in {merge_time:.2f}s")

                except Exception as e:
                    print(f"[ERROR] Failed to merge partition {i}: {str(e)}")
                    partition_merge_results.append({
                        'partition_id': i,
                        'source_rows': f"{source_partitions[i]['start_row']}-{source_partitions[i]['end_row']}",
                        'target_rows': f"{target_partitions[i]['start_row']}-{target_partitions[i]['end_row']}",
                        'success': False,
                        'error': str(e)
                    })

            print(f"[PARTITION] Step 3 completed: All partition pairs processed")

            # Write partition merge results to file for verification
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            partition_merge_output_file = f"partition_merge_results_{timestamp}.txt"

            print(f"[PARTITION] Writing merge results to: {partition_merge_output_file}")

            with open(partition_merge_output_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("PARTITION MERGE RESULTS\n")
                f.write("=" * 80 + "\n\n")

                # Write summary
                successful_partitions = sum(1 for r in partition_merge_results if r.get('success'))
                failed_partitions = len(partition_merge_results) - successful_partitions
                total_merge_time = sum(r.get('merge_time', 0) for r in partition_merge_results if r.get('success'))

                f.write("SUMMARY\n")
                f.write("-" * 80 + "\n")
                f.write(f"Total Partitions: {len(partition_merge_results)}\n")
                f.write(f"Successful: {successful_partitions}\n")
                f.write(f"Failed: {failed_partitions}\n")
                f.write(f"Instance Merge Time: {total_merge_time:.2f}s\n")
                f.write(f"Match Time: {schema_merge_response.get('metrics', {}).get('match_generation_time', 0):.2f}s\n")
                f.write(f"Schema Merge Time: {schema_merge_response.get('metrics', {}).get('merge_generation_time', 0):.2f}s\n")
                f.write(f"Total Pipeline Time: {schema_merge_response.get('metrics', {}).get('total_time', 0) + total_merge_time:.2f}s\n")
                f.write("\n")

                # Write schema merge result (used for all partition merges)
                f.write("MERGED SCHEMA (HMD_Merged_Schema + VMD_Merged_Schema)\n")
                f.write("-" * 80 + "\n")
                f.write(json.dumps(actual_merged_schema, indent=2))
                f.write("\n\n")

                # Write each partition merge result
                f.write("PARTITION MERGE RESULTS\n")
                f.write("-" * 80 + "\n\n")

                for result in partition_merge_results:
                    f.write(f"Partition {result['partition_id']}:\n")
                    f.write(f"  Source Rows: {result['source_rows']}\n")
                    f.write(f"  Target Rows: {result['target_rows']}\n")
                    f.write(f"  Success: {result.get('success', False)}\n")

                    if result.get('success'):
                        f.write(f"  Merge Time: {result.get('merge_time', 0):.2f}s\n")
                        f.write(f"  Merged Data:\n")
                        f.write(json.dumps(result.get('data', {}), indent=4))
                        f.write("\n")
                    else:
                        f.write(f"  Error: {result.get('error', 'Unknown error')}\n")

                    f.write("\n" + "-" * 80 + "\n\n")

                # Add "Rest of Table 1" section if there are remainder rows
                if partition_stats.get('table1_rest', 0) > 0:
                    f.write("Rest of Table 1\n")
                    f.write("{\n")

                    # Extract remainder rows from source table
                    total_partitions = len(source_partitions)
                    if total_partitions > 0:
                        last_partition = source_partitions[-1]
                        # Get the table name from the partition schema keys
                        table_keys = list(last_partition['schema'].keys())
                        if table_keys:
                            table_name = table_keys[0].split('.')[0]

                            # Extract HMD, VMD, and Data from the source table
                            source_hmd = source_data.get(f'{table_name}.HMD', [])
                            source_vmd = source_data.get(f'{table_name}.VMD', [])
                            source_data_rows = source_data.get(f'{table_name}.Data', [])

                            # Get remainder rows (rows not in regular partitions)
                            remainder_start = partition_stats['partitions'] * partition_stats['table1_partition_size']
                            if remainder_start < len(source_data_rows):
                                remainder_vmd = slice_hierarchical_vmd(source_vmd, remainder_start, len(source_data_rows))
                                remainder_data = source_data_rows[remainder_start:]

                                rest_table = {
                                    "Table1.HMD": source_hmd,
                                    "Table1.VMD": remainder_vmd,
                                    "Table1.Data": remainder_data,
                                    "id": "tab-12-rest"
                                }

                                f.write(json.dumps(rest_table, indent=2))
                                f.write("\n")

                    f.write("}\n\n")

                # Add "Rest of Table 2" section if there are remainder rows
                if partition_stats.get('table2_rest', 0) > 0:
                    f.write("Rest of Table 2\n")
                    f.write("{\n")

                    # Extract remainder rows from target table
                    total_partitions = len(target_partitions)
                    if total_partitions > 0:
                        last_partition = target_partitions[-1]
                        # Get the table name from the partition schema keys
                        table_keys = list(last_partition['schema'].keys())
                        if table_keys:
                            table_name = table_keys[0].split('.')[0]

                            # Extract HMD, VMD, and Data from the target table
                            target_hmd = target_data.get(f'{table_name}.HMD', [])
                            target_vmd = target_data.get(f'{table_name}.VMD', [])
                            target_data_rows = target_data.get(f'{table_name}.Data', [])

                            # Get remainder rows (rows not in regular partitions)
                            remainder_start = partition_stats['partitions'] * partition_stats['table2_partition_size']
                            if remainder_start < len(target_data_rows):
                                remainder_vmd = slice_hierarchical_vmd(target_vmd, remainder_start, len(target_data_rows))
                                remainder_data = target_data_rows[remainder_start:]

                                rest_table = {
                                    "Table2.HMD": target_hmd,
                                    "Table2.VMD": remainder_vmd,
                                    "Table2.Data": remainder_data,
                                    "id": "tab-32-rest"
                                }

                                f.write(json.dumps(rest_table, indent=2))
                                f.write("\n")

                    f.write("}\n\n")
                else:
                    # No remainder rows in Table 2
                    f.write("Rest of Table 2\n")
                    f.write(" \n")
                    f.write("--- \n\n")

                # Add "Fully Merged data" section combining all partitions
                f.write("Fully Merged data\n")

                # Combine all partition merge results into one merged data object
                fully_merged_data = {}
                for result in partition_merge_results:
                    if result.get('success') and result.get('data'):
                        merged_data_section = result['data'].get('Merged_Data', {})
                        for vmd_attr, values in merged_data_section.items():
                            if vmd_attr not in fully_merged_data:
                                fully_merged_data[vmd_attr] = values
                            else:
                                # Merge values from multiple partitions
                                # For overlapping attributes, prefer non-empty values
                                source_vals = values.get('source', [])
                                target_vals = values.get('target', [])

                                existing_source = fully_merged_data[vmd_attr].get('source', [])
                                existing_target = fully_merged_data[vmd_attr].get('target', [])

                                # If existing values are mostly empty, replace with new values
                                if source_vals and sum(1 for v in existing_source if v) < sum(1 for v in source_vals if v):
                                    fully_merged_data[vmd_attr]['source'] = source_vals
                                if target_vals and sum(1 for v in existing_target if v) < sum(1 for v in target_vals if v):
                                    fully_merged_data[vmd_attr]['target'] = target_vals

                # Add remainder data to fully merged
                if partition_stats.get('table1_rest', 0) > 0:
                    # Include the HMD, VMD, and Data from Rest sections
                    total_partitions = len(source_partitions)
                    if total_partitions > 0:
                        last_partition = source_partitions[-1]
                        table_keys = list(last_partition['schema'].keys())
                        if table_keys:
                            table_name = table_keys[0].split('.')[0]
                            source_hmd = source_data.get(f'{table_name}.HMD', [])
                            source_vmd = source_data.get(f'{table_name}.VMD', [])
                            source_data_rows = source_data.get(f'{table_name}.Data', [])

                            remainder_start = partition_stats['partitions'] * partition_stats['table1_partition_size']
                            if remainder_start < len(source_data_rows):
                                remainder_vmd = slice_hierarchical_vmd(source_vmd, remainder_start, len(source_data_rows))
                                remainder_data = source_data_rows[remainder_start:]

                                fully_merged_output = {
                                    "Merged_Data": fully_merged_data,
                                    "Table1.HMD": source_hmd,
                                    "Table1.VMD": remainder_vmd,
                                    "Table1.Data": remainder_data,
                                    "id": "tab-12-rest"
                                }

                                f.write(json.dumps(fully_merged_output, indent=2))
                            else:
                                f.write(json.dumps({"Merged_Data": fully_merged_data}, indent=2))
                        else:
                            f.write(json.dumps({"Merged_Data": fully_merged_data}, indent=2))
                else:
                    f.write(json.dumps({"Merged_Data": fully_merged_data}, indent=2))

                f.write("\n\n")

                f.write("=" * 80 + "\n")
                f.write("END OF PARTITION MERGE RESULTS\n")
                f.write("=" * 80 + "\n")

            abs_path = os.path.abspath(partition_merge_output_file)
            print(f"[PARTITION] Merge results written to: {abs_path}")

            # Prepare fully merged data for frontend display (same format as regular instance merge)
            # Convert partition merge format to UI-expected format
            hmd_schema = actual_merged_schema.get('HMD_Merged_Schema', [])
            ui_formatted_merged_data = convert_partition_merge_to_ui_format(fully_merged_data, hmd_schema)
            
            frontend_merged_data = {
                'Merged_Data': fully_merged_data,  # Return RAW structure (Object with source/target arrays) for new frontend logic
                'HMD_Merged_Schema': hmd_schema,
                # Extract VMD keys from actual Merged_Data (using the UI formatted version helper)
                # (LLM-generated VMD_Merged_Schema may have mismatched short/long key formats)
                'VMD_Merged_Schema': extract_vmd_keys_from_merged_data(ui_formatted_merged_data)
            }

            # Apply merge value strategy (delimited/range/average) just like regular instance merge
            from modules.processors import apply_merge_value_strategy
            frontend_merged_data = apply_merge_value_strategy(frontend_merged_data, merge_value_strategy)
            print(f"[PARTITION] Applied merge value strategy: {merge_value_strategy}")

            # Return fully merged data for frontend display
            match_time = schema_merge_response.get('metrics', {}).get('match_generation_time', 0)
            schema_merge_time = schema_merge_response.get('metrics', {}).get('merge_generation_time', 0)
            schema_total_time = schema_merge_response.get('metrics', {}).get('total_time', 0)

            result = {
                'success': True,
                'data': frontend_merged_data,  # Return fully merged data for frontend table display
                'metrics': {
                    'match_time': match_time,
                    'schema_merge_time': schema_merge_time,
                    'instance_merge_time': total_merge_time,
                    'total_time': schema_total_time + total_merge_time,
                    'partition_count': len(source_partitions),
                    'successful_partitions': successful_partitions,
                    'failed_partitions': failed_partitions
                },
                'raw_response': f"Processed {len(partition_merge_results)} partition pairs. Results written to {partition_merge_output_file}",
                'partition_results_file': partition_merge_output_file
            }

        else:
            # Normal processing (non-partition)
            llm_merge_method = merge_method
            if merge_method in ['table_partition_horizontal', 'table_partition_vertical']:
                llm_merge_method = 'json_default'
                print(f"[DEBUG] Partition method detected, using '{llm_merge_method}' for LLM processing")

            # HITL: Handle match-only mode
            # When match_only is True, force operation to 'match' and return results for user approval
            actual_operation_type = operation_type
            if match_only:
                actual_operation_type = 'match'
                print(f"[HITL] Match-only mode: forcing operation_type from '{operation_type}' to 'match'")
            
            # HITL: If pre-approved match result is provided, pass it to processor
            # This allows user-edited match results to be used for merge
            result = process_with_llm_enhanced(source_schema, target_schema, schema_type, processing_type, actual_operation_type, llm_model,
                                             max_tokens=parameters.get('maxTokens'),
                                             temperature=parameters.get('temperature'),
                                             top_p=parameters.get('topP'),
                                             frequency_penalty=parameters.get('frequencyPenalty'),
                                             presence_penalty=parameters.get('presencePenalty'),
                                             use_merge_multi_step=use_merge_multi_step,
                                             match_operation=match_operation,
                                             matching_method=matching_method,
                                             merge_method=llm_merge_method,
                                             matching_llm=matching_llm,
                                             merge_llm=merge_llm,
                                             user_api_keys=user_api_keys,
                                             merge_value_strategy=merge_value_strategy,
                                             pre_approved_match_result=pre_approved_match_result)
            
            # HITL: If match-only mode, add a flag to help the frontend know approval is needed
            if match_only and result.get('success'):
                result['match_only_mode'] = True
                result['pending_merge'] = (operation_type in ['merge', 'instance_merge'])
                print(f"[HITL] Match-only complete. Pending merge: {result['pending_merge']}")

        print(f"[DEBUG] LLM processing completed. result['success'] = {result.get('success', 'KEY_NOT_FOUND')}")

        if result['success']:
            operation_description = f"{schema_type.capitalize()} {processing_type} {operation_type} schema operation completed using {llm_model}"

            store_llm_response_to_mongodb(
                request_data=data,
                response_data=result['data'],
                metrics_data=result['metrics'],
                raw_response=result['raw_response'],
                match_result=result.get('match_result'),
                multi_step_results=result.get('multi_step_results')
            )

            # Calculate partition stats if table partition method is selected
            print(f"[DEBUG] Checking partition condition: merge_method='{merge_method}'")
            partition_stats = None
            if merge_method in ['table_partition_horizontal', 'table_partition_vertical']:
                print(f"[DEBUG] Table partition method detected: {merge_method}")
                try:
                    # Parse source and target schemas to get data row counts
                    import json
                    source_data = json.loads(source_schema) if isinstance(source_schema, str) else source_schema
                    target_data = json.loads(target_schema) if isinstance(target_schema, str) else target_schema

                    print(f"[DEBUG] Source schema keys: {list(source_data.keys()) if isinstance(source_data, dict) else 'Not a dict'}")
                    print(f"[DEBUG] Target schema keys: {list(target_data.keys()) if isinstance(target_data, dict) else 'Not a dict'}")

                    source_data_rows = get_data_row_count_from_schema(source_data) if get_data_row_count_from_schema else 0
                    target_data_rows = get_data_row_count_from_schema(target_data) if get_data_row_count_from_schema else 0

                    print(f"[DEBUG] Source data rows: {source_data_rows}, Target data rows: {target_data_rows}")

                    if calculate_partition_stats:
                        partition_stats = calculate_partition_stats(source_data_rows, target_data_rows)
                        print(f"[DEBUG] Partition stats calculated: {partition_stats}")

                        # Create partitioned schemas and write to file for verification
                        if create_partitioned_schemas:
                            try:
                                print("[DEBUG] Creating partitioned schemas...")
                                partitioned_data = create_partitioned_schemas(source_data, target_data, partition_stats)
                                print(f"[DEBUG] Partitioned data created. Source partitions: {len(partitioned_data.get('source_partitions', []))}, Target partitions: {len(partitioned_data.get('target_partitions', []))}")

                                # Write partition analysis to timestamped text file
                                import datetime
                                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                                partition_output_file = f"partition_analysis_{timestamp}.txt"
                                print(f"[DEBUG] Writing partition analysis to: {partition_output_file}")

                                with open(partition_output_file, 'w', encoding='utf-8') as f:
                                    f.write("=" * 80 + "\n")
                                    f.write("PARTITION ANALYSIS REPORT\n")
                                    f.write("=" * 80 + "\n\n")

                                    # Write partition statistics
                                    f.write("PARTITION STATISTICS\n")
                                    f.write("-" * 80 + "\n")
                                    f.write(f"Number of Partitions: {partition_stats['partitions']}\n")
                                    f.write(f"Source Table Data Rows: {partition_stats['table1_data_rows']}\n")
                                    f.write(f"Source Table Partition Size: {partition_stats['table1_partition_size']}\n")
                                    f.write(f"Source Table Remainder: {partition_stats['table1_rest']}\n")
                                    f.write(f"Target Table Data Rows: {partition_stats['table2_data_rows']}\n")
                                    f.write(f"Target Table Partition Size: {partition_stats['table2_partition_size']}\n")
                                    f.write(f"Target Table Remainder: {partition_stats['table2_rest']}\n")
                                    f.write("\n")

                                    # Write source partitions
                                    f.write("SOURCE TABLE PARTITIONS\n")
                                    f.write("-" * 80 + "\n")
                                    source_partitions = partitioned_data.get('source_partitions', [])
                                    for i, partition in enumerate(source_partitions):
                                        f.write(f"\nPartition {partition['partition_id']}:\n")
                                        f.write(f"  Table Name: {partition['table_name']}\n")
                                        f.write(f"  Row Range: {partition['start_row']}-{partition['end_row']} (total: {partition['row_count']} rows)\n")
                                        f.write(f"  Is Remainder: {partition['is_remainder']}\n")
                                        f.write(f"  Schema Keys: {list(partition['schema'].keys())}\n")

                                        # Show sample data (first 3 rows)
                                        data_key = f"{partition['table_name']}.Data"
                                        if data_key in partition['schema']:
                                            data_rows = partition['schema'][data_key]
                                            f.write(f"  Sample Data (first 3 rows):\n")
                                            for j, row in enumerate(data_rows[:3]):
                                                f.write(f"    Row {partition['start_row'] + j}: {str(row)[:100]}...\n")

                                    f.write("\n")

                                    # Write target partitions
                                    f.write("TARGET TABLE PARTITIONS\n")
                                    f.write("-" * 80 + "\n")
                                    target_partitions = partitioned_data.get('target_partitions', [])
                                    for i, partition in enumerate(target_partitions):
                                        f.write(f"\nPartition {partition['partition_id']}:\n")
                                        f.write(f"  Table Name: {partition['table_name']}\n")
                                        f.write(f"  Row Range: {partition['start_row']}-{partition['end_row']} (total: {partition['row_count']} rows)\n")
                                        f.write(f"  Is Remainder: {partition['is_remainder']}\n")
                                        f.write(f"  Schema Keys: {list(partition['schema'].keys())}\n")

                                        # Show sample data (first 3 rows)
                                        data_key = f"{partition['table_name']}.Data"
                                        if data_key in partition['schema']:
                                            data_rows = partition['schema'][data_key]
                                            f.write(f"  Sample Data (first 3 rows):\n")
                                            for j, row in enumerate(data_rows[:3]):
                                                f.write(f"    Row {partition['start_row'] + j}: {str(row)[:100]}...\n")

                                    f.write("\n")
                                    f.write("=" * 80 + "\n")
                                    f.write("END OF PARTITION ANALYSIS\n")
                                    f.write("=" * 80 + "\n")

                                import os
                                abs_path = os.path.abspath(partition_output_file)
                                print(f"[INFO] Partition analysis written to: {abs_path}")
                                print(f"[INFO] File exists: {os.path.exists(abs_path)}, Size: {os.path.getsize(abs_path) if os.path.exists(abs_path) else 0} bytes")

                            except Exception as e:
                                print(f"[WARNING] Failed to create partitioned schemas or write to file: {e}")
                                import traceback
                                traceback.print_exc()

                except Exception as e:
                    print(f"[WARNING] Failed to calculate partition stats: {e}")
                    partition_stats = None

            response_data = {
                'success': True,
                'operation_description': operation_description,
                'data': result['data'],
                'metrics': result['metrics'],
                'raw_response': result['raw_response'],
                'match_result': result.get('match_result')
            }

            # Add partition stats to response if available
            if partition_stats:
                response_data['partition_stats'] = partition_stats

            return JSONResponse(response_data)
        else:
            return JSONResponse({'success': False, 'error': result['error']})
    except Exception as e:
        return JSONResponse({'success': False, 'error': f'Processing error: {str(e)}'})

@app.get("/fuze/health")
async def health():
    import datetime
    return JSONResponse({
        'status': 'healthy',
        'timestamp': datetime.datetime.now().isoformat(),
        'groq_configured': client is not None,
        'gemini_configured': gemini_client is not None,
        'anthropic_configured': anthropic_client is not None,
        'storage_configured': True,
        'available_models': {
            'groq': [k for k in MODEL_MAP.keys() if k.startswith('llama') or k.startswith('openai/') or k.startswith('qwen/') or k.startswith('deepseek')] if client else [],
            'gemini': [k for k in MODEL_MAP.keys() if k.startswith('gemini')] if gemini_client else [],
            'claude': [k for k in MODEL_MAP.keys() if k.startswith('claude')] if anthropic_client else []
        },
        'storage_info': {
            'storage_dir': STORAGE_DIR,
            'logs_dir': LOGS_DIR,
            'results_dir': RESULTS_DIR,
            'uploads_dir': UPLOADS_DIR,
            'connected': True
        }
    })

# Preloaded pairs configuration
PRELOADED_PAIRS = {
    'aitqa_12': {
        'name': 'AITQA Case 12',
        'description': 'Complex hierarchical tables from AI-TQA dataset',
        'source': 'Preload_Pairs/AITQA_case12/table12.json',
        'target': 'Preload_Pairs/AITQA_case12/table32.json'
    },
    'aitqa_16': {
        'name': 'AITQA Case 16',
        'description': 'Complex hierarchical tables from AI-TQA dataset',
        'source': 'Preload_Pairs/AITQA_case16/table12.json',
        'target': 'Preload_Pairs/AITQA_case16/table32.json'
    },
    'aitqa_17': {
        'name': 'AITQA Case 17',
        'description': 'Complex hierarchical tables from AI-TQA dataset',
        'source': 'Preload_Pairs/AITQA_case17/table12.json',
        'target': 'Preload_Pairs/AITQA_case17/table32.json'
    }
}

@app.get("/fuze/preloaded-pairs")
async def get_preloaded_pairs():
    """List available preloaded table pairs"""
    return JSONResponse({
        'success': True,
        'pairs': [
            {'id': k, 'name': v['name'], 'description': v['description']}
            for k, v in PRELOADED_PAIRS.items()
        ]
    })

@app.get("/fuze/load-pair/{pair_name}")
async def load_pair(pair_name: str):
    """Load a preloaded table pair by name"""
    if pair_name not in PRELOADED_PAIRS:
        return JSONResponse({
            'success': False,
            'error': f'Pair "{pair_name}" not found. Available: {list(PRELOADED_PAIRS.keys())}'
        }, status_code=404)
    
    pair_config = PRELOADED_PAIRS[pair_name]
    
    try:
        from modules.profiler import calculate_schema_profile, format_profile_for_display
        
        # Get the base directory (where main_fast.py is located)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Read source file
        source_path = os.path.join(base_dir, pair_config['source'])
        with open(source_path, 'r', encoding='utf-8') as f:
            source_json_text = f.read()
            source_data = json.loads(source_json_text)
        
        # Read target file
        target_path = os.path.join(base_dir, pair_config['target'])
        with open(target_path, 'r', encoding='utf-8') as f:
            target_json_text = f.read()
            target_data = json.loads(target_json_text)
        
        # Generate HTML preview for source (using same method as /upload endpoint)
        source_result = parse_json_input(source_json_text) if parse_json_input else {'success': True}
        source_html = source_result.get('html', '<p>Data loaded</p>')
        source_profile = None
        try:
            profile = calculate_schema_profile(source_data, source_json_text)
            source_profile = format_profile_for_display(profile)
        except Exception as e:
            print(f"[PRELOAD] Source profile error: {e}")
        
        # Generate HTML preview for target
        target_result = parse_json_input(target_json_text) if parse_json_input else {'success': True}
        target_html = target_result.get('html', '<p>Data loaded</p>')
        target_profile = None
        try:
            profile = calculate_schema_profile(target_data, target_json_text)
            target_profile = format_profile_for_display(profile)
        except Exception as e:
            print(f"[PRELOAD] Target profile error: {e}")
        
        print(f"[PRELOAD] Loaded pair '{pair_name}': {pair_config['source']} + {pair_config['target']}")
        
        return JSONResponse({
            'success': True,
            'pair_name': pair_name,
            'pair_info': pair_config,
            'source': {
                'data': source_data,
                'html': source_html,
                'profile': source_profile
            },
            'target': {
                'data': target_data,
                'html': target_html,
                'profile': target_profile
            }
        })
        
    except FileNotFoundError as e:
        return JSONResponse({
            'success': False,
            'error': f'File not found: {str(e)}'
        }, status_code=404)
    except json.JSONDecodeError as e:
        return JSONResponse({
            'success': False,
            'error': f'Invalid JSON: {str(e)}'
        }, status_code=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            'success': False,
            'error': f'Error loading pair: {str(e)}'
        }, status_code=500)

@app.get("/fuze/logs")
async def get_logs(limit: int = 10):
    import datetime
    try:
        limit = min(limit, 100)
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        log_filename = f"activity_log_{date_str}.json"
        logs = load_from_json_file(log_filename, LOGS_DIR) if load_from_json_file else []

        if logs:
            logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            logs = logs[:limit]
            return JSONResponse({'success': True, 'count': len(logs), 'logs': logs})
        else:
            return JSONResponse({'success': True, 'count': 0, 'logs': []})
    except Exception as e:
        return JSONResponse({'success': False, 'error': f'Logs query error: {str(e)}'})

@app.get("/fuze/results")
async def list_results():
    import datetime
    try:
        files = []
        for filename in os.listdir(RESULTS_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(RESULTS_DIR, filename)
                stat = os.stat(filepath)
                files.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'modified': datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
                })

        files.sort(key=lambda x: x['modified'], reverse=True)
        return JSONResponse({'success': True, 'count': len(files), 'files': files, 'storage_dir': STORAGE_DIR})
    except Exception as e:
        return JSONResponse({'success': False, 'error': f'Storage query error: {str(e)}'})

@app.post("/fuze/test-api-keys")
async def test_api_keys(request: Request):
    from groq import Groq
    from anthropic import Anthropic
    try:
        import google.generativeai as genai
        GEMINI_AVAILABLE_LOCAL = True
    except:
        GEMINI_AVAILABLE_LOCAL = False

    try:
        data = await request.json()
        user_api_keys = data.get('apiKeys', {})
        results = {}

        if user_api_keys.get('groq'):
            try:
                test_groq = Groq(api_key=user_api_keys['groq'])
                test_response = test_groq.chat.completions.create(
                    messages=[{"role": "user", "content": "Hello"}],
                    model="llama3-8b-8192",
                    max_tokens=5
                )
                results['groq'] = {'valid': True, 'message': 'API key is valid'}
            except Exception as e:
                results['groq'] = {'valid': False, 'message': f'Invalid API key: {str(e)}'}

        if user_api_keys.get('anthropic'):
            try:
                test_anthropic = Anthropic(api_key=user_api_keys['anthropic'])
                test_response = test_anthropic.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=5,
                    messages=[{"role": "user", "content": "Hello"}]
                )
                results['anthropic'] = {'valid': True, 'message': 'API key is valid'}
            except Exception as e:
                results['anthropic'] = {'valid': False, 'message': f'Invalid API key: {str(e)}'}

        if user_api_keys.get('gemini') and GEMINI_AVAILABLE_LOCAL:
            try:
                genai.configure(api_key=user_api_keys['gemini'])
                model = genai.GenerativeModel('gemini-pro')
                test_response = model.generate_content("Hello",
                    generation_config=genai.types.GenerationConfig(max_output_tokens=5))
                results['gemini'] = {'valid': True, 'message': 'API key is valid'}
            except Exception as e:
                results['gemini'] = {'valid': False, 'message': f'Invalid API key: {str(e)}'}

        return JSONResponse({'success': True, 'results': results})
    except Exception as e:
        return JSONResponse({'success': False, 'error': f'API key test error: {str(e)}'})

@app.post("/fuze/pipeline-metrics")
async def get_pipeline_metrics(request: Request):
    """Get average performance metrics for a pipeline configuration"""
    try:
        from modules.metrics import get_pipeline_metrics

        data = await request.json()
        match_operator = data.get('matchOperator', '')
        match_method = data.get('matchMethod', '')
        match_llm = data.get('matchLLM', '')
        merge_operator = data.get('mergeOperator')
        merge_method = data.get('mergeMethod')
        merge_llm = data.get('mergeLLM')

        print(f"[METRICS API] Request received: operator={match_operator}, method={match_method}, llm={match_llm}")

        if not all([match_operator, match_method, match_llm]):
            return JSONResponse({
                'success': False,
                'error': 'Match operator, method, and LLM are required'
            })

        metrics = get_pipeline_metrics(
            match_operator=match_operator,
            match_method=match_method,
            match_llm=match_llm,
            merge_operator=merge_operator,
            merge_method=merge_method,
            merge_llm=merge_llm
        )

        print(f"[METRICS API] Response: {metrics}")

        return JSONResponse({
            'success': True,
            'metrics': metrics
        })
    except Exception as e:
        import traceback
        print(f"[METRICS API] Error: {str(e)}")
        print(traceback.format_exc())
        return JSONResponse({
            'success': False,
            'error': f'Metrics calculation error: {str(e)}'
        })



# ============================================================================
# PDF Extraction Endpoint
# ============================================================================
@app.get("/fuze/list-pdf-preloads")
async def list_pdf_preloads(username: str = Depends(verify_credentials)):
    """List available PDF-Schema pairs in the preloads directory."""
    preload_dir = Path(__file__).parent / "pdf_preloads"
    if not preload_dir.exists():
        return JSONResponse(content={"preloads": []})
    
    preloads = []
    for item in preload_dir.iterdir():
        if item.is_dir():
            # Check if it has the required files (fuzzy or exact)
            has_pdf = any(f.suffix.lower() == '.pdf' for f in item.iterdir())
            has_schema = any(f.suffix.lower() == '.json' for f in item.iterdir())
            
            if has_pdf and has_schema:
                preloads.append(item.name)
    
    return JSONResponse(content={"preloads": sorted(preloads)})

@app.post("/fuze/run-pdf-preload")
async def run_pdf_preload(
    request: Request,
    username: str = Depends(verify_credentials)
):
    """Execute extraction for a preloaded local folder."""
    print(f"DEBUG: [run-pdf-preload] Received request from user: {username}")
    data = await request.json()
    folder_name = data.get('folder_name')
    print(f"DEBUG: [run-pdf-preload] Folder: {folder_name}")
    llm_model = data.get('llm_model', 'Qwen2.5:14B')
    tuples_per_partition = data.get('tuples_per_partition', 5)
    
    if not folder_name:
        return JSONResponse(status_code=400, content={"error": "Folder name required"})
        
    preload_dir = Path(__file__).parent / "pdf_preloads" / folder_name
    if not preload_dir.exists() or not preload_dir.is_dir():
        return JSONResponse(status_code=404, content={"error": f"Preload folder '{folder_name}' not found"})
        
    pdf_path = next((f for f in preload_dir.iterdir() if f.suffix.lower() == '.pdf'), None)
    schema_path = next((f for f in preload_dir.iterdir() if f.suffix.lower() == '.json'), None)
    
    if not pdf_path or not schema_path:
        return JSONResponse(status_code=400, content={"error": f"Missing PDF or Schema in '{folder_name}'"})
        
    try:
        with open(schema_path, 'r') as f:
            schema_json = json.load(f)
            
        result = await run_in_threadpool(
            process_single_pdf,
            pdf_path,
            schema_json,
            pdf_path.name,
            llm_model,
            tuples_per_partition
        )
        
        return JSONResponse(content={"results": [result]})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/fuze/extract_pdf")
async def extract_pdf(
    files: List[UploadFile] = File(...),
    schema_files: List[UploadFile] = File(...),
    llm_model: str = Form("Qwen2.5:14B"),
    tuples_per_partition: int = Form(5)
):
    """
    Handle paired PDF + Schema extraction locally using Ollama.
    Expects 1:1 mapping between files and schema_files.
    """
    print(f"DEBUG: [extract_pdf] Received request. PDFs: {len(files)}, Schemas: {len(schema_files)}, Model: {llm_model}")
    # Validate pairing
    if len(files) != len(schema_files):
        return JSONResponse(
            status_code=400,
            content={"error": f"Mismatch: Received {len(files)} PDFs and {len(schema_files)} Schemas. Must be equal."}
        )
        
    if len(files) > 3:
        return JSONResponse({'success': False, 'error': 'Maximum 3 file pairs allowed'}, status_code=400)

    results = []
    
    # Temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        for i, pdf_file in enumerate(files):
            # Check range
            if i >= len(schema_files):
                break
                
            schema_file = schema_files[i]
            
            # Validation
            if not pdf_file.filename.lower().endswith('.pdf'):
                results.append({
                    "filename": pdf_file.filename,
                    "success": False,
                    "error": "Not a PDF file"
                })
                continue
            
            try:
                # Save PDF to disk (needed for pdfplumber)
                # Use safe filename to avoid conflicts in temp dir
                safe_name = "".join(x for x in pdf_file.filename if x.isalnum() or x in "._-")
                pdf_save_path = temp_path / safe_name
                
                with open(pdf_save_path, "wb") as f:
                    content = await pdf_file.read()
                    f.write(content)
                
                # Read Schema content directly
                schema_content = await schema_file.read()
                try:
                    # We pass the bytes/str directly to the processor
                    schema_json = json.loads(schema_content)
                except json.JSONDecodeError:
                    raise ValueError(f"Invalid JSON in schema file: {schema_file.filename}")
                
                # Process
                result = await run_in_threadpool(
                    process_single_pdf,
                    pdf_save_path, 
                    schema_json,
                    pdf_file.filename, 
                    llm_model,
                    tuples_per_partition
                )
                
                results.append(result)
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                results.append({
                    "filename": pdf_file.filename,
                    "success": False,
                    "error": str(e)
                })

    return JSONResponse(content={"results": results})

@app.on_event("startup")
async def startup_event():
    print("[START] Enhanced Schema Fusion App (FastAPI)")
    print("[INFO] All functionality imported from fusion_helpers.py")
    print("[INFO] Access at: http://localhost:8000/fuze/")
    print("[INFO] API docs at: http://localhost:8000/docs")
    print("[INFO] Public URL: http://cancerkg.org/fuze/")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081, reload=False)
