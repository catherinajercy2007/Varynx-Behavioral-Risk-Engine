"""Evaluation API — POST /evaluate/run, GET /evaluate/scenarios, etc.

Satisfies: REQ-015, REQ-025, REQ-016
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from varynx.api.schemas import error_response, success_response

router = APIRouter()

def get_pipeline(request: Request):
    from varynx.api.app import get_pipeline as _gp
    return _gp()

class EvalRunRequest(BaseModel):
    scenario_name: str
    seed: int = 42
    ablation: dict = {}

@router.post("/evaluate/run", summary="Execute a named scenario")
async def run_evaluation(body: EvalRunRequest, request: Request):
    from varynx.evaluation.runner import ScenarioRunner
    pipeline = get_pipeline(request)
    runner = ScenarioRunner(pipeline=pipeline)
    try:
        result = runner.run_named(body.scenario_name, seed=body.seed)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=error_response("SCENARIO_NOT_FOUND", f"Scenario '{body.scenario_name}' not found"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=error_response("EVALUATION_ERROR", str(exc)))
    return success_response(result)

@router.get("/evaluate/scenarios", summary="List available scenarios")
async def list_scenarios(request: Request):
    import pathlib
    scenarios_dir = pathlib.Path("scenarios")
    if not scenarios_dir.exists():
        return success_response({"scenarios": []})
    files = list(scenarios_dir.glob("*.yaml")) + list(scenarios_dir.glob("*.yml"))
    return success_response({"scenarios": [f.stem for f in files]})

@router.get("/evaluate/results/{run_id}", summary="Get evaluation run results")
async def get_eval_results(run_id: str, request: Request):
    import json
    import pathlib
    results_file = pathlib.Path(f"output/eval_{run_id}.json")
    if not results_file.exists():
        raise HTTPException(status_code=404, detail=error_response("RUN_NOT_FOUND", f"Run {run_id} not found"))
    return success_response(json.loads(results_file.read_text()))
