"""Define the state structures for the agent."""

from __future__ import annotations

from dataclasses import dataclass
from langgraph.graph import MessagesState


class State(MessagesState):
    """Simple state."""
    requested_agent: str = None
