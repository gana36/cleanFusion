"""
HTML generation and rendering utilities for schema display
"""
from typing import List, Dict, Any, Optional
from modules.config import *


def extract_data_from_nested_vmd(vmd_data, col_count):
    """Extract data values from nested VMD structure preserving order
    
    For nested VMD like:
    {
        "DEMOGRAPHICS": {"Age": "--", "Gender": "Female"},
        "BASELINE": {"ECOG PS": "1"}
    }
    
    Returns: [["--"], ["Female"], ["1"]] - maintaining the hierarchical order
    """
    if not vmd_data or not isinstance(vmd_data, dict):
        return None
    
    data_rows = []
    
    # Process categories in order to match VMD structure
    for category, fields in vmd_data.items():
        if isinstance(fields, dict):
            # Extract values for each field in this category
            for field_name, value in fields.items():
                # Wrap value in a list (one column)
                data_rows.append([str(value) if value is not None else "--"])
        else:
            # Single value (shouldn't happen in your structure)
            data_rows.append([str(fields) if fields is not None else "--"])
    
    print(f"[HTML] extract_data_from_nested_vmd: extracted {len(data_rows)} data rows")
    return data_rows if data_rows else None


def convert_hmd_vmd_to_html_enhanced(data):
    """Enhanced HTML conversion with professional styling matching reference design"""
    print(f"[HTML] convert_hmd_vmd_to_html_enhanced called with keys: {list(data.keys()) if data else 'None'}")
    
    html_parts = []

    tables = {}
    
    # Handle both flat format (Table1.HMD) and nested format (Table1: {HMD: ..., VMD: ...})
    for key, value in data.items():
        if isinstance(value, dict) and ('HMD' in value or 'VMD' in value):
            # Nested format: Table1: {HMD: [...], VMD: [...], ...}
            tables[key] = value
            print(f"[HTML] Found table '{key}' with nested structure")
        elif '.' in key:
            # Flat format: Table1.HMD, Table1.VMD
            table_name, data_type = key.split('.', 1)
            if table_name not in tables:
                tables[table_name] = {}
            tables[table_name][data_type] = value
    
    print(f"[HTML] Parsed {len(tables)} tables: {list(tables.keys())}")
    
    if not tables:
        print("[HTML] WARNING: No tables found in data structure!")
        return ""

    for table_name, table_data in tables.items():
        # Table container with title - using inline styles
        html_parts.append(f'<div style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; margin: 20px 0; overflow-x: auto;">')
        html_parts.append(f'<div style="background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); padding: 15px 20px; border-radius: 8px 8px 0 0; border: 1px solid #90caf9; border-bottom: none;"><h3 style="font-size: 18px; font-weight: 600; color: #1565c0; margin: 0;">{table_name}</h3></div>')
        html_parts.append('<table style="width: 100%; border-collapse: collapse; background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-radius: 0 0 8px 8px; overflow: hidden;">')

        if 'HMD' in table_data and table_data['HMD']:
            html_parts.append('<thead>')
            vmd_label = table_data.get('VMD_HEADER', '')
            header_html = build_enhanced_headers(table_data['HMD'], vmd_label)
            html_parts.extend(header_html)
            html_parts.append('</thead>')

        if 'VMD' in table_data and table_data['VMD']:
            html_parts.append('<tbody>')
            col_count = count_columns_from_hmd_fixed(table_data.get('HMD', []))

            vmd_data = table_data['VMD']
            
            # Save original VMD dict for data extraction
            original_vmd_dict = vmd_data if isinstance(vmd_data, dict) else None
            
            # Convert nested dict VMD to hierarchical list format
            if isinstance(vmd_data, dict):
                print(f"[HTML] Converting nested VMD dict to hierarchical list")
                vmd_list = []
                for category, fields in vmd_data.items():
                    if isinstance(fields, dict):
                        # Create category with children
                        children = list(fields.keys())
                        vmd_list.append({
                            "is_vmd_category": True,
                            "text": category,
                            "children": children
                        })
                    else:
                        # Flat field
                        vmd_list.append(category)
                vmd_data = vmd_list
                print(f"[HTML] Converted to {len(vmd_list)} VMD items")
            elif isinstance(vmd_data, list) and vmd_data and isinstance(vmd_data[0], dict):
                vmd_data = _flatten_vmd_objects(vmd_data)

            # Extract data values: prioritize explicitly provided 'Data' key
            table_data_values = table_data.get('Data')
            if not table_data_values and original_vmd_dict:
                print(f"[HTML] No 'Data' key found, extracting from nested VMD dict")
                table_data_values = extract_data_from_nested_vmd(original_vmd_dict, col_count)
            
            print(f"[HTML] Table: {table_name}, ColCount: {col_count}, DataRows: {len(table_data_values) if table_data_values else 0}")
            if table_data_values and len(table_data_values) > 0:
                print(f"[HTML] Data Sample: {table_data_values[0]}")

            html_parts.append(render_enhanced_vmd_rows(vmd_data, col_count, table_data_values))
            html_parts.append('</tbody>')

        html_parts.append('</table></div>')

    return ''.join(html_parts)

