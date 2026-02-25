"""
DOCX and JSON parsing functions for schema extraction
"""
import io
import json
import re
from docx import Document
from docx.table import Table as DocxTable
from typing import List, Dict, Any, Optional
from modules.config import *
from modules.models import *
from modules.html_utils import (
    convert_hmd_vmd_to_html_enhanced,
    flatten_hmd_and_rowheader,
    _flatten_vmd_objects,
    isRowMatched
)
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
            
            # SMART INCREMENT: Only consume data row if it's actually empty (placeholder)
            # If the row has data, it belongs to the first child, so don't consume it
            should_consume_row = True
            if table_data and data_row_index < len(table_data):
                current_row = table_data[data_row_index]
                if isinstance(current_row, list) and any(cell and str(cell).strip() and cell != '-' for cell in current_row):
                    # Row has data - don't consume it, it belongs to first child
                    should_consume_row = False
            
            if should_consume_row:
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

def parse_json_input(json_text):
    """Parse JSON input and convert to display format"""
    try:
        data = json.loads(json_text)

        # Detect PDF extraction results format: {"Table1": {"HMD": ..., "VMD": ...}, ...}
        if isinstance(data, dict) and any(
            isinstance(v, dict) and ('HMD' in v or 'VMD' in v)
            for v in data.values()
        ):
            print("[PARSER] Detected nested PDF extraction format")
            normalized = {}
            for table_name, table_body in data.items():
                if not isinstance(table_body, dict):
                    continue
                
                # Normalize HMD if it's a dict (convert to flat dot notation list)
                hmd = table_body.get('HMD', [])
                if isinstance(hmd, dict):
                    # For HMD dicts, we want to flatten them into list of dot.notated.paths
                    hmd_list = []
                    def flatten_hmd_dict(d, prefix=""):
                        for k, v in d.items():
                            path = f"{prefix}.{k}" if prefix else k
                            if isinstance(v, dict):
                                flatten_hmd_dict(v, path)
                            else:
                                hmd_list.append(path)
                    flatten_hmd_dict(hmd)
                    normalized[f"{table_name}.HMD"] = hmd_list
                else:
                    normalized[f"{table_name}.HMD"] = hmd

                # Normalize VMD if it's a dict (convert to hierarchical list)
                vmd = table_body.get('VMD', [])
                table_data_rows = []
                if isinstance(vmd, dict):
                    # Standard VMD hierarchical list format: [{"text": "Cat", "is_vmd_category": True, "children": [...]}, ...]
                    vmd_list = []
                    for category, fields in vmd.items():
                        if isinstance(fields, dict):
                            vmd_list.append({
                                "is_vmd_category": True,
                                "text": category,
                                "children": list(fields.keys())
                            })
                            # Extract data values for each field in this category
                            for field_name, value in fields.items():
                                table_data_rows.append([str(value) if value is not None else "--"])
                        else:
                            vmd_list.append(category)
                            table_data_rows.append([str(fields) if fields is not None else "--"])
                    
                    normalized[f"{table_name}.VMD"] = vmd_list
                    # Add extracted Data values
                    if table_data_rows:
                        normalized[f"{table_name}.Data"] = table_data_rows
                else:
                    normalized[f"{table_name}.VMD"] = vmd
            
            return {
                "success": True,
                "data": normalized,
                "html": convert_hmd_vmd_to_html_enhanced(normalized)
            }

        # Original flat format support: {"Table1.HMD": [...], "Table1.VMD": [...]}
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

        # Simple JSON handling (lists, etc.)
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

        simple = {"Table1.HMD": [], "Table1.VMD": []}
        # simple = {"SimpleTable.HMD": [], "SimpleTable.VMD": []}
        return {"success": True, "data": simple, "html": convert_hmd_vmd_to_html_enhanced(simple)}

    except Exception as e:
        return {"success": False, "error": f"JSON parsing error: {str(e)}"}


