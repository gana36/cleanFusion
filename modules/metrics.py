"""
Metrics Module - Calculate pipeline performance metrics from training data
"""

import pandas as pd
import os
from typing import Dict, Optional, Any

def load_training_data(csv_path: str = "train.csv") -> Optional[pd.DataFrame]:
    """Load training data from CSV file"""
    try:
        if not os.path.exists(csv_path):
            print(f"[WARNING] Training data not found at {csv_path}")
            return None

        df = pd.read_csv(csv_path)
        return df
    except Exception as e:
        print(f"[ERROR] Failed to load training data: {str(e)}")
        return None

def normalize_model_name(model_name: str) -> str:
    """Normalize model names to match between frontend and CSV"""
    # Mapping from frontend display names to CSV names
    model_mapping = {
        "gemini-2.5-flash": "Gemini 2.5 Flash",
        "gemini-2.0-flash-exp": "Gemini 2.0 Flash Exp",
        "gemini-1.5-flash": "Gemini 1.5 Flash",
        "claude-3-5-haiku-20241022": "Claude 3.5 Haiku",
        "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet",
        "claude-sonnet-4-20250514": "Claude Sonnet 4",
        "openai/gpt-oss-20b": "GPT Oss 20B",
        "openai/gpt-oss-120b": "GPT Oss 120B",
        "llama-3.1-8b-instant": "Llama 3.1 8B",
        "qwen/qwen3-32b": "Qwen 3 32B",
        "deepseek-r1-distill-llama-70b": "DeepSeek R1",
    }

    return model_mapping.get(model_name, model_name)

def normalize_operator_name(operator: str) -> str:
    """Normalize operator names"""
    if operator.lower() == "operator":
        return "Operator"
    elif operator.lower() == "instance merge":
        return "Instance Merge"
    return operator

def normalize_method_name(method: str) -> str:
    """Normalize method names"""
    method_mapping = {
        "json": "JSON",
        "json (default)": "JSON",
        "knowledge graph": "Knowledge Graph",
        "multi-step": "Multi-Step",
        "multi_step": "Multi-Step",
    }
    return method_mapping.get(method.lower(), method)

def get_pipeline_metrics(
    match_operator: str,
    match_method: str,
    match_llm: str,
    merge_operator: Optional[str] = None,
    merge_method: Optional[str] = None,
    merge_llm: Optional[str] = None,
    csv_path: str = "train.csv"
) -> Dict[str, Any]:
    """
    Get average metrics for a specific pipeline configuration

    Args:
        match_operator: Match operation type (e.g., "Operator")
        match_method: Match method (e.g., "JSON")
        match_llm: LLM model for matching
        merge_operator: Merge operation type (optional)
        merge_method: Merge method (optional)
        merge_llm: LLM model for merging (optional)
        csv_path: Path to training CSV file

    Returns:
        Dictionary with average metrics or empty dict if no data found
    """
    df = load_training_data(csv_path)

    if df is None or df.empty:
        return {
            "error": "No training data available",
            "sample_count": 0
        }

    # Normalize input parameters
    match_operator = normalize_operator_name(match_operator)
    match_method = normalize_method_name(match_method)
    match_llm = normalize_model_name(match_llm)

    # Build filter conditions for matching
    filters = (
        (df["Match Operator"] == match_operator) &
        (df["Match Method"] == match_method) &
        (df["LLM used for matching"] == match_llm)
    )

    # Add merge filters if provided
    if merge_operator and merge_method and merge_llm:
        merge_operator = normalize_operator_name(merge_operator)
        merge_method = normalize_method_name(merge_method)
        merge_llm = normalize_model_name(merge_llm)

        filters = filters & (
            (df["Merge Operator"] == merge_operator) &
            (df["Merge Method"] == merge_method) &
            (df["LLM used for merging"] == merge_llm)
        )

    # Filter the dataframe
    filtered_df = df[filters]

    if filtered_df.empty:
        return {
            "error": "No matching data found for this configuration",
            "sample_count": 0,
            "config": {
                "match_operator": match_operator,
                "match_method": match_method,
                "match_llm": match_llm,
                "merge_operator": merge_operator,
                "merge_method": merge_method,
                "merge_llm": merge_llm
            }
        }

    # Calculate metrics and convert numpy types to Python native types for JSON serialization
    metrics = {
        "sample_count": int(len(filtered_df)),
        "avg_cost": float(round(filtered_df["api_call_cost"].mean(), 6)) if "api_call_cost" in filtered_df.columns else 0.0,
        "avg_match_time": float(round(filtered_df["match_generation_time"].mean(), 4)) if "match_generation_time" in filtered_df.columns else 0.0,
        "avg_merge_time": float(round(filtered_df["merge_generation_time"].mean(), 4)) if "merge_generation_time" in filtered_df.columns else 0.0,
        "avg_total_time": float(round(
            (filtered_df["match_generation_time"] + filtered_df["merge_generation_time"]).mean(), 4
        )) if all(col in filtered_df.columns for col in ["match_generation_time", "merge_generation_time"]) else 0.0,
        "avg_accuracy": float(round(filtered_df["precision"].mean(), 4)) if "precision" in filtered_df.columns else 0.0,
        "avg_input_tokens": float(round(filtered_df["input_prompt_tokens"].mean(), 2)) if "input_prompt_tokens" in filtered_df.columns else 0.0,
        "avg_output_tokens": float(round(filtered_df["output_tokens"].mean(), 2)) if "output_tokens" in filtered_df.columns else 0.0,
        "config": {
            "match_operator": match_operator,
            "match_method": match_method,
            "match_llm": match_llm,
            "merge_operator": merge_operator,
            "merge_method": merge_method,
            "merge_llm": merge_llm
        }
    }

    return metrics

def get_all_available_configs(csv_path: str = "train.csv") -> Dict[str, Any]:
    """Get all unique pipeline configurations from training data"""
    df = load_training_data(csv_path)

    if df is None or df.empty:
        return {"error": "No training data available"}

    configs = {
        "match_operators": df["Match Operator"].dropna().unique().tolist(),
        "match_methods": df["Match Method"].dropna().unique().tolist(),
        "match_llms": df["LLM used for matching"].dropna().unique().tolist(),
        "merge_operators": df["Merge Operator"].dropna().unique().tolist(),
        "merge_methods": df["Merge Method"].dropna().unique().tolist(),
        "merge_llms": df["LLM used for merging"].dropna().unique().tolist(),
    }

    return configs