def count_columns_from_hmd_fixed(hmd_data):
    """Fixed column counting that properly handles childless parents"""
    if not hmd_data:
        return 0
    
    count = 0
    for item in hmd_data:
        if isinstance(item, dict) and item.get("is_childless"):
            count += item.get("colspan", 1)
        elif isinstance(item, str):
            count += 1
        else:
            count += 1
    
    return count

def build_preview_headers_with_vmd(hmd_data, vmd_header_label=""):
    """Build preview headers with VMD support"""
    if not hmd_data:
        return []

    hierarchical_items = []
    childless_parents = []

    for item in hmd_data:
        if isinstance(item, dict) and item.get("is_childless"):
            childless_parents.append(item)
        elif isinstance(item, str):
            hierarchical_items.append(item)

    has_hierarchy = any('.' in item for item in hierarchical_items)
    
    if not has_hierarchy:
        headers = ['<tr>']
        safe_label = (vmd_header_label or "").strip()
        
        headers.append(
            f'<th class="hmd-header level-0" '
            f'style="border: 1px solid #333; padding: 4px; background: #2E7D32; '
            f'color: white; text-align: left;">{safe_label}</th>'
        )
        
        for item in hierarchical_items:
            headers.append(
                f'<th class="hmd-header level-0" data-header="{item}" '
                f'style="border: 1px solid #333; padding: 4px; background: #2E7D32; '
                f'color: white; text-align: center;">{item}</th>'
            )
        
        for item in childless_parents:
            colspan = item.get("colspan", 1)
            text = item.get("text", "")
            headers.append(
                f'<th class="hmd-header level-0" data-header="{text}" colspan="{colspan}" '
                f'style="border: 1px solid #333; padding: 4px; background: #2E7D32; '
                f'color: white; text-align: center;">{text}</th>'
            )
        
        headers.append('</tr>')
        return headers

    structure = parse_hmd_structure_correctly(hierarchical_items)
    max_levels = structure['levels']
    
    headers = []
    for level in range(max_levels):
        headers.append('<tr>')
        
        if level == 0:
            safe_label = (vmd_header_label or "").strip()
            headers.append(
                f'<th class="hmd-header level-0" rowspan="{max_levels}" '
                f'style="border: 1px solid #333; padding: 4px; background: #2E7D32; '
                f'color: white; text-align: left;">{safe_label}</th>'
            )
            
            processed = set()
            for item in hierarchical_items:
                if item in processed:
                    continue
                    
                parts = item.split('.')
                current_part = parts[0]
                
                colspan = 1
                j = hierarchical_items.index(item) + 1
                while j < len(hierarchical_items):
                    next_item = hierarchical_items[j]
                    if next_item.split('.')[0] == current_part:
                        processed.add(next_item)
                        colspan += 1
                        j += 1
                    else:
                        break
                
                processed.add(item)
                headers.append(
                    f'<th class="hmd-header level-0" data-header="{current_part}" colspan="{colspan}" '
                    f'style="border: 1px solid #333; padding: 4px; background: #2E7D32; '
                    f'color: white; text-align: center;">{current_part}</th>'
                )
            
            for item in childless_parents:
                text = item.get("text", "")
                headers.append(
                    f'<th class="hmd-header level-0" data-header="{text}" rowspan="{max_levels}" '
                    f'style="border: 1px solid #333; padding: 4px; background: #2E7D32; '
                    f'color: white; text-align: center;">{text}</th>'
                )
        else:
            for item in hierarchical_items:
                parts = item.split('.')
                if level < len(parts):
                    part = parts[level]
                    bg_color = '#4CAF50' if level == 1 else '#81C784'
                    # Use full hierarchical path as data-header for sub-levels
                    full_path = '.'.join(parts[:level+1])
                    headers.append(
                        f'<th class="hmd-header level-{level}" data-header="{full_path}" '
                        f'style="border: 1px solid #333; padding: 4px; background: {bg_color}; '
                        f'color: white; text-align: center;">{part}</th>'
                    )
        
        headers.append('</tr>')
    
    return headers

