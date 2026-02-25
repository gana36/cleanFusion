"""
Pydantic models for data validation
"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# --- Pydantic Models for Response Validation ---
class MatchResult(BaseModel):
    matches: List[Dict[str, str]]

class MergeResult(BaseModel):
    Merged_Schema: List[str]
    Merged_Data: Optional[List[Dict[str, Any]]] = []
    Map_Schema1: Optional[List[Dict[str, str]]] = []
    Map_Schema2: Optional[List[Dict[str, str]]] = []

class ComplexInstanceMergeResult(BaseModel):
    HMD_Merged_Schema: List[Dict[str, Any]] = []
    VMD_Merged_Schema: List[Dict[str, Any]] = []
    Merged_Data: Dict[str, Any] = {}
    HMD_Map_Schema1: List[Dict[str, str]] = []
    VMD_Map_Schema1: List[Dict[str, str]] = []
    HMD_Map_Schema2: List[Dict[str, str]] = []
    VMD_Map_Schema2: List[Dict[str, str]] = []

    class Config:
        extra = "forbid"  # Prevent extra fields

class ProcessingMetrics(BaseModel):
    script_id: str
    timestamp: str
    llm_model: str
    schema_type: str
    processing_type: str
    operation_type: str
    total_generation_time: float
    input_prompt_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0
    total_tokens: Optional[int] = 0
    tokens_per_second: Optional[float] = 0.0
    api_call_cost: Optional[float] = 0.0
    preprocessing_time: Optional[float] = 0.0
    hmd_matches: Optional[int] = 0
    vmd_matches: Optional[int] = 0
    total_matches: Optional[int] = 0
    match_generation_time: Optional[float] = 0.0
    merge_generation_time: Optional[float] = 0.0

    # Detailed metrics for separate match and merge steps
    match_input_tokens: Optional[int] = None
    match_output_tokens: Optional[int] = None
    merge_input_tokens: Optional[int] = None
    merge_output_tokens: Optional[int] = None
    match_api_cost: Optional[float] = None
    merge_api_cost: Optional[float] = None
    matching_llm_used: Optional[str] = None
    merge_llm_used: Optional[str] = None
    pipeline_description: Optional[str] = None
