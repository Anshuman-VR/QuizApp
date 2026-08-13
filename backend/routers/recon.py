from fastapi import APIRouter, Request, Response
from backend.schemas import ReconRequest
from backend.config import settings
from jose import jwt
import datetime
import os

router = APIRouter()
log_path = os.path.join(os.path.dirname(__file__), '..', 'easter_egg.log')

@router.post("/recon")
async def recon_endpoint(req: ReconRequest, request: Request, response: Response):
    if req.flag != settings.EASTER_EGG_SECRET:
        response.status_code = 418
        return {"message": "Wrong key. The flag format is ACE{...}. Keep digging."}
        
    # Attempt to identify the student from cookie
    token = request.cookies.get("session")
    reg_no = "unknown"
    if token:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
            reg_no = payload.get("sub", "unknown")
        except:
            pass
            
    # Log it
    ts = datetime.datetime.utcnow().isoformat()
    ip = request.client.host
    ua = request.headers.get("user-agent", "")
    
    with open(log_path, 'a') as f:
        f.write(f'{{ "ts": "{ts}", "reg_no": "{reg_no}", "ip": "{ip}", "ua": "{ua}" }}\n')
        
    return {
        "message": "Impressive. We see you. 👁️",
        "flag": settings.EASTER_EGG_FLAG,
        "note": "This interaction has been logged. Mention this at the interview. 😈"
    }

@router.get("/recon")
async def recon_get(response: Response):
    response.status_code = 405
    return {"error": "Method Not Allowed", "hint": "Try POST. Bring a gift."}
