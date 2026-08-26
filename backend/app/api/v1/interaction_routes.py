from fastapi import APIRouter

from app.bass.interaction import (
    JointGenerateRequest,
    JointGenerateResponse,
    generate_joint_candidates,
)
from app.bass.persistence import BassDatabase
from app.persistence.database import GrooveDatabase

router = APIRouter(prefix="/api/v1/interaction", tags=["interaction"])
bass_db = BassDatabase()
groove_db = GrooveDatabase()


@router.post("/generate", response_model=JointGenerateResponse)
def generate(request: JointGenerateRequest) -> JointGenerateResponse:
    response = generate_joint_candidates(request, bass_db.preference_summary())
    for candidate in response.candidates:
        groove_db.save_generation(candidate.groove_pattern)
        bass_db.save_generation(candidate.bass_pattern)
    return response


@router.get("/capabilities")
def capabilities() -> dict:
    return {
        "modes": ["follow", "negotiate", "co_create"],
        "smallest_joint_modification": True,
        "shared_complexity_budget": True,
        "lock_preservation": True,
    }
