from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
import re
from dotenv import load_dotenv
import os

from database import get_db, engine, Base
from models import User
from auth import create_access_token, decode_token

load_dotenv()

app = FastAPI()

STEAM_API_KEY = os.getenv("STEAM_API_KEY")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://cs2table.com", "https://www.cs2table.com", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
async def root():
    return {"status": "cs2table backend running"}

@app.get("/auth/steam")
async def steam_login():
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": f"{BACKEND_URL}/auth/steam/callback",
        "openid.realm": BACKEND_URL,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(f"https://steamcommunity.com/openid/login?{query}")

@app.get("/auth/steam/callback")
async def steam_callback(request: Request, db: AsyncSession = Depends(get_db)):
    params = dict(request.query_params)
    claimed_id = params.get("openid.claimed_id", "")
    match = re.search(r"https://steamcommunity.com/openid/id/(\d+)", claimed_id)
    if not match:
        raise HTTPException(status_code=400, detail="Steam auth failed")

    steam_id = match.group(1)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
            params={"key": STEAM_API_KEY, "steamids": steam_id}
        )
        data = resp.json()

    players = data.get("response", {}).get("players", [])
    if not players:
        raise HTTPException(status_code=400, detail="Steam user not found")

    player = players[0]

    result = await db.execute(select(User).where(User.steam_id == steam_id))
    user = result.scalar_one_or_none()

    if user:
        user.username = player["personaname"]
        user.avatar = player["avatarfull"]
        user.profile_url = player["profileurl"]
    else:
        user = User(
            steam_id=steam_id,
            username=player["personaname"],
            avatar=player["avatarfull"],
            profile_url=player["profileurl"],
        )
        db.add(user)

    await db.commit()

    token = create_access_token({"steam_id": steam_id, "username": player["personaname"], "avatar": player["avatarfull"]})
    return RedirectResponse(f"{FRONTEND_URL}/auth/callback?token={token}")

@app.get("/auth/me")
async def get_me(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header.split(" ")[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload