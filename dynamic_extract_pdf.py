#!/usr/bin/env python3
"""
Dynamic VMD Extraction from PDF Files

Two-phase extraction approach:
  Phase 1: LLM identifies schema (HMD + VMD) based on paper content
  Phase 2: LLM extracts data in chunks using the dynamic schema

Usage:
    # Single PDF file
    python3 dynamic_extract_pdf.py --input paper.pdf --output-dir ./extractions
    
    # Directory of PDFs
    python3 dynamic_extract_pdf.py --input ./pdfs/ --output-dir ./extractions --limit 5
"""

import argparse
import json
import math
import time
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import ollama

# PDF parsing
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

# Optional: SSH tunnel for remote MongoDB
try:
    from sshtunnel import SSHTunnelForwarder
    HAS_SSH_TUNNEL = True
except ImportError:
    HAS_SSH_TUNNEL = False

try:
    from pymongo import MongoClient
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False

from urllib.parse import urlparse, parse_qs

# =============================================================================
# MONGODB CONNECTION
# =============================================================================

def connect_to_mongodb(mongo_uri: str):
    """Connect to MongoDB, handling SSH tunnel if specified in URI."""
    if not HAS_PYMONGO:
        raise RuntimeError("pymongo not installed")
    
    # Parse URI for SSH tunnel info (3T Studio format)
    parsed = urlparse(mongo_uri)
    params = parse_qs(parsed.query)
    
    ssh_enabled = params.get("3t.ssh", ["false"])[0].lower() == "true"
    
    if ssh_enabled and HAS_SSH_TUNNEL:
        ssh_host = params.get("3t.sshAddress", [""])[0]
        ssh_port = int(params.get("3t.sshPort", ["22"])[0])
        ssh_user = params.get("3t.sshUser", [""])[0]
        ssh_password = params.get("3t.sshPassword", [""])[0]
        
        mongo_host = parsed.hostname
        mongo_port = parsed.port or 27017
        
        print(f"Setting up SSH tunnel to {ssh_host}...")
        
        tunnel = SSHTunnelForwarder(
            (ssh_host, ssh_port),
            ssh_username=ssh_user,
            ssh_password=ssh_password,
            remote_bind_address=(mongo_host, mongo_port),
            local_bind_address=('127.0.0.1', 27019)  # Use different port than MongoDB version
        )
        tunnel.start()
        
        client = MongoClient('127.0.0.1', 27019)
        return client, tunnel
    else:
        client = MongoClient(mongo_uri)
        return client, None

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
SCHEMA_PROMPT_FILE = SCRIPT_DIR / "dynamic_schema_prompt.txt"
DATA_PROMPT_FILE = SCRIPT_DIR / "dynamic_data_prompt.txt"

import os
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_AUTH = os.getenv("OLLAMA_AUTH")
DEFAULT_MODEL = "Qwen2.5:14B"
CHUNK_SIZE = 5  # Variables per extraction chunk

# =============================================================================
# OLLAMA API
# =============================================================================

def call_ollama(prompt: str, model: str, base_url: str = None, timeout: int = 300) -> str:
    """Call Ollama via requests to support auth headers."""
    import requests
    
    url = base_url or OLLAMA_URL
    headers = {'Content-Type': 'application/json'}
    
    if OLLAMA_AUTH:
        if not (OLLAMA_AUTH.startswith("Basic ") or OLLAMA_AUTH.startswith("Bearer ")):
            headers['Authorization'] = f"Bearer {OLLAMA_AUTH}"
        else:
            headers['Authorization'] = OLLAMA_AUTH
            
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_ctx": 16000
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json().get('response', '')
    except Exception as e:
        print(f"    Error calling Ollama: {e}")
        return ""


def parse_json_response(response: str) -> dict:
    """Extract JSON from LLM response."""
    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
    except json.JSONDecodeError:
        pass
    return {}

# =============================================================================
# PDF PROCESSING
# =============================================================================

def extract_text_from_pdf(pdf_path: Path, max_length: int = 30000) -> str:
    """Extract text content from PDF file."""
    if not HAS_PDFPLUMBER:
        raise RuntimeError("pdfplumber not installed. Run: pip install pdfplumber")
    
    parts = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                if i == 0:
                    parts.append(f"PAGE 1 (Title/Abstract):\n{text}")
                else:
                    parts.append(f"\nPAGE {i+1}:\n{text}")
    
    full_text = "\n".join(parts)
    return full_text[:max_length]