def parse_hmd_structure_correctly(hmd_data):
    """Parse HMD data into a structure that preserves column alignment"""
    structure = {
        'levels': 0,
        'columns': []
    }
    
    max_levels = max(len(str(item).split('.')) for item in hmd_data)
    structure['levels'] = max_levels
    
    for item in hmd_data:
        parts = str(item).split('.')
        column = {
            'parts': parts,
            'full_path': str(item)
        }
        structure['columns'].append(column)
    
    return structure

def _flatten_vmd_objects(vmd_list):
    """Flatten VMD objects with support for structured hierarchy (user's JSON format)"""
    if not isinstance(vmd_list, list):
        return []
    
    result = []
    
    for vmd_obj in vmd_list:
        if not isinstance(vmd_obj, dict):
            if isinstance(vmd_obj, str) and vmd_obj.strip():
                result.append(vmd_obj.strip())
            continue
        
        # Check if this is already a processed VMD category
        if vmd_obj.get("is_vmd_category"):
            result.append(vmd_obj)
            continue
            
        # Check if this has the new hierarchical structure
        if 'children' not in vmd_obj:
            # Legacy format - extract any string values
            for v in vmd_obj.values():
                if isinstance(v, str) and v.strip():
                    result.append(v.strip())
            continue
            
        # Extract parent name from attributeX
        parent_name = None
        for key, value in vmd_obj.items():
            if key.startswith('attribute') and isinstance(value, str) and value.strip():
                parent_name = value.strip()
                break
        
        if not parent_name:
            continue  # Skip if no parent name found
            
        # Extract children
        children_array = vmd_obj.get('children', [])
        if not isinstance(children_array, list):
            # No children, treat as flat
            result.append(parent_name)
            continue
            
        # Process children to extract child names
        child_names = []
        for child_dict in children_array:
            if isinstance(child_dict, dict):
                # Extract all child_level1.attributeX values
                child_attrs = []
                for k, v in child_dict.items():
                    if k.startswith('child_level1.') and isinstance(v, str) and v.strip():
                        child_attrs.append((k, v.strip()))
                
                # Sort and add to child names
                child_attrs.sort()
                for _, name in child_attrs:
                    child_names.append(name)
        
        # Create VMD category object
        if child_names:
            vmd_category = {
                "text": parent_name,
                "is_vmd_category": True,
                "children": child_names,
                "rowspan": len(child_names) + 1
            }
            result.append(vmd_category)
        else:
            # No children found, add as flat item
            result.append(parent_name)
    
    return result

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

# --- LLM Processing ---
def createEnhancedTable(data, type, matchData):
    """Create enhanced table with proper column counting"""
    html = '<div style="border: 2px solid #333; background: white; overflow: hidden;">'
    hmd_data = None
    vmd_data = None
    vmd_header = ''
    
    for key, value in data.items():
        if key.endswith('.HMD'):
            hmd_data = value
        elif key.endswith('.VMD'):
            vmd_data = value
        elif key.endswith('.VMD_HEADER') and isinstance(value, str):
            vmd_header = value
    
    if not hmd_data or not vmd_data:
        return '<p>Invalid table structure</p>'

    html += '<table style="width: 100%; border-collapse: collapse; font-size: 14px; font-weight: bold;">'
    
    # Build headers
    header_html = build_preview_headers_with_vmd(hmd_data, vmd_header)
    html += '<thead>' + ''.join(header_html) + '</thead>'
    
    html += '<tbody>'
    
    column_count = count_columns_from_hmd_fixed(hmd_data)
    
    # Enhanced VMD rendering with hierarchy support  
    # Get table data for this table
    table_data_values = None
    for key, value in data.items():
        if key.endswith('.Data'):
            table_data_values = value
            break
    
    html += render_vmd_rows_with_hierarchy(vmd_data, type, matchData, column_count, table_data_values)
    
    html += '</tbody></table></div>'
    return html

