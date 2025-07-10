from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Dict
from datetime import datetime

from . import models
from .db import get_db, User, Game, init_db
from .auth import (
    get_password_hash, authenticate_user, create_access_token, get_current_user
)

router = APIRouter()

active_websockets: Dict[int, List[WebSocket]] = {}  # For game_id: [websockets]


# PUBLIC_INTERFACE
@router.post("/auth/register", summary="Register a new user", response_model=models.UserRead, tags=["auth"])
def register_user(user_data: models.UserCreate, db: Session = Depends(get_db)):
    """Register a new user. Returns basic user info."""
    user = db.query(User).filter(
        (User.username == user_data.username) | (User.email == user_data.email)
    ).first()
    if user:
        raise HTTPException(status_code=400, detail="Username or email already registered.")
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return models.UserRead.from_orm(db_user)


# PUBLIC_INTERFACE
@router.post("/auth/token", summary="Login and get JWT access token", response_model=models.Token, tags=["auth"])
def login(form_data: models.UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return JWT token."""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials"
        )
    access_token = create_access_token({"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


# PUBLIC_INTERFACE
@router.get("/users/me", response_model=models.UserRead, summary="Get current logged-in user", tags=["auth"])
def read_users_me(current_user: User = Depends(get_current_user)):
    """Get details for the currently authenticated user."""
    return {"id": current_user.id, "username": current_user.username}


# --------- GAME ROUTES ----------

def empty_ttt_board():
    return [["", "", ""], ["", "", ""], ["", "", ""]]


def game_result(board):
    # Check rows, cols, diagonals
    for i in range(3):
        if board[i][0] and all(board[i][j] == board[i][0] for j in range(3)):
            return board[i][0]
        if board[0][i] and all(board[j][i] == board[0][i] for j in range(3)):
            return board[0][i]
    if board[0][0] and all(board[i][i] == board[0][0] for i in range(3)):
        return board[0][0]
    if board[0][2] and all(board[i][2-i] == board[0][2] for i in range(3)):
        return board[0][2]
    if all(cell for row in board for cell in row):
        return "draw"
    return None


# PUBLIC_INTERFACE
@router.post("/games/", summary="Create a new game", response_model=models.GameState, tags=["game"])
def create_game(
    game_create: models.GameCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new game (PvP if opponent username provided, else AI/random)."""
    if game_create.opponent_username:
        opponent = db.query(User).filter(User.username == game_create.opponent_username).first()
        if not opponent or opponent.id == current_user.id:
            raise HTTPException(status_code=400, detail="Invalid opponent.")
        player_x, player_o = current_user, opponent
    else:
        # For now random (just same user vs themselves - can extend for AI)
        player_x, player_o = current_user, current_user
    new_game = Game(
        player_x_id=player_x.id,
        player_o_id=player_o.id,
        board_state=empty_ttt_board(),
        turn=player_x.username,
        status="active"
    )
    db.add(new_game)
    db.commit()
    db.refresh(new_game)
    return _game_to_state(new_game, db)


def _game_to_state(game: Game, db: Session) -> models.GameState:
    player_x = db.query(User).get(game.player_x_id)
    player_o = db.query(User).get(game.player_o_id)
    return models.GameState(
        game_id=game.id,
        board=game.board_state,
        players=[player_x.username, player_o.username],
        next_turn=game.turn,
        winner=game.winner,
        is_draw=game.is_draw,
        status=game.status
    )


# PUBLIC_INTERFACE
@router.get("/games/{game_id}/state", summary="Get current state of a game", response_model=models.GameState, tags=["game"])
def get_game_state(game_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get the full state of a game (board, players, turn, etc.)."""
    game = db.query(Game).get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    # Only allow users to view their own games by default
    if current_user.id not in {game.player_x_id, game.player_o_id}:
        raise HTTPException(status_code=403, detail="Not your game")
    return _game_to_state(game, db)


# PUBLIC_INTERFACE
@router.post("/games/{game_id}/move", summary="Make a move in a game", response_model=models.GameState, tags=["game"])
def make_move(game_id: int, move: models.MoveRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Submit a move in a Tic Tac Toe game."""
    game = db.query(Game).get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.status != "active":
        raise HTTPException(status_code=400, detail="Game finished")
    if current_user.username != game.turn:
        raise HTTPException(status_code=400, detail="Not your turn")
    if current_user.id not in {game.player_x_id, game.player_o_id}:
        raise HTTPException(status_code=403, detail="Not your game")

    # Validate move
    if not (0 <= move.row <= 2 and 0 <= move.col <= 2):
        raise HTTPException(status_code=400, detail="Cell out of bounds")
    board = game.board_state
    if board[move.row][move.col]:
        raise HTTPException(status_code=400, detail="Cell already played")
    symbol = "X" if current_user.id == game.player_x_id else "O"
    board[move.row][move.col] = symbol
    game.board_state = board

    # Check win
    result = game_result(board)
    if result == symbol:
        game.status = "finished"
        game.winner = current_user.username
        game.finished_at = datetime.utcnow()
        game.is_draw = False
    elif result == "draw":
        game.status = "finished"
        game.winner = None
        game.finished_at = datetime.utcnow()
        game.is_draw = True
    else:
        # Switch turn
        opp_username = db.query(User).get(game.player_o_id if current_user.id == game.player_x_id else game.player_x_id).username
        game.turn = opp_username

    db.commit()
    db.refresh(game)

    state = _game_to_state(game, db)
    # Broadcast via websocket if any
    _broadcast_game(game_id, state.dict())
    return state


def _broadcast_game(game_id: int, state: dict):
    clients = active_websockets.get(game_id)
    if clients:
        for ws in clients[:]:
            try:
                import asyncio
                asyncio.create_task(ws.send_json(state))
            except Exception:
                try:
                    clients.remove(ws)
                except Exception:
                    pass


# PUBLIC_INTERFACE
@router.get("/games/me/history", summary="Get user's game history", response_model=List[models.GameHistoryItem], tags=["game"])
def get_my_game_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """List recent games played by the user with result (win/loss/draw)."""
    games = (
        db.query(Game)
        .filter((Game.player_x_id == current_user.id) | (Game.player_o_id == current_user.id))
        .order_by(Game.created_at.desc())
        .limit(20)
        .all()
    )
    out = []
    for game in games:
        if game.status != "finished":
            continue
        if game.is_draw:
            result = "draw"
        elif game.winner == current_user.username:
            result = "win"
        else:
            result = "loss"
        opponent = db.query(User).get(game.player_o_id if game.player_x_id == current_user.id else game.player_x_id).username
        out.append(
            models.GameHistoryItem(
                game_id=game.id,
                opponent=opponent,
                result=result,
                timestamp=game.finished_at or game.created_at
            )
        )
    return out


# PUBLIC_INTERFACE
@router.get("/scoreboard", summary="Leaderboard by wins", response_model=List[models.ScoreboardEntry], tags=["scoreboard"])
def get_scoreboard(db: Session = Depends(get_db)):
    """Leaderboard, sorted by wins."""
    from sqlalchemy import func
    # All finished games, leaderboard of top 10 users.
    win_counts = (
        db.query(User.username.label("username"),
                 func.count(Game.id).filter(Game.status == "finished", Game.winner == User.username).label("wins"),
                 func.count(Game.id).filter(Game.status == "finished", Game.winner != User.username, Game.is_draw == False).label("losses"),
                 func.count(Game.id).filter(Game.status == "finished", Game.is_draw == True).label("draws"))
        .outerjoin(Game, ((Game.player_x_id == User.id) | (Game.player_o_id == User.id)))
        .group_by(User.id)
        .order_by(func.count(Game.id).filter(Game.status == "finished", Game.winner == User.username).desc())
        .limit(10)
        .all()
    )
    return [
        models.ScoreboardEntry(
            username=row.username or "",
            wins=row.wins or 0,
            losses=row.losses or 0,
            draws=row.draws or 0
        ) for row in win_counts
    ]


# PUBLIC_INTERFACE
@router.websocket("/ws/games/{game_id}")
async def game_ws(websocket: WebSocket, game_id: int):
    """WebSocket connection for live updates of a particular game."""
    await websocket.accept()
    clients = active_websockets.setdefault(game_id, [])
    clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients.remove(websocket)
    except Exception:
        try:
            clients.remove(websocket)
        except Exception:
            pass


@router.on_event("startup")
def startup_event():
    """Initialize DB tables if needed at app startup."""
    init_db()