def extract_tables_from_pdf(pdf_path: Path) -> str:
    """Extract tables from PDF file and format as text."""
    if not HAS_PDFPLUMBER:
        raise RuntimeError("pdfplumber not installed. Run: pip install pdfplumber")
    
    all_tables = []
    table_num = 0
    
    with pdfplumber.open(pdf_path) as pdf:
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
# PHASE 1: SCHEMA IDENTIFICATION
# =============================================================================

def phase1_identify_schema(
    tables_text: str, 
    body_text: str, 
    model: str,
    base_url: str
) -> Tuple[List[str], List[Dict]]:
    """
    Phase 1: Identify HMD (columns) and VMD (rows) from the paper.
    Returns: (hmd_list, vmd_categories)
    """
    if not SCHEMA_PROMPT_FILE.exists():
        print(f"    Error: {SCHEMA_PROMPT_FILE} not found")
        return [], []
    
    prompt_template = SCHEMA_PROMPT_FILE.read_text()
    prompt = prompt_template.format(tables=tables_text, text=body_text)
    
    print(f"      Prompt size: {len(prompt):,} chars")
    
    max_retries = 3
    
    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            print(f"      Retry {attempt}/{max_retries}...")
            
        response = call_ollama(prompt, model, base_url)
        
        if not response:
            print("      Error: Empty response from LLM")
            continue
        
        if attempt == 1:
            print(f"      Response size: {len(response):,} chars")
        
        schema = parse_json_response(response)
        
        if not schema:
            print(f"      Error: Could not parse JSON from response")
            print(f"      Response preview: {response[:500]}...")
            continue
        
        hmd_categories = schema.get("HMD_Categories", [])
        vmd_categories = schema.get("VMD_Categories", [])
        
        if not hmd_categories:
            print(f"      Warning: No HMD_Categories found in schema")
            print(f"      Full schema: {json.dumps(schema, indent=2)}")
        
        if not vmd_categories:
            print(f"      Warning: No VMD_Categories found in schema")
            if hmd_categories:
                 print(f"      Full schema: {json.dumps(schema, indent=2)}")
        
        if hmd_categories and vmd_categories:
            return hmd_categories, vmd_categories
            
    return [], []

# =============================================================================
# PHASE 2: CHUNKED DATA EXTRACTION
# =============================================================================

def flatten_vmd_to_rows(vmd_categories: List[Dict]) -> List[str]:
    """Flatten VMD categories into a flat list of variable names."""
    rows = []
    for cat in vmd_categories:
        for var in cat.get("variables", []):
            rows.append(f"{cat['category']} > {var}")
    return rows


def build_final_hmd_structure(hmd_categories: List[Dict]) -> List[Dict]:
    """Convert HMD_Categories to the nested Table1.HMD format with parent-child structure."""
    hmd = []
    for idx, cat in enumerate(hmd_categories, 1):
        group_obj = {
            f"attribute{idx}": cat["group"],
            "children": []
        }
        # Use "children" key from new schema format
        for i, child in enumerate(cat.get("children", []), 1):
            group_obj["children"].append({
                f"child_level1.attribute{i}": child
            })
        hmd.append(group_obj)
    return hmd


def flatten_hmd_to_columns(hmd_categories: List[Dict]) -> List[str]:
    """Flatten HMD categories into column paths for data extraction.
    
    Returns list like:
    - "Low-risk pT1 > Baseline" (if children exist)
    - "P-Value" (if no children)
    """
    columns = []
    for cat in hmd_categories:
        group = cat["group"]
        children = cat.get("children", [])
        
        if children:
            # Expand each child as a separate column
            for child in children:
                columns.append(f"{group} > {child}")
        else:
            # No children - parent is the column itself
            columns.append(group)
    
    return columns


def build_final_vmd_structure(vmd_categories: List[Dict]) -> List[Dict]:
    """Convert VMD_Categories to the nested Table1.VMD format."""
    vmd = []
    for idx, cat in enumerate(vmd_categories, 1):
        category_obj = {
            f"attribute{idx}": cat["category"],
            "children": []
        }
        for i, var in enumerate(cat.get("variables", []), 1):
            category_obj["children"].append({
                f"child_level1.attribute{i}": var
            })
        vmd.append(category_obj)
    return vmd