def flatten_hmd_and_rowheader(hmd_list):
    """Flatten HMD objects while preserving JSON order and handling complex hierarchies"""
    hmd_out = []
    row_header = None

    if not isinstance(hmd_list, list):
        return [], None

    max_depth = 1
    for obj in hmd_list:
        if not isinstance(obj, dict):
            continue
        children = obj.get("children", [])
        if isinstance(children, list) and children:
            max_depth = max(max_depth, 2)

    for obj in hmd_list:
        if not isinstance(obj, dict):
            continue

        parent = None
        is_attribute1 = False
        for k, v in obj.items():
            if k.startswith("attribute") and isinstance(v, str):
                parent = v.strip()
                if k == "attribute1":
                    is_attribute1 = True
                break

        children = obj.get("children", [])
        
        if is_attribute1:
            if row_header is None:
                row_header = parent
            
            if isinstance(children, list) and children:
                for child in children:
                    if isinstance(child, dict):
                        for _, grade in child.items():
                            if isinstance(grade, str) and grade.strip():
                                hmd_out.append(f"{parent}.{grade.strip()}" if parent else grade.strip())
            
        elif isinstance(children, list) and children:
            # Handle complex children structure (like Table2's Treatment Group)
            for child in children:
                if isinstance(child, dict):
                    # Extract all child_level1.attributeX values from this child object
                    child_attributes = []
                    for child_key, child_value in child.items():
                        if child_key.startswith("child_level1.") and isinstance(child_value, str) and child_value.strip():
                            child_attributes.append((child_key, child_value.strip()))
                    
                    # Sort by attribute order (attribute1, attribute2, etc.)
                    child_attributes.sort(key=lambda x: x[0])
                    
                    # Add each child column as a separate item
                    for _, child_value in child_attributes:
                        if parent:
                            hmd_out.append(f"{parent}.{child_value}")
                        else:
                            hmd_out.append(child_value)
        else:
            if parent:
                hmd_out.append({
                    "text": parent,
                    "is_childless": True,
                    "rowspan": max_depth,
                    "colspan": 1
                })

    return hmd_out, row_header

# --- DOCX Processing ---
def isRowMatched(rowName, matchData):
    """Check if row is matched in VMD_matches"""
    if not matchData or not isinstance(matchData, dict):
        return False
    vmd_matches = matchData.get('VMD_matches', [])
    if not isinstance(vmd_matches, list):
        return False
    
    row_lower = str(rowName).lower().strip()
    for match in vmd_matches:
        if isinstance(match, dict):
            source = str(match.get('source', '')).lower().strip()
            target = str(match.get('target', '')).lower().strip()
            if row_lower == source or row_lower == target:
                return True
    return False

def create_merged_schema_table(merge_result_data):
    """Create a table structure from HMD_Merged_Schema and VMD_Merged_Schema"""
    if not merge_result_data:
        return {}
    
    # Support both old and new JSON structure formats
    hmd_merged = merge_result_data.get('HMD_Merged_Schema', [])
    vmd_merged = merge_result_data.get('VMD_Merged_Schema', [])
    
    # Check for new nested format
    if not hmd_merged and not vmd_merged and 'Merged_Schema' in merge_result_data:
        nested_schema = merge_result_data['Merged_Schema']
        hmd_merged = nested_schema.get('HMD_Merged_Schema', [])
        vmd_merged = nested_schema.get('VMD_Merged_Schema', [])
    
    if not hmd_merged and not vmd_merged:
        return {}
    
    # Process HMD - handle both object format and string format
    processed_hmd = []
    for item in hmd_merged:
        if isinstance(item, dict):
            # Handle object format from LLM: {"attribute1": "Bleeding.(n=35)", "children": []}
            # Extract the attribute value from attributeX keys
            attribute_value = None
            for key, value in item.items():
                if key.startswith('attribute') and isinstance(value, str):
                    attribute_value = value.strip()
                    break
            
            if attribute_value:
                if '.' in attribute_value:
                    # Handle hierarchy like "Bleeding.(n=35)" -> parent: "Bleeding", child: "(n=35)"
                    parts = attribute_value.split('.', 1)
                    parent = parts[0].strip()
                    child = parts[1].strip()
                    
                    # Check if parent already exists
                    parent_found = False
                    for existing in processed_hmd:
                        if isinstance(existing, dict) and existing.get('attribute1') == parent:
                            if 'children' not in existing:
                                existing['children'] = []
                            existing['children'].append({'child_level1.attribute1': child})
                            parent_found = True
                            break
                    
                    if not parent_found:
                        # Create new parent with child
                        processed_hmd.append({
                            'attribute1': parent,
                            'children': [{'child_level1.attribute1': child}]
                        })
                else:
                    # Simple item without hierarchy
                    processed_hmd.append({'attribute1': attribute_value})
        elif isinstance(item, str):
            # Handle string format: "Bleeding.(n=35)"
            if '.' in item:
                # Handle hierarchy like "Bleeding.(n=35)" -> parent: "Bleeding", child: "(n=35)"
                parts = item.split('.', 1)
                parent = parts[0].strip()
                child = parts[1].strip()
                
                # Check if parent already exists
                parent_found = False
                for existing in processed_hmd:
                    if isinstance(existing, dict) and existing.get('attribute1') == parent:
                        if 'children' not in existing:
                            existing['children'] = []
                        existing['children'].append({'child_level1.attribute1': child})
                        parent_found = True
                        break
                
                if not parent_found:
                    # Create new parent with child
                    processed_hmd.append({
                        'attribute1': parent,
                        'children': [{'child_level1.attribute1': child}]
                    })
            else:
                # Simple item without hierarchy
                processed_hmd.append({'attribute1': str(item)})
    
    # Process VMD - handle both object format and string format
    processed_vmd = []
    for item in vmd_merged:
        if isinstance(item, dict):
            # Handle object format from LLM: {"attribute1": "Age, mean±SD,y", "children": []}
            # Extract the attribute value from attributeX keys
            attribute_value = None
            for key, value in item.items():
                if key.startswith('attribute') and isinstance(value, str):
                    attribute_value = value.strip()
                    break
            
            if attribute_value:
                processed_vmd.append(attribute_value)
        elif isinstance(item, str):
            processed_vmd.append(str(item))
    
    # Create the merged table structure
    merged_table = {
        'MergedTable.HMD': processed_hmd,
        'MergedTable.VMD': processed_vmd,
        'MergedTable.VMD_HEADER': 'Merged Attributes'
    }
    
    return merged_table


