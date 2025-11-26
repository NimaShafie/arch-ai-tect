# server/routers/brief_ai.py

import json
import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Environment configuration
AI_API_BASE = os.getenv("AI_API_BASE", "").rstrip("/")
AI_MODEL = os.getenv("AI_MODEL", "").strip()
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()  # optional


router = APIRouter(tags=["ai-brief"])


class BriefInterpretIn(BaseModel):
    prompt: str = Field(..., description="Natural language description of the system")


class BriefOut(BaseModel):
    brief: Dict[str, Any]


def _build_messages(prompt: str) -> List[Dict[str, str]]:
    """
    Build OpenAI-style messages for OpenWebUI's /api/chat/completions endpoint.
    """
    system_instructions = (
        "You are a senior software architect. The user will describe a software system. "
        "Return a SINGLE JSON object describing a 'requirements brief' for that system. "
        "DO NOT include Markdown or code fences. "
        "The JSON should have this shape:\n"
        "{\n"
        '  "project_name": string,\n'
        '  "summary": string,\n'
        '  "actors": [ { "name": string, "description": string } ],\n'
        '  "primary_flows": [ { "name": string, "description": string } ],\n'
        '  "non_functional": [ string ],\n'
        '  "tech_preferences": [ string ]\n'
        "}\n"
        "If the user is vague, make reasonable assumptions but keep them clearly labeled "
        "in the summary and flows."
    )

    return [
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": prompt},
    ]


async def _call_openwebui(prompt: str) -> Dict[str, Any]:
    """
    Call OpenWebUI's /api/chat/completions endpoint and return the parsed JSON body.
    """
    if not AI_API_BASE:
        raise HTTPException(
            status_code=503,
            detail="AI backend is not configured (AI_API_BASE is missing).",
        )
    if not AI_MODEL:
        raise HTTPException(
            status_code=503,
            detail="AI backend model is not configured (AI_MODEL is missing).",
        )

    url = f"{AI_API_BASE}/api/chat/completions"

    headers = {"Content-Type": "application/json"}
    if AI_API_KEY:
        headers["Authorization"] = f"Bearer {AI_API_KEY}"

    payload = {
        "model": AI_MODEL,
        "messages": _build_messages(prompt),
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Error talking to AI backend at {AI_API_BASE}: {exc}",
        ) from exc

    # Non-200 from OpenWebUI
    if resp.status_code != 200:
        # Try to surface OpenWebUI's error payload if JSON, otherwise raw text
        try:
            body = resp.json()
            body_str = json.dumps(body)
        except Exception:
            body_str = resp.text
        raise HTTPException(
            status_code=502,
            detail=f"AI backend returned HTTP {resp.status_code}: {body_str}",
        )

    try:
        return resp.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI backend returned non-JSON response: {exc}",
        ) from exc


def _extract_brief_from_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and normalize the 'brief' from an OpenAI-style chat completion response.

    We expect OpenWebUI's /api/chat/completions to return an OpenAI-compatible payload:
      { "choices": [ { "message": { "content": "..." } } ] }

    The content should be JSON matching our brief schema. If not, we fall back to a
    generic wrapper so the user still sees the raw text and can edit it.
    """
    # Try standard OpenAI-style shape
    content: Optional[str] = None
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        # If the shape is different, just dump the whole object
        return {
            "raw_response": data,
            "note": (
                "AI backend returned an unexpected payload shape. "
                "Please inspect raw_response and edit into a structured brief."
            ),
        }

    if not isinstance(content, str):
        return {
            "raw_response": data,
            "note": (
                "AI backend message content was not text. "
                "Please inspect raw_response and edit into a structured brief."
            ),
        }

    # Try to parse the content as JSON
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # Not JSON – wrap as raw text
        return {
            "project_name": "",
            "summary": "AI draft (unstructured text – please edit into JSON fields).",
            "actors": [],
            "primary_flows": [],
            "non_functional": [],
            "tech_preferences": [],
            "raw_text": content,
        }

    # If the model already returned the full brief object, just use it
    if isinstance(parsed, dict):
        return parsed

    # Anything else (e.g., list or string) gets wrapped
    return {
        "project_name": "",
        "summary": "AI draft (non-object JSON – please normalize).",
        "actors": [],
        "primary_flows": [],
        "non_functional": [],
        "tech_preferences": [],
        "raw_json": parsed,
    }


@router.post("/api/projects/{slug}/brief/interpret", response_model=BriefOut)
async def interpret_brief(slug: str, body: BriefInterpretIn) -> BriefOut:
    """
    Interpret a free-form requirements prompt into a structured brief using OpenWebUI.
    The slug is currently just passed through for logging/consistency; the brief itself
    is derived entirely from the prompt text.
    """
    # Call AI backend
    data = await _call_openwebui(body.prompt)

    # Normalize into our brief shape
    brief = _extract_brief_from_response(data)

    return BriefOut(brief=brief)
