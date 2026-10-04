import os
import uuid
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from livekit import api
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="CommunityConnect AI")


class TokenRequest(BaseModel):
    language: Literal["en", "hi"] = "en"


@app.post("/api/token")
def create_token(request: TokenRequest | None = None) -> dict[str, str]:
    """Give the browser a short-lived token to join a fresh LiveKit room. The voice agent
    worker joins every new room automatically and reads the chosen language from the
    participant's attributes."""
    language = request.language if request else "en"
    url = os.getenv("LIVEKIT_URL")
    key = os.getenv("LIVEKIT_API_KEY")
    secret = os.getenv("LIVEKIT_API_SECRET")
    if not (url and key and secret):
        raise HTTPException(503, "LiveKit is not configured on the server.")

    room = f"cc-{uuid.uuid4().hex[:8]}"
    identity = f"user-{uuid.uuid4().hex[:8]}"
    token = (
        api.AccessToken(key, secret)
        .with_identity(identity)
        .with_attributes({"language": language})
        .with_grants(api.VideoGrants(room_join=True, room=room))
        .to_jwt()
    )
    return {"url": url, "token": token, "room": room, "identity": identity, "language": language}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


frontend_dist = Path(__file__).with_name("frontend") / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