def build_enhanced_headers(hmd_data, vmd_header_label=""):
    """Build headers with enhanced styling for extraction tables"""
    if not hmd_data:
        return []

    hierarchical_items = []
    childless_parents = []

    for item in hmd_data:
        if isinstance(item, dict):
            # If it explicitly says it's childless, or if it has no 'children' dict/list
            if item.get("is_childless") or not item.get("children"):
                childless_parents.append(item)
            else:
                # If a dict has children but was left here, it will be ignored by this basic renderer
                pass
        elif isinstance(item, str):
            hierarchical_items.append(item)

    has_hierarchy = any('.' in item for item in hierarchical_items)
    
    if not has_hierarchy:
        headers = ['<tr>']
        safe_label = (vmd_header_label or "").strip()
        
        headers.append(f'<th style="background: linear-gradient(135deg, #c62828 0%, #d32f2f 100%); color: white; padding: 10px 16px; text-align: left; font-weight: 600; border: 1px solid #b71c1c;">{safe_label}</th>')
        
        for item in hierarchical_items:
            headers.append(f'<th data-header="{item}" style="background: linear-gradient(135deg, #2e7d32 0%, #388e3c 100%); color: white; padding: 12px 16px; text-align: center; font-weight: 600; border: 1px solid #1b5e20; font-size: 14px;">{item}</th>')
        
        for item in childless_parents:
            colspan = item.get("colspan", 1)
            text = item.get("text", "")
            if not text:
                # Fallback to attribute1, attribute2, etc. (like "attribute2": "Total N")
                for k, v in item.items():
                    if k.startswith("attribute") and isinstance(v, str):
                        text = v.strip()
                        break
            headers.append(f'<th data-header="{text}" colspan="{colspan}" style="background: linear-gradient(135deg, #2e7d32 0%, #388e3c 100%); color: white; padding: 12px 16px; text-align: center; font-weight: 600; border: 1px solid #1b5e20; font-size: 14px;">{text}</th>')
        
        headers.append('</tr>')
        return headers

    # Multi-level headers
    structure = parse_hmd_structure_correctly(hierarchical_items)
    max_levels = structure['levels']
    
    headers = []
    for level in range(max_levels):
        headers.append('<tr>')
        
        if level == 0:
            safe_label = (vmd_header_label or "").strip()
            headers.append(f'<th rowspan="{max_levels}" style="background: linear-gradient(135deg, #2e7d32 0%, #388e3c 100%); color: white; padding: 10px 16px; text-align: left; font-weight: 600; border: 1px solid #1b5e20;">{safe_label}</th>')
            
            processed = set()
            for item in hierarchical_items:
                if item in processed:
                    continue
                    
                parts = item.split('.')
                current_part = parts[0]
                
                colspan = 1
                j = hierarchical_items.index(item) + 1
                while j < len(hierarchical_items):
                    next_item = hierarchical_items[j]
                    if next_item.split('.')[0] == current_part:
                        processed.add(next_item)
                        colspan += 1
                        j += 1
                    else:
                        break
                
                processed.add(item)
                headers.append(f'<th data-header="{current_part}" colspan="{colspan}" style="background: linear-gradient(135deg, #2e7d32 0%, #388e3c 100%); color: white; padding: 12px 16px; text-align: center; font-weight: 600; border: 1px solid #1b5e20; font-size: 14px;">{current_part}</th>')
            
            for item in childless_parents:
                text = item.get("text", "")
                if not text:
                    for k, v in item.items():
                        if k.startswith("attribute") and isinstance(v, str):
                            text = v.strip()
                            break
                headers.append(f'<th data-header="{text}" rowspan="{max_levels}" style="background: linear-gradient(135deg, #2e7d32 0%, #388e3c 100%); color: white; padding: 12px 16px; text-align: center; font-weight: 600; border: 1px solid #1b5e20; font-size: 14px;">{text}</th>')
        else:
            for item in hierarchical_items:
                parts = item.split('.')
                if level < len(parts):
                    part = parts[level]
                    full_path = '.'.join(parts[:level+1])
                    headers.append(f'<th data-header="{full_path}" style="background: linear-gradient(135deg, #2e7d32 0%, #388e3c 100%); color: white; padding: 12px 16px; text-align: center; font-weight: 600; border: 1px solid #1b5e20; font-size: 14px;">{part}</th>')
        
        headers.append('</tr>')
    
    return headers

