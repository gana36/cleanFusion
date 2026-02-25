from fastapi import FastAPI, UploadFile, File, Request, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json

from fusion_helpers import (
    extract_combined_features,
    predict_best_paths,
)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/predict")
async def predict(
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
    backend: str = Form("rf"),
    mode: str = Form("merge"),
):
    """
    1) Read two JSON tables.
    2) Extract schema_type + input_prompt_tokens.
    3) Use selected model backend + mode to predict best paths.
    """
    try:
        raw_a = await file_a.read()
        raw_b = await file_b.read()

        table1 = json.loads(raw_a.decode("utf-8"))
        table2 = json.loads(raw_b.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON input: {e}")

    # Step 1: extraction
    features = extract_combined_features(table1, table2)

    schema_type = features["schema_type"]
    input_tokens = features["input_prompt_tokens"]

    # Step 2: prediction (best paths)
    try:
        best_paths = predict_best_paths(
            backend=backend,
            mode=mode,
            schema_type=schema_type,
            input_tokens=input_tokens,
        )
    except RuntimeError as e:
        # Return extraction info + a clear error message about models
        raise HTTPException(
            status_code=500,
            detail=f"Model/pipeline error: {e}",
        )

    # Merge both extraction + prediction into one response
    return {
        "extraction": features,
        "prediction": best_paths,
    }
