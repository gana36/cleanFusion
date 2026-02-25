import sys
import os
import json

# Redirect stdout/stderr to file for reliable logging
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_log_utf8.txt")
sys.stdout = open(log_file, "w", encoding="utf-8")
sys.stderr = sys.stdout

# Manual .env loading since python-dotenv is missing
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    print(f"Loading .env from {env_path}")
    with open(env_path, "r") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                key, value = line.strip().split("=", 1)
                os.environ[key] = value
else:
    print(f"WARNING: .env not found at {env_path}")
    # Try parent directory
    parent_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(parent_env):
        print(f"Loading .env from {parent_env}")
        with open(parent_env, "r") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value

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
# Paths provided by user
pdf_path = r"C:\FSU\Research\task4_html-json\case_reports\data\cro-0010-0021.pdf"
schema_path = r"C:\FSU\Research\task4_html-json\case_reports\data\schema.json"
model = "llama-3.3-70b-versatile"

print(f"--- STARTING DEBUG EXTRACTION ---")
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
    # process_single_pdf(pdf_file, schema_file, filename, model)
    # pdf_file arg requires a path or file-like object. It handles paths.
    result = process_single_pdf(
        pdf_path, 
        schema_json, 
        "cro-0010-0021.pdf", 
        model
    )
    
    print("\n\n=== EXTRACTION RESULT ===")
    print(json.dumps(result, indent=2))
    
    # Save to file
    with open("FusionFrontend/debug_output.json", "w", encoding="utf-8") as out:
        json.dump(result, out, indent=2)
    print("\n\nSaved full result to FusionFrontend/debug_output.json")
    
    if result.get("success"):
        data_len = len(result.get("extracted_data", {}).get("Data", []))
        print(f"\nSUCCESS: Extracted {data_len} rows of data.")
    else:
        print(f"\nFAILURE: {result.get('error')}")

except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"\nCRITICAL ERROR: {e}")
