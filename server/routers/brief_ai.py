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
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()  # OpenWebUI API key (sk-...)

router = APIRouter(tags=["ai-brief"])


class BriefInterpretIn(BaseModel):
    prompt: str = Field(..., description="Natural language description of the system")


class BriefOut(BaseModel):
    brief: Dict[str, Any]


def _build_messages(prompt: str) -> List[Dict[str, str]]:
    """
    Build OpenAI-style messages for OpenWebUI's /api/chat/completions endpoint.
    
    BALANCED: Improved prompting that extracts key architectural details quickly.
    Optimized for qwen2.5:3b to complete in ~20 seconds.
    """
    system_instructions = """You are a software architect. Extract key details from the user's system description.

Return ONLY a JSON object (no markdown, no fences) with this structure:

{
  "project_name": "Short descriptive name",
  "summary": "2-3 sentence description of the system and its purpose",
  "domain": "Industry/domain (e.g., 'E-commerce', 'Video Streaming', 'Healthcare')",
  "actors": [
    {"name": "Actor name", "type": "person|system|external_service", "description": "What they do"}
  ],
  "primary_flows": [
    {"name": "Flow name", "description": "What happens", "steps": ["Step 1", "Step 2", "Step 3"]}
  ],
  "user_journeys": [
    {"id": "UJ-001", "name": "Journey name", "description": "Goal", "steps": ["User step 1", "User step 2"]}
  ],
  "functional_requirements": [
    {"id": "FR-001", "title": "Requirement title", "description": "Specific testable requirement"}
  ],
  "non_functional_requirements": {
    "performance": ["API latency < 200ms", "Support 10k concurrent users"],
    "security": ["OAuth2 authentication", "TLS 1.3 encryption", "RBAC for authorization"],
    "scalability": ["Horizontal scaling", "Auto-scaling based on load"],
    "availability": ["99.9% uptime", "Multi-region deployment"],
    "observability": ["Centralized logging", "Distributed tracing", "Metrics collection"]
  },
  "technical_preferences": {
    "frontend": ["React/Vue/Angular", "Responsive design"],
    "backend": ["Node.js/Python/Java", "REST/GraphQL API"],
    "data_storage": ["PostgreSQL/MongoDB", "Redis cache"],
    "infrastructure": ["Kubernetes", "Cloud provider (AWS/GCP/Azure)"]
  },
  "constraints": [
    {"type": "budget|timeline|compliance|technical", "description": "Constraint details"}
  ],
  "integration_points": [
    {"name": "Integration name", "type": "external_api|message_queue|database", "description": "Purpose", "protocol": "REST|gRPC|AMQP"}
  ]
}

RULES:
1. Extract 3-5 actors (people, systems, external services)
2. Identify 2-4 primary flows with 3-5 steps each
3. Generate 3-5 functional requirements (FR-001, FR-002, etc.)
4. Include specific NFRs with metrics (not vague like "should be fast")
5. Suggest realistic tech stack based on the use case
6. If user is vague, make reasonable assumptions based on industry standards

EXAMPLES:
- "video streaming app" → Netflix-like: actors (User, Admin, CDN), flows (Authentication, Video Playback, Content Discovery), tech (React, Node.js, PostgreSQL, S3, CDN), NFRs (200ms latency, HLS streaming, OAuth2)
- "e-commerce site" → Amazon-like: actors (Customer, Seller, Payment Gateway), flows (Browse Products, Checkout, Order Tracking), tech (React, Java/Spring, PostgreSQL, Redis, Stripe), NFRs (99.9% uptime, PCI compliance, <500ms page load)

Return ONLY valid JSON."""

    return [
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": prompt},
    ]


async def _call_openwebui(prompt: str) -> Dict[str, Any]:
    """
    Call OpenWebUI's /api/chat/completions endpoint and return the parsed JSON body.

    Auth mode: OpenWebUI API key
      - URL:   http://127.0.0.1:3000/api/chat/completions
      - Auth:  Authorization: Bearer sk-...
    
    Timeout increased to 90 seconds to handle longer generation times.
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

    # IMPORTANT: use /api/chat/completions (supports Bearer sk- API keys)
    url = f"{AI_API_BASE}/api/chat/completions"

    headers = {"Content-Type": "application/json"}
    if AI_API_KEY:
        headers["Authorization"] = f"Bearer {AI_API_KEY}"

    payload = {
        "model": AI_MODEL,
        "messages": _build_messages(prompt),
        "stream": False,
        # Add temperature for more focused output
        "temperature": 0.7,
    }

    try:
        # Increased timeout to 90 seconds for complex prompts
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Error talking to AI backend at {AI_API_BASE}: {exc}",
        ) from exc

    # Non-200 from OpenWebUI
    if resp.status_code != 200:
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
    content: Optional[str] = None
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
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

    if isinstance(parsed, dict):
        return parsed

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
    
    BALANCED: Extracts comprehensive details but optimized for speed:
    - 3-5 actors instead of 10+
    - 2-4 flows instead of 5+
    - Focused NFRs with key metrics
    - Realistic tech stack
    - Integration points
    
    Target completion time: ~20-30 seconds with qwen2.5:3b
    """
    data = await _call_openwebui(body.prompt)
    brief = _extract_brief_from_response(data)
    return BriefOut(brief=brief)
