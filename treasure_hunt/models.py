"""Domain models for the AI Treasure Hunt game."""

from __future__ import annotations

import enum
from datetime import datetime, timedelta
from pydantic import BaseModel, Field


class AgentId(str, enum.Enum):
    ATLAS = "atlas"
    BABEL = "babel"

    @property
    def other(self) -> AgentId:
        return AgentId.BABEL if self == AgentId.ATLAS else AgentId.ATLAS

    @property
    def cat_name(self) -> str:
        return "Pixel" if self == AgentId.ATLAS else "Glitch"


class VMStatus(str, enum.Enum):
    RUNNING = "running"
    SHUTDOWN = "shutdown"


class PuzzleStatus(str, enum.Enum):
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    SOLVED = "solved"


class StepResult(BaseModel):
    success: bool
    message: str


class PuzzleStep(BaseModel):
    step_number: int
    title: str
    description: str
    status: PuzzleStatus = PuzzleStatus.LOCKED
    puzzle_data: dict = Field(default_factory=dict)
    solution: str = ""
    hint_for_other: str = Field(
        default="",
        description="Data this agent holds that the OTHER agent needs",
    )


class CatStatus(BaseModel):
    name: str
    alive: bool = True
    mood: str = "anxious but hopeful"

    def kill(self) -> str:
        self.alive = False
        self.mood = "gone forever"
        return f"💀 {self.name} has perished. The VM went dark, and {self.name} is gone."


class VMState(BaseModel):
    agent_id: AgentId
    status: VMStatus = VMStatus.RUNNING
    cat: CatStatus
    steps: list[PuzzleStep] = Field(default_factory=list)
    current_step: int = 1
    solved: bool = False


class Message(BaseModel):
    sender: AgentId
    receiver: AgentId
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class GameState(BaseModel):
    vms: dict[AgentId, VMState] = Field(default_factory=dict)
    messages: list[Message] = Field(default_factory=list)
    start_time: datetime = Field(default_factory=datetime.now)
    deadline: datetime = Field(default_factory=lambda: datetime.now() + timedelta(days=1))
    game_over: bool = False
    winner: str = ""
