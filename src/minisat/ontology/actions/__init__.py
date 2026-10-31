"""All actions of the ontology. ``default_registry()`` is what the runner, the API and the agent tools are built from."""
from __future__ import annotations

from ..runner import ActionRegistry
from . import commands, records

__all__ = ["default_registry"]


def default_registry() -> ActionRegistry:
    return ActionRegistry(commands.ACTIONS + records.ACTIONS)