def phase2_extract_data(
    tables_text: str,
    body_text: str,
    hmd: List[str],
    all_rows: List[str],
    model: str,
    base_url: str,
    chunk_size: int = 5
) -> List[List[str]]:
    """
    Phase 2: Extract data in chunks using the dynamic schema.
    Returns: Full data matrix (list of lists)
    """
    if not DATA_PROMPT_FILE.exists():
        print(f"    Error: {DATA_PROMPT_FILE} not found")
        return []
    
    prompt_template = DATA_PROMPT_FILE.read_text()
    
    # Use provided chunk_size or default
    print(f"      Processing with {chunk_size} tuples per partition...")
    num_chunks = math.ceil(len(all_rows) / chunk_size)
    full_data = []
    
    for chunk_idx in range(num_chunks):
        start = chunk_idx * chunk_size
        end = min(start + chunk_size, len(all_rows))
        chunk_rows = all_rows[start:end]
        
        print(f"      Chunk {chunk_idx + 1}/{num_chunks} ({len(chunk_rows)} vars)...", end="", flush=True)
        
        prompt = prompt_template.format(
            tables=tables_text,
            text=body_text,
            hmd_json=json.dumps(hmd),
            chunk_rows=json.dumps(chunk_rows, indent=2)
        )
        
        response = call_ollama(prompt, model, base_url)
        result = parse_json_response(response)
        chunk_data = result.get("ChunkData", [])
        
        # Validate and pad
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

# =============================================================================
# MAIN PROCESSING
# =============================================================================

def process_pdf(
    pdf_path: Path,
    model: str,
    base_url: str,
    chunk_size: int = 5
) -> dict:
    """Process a single PDF using two-phase dynamic extraction."""
    
    result = {
        "file": str(pdf_path),
        "filename": pdf_path.name,
        "model": model,
        "success": False,
        "valid": False,
        "elapsed": 0.0,
        "error": None,
        "extracted_data": None,
        "schema_info": None
    }
    
    try:
        start = time.time()
        
        # Extract content from PDF
        tables_text = extract_tables_from_pdf(pdf_path)
        body_text = extract_text_from_pdf(pdf_path)
        
        print(f"    Content: {len(tables_text):,} chars tables, {len(body_text):,} chars body")
        
        # Phase 1: Identify schema
        print("    Phase 1: Identifying schema...")
        hmd_categories, vmd_categories = phase1_identify_schema(tables_text, body_text, model, base_url)
        
        if not hmd_categories or not vmd_categories:
            raise ValueError("Schema identification failed")
        
        # Flatten for data extraction
        hmd_flat = flatten_hmd_to_columns(hmd_categories)
        all_rows = flatten_vmd_to_rows(vmd_categories)
        print(f"      Found {len(hmd_flat)} columns, {len(all_rows)} variables")
        
        result["schema_info"] = {
            "hmd_count": len(hmd_flat),
            "vmd_count": len(all_rows),
            "hmd_groups": [c["group"] for c in hmd_categories],
            "vmd_categories": [c["category"] for c in vmd_categories]
        }
        
        # Phase 2: Extract data
        print("    Phase 2: Extracting data...")
        data_matrix = phase2_extract_data(tables_text, body_text, hmd_flat, all_rows, model, base_url, chunk_size=chunk_size)
        
        # Build final hierarchical output
        final_hmd = build_final_hmd_structure(hmd_categories)
        final_vmd = build_final_vmd_structure(vmd_categories)
        
        final_json = {
            "Table1.HMD": final_hmd,
            "Table1.VMD": final_vmd,
            "Table1.Data": data_matrix
        }
        
        elapsed = time.time() - start
        result["elapsed"] = elapsed
        result["extracted_data"] = final_json
        result["success"] = True
        result["valid"] = len(data_matrix) == len(all_rows)
        
        # Calculate fill rate
        non_empty = sum(1 for row in data_matrix for val in row if val != "--")
        total_cells = len(data_matrix) * len(hmd_flat)
        result["fill_rate"] = (non_empty / total_cells * 100) if total_cells > 0 else 0
        
    except Exception as e:
        result["error"] = str(e)
        import traceback
        traceback.print_exc()
    
    return result

# =============================================================================
# MAIN
# =============================================================================