def clean_llm_json_response(response):
    """Clean and extract JSON from LLM response with enhanced malformed JSON handling.
    
    This function handles common LLM response issues including:
    - Multiple JSON objects in response (takes the first complete one)
    - Extra text before/after JSON
    - Markdown code blocks
    - Trailing commas and other malformations
    """
    response = response.strip()

    # Remove markdown code blocks
    if '`json' in response:
        start = response.find('`json') + 5
        end = response.find('`', start)
        if end > start:
            response = response[start:end].strip()
    elif '`' in response:
        start = response.find('`') + 3
        end = response.find('`', start)
        if end > start:
            response = response[start:end].strip()

    # Find the first JSON object by balancing braces
    json_start = response.find('{')
    
    if json_start < 0:
        return '{"HMD_matches": [], "VMD_matches": []}'
    
    # Use brace balancing to find the end of the first complete JSON object
    brace_count = 0
    in_string = False
    escape_next = False
    json_end = -1
    
    for i, char in enumerate(response[json_start:], start=json_start):
        if escape_next:
            escape_next = False
            continue
            
        if char == '\\' and in_string:
            escape_next = True
            continue
            
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
            
        if in_string:
            continue
            
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                json_end = i + 1
                break
    
    if json_end > json_start:
        json_content = response[json_start:json_end]

        # Fix common JSON malformation issues
        json_content = json_content.replace('}\n  ]', '}]')  # Fix array ending
        json_content = json_content.replace('}\n]', '}]')    # Fix array ending
        json_content = json_content.replace(',\n}', '\n}')   # Fix trailing comma
        json_content = json_content.replace(',}', '}')       # Fix trailing comma
        json_content = json_content.replace(',]', ']')       # Fix trailing comma in array
        
        # Try to parse and validate the JSON
        try:
            import json
            parsed = json.loads(json_content)
            return json_content
        except json.JSONDecodeError as e:
            print(f"[DEBUG] JSON validation failed after brace balancing: {e}")
            # Fall back to trying to fix more issues
            
            # Try to find and fix truncated arrays
            json_content = _fix_truncated_json(json_content)
            
            try:
                json.loads(json_content)
                return json_content
            except json.JSONDecodeError:
                pass
    
    # Fallback: use rfind but warn about potential issues
    json_end_fallback = response.rfind('}') + 1
    if json_start >= 0 and json_end_fallback > json_start:
        json_content = response[json_start:json_end_fallback]
        
        # Fix common JSON malformation issues
        json_content = json_content.replace('}\n  ]', '}]')
        json_content = json_content.replace('}\n]', '}]')
        json_content = json_content.replace(',\n}', '\n}')
        json_content = json_content.replace(',}', '}')
        json_content = json_content.replace(',]', ']')
        
        return json_content

    return '{"HMD_matches": [], "VMD_matches": []}'


def _fix_truncated_json(json_content):
    """Attempt to fix truncated or malformed JSON by closing unclosed brackets/braces."""
    import re
    
    # Count unclosed braces and brackets
    open_braces = json_content.count('{') - json_content.count('}')
    open_brackets = json_content.count('[') - json_content.count(']')
    
    # Remove any incomplete key-value pairs at the end (e.g., "key": or "key":  ")
    # Remove trailing incomplete strings
    json_content = re.sub(r',\s*"[^"]*":\s*"?[^"]*$', '', json_content)
    json_content = re.sub(r',\s*"[^"]*":\s*$', '', json_content)
    
    # Recount after cleanup
    open_braces = json_content.count('{') - json_content.count('}')
    open_brackets = json_content.count('[') - json_content.count(']')
    
    # Close any unclosed brackets first, then braces
    json_content = json_content.rstrip()
    if json_content.endswith(','):
        json_content = json_content[:-1]
    
    json_content += ']' * open_brackets
    json_content += '}' * open_braces
    
    return json_content

