# HTTP endpoints. Each file is one part of the product; they only move data in and out of the database
# and call the agents (agents/) or the maths checker (maths/).

from fastapi import Depends

from app.ai.models import AiModels
from app.config import Settings, getSettings


def getAi(settings: Settings = Depends(getSettings)) -> AiModels:
    """The AI models. Tests replace this with a fake."""
    return AiModels(settings)