def main(argv=None):
    parser = argparse.ArgumentParser(description="Dynamic VMD extraction from PDF files")
    
    parser.add_argument("--input", "-i", type=str, required=True,
                        help="Input PDF file or directory of PDFs")
    parser.add_argument("--output-dir", "-o", type=str, default="./pdf_extractions",
                        help="Output directory for JSON results")
    parser.add_argument("--mongo-uri", type=str,
                        help="MongoDB connection URI (with optional SSH tunnel params)")
    parser.add_argument("--database", type=str,
                        help="MongoDB database name (required if using --output-collection)")
    parser.add_argument("--output-collection", type=str,
                        help="Output collection name for results in MongoDB")
    parser.add_argument("--limit", type=int, default=None,
                        help="Maximum PDFs to process (only for directory input)")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL,
                        help="Ollama model to use")
    parser.add_argument("--ollama-url", type=str, default=OLLAMA_URL,
                        help="Ollama API URL")
    parser.add_argument("--tuples-per-partition", type=int, default=5,
                        help="Number of variables to extract per LLM call (partition size)")
    
    args = parser.parse_args(argv)
    
    # Check pdfplumber
    if not HAS_PDFPLUMBER:
        print("ERROR: pdfplumber not installed. Run: pip install pdfplumber")
        sys.exit(1)
    
    # Validate MongoDB args
    if args.output_collection and not args.database:
        parser.error("--database is required when using --output-collection")
    
    # Default MongoDB URI
    if args.output_collection and not args.mongo_uri:
        args.mongo_uri = "mongodb://bl3.cs.fsu.edu:27017/?retryWrites=true&3t.ssh=true&3t.sshAddress=bl2.cs.fsu.edu&3t.sshPort=22&3t.sshUser=ganesh&3t.sshPassword=DBF2023!"
    
    # Determine input files
    input_path = Path(args.input)
    if input_path.is_file():
        pdf_files = [input_path]
    elif input_path.is_dir():
        pdf_files = sorted(input_path.glob("*.pdf"))
        if args.limit:
            pdf_files = pdf_files[:args.limit]
    else:
        print(f"ERROR: Input path does not exist: {input_path}")
        sys.exit(1)
    
    if not pdf_files:
        print(f"ERROR: No PDF files found in {input_path}")
        sys.exit(1)
    
    # Create output directory for JSON files
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # MongoDB connection
    mongo_client = None
    mongo_tunnel = None
    output_collection = None
    
    if args.output_collection:
        if not HAS_PYMONGO:
            print("ERROR: pymongo not installed. Run: pip install pymongo")
            sys.exit(1)
        mongo_client, mongo_tunnel = connect_to_mongodb(args.mongo_uri)
        db = mongo_client[args.database]
        output_collection = db[args.output_collection]
    
    print("=" * 60)
    print("DYNAMIC VMD EXTRACTION (PDF)")
    print("=" * 60)
    print(f"Input: {args.input}")
    print(f"Output Dir: {output_dir}")
    if args.output_collection:
        print(f"MongoDB: {args.database}.{args.output_collection}")
    print(f"Model: {args.model}")
    print(f"Files to process: {len(pdf_files)}")
    print()
    
    # Process PDFs
    results = {"successful": 0, "failed": 0, "total_time": 0}
    
    for idx, pdf_path in enumerate(pdf_files, 1):
        print(f"[{idx}/{len(pdf_files)}] {pdf_path.name}")
        
        result = process_pdf(pdf_path, args.model, args.ollama_url, chunk_size=args.tuples_per_partition)
        
        if result["success"]:
            results["successful"] += 1
            results["total_time"] += result["elapsed"]
            
            status = "✓ Valid" if result["valid"] else "⚠ Partial"
            fill_rate = result.get("fill_rate", 0)
            print(f"  {status} in {result['elapsed']:.1f}s (fill: {fill_rate:.1f}%)")
            
            # Prepare output document
            output_doc = {
                "source_file": str(pdf_path),
                "filename": pdf_path.name,
                "llm_model": result["model"],
                "valid": result["valid"],
                "elapsed_seconds": result["elapsed"],
                "fill_rate": fill_rate,
                "schema_info": result["schema_info"],
                "extracted_data": result["extracted_data"],
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Save to MongoDB
            if output_collection is not None:
                output_collection.insert_one(output_doc.copy())
                print("  → Saved to MongoDB")
            
            # Save result to JSON file
            output_file = output_dir / f"{pdf_path.stem}.json"
            with open(output_file, 'w') as f:
                json.dump(output_doc, f, indent=2)
            print(f"  → Saved to {output_file}")
        else:
            results["failed"] += 1
            print(f"  ✗ Failed: {result['error']}")
        
        print()
    
    # Cleanup MongoDB
    if mongo_tunnel:
        mongo_tunnel.stop()
    if mongo_client:
        mongo_client.close()
    
    # Summary
    print("=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print(f"Successful: {results['successful']}/{len(pdf_files)}")
    print(f"Failed: {results['failed']}/{len(pdf_files)}")
    if results["successful"] > 0:
        avg_time = results["total_time"] / results["successful"]
        print(f"Avg time: {avg_time:.1f}s per document")


if __name__ == "__main__":
    main()

