"""
Schema Profiler Module - Calculate metadata and statistics from schema data
"""

import json
from typing import Dict, Any, List
import sys


def calculate_schema_profile(schema_data: Dict[str, Any], schema_json_str: str = None) -> Dict[str, Any]:
    """
    Calculate profile information from parsed schema data

    Args:
        schema_data: Parsed schema dictionary
        schema_json_str: Original JSON string for size calculation

    Returns:
        Dictionary with profile information
    """
    profile = {
        "total_tables": 0,
        "total_hmds": 0,
        "total_vmds": 0,
        "total_data_rows": 0,
        "size_bytes": 0,
        "size_kb": 0,
        "tables": []
    }

    # Calculate size if JSON string provided
    if schema_json_str:
        profile["size_bytes"] = len(schema_json_str.encode('utf-8'))
        profile["size_kb"] = round(profile["size_bytes"] / 1024, 2)
    elif schema_data:
        # Estimate from schema_data
        json_str = json.dumps(schema_data)
        profile["size_bytes"] = len(json_str.encode('utf-8'))
        profile["size_kb"] = round(profile["size_bytes"] / 1024, 2)

    # Analyze each table in the schema
    table_names = set()

    for key, value in schema_data.items():
        # Extract table name (remove .HMD, .VMD, .Data suffix)
        if '.' in key:
            table_name = key.split('.')[0]
            table_type = key.split('.')[1]

            table_names.add(table_name)

            # Count HMDs
            if table_type == "HMD" and isinstance(value, list):
                hmds = len(value)
                profile["total_hmds"] += hmds

                # Update or create table entry
                update_table_profile(profile["tables"], table_name, "hmds", hmds)

            # Count VMDs
            elif table_type == "VMD" and isinstance(value, list):
                vmds = len(value)
                profile["total_vmds"] += vmds

                update_table_profile(profile["tables"], table_name, "vmds", vmds)

            # Count Data rows
            elif table_type == "Data" and isinstance(value, list):
                data_rows = len(value)
                profile["total_data_rows"] += data_rows

                update_table_profile(profile["tables"], table_name, "data_rows", data_rows)

    profile["total_tables"] = len(table_names)

    # Sort tables by name
    profile["tables"] = sorted(profile["tables"], key=lambda x: x["table_name"])

    return profile


def update_table_profile(tables: List[Dict], table_name: str, field: str, value: int):
    """Helper function to update or create table profile entry"""
    # Find existing table
    for table in tables:
        if table["table_name"] == table_name:
            table[field] = value
            return

    # Create new table entry
    new_table = {
        "table_name": table_name,
        "hmds": 0,
        "vmds": 0,
        "data_rows": 0
    }
    new_table[field] = value
    tables.append(new_table)


def format_profile_for_display(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Format profile data for frontend display"""
    return {
        "summary": {
            "Total Tables": profile["total_tables"],
            "Total HMDs": profile["total_hmds"],
            "Total VMDs": profile["total_vmds"],
            "Total Data Rows": profile["total_data_rows"],
            "Size": f"{profile['size_kb']} KB ({profile['size_bytes']} bytes)"
        },
        "tables": profile["tables"]
    }
