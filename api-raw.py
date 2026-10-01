"""
BB Code Simulation REST API
============================
Run with:
    pip install fastapi uvicorn ldpc stim scipy numpy
    uvicorn api:app --reload

Then POST to /simulate or GET /health.
"""

import builtins
builtins.input = lambda _="": "n"

import time
import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

# ── local modules (must live alongside this file) ────────────────────
from bbcodesim import circuit_level_simulation
from codes import create_bivariate_bicycle_codes
from ldpc import bposd_decoder, bp_decoder

app = FastAPI(
    title="BB Code Simulation API",
    description="REST API for bivariate bicycle quantum LDPC code circuit-level simulations.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Decoder wrappers (mirrors run.py) ────────────────────────────────

class BPOSDDecoder:
    name = "BPOSD"

    def set_h(self, H, priors, error_rate):
        self.decoder = bposd_decoder(
            H,
            channel_probs=priors,
            max_iter=100,
            bp_method="ms",
            ms_scaling_factor=0.625,
            osd_method="osd_cs",
            osd_order=7,
        )

    def decode(self, syndrome):
        return self.decoder.decode(syndrome)


class BPDecoder:
    name = "BP"

    def set_h(self, H, priors, error_rate):
        self.decoder = bp_decoder(
            H,
            channel_probs=priors,
            max_iter=100,
            bp_method="ms",
            ms_scaling_factor=0.625,
        )

    def decode(self, syndrome):
        return self.decoder.decode(syndrome)


DECODER_REGISTRY = {
    "BPOSD": BPOSDDecoder,
    "BP": BPDecoder,
}


# ── Request / Response models ─────────────────────────────────────────

class CodeParams(BaseModel):
    """Parameters that define the bivariate bicycle code."""
    ell: int = Field(6, ge=2, description="First dimension (ell) of the BB code.")
    m: int = Field(6, ge=2, description="Second dimension (m) of the BB code.")
    a1: List[int] = Field([3], description="Exponents for A-polynomial term 1.")
    a23: List[int] = Field([1, 2], description="Exponents for A-polynomial terms 2 & 3.")
    b12: List[int] = Field([1, 2], description="Exponents for B-polynomial terms 1 & 2.")
    b3: List[int] = Field([3], description="Exponents for B-polynomial term 3.")

    model_config = {"json_schema_extra": {"example": {
        "ell": 6, "m": 6, "a1": [3], "a23": [1, 2], "b12": [1, 2], "b3": [3]
    }}}


class SimulationRequest(BaseModel):
    """Full simulation request — mirrors the parameters in run.py."""

    code: CodeParams = Field(default_factory=CodeParams)

    error_rate: float = Field(
        0.01, ge=1e-6, le=0.5,
        description="Physical error rate p.",
    )
    num_trials: int = Field(
        10000, ge=1, le=1_000_000,
        description="Number of Monte Carlo shots.",
    )
    num_repeat: int = Field(
        12, ge=1,
        description="Number of syndrome-measurement rounds.",
    )
    W: int = Field(1, ge=1, description="Sliding-window size.")
    F: int = Field(1, ge=1, description="Sliding-window stride.")
    z_basis: bool = Field(False, description="Decode in Z basis (True) or X basis (False).")
    method: int = Field(0, ge=0, le=2, description="Decoding method (0=standard, 1/2=windowed with noisy prior).")
    decoders: List[str] = Field(
        ["BPOSD", "BP"],
        description="List of decoder names to benchmark. Available: BPOSD, BP.",
    )

    @field_validator("decoders")
    @classmethod
    def validate_decoders(cls, v):
        unknown = [d for d in v if d not in DECODER_REGISTRY]
        if unknown:
            raise ValueError(f"Unknown decoder(s): {unknown}. Available: {list(DECODER_REGISTRY)}")
        if not v:
            raise ValueError("At least one decoder must be specified.")
        return v

    model_config = {"json_schema_extra": {"example": {
        "code": {"ell": 6, "m": 6, "a1": [3], "a23": [1, 2], "b12": [1, 2], "b3": [3]},
        "error_rate": 0.01,
        "num_trials": 10000,
        "num_repeat": 12,
        "W": 1,
        "F": 1,
        "z_basis": False,
        "method": 0,
        "decoders": ["BPOSD", "BP"],
    }}}


class DecoderResult(BaseModel):
    logical_error_rate: float = Field(description="Fraction of trials with a logical error.")
    logical_error_rate_per_round: float = Field(description="Per-round logical error rate.")
    avg_decoding_time_seconds: float = Field(description="Average decoding time per syndrome (seconds).")


class SimulationResponse(BaseModel):
    code_name: str
    code_n: int
    code_k: int
    error_rate: float
    num_trials: int
    num_repeat: int
    results: dict[str, DecoderResult]
    wall_time_seconds: float = Field(description="Total wall-clock time for this request.")


# ── Helper ────────────────────────────────────────────────────────────

def _run_simulation(req: SimulationRequest) -> SimulationResponse:
    """Blocking simulation — called inside a thread/process pool."""

    # Build the code
    try:
        code = create_bivariate_bicycle_codes(
            req.code.ell,
            req.code.m,
            req.code.a1,
            req.code.a23,
            req.code.b12,
            req.code.b3,
        )
    except Exception as exc:
        raise ValueError(f"Failed to construct BB code: {exc}") from exc

    # Instantiate decoders
    decoder_instances = [DECODER_REGISTRY[name]() for name in req.decoders]

    wall_start = time.perf_counter()

    logical_errs, logical_errs_per_round, timing = circuit_level_simulation(
        code=code,
        error_rate=req.error_rate,
        decoders=decoder_instances,
        num_repeat=req.num_repeat,
        num_trials=req.num_trials,
        W=req.W,
        F=req.F,
        z_basis=req.z_basis,
        method=req.method,
        plot=False,
    )

    wall_time = time.perf_counter() - wall_start

    results = {
        name: DecoderResult(
            logical_error_rate=logical_errs[name],
            logical_error_rate_per_round=logical_errs_per_round[name],
            avg_decoding_time_seconds=timing[name],
        )
        for name in req.decoders
    }

    return SimulationResponse(
        code_name=code.name,
        code_n=int(code.N),
        code_k=int(code.K),
        error_rate=req.error_rate,
        num_trials=req.num_trials,
        num_repeat=req.num_repeat,
        results=results,
        wall_time_seconds=wall_time,
    )


# ── Routes ────────────────────────────────────────────────────────────

@app.get("/health", summary="Health check")
def health():
    """Returns 200 OK if the service is running."""
    return {"status": "ok"}


@app.get("/decoders", summary="List available decoders")
def list_decoders():
    """Returns the names of all supported decoders."""
    return {"decoders": list(DECODER_REGISTRY.keys())}


@app.post(
    "/simulate",
    response_model=SimulationResponse,
    summary="Run a circuit-level simulation",
    description=(
        "Constructs a bivariate bicycle (BB) code, builds the stim circuit, "
        "runs Monte Carlo sampling, and benchmarks each requested decoder. "
        "Large `num_trials` values may take several minutes."
    ),
)
async def simulate(req: SimulationRequest):
    """
    Run the BB code simulation with the supplied parameters.

    The simulation is CPU-intensive; it is offloaded to a thread executor so
    the event loop stays responsive.
    """
    loop = asyncio.get_running_loop()
    try:
        # Run blocking simulation in a thread pool to avoid blocking the event loop
        result = await loop.run_in_executor(None, _run_simulation, req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {exc}")
    return result


@app.post(
    "/simulate/quick",
    response_model=SimulationResponse,
    summary="Quick sanity-check simulation (100 trials)",
    description="Same as /simulate but forces num_trials=100 for a rapid sanity check.",
)
async def simulate_quick(req: SimulationRequest):
    req = req.model_copy(update={"num_trials": 100})
    return await simulate(req)