import sys
import os
import json
import logging

# Redirect stdout/stderr to file for reliable logging
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_log_local.txt")
# logging configuration
logging.basicConfig(
    filename='extraction_debug.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

sys.stdout = open(log_file, "w", encoding="utf-8")
sys.stderr = sys.stdout

# Ensure we can import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Import the processor
try:
    from modules.dynamic_pdf import process_single_pdf
except ImportError:
    # If running from parent dir, try appending inner dir
    sys.path.append(os.path.join(current_dir, "FusionFrontend"))
    from modules.dynamic_pdf import process_single_pdf

# Paths provided by user
# Using example files from pdf_preloads
pdf_path = os.path.join(current_dir, "pdf_preloads", "example_pair_1", "A.pdf")
schema_path = os.path.join(current_dir, "pdf_preloads", "example_pair_1", "schema_small.json")
# Using the model that is default in frontend
model = "Qwen2.5:14B" 

print(f"--- STARTING DEBUG EXTRACTION (LOCAL) ---")
print(f"PDF: {pdf_path}")
print(f"Schema: {schema_path}")
print(f"Model: {model}")

if not os.path.exists(pdf_path):
    print(f"ERROR: PDF not found at {pdf_path}")
    sys.exit(1)
if not os.path.exists(schema_path):
    print(f"ERROR: Schema not found at {schema_path}")
    sys.exit(1)

# Load Schema
with open(schema_path, 'r', encoding='utf-8') as f:
    schema_json = json.load(f)

# Run Extraction
try:
    print("Calling process_single_pdf...")
    result = process_single_pdf(
        pdf_path, 
        schema_json, 
        "A.pdf", 
        model
    )
    
    print("\n\n=== EXTRACTION RESULT ===")
    print(json.dumps(result, indent=2))
    
    # Save to file
    with open("debug_output_local.json", "w", encoding="utf-8") as out:
        json.dump(result, out, indent=2)
    print("\n\nSaved full result to debug_output_local.json")
    
    if result.get("success"):
        extracted_data = result.get("extracted_data", {})
        data_rows = extracted_data.get("Data", [])
        if not data_rows and "Data" not in extracted_data and isinstance(extracted_data, list):
             pass # might be just list
        
        print(f"\nSUCCESS: Extraction complete.")
    else:
        print(f"\nFAILURE: {result.get('error')}")

except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"\nCRITICAL ERROR: {e}")