def render_enhanced_vmd_rows(vmd_data, column_count, table_data=None):
    """Render VMD rows with enhanced styling"""
    if not vmd_data:
        return ''

    html = ''
    data_row_index = 0

    for index, item in enumerate(vmd_data):
        if isinstance(item, dict) and item.get("is_vmd_category"):
            # Category with children
            category_text = item["text"]
            children = item.get("children", [])
            
            html += f'<tr data-row="{category_text}">'
            html += f'<td style="background: white; color: #c62828; padding: 10px 16px; text-align: left; font-weight: 700; border: 1px solid #e0e0e0; font-size: 15px;">{category_text}</td>'
            
            for i in range(column_count):
                html += '<td style="background: white; padding: 8px 16px; border: 1px solid #e0e0e0; text-align: center; font-size: 13px;"></td>'
            
            html += '</tr>'
            
            # Category rows don't consume data - skip to children
            # Render children
            for child_index, child in enumerate(children):
                html += f'<tr data-row="{child}">'
                html += f'<td style="background: white; color: #c62828; padding: 8px 16px 8px 32px; text-align: left; font-weight: 500; border: 1px solid #e0e0e0;">{child}</td>'
                
                for i in range(column_count):
                    cell_value = ""
                    if table_data and data_row_index < len(table_data):
                        row_data = table_data[data_row_index]
                        if isinstance(row_data, list) and i < len(row_data):
                            cell_value = row_data[i] or ""
                    
                    html += f'<td data-cell-value="{cell_value}" style="background: white; color: #333; padding: 8px 16px; border: 1px solid #e0e0e0; text-align: center; font-size: 13px;">{cell_value if cell_value else ""}</td>'

                html += '</tr>'
                data_row_index += 1

        elif isinstance(item, str):
            # Skip hierarchical paths already rendered
            if "." in item:
                parts = item.split(".", 1)
                if len(parts) == 2:
                    parent_category = parts[0]
                    found_parent = False
                    for prev_item in vmd_data[:index]:
                        if (isinstance(prev_item, dict) and 
                            prev_item.get("is_vmd_category") and 
                            prev_item["text"] == parent_category):
                            found_parent = True
                            break
                    
                    if found_parent:
                        continue
            
            # Flat item
            html += f'<tr data-row="{item}">'
            html += f'<td style="background: white; color: #c62828; padding: 8px 16px; text-align: left; font-weight: 500; border: 1px solid #e0e0e0;">{item}</td>'
            
            for i in range(column_count):
                cell_value = ""
                if table_data and data_row_index < len(table_data):
                    row_data = table_data[data_row_index]
                    if isinstance(row_data, list) and i < len(row_data):
                        cell_value = row_data[i] or ""
                
                html += f'<td data-cell-value="{cell_value}">{cell_value if cell_value else ""}</td>'

            html += '</tr>'
            data_row_index += 1

    return html
