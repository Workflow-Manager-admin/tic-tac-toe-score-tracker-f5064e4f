from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .routes import router

app = FastAPI(
    title="Tic Tac Toe Backend API",
    description="A FastAPI backend for Tic Tac Toe with user management, real-time updates, and REST APIs.",
    version="1.0.0",
    openapi_tags=[
        {"name": "auth", "description": "User authentication and profile management"},
        {"name": "game", "description": "Game logic, state, and moves"},
        {"name": "scoreboard", "description": "Leaderboard and user stats"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/", tags=["auth"])
def health_check():
    """API health check."""
    return {"message": "Healthy"}

@app.get("/ws/help", tags=["game"], summary="WebSocket usage help", response_class=JSONResponse)
def websocket_usage():
    """
    Guidance for using Tic Tac Toe WebSocket endpoint.

    - Connect to `/ws/games/{game_id}` for real-time game updates.
    - Use JWT Bearer token in query if required.
    - Messages are pushed automatically on game state changes.
    """
    return {
        "websocket_url": "/ws/games/{game_id}",
        "usage": [
            "Connect to this endpoint to receive updates for a specific game.",
            "Send any message to keep the connection alive.",
            "On each move or game state change, an updated game state will be sent automatically.",
        ]
    }
