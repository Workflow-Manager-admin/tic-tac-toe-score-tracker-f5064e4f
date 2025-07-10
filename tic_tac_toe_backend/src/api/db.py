import os
from sqlalchemy import (
    create_engine, Column, Integer, String, ForeignKey, DateTime, JSON, Boolean
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.sql import func
from dotenv import load_dotenv

# Load DB credentials from .env
load_dotenv()

DB_URL = os.environ.get("TIC_TAC_TOE_DATABASE_URL") or os.environ.get("MYSQL_URL")

# Create SQLAlchemy engine and sessionmaker
engine = create_engine(DB_URL, echo=False, pool_pre_ping=True, pool_recycle=280)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# PUBLIC_INTERFACE
class User(Base):
    """DB model for user."""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    hashed_password = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    games = relationship("Game", back_populates="player_x", foreign_keys="Game.player_x_id")
    games_as_o = relationship("Game", back_populates="player_o", foreign_keys="Game.player_o_id")


# PUBLIC_INTERFACE
class Game(Base):
    """DB model for TicTacToe game."""
    __tablename__ = "games"
    id = Column(Integer, primary_key=True, index=True)
    player_x_id = Column(Integer, ForeignKey("users.id"))
    player_o_id = Column(Integer, ForeignKey("users.id"))
    board_state = Column(JSON, nullable=False, default=[["", "", ""], ["", "", ""], ["", "", ""]])
    turn = Column(String(50), nullable=False)  # username whose turn it is
    status = Column(String(20), nullable=False, default="active")  # "active", "finished"
    winner = Column(String(50), nullable=True)
    is_draw = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    player_x = relationship("User", foreign_keys=[player_x_id], back_populates="games")
    player_o = relationship("User", foreign_keys=[player_o_id], back_populates="games_as_o")


def init_db():
    """Initialize all tables."""
    Base.metadata.create_all(bind=engine)
