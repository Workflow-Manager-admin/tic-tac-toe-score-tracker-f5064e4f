from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field

# PUBLIC_INTERFACE
class UserCreate(BaseModel):
    """Model for user registration data."""
    username: str = Field(..., description="Unique username for the user")
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=6, description="User's password (min 6 chars)")


# PUBLIC_INTERFACE
class UserLogin(BaseModel):
    """Model for user login request."""
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


# PUBLIC_INTERFACE
class Token(BaseModel):
    """Model for returning JWT token."""
    access_token: str = Field(..., description="Access token")
    token_type: str = Field(..., description="Type of token (bearer)")


# PUBLIC_INTERFACE
class UserRead(BaseModel):
    """User readout without sensitive info."""
    id: int
    username: str

    class Config:
        orm_mode = True


# PUBLIC_INTERFACE
class GameCreate(BaseModel):
    """Request model to start a new game."""
    opponent_username: Optional[str] = Field(None, description="(Optional) Username of opponent for PvP; blank for random or AI.")


# PUBLIC_INTERFACE
class MoveRequest(BaseModel):
    """Request model for making a move."""
    game_id: int = Field(..., description="Game ID")
    row: int = Field(..., ge=0, le=2, description="Row index of move (0-2)")
    col: int = Field(..., ge=0, le=2, description="Column index of move (0-2)")


# PUBLIC_INTERFACE
class GameState(BaseModel):
    """Game state representation."""
    game_id: int
    board: List[List[str]]
    players: List[str]
    next_turn: str
    winner: Optional[str]
    is_draw: bool
    status: str  # active, finished, etc.

    class Config:
        orm_mode = True


# PUBLIC_INTERFACE
class GameHistoryItem(BaseModel):
    """Game summary for history API."""
    game_id: int
    opponent: str
    result: str  # "win", "loss", "draw"
    timestamp: datetime

    class Config:
        orm_mode = True


# PUBLIC_INTERFACE
class ScoreboardEntry(BaseModel):
    """Scoreboard leaderboard entry."""
    username: str
    wins: int
    losses: int
    draws: int

    class Config:
        orm_mode = True
