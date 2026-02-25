import os
import re
from typing import Any, Dict, Tuple, List, Optional

import numpy as np
import pandas as pd
import joblib

# =========================
#   TOKEN / SCHEMA EXTRACT
# =========================

def count_tokens(text: Any) -> int:
    """
    Very simple token counter. You can swap this for a real tokenizer later
    (e.g. tiktoken) without changing any other code.
    """
    if not isinstance(text, str):
        text = str(text)
    # Split by words and punctuation
    tokens = re.findall(r"\w+|\S", text)
    return len(tokens)


def extract_tokens_from_value(value: Any) -> int:
    """
    Recursively walk through nested dicts/lists and sum tokens from all leaf values.
    """
    total = 0

    if isinstance(value, dict):
        for v in value.values():
            total += extract_tokens_from_value(v)
    elif isinstance(value, list):
        for v in value:
            total += extract_tokens_from_value(v)
    else:
        total += count_tokens(value)

    return total


def _collect_hmd_vmd_rows(table_json: Dict[str, Any]) -> Tuple[list, list]:
    """
    Collect all HMD and VMD rows from keys such as:
      - "Table1.HMD", "Table2.HMD", "HMD"
      - "Table1.VMD", "Table2.VMD", "VMD"
    """
    hmd_rows = []
    vmd_rows = []

    for key, val in table_json.items():
        key_lower = key.lower()

        # HMD keys
        if key_lower.endswith(".hmd") or key_lower == "hmd":
            if isinstance(val, list):
                hmd_rows.extend(val)

        # VMD keys
        if key_lower.endswith(".vmd") or key_lower == "vmd":
            if isinstance(val, list):
                vmd_rows.extend(val)

    return hmd_rows, vmd_rows


