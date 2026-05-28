"""
LLM router — chat + rationale endpoints.

POST /v1/recommendations/{rec_id}/chat       — ask-the-planner chat
POST /v1/recommendations/{rec_id}/rationale  — regenerate LLM rationale
"""
from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.dependencies import CurrentUser, get_current_user
from app.llm import chat as chat_service
from app.llm import rationale as rationale_service
from app.recommendations import service as rec_service

logger = logging.getLogger(__name__)
router = APIRouter()         # mounted under /v1/recommendations
general_router = APIRouter() # mounted under /v1/chat — for the floating bot

UserDep = Annotated[CurrentUser, Depends(get_current_user)]


class ChatRequest(BaseModel):
    message: str
    history: Optional[list[dict[str, str]]] = None


class GeneralChatRequest(BaseModel):
    """For the floating chatbot — recId is optional context."""
    message: str
    rec_id: Optional[str] = None
    history: Optional[list[dict[str, str]]] = None


class ChatResponse(BaseModel):
    reply: str
    recId: Optional[str] = None


class RationaleResponse(BaseModel):
    recId: str
    rationale: str


@router.post("/{rec_id}/chat", response_model=ChatResponse,
             summary="Ask-the-planner chat (Q2.2)")
async def chat_endpoint(
    rec_id: str,
    body: ChatRequest,
    _user: UserDep,
) -> ChatResponse:
    rec = await rec_service.get_one(rec_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Recommendation not found")

    reply = await chat_service.chat(
        rec_id=rec_id,
        user_message=body.message,
        conversation_history=body.history,
    )
    return ChatResponse(reply=reply, recId=rec_id)


@router.post("/{rec_id}/rationale", response_model=RationaleResponse,
             summary="Regenerate LLM rationale (Q2.2)")
async def rationale_endpoint(
    rec_id: str,
    _user: UserDep,
) -> RationaleResponse:
    rec = await rec_service.get_one(rec_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Recommendation not found")

    text = await rationale_service.generate_rationale(rec)
    return RationaleResponse(recId=rec_id, rationale=text)


# ── General chat endpoint for the floating bot ───────────────────────────────

@general_router.post("", response_model=ChatResponse,
                     summary="General planner-assistant chat (floating bot)")
async def general_chat_endpoint(
    body: GeneralChatRequest,
    _user: UserDep,
) -> ChatResponse:
    """
    Conversational entry point for the floating ChatBot.

    rec_id is optional context — when the planner is on a Recommendation
    Detail page the UI passes it in so the LLM has full per-rec context.
    When absent (executive dashboard, list view, etc.), the LLM gets a
    queue summary and answers general questions.
    """
    reply = await chat_service.chat(
        rec_id=body.rec_id,
        user_message=body.message,
        conversation_history=body.history,
    )
    return ChatResponse(reply=reply, recId=body.rec_id)
