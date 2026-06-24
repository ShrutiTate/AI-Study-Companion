from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, constr

from backend.services.preferences_service import get_language, set_language

router = APIRouter(prefix="/preferences", tags=["preferences"])

class PrefUpdate(BaseModel):
    user_id: constr(min_length=1)
    language_code: constr(min_length=2, max_length=5)

@router.get("/{user_id}", response_model=dict)
async def read_pref(user_id: str):
    lang = get_language(user_id)
    if not lang:
        raise HTTPException(status_code=404, detail="Preference not found")
    return {"user_id": user_id, "language_code": lang}

@router.post("/update")
async def update_pref(payload: PrefUpdate):
    set_language(payload.user_id, payload.language_code)
    return {"msg": "preference saved", "user_id": payload.user_id}