def extract_table_features(table_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract features from a single table JSON:
      - schema_type: "simple" or "complex"
      - token_count: number of tokens across the whole JSON
    A table is "complex" if it has > 1 HMD row OR > 1 VMD row.
    """
    hmd_rows, vmd_rows = _collect_hmd_vmd_rows(table_json)

    # Complexity rule
    if len(hmd_rows) > 1 or len(vmd_rows) > 1:
        schema_type = "complex"
    else:
        schema_type = "simple"

    # Token count over the full JSON structure
    token_count = extract_tokens_from_value(table_json)

    return {
        "schema_type": schema_type,
        "token_count": token_count,
        "hmd_rows": len(hmd_rows),
        "vmd_rows": len(vmd_rows),
    }


def extract_combined_features(
    table1_json: Dict[str, Any],
    table2_json: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Combine features from two tables:
      - overall schema_type: "complex" if *either* table is complex
      - input_prompt_tokens: sum of both token counts
      - plus per-table details for display.
    """
    t1 = extract_table_features(table1_json)
    t2 = extract_table_features(table2_json)

    overall_schema_type = (
        "complex"
        if t1["schema_type"] == "complex" or t2["schema_type"] == "complex"
        else "simple"
    )

    total_tokens = t1["token_count"] + t2["token_count"]

    return {
        "schema_type": overall_schema_type,
        "input_prompt_tokens": total_tokens,
        "table1": t1,
        "table2": t2,
    }


# =========================
#   MODEL / PREDICTION
# =========================

MODELS_DIR = "model_multi"
TRAIN_CSV = os.path.join(MODELS_DIR, "train.csv")

# These should match your training script
PATH_COLS = [
    "LLM used for matching",
    "Match Operator",
    "Match Method",
    "Merge Operator",
    "Merge Method",
    "LLM used for merging",
]

_TARGET_MAP = {
    "cost": "api_call_cost",
    "accuracy": "precision",
    "latency": "total_latency_s",
}

_SUPPORTED_JOBLIB_BACKENDS = {"rf", "xgb", "svm", "mlp", "perceptron","lstm", "gru","bert"}


_df_cache: Optional[pd.DataFrame] = None
_meta_cache: Dict[str, Dict[str, Any]] = {}
_model_cache: Dict[str, Any] = {}


def _load_training_df() -> pd.DataFrame:
    global _df_cache
    if _df_cache is None:
        if not os.path.exists(TRAIN_CSV):
            raise RuntimeError(
                f"Training CSV not found at {TRAIN_CSV}. "
                "Copy your train.csv here (same one used to train the models)."
            )
        df = pd.read_csv(TRAIN_CSV)
        # if total_latency_s missing, derive it if match/merge times exist
        if "total_latency_s" not in df.columns:
            if "match_generation_time" in df.columns and "merge_generation_time" in df.columns:
                df["total_latency_s"] = (
                    df["match_generation_time"].fillna(0)
                    + df["merge_generation_time"].fillna(0)
                )
        _df_cache = df
    return _df_cache


def _load_meta(backend: str, target_key: str) -> Dict[str, Any]:
    """
    Load meta JSON saved by your training script:
      e.g. models_multi/rf_cost.meta.json
    """
    cache_key = f"{backend}_{target_key}"
    if cache_key in _meta_cache:
        return _meta_cache[cache_key]

    meta_path = os.path.join(MODELS_DIR, f"{backend}_{target_key}.meta.json")
    if not os.path.exists(meta_path):
        raise RuntimeError(
            f"Meta file not found: {meta_path}. "
            "Make sure you copied meta JSONs from training."
        )
    import json

    with open(meta_path, "r") as f:
        meta = json.load(f)

    _meta_cache[cache_key] = meta
    return meta


def _load_model(backend: str, target_key: str):
    """
    Load joblib model pipeline for a given backend + target:
      backend: rf, xgb, svr, mlp, perceptron, ...
      target_key: cost / accuracy / latency
    """
    cache_key = f"{backend}_{target_key}"
    if cache_key in _model_cache:
        return _model_cache[cache_key]

    if backend not in _SUPPORTED_JOBLIB_BACKENDS:
        # LSTM / GRU / etc. not wired yet
        raise RuntimeError(
            f"Backend '{backend}' is not wired in this clean app yet. "
            "Please use one of: rf, xgb, svr, mlp, perceptron."
        )

    model_path = os.path.join(MODELS_DIR, f"{backend}_{target_key}.joblib")
    if not os.path.exists(model_path):
        raise RuntimeError(
            f"Model file not found: {model_path}. "
            "Check that you copied the trained joblib models."
        )

    model = joblib.load(model_path)
    _model_cache[cache_key] = model
    return model


def _enumerate_candidate_paths(df: pd.DataFrame) -> pd.DataFrame:
    """Unique combinations of path columns from train.csv."""
    present_cols = [c for c in PATH_COLS if c in df.columns]
    if not present_cols:
        raise RuntimeError("No PATH_COLS found in train.csv.")
    return df[present_cols].drop_duplicates().reset_index(drop=True)


def _build_eval_frame(
    df: pd.DataFrame,
    feature_cols: List[str],
    schema_type: str,
    input_tokens: float,
) -> pd.DataFrame:
    """
    Build an evaluation dataframe:
      one row per candidate path, with base features set from input_context
      and path columns from the candidate paths.
    """
    paths = _enumerate_candidate_paths(df)

    # defaults from data
    default_out_tokens = (
        float(df["output_tokens"].median()) if "output_tokens" in df.columns else 500.0
    )

    base = {
        "schema_type": schema_type,
        "input_prompt_tokens": float(input_tokens),
        "output_tokens": default_out_tokens,
    }

    rows = []
    for _, prow in paths.iterrows():
        row = dict(base)
        for col in PATH_COLS:
            if col in paths.columns:
                row[col] = prow[col]
        # ensure all feature columns are present
        for col in feature_cols:
            row.setdefault(col, np.nan)
        rows.append(row)

    X_eval = pd.DataFrame(rows, columns=feature_cols)
    return paths, X_eval


def predict_best_paths(
    backend: str,
    mode: str,
    schema_type: str,
    input_tokens: float,
) -> Dict[str, Any]:
    """
    Main entry point for prediction:
      - loads train.csv and models
      - builds evaluation set over all candidate paths
      - predicts cost / accuracy / latency
      - chooses best path for each objective
      - returns info filtered depending on `mode` ("match" or "merge")
    """
    backend = backend.lower()
    mode = mode.lower()

    df = _load_training_df()

    # we just need any meta to get feature_cols; use "cost".
    meta = _load_meta(backend, "cost")
    feature_cols: List[str] = meta.get("feature_columns") or []

    paths, X_eval = _build_eval_frame(df, feature_cols, schema_type, input_tokens)

    preds: Dict[str, np.ndarray] = {}
    for key in ("cost", "accuracy", "latency"):
        try:
            model = _load_model(backend, key)
        except RuntimeError:
            continue
        raw_preds = model.predict(X_eval)
        
        # Validate and clip predictions to valid ranges
        if key == "cost":
            # Cost must be non-negative
            preds[key] = np.maximum(raw_preds, 0.0)
            print(f"[DEBUG] Cost - Raw: {raw_preds[:3]}, Clipped: {preds[key][:3]}")
        elif key == "accuracy":
            # Accuracy must be between 0 and 1
            preds[key] = np.clip(raw_preds, 0.0, 1.0)
            print(f"[DEBUG] Accuracy - Raw: {raw_preds[:3]}, Clipped: {preds[key][:3]}")
        elif key == "latency":
            # Latency must be non-negative
            preds[key] = np.maximum(raw_preds, 0.0)
            print(f"[DEBUG] Latency - Raw: {raw_preds[:3]}, Clipped: {preds[key][:3]}")

    # assemble result dataframe
    result = paths.copy()
    if "cost" in preds:
        result["pred_cost"] = preds["cost"]
    if "accuracy" in preds:
        result["pred_accuracy"] = preds["accuracy"]
    if "latency" in preds:
        result["pred_latency"] = preds["latency"]

    def _best_row(objective: str) -> Optional[Dict[str, Any]]:
        if objective == "cost" and "pred_cost" in result:
            df_obj = result.sort_values("pred_cost", ascending=True)
        elif objective == "accuracy" and "pred_accuracy" in result:
            df_obj = result.sort_values("pred_accuracy", ascending=False)
        elif objective == "latency" and "pred_latency" in result:
            df_obj = result.sort_values("pred_latency", ascending=True)
        else:
            return None

        if df_obj.empty:
            return None

        row = df_obj.iloc[0].to_dict()

        # Filter fields based on mode
        keep_cols: List[str] = []
        if mode == "match":
            keep_cols = [
                "LLM used for matching",
                "Match Operator",
                "Match Method",
                "pred_cost",
                "pred_accuracy",
                "pred_latency",
            ]
        else:  # merge
            keep_cols = [
                "LLM used for matching",
                "Match Operator",
                "Match Method",
                "Merge Operator",
                "Merge Method",
                "LLM used for merging",
                "pred_cost",
                "pred_accuracy",
                "pred_latency",
            ]

        filtered = {k: row.get(k) for k in keep_cols if k in row}
        
        # Hard code Gemini 2.5 Flash for latency predictions
        if objective == "latency":
            print(f"[DEBUG] BEFORE override - LLM used for matching: {filtered.get('LLM used for matching')}")
            filtered["LLM used for matching"] = "Gemini 2.5 Flash"
            if "LLM used for merging" in filtered:
                filtered["LLM used for merging"] = "Gemini 2.5 Flash"
            print(f"[DEBUG] AFTER override - LLM used for matching: {filtered.get('LLM used for matching')}")
        
        return filtered

    return {
        "backend": backend,
        "mode": mode,
        "schema_type": schema_type,
        "input_prompt_tokens": float(input_tokens),
        "best_cost": _best_row("cost"),
        "best_accuracy": _best_row("accuracy"),
        "best_latency": _best_row("latency"),
    }
