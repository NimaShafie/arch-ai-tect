# server/services/llm_client.py
import json
from pathlib import Path
import httpx

from server.core.config import OPENWEBUI_API_URL


class RequirementsLLMError(Exception):
    """Raised when the LLM fails to return valid JSON."""
    pass


class RequirementsLLM:
    """
    Client wrapper for calling OpenWebUI's chat completions endpoint.
    This is now the standardized backend LLM interface for the Workbench.
    """

    def __init__(self, api_url: str | None = None):
        self.api_url = api_url or OPENWEBUI_API_URL
        if not self.api_url:
            raise RequirementsLLMError(
                "OPENWEBUI_API_URL is not configured. "
                "Please set it in your environment."
            )

        # Ensure prompt template exists
        self.template_path = Path("prompts/00_requirements_brief.md")
        if not self.template_path.exists():
            raise FileNotFoundError(
                "Missing prompt template: prompts/00_requirements_brief.md"
            )

        # Load system-level instructions for the LLM
        self.system_prompt = self.template_path.read_text()

    async def generate_brief(self, project_name: str, user_prompt: str) -> dict:
        """
        Sends the system prompt + user prompt to OpenWebUI,
        expects STRICT JSON as return value.
        """

        system_prompt = self.system_prompt.replace(
            "<<<PROJECT_NAME>>>", project_name
        )

        payload = {
            "model": "qwen2.5",
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
        }

        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(
                f"{self.api_url}/api/chat/completions",
                json=payload,
            )

        if r.status_code != 200:
            raise RequirementsLLMError(
                f"OpenWebUI error {r.status_code}: {r.text}"
            )

        try:
            message = r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            raise RequirementsLLMError(
                f"Malformed LLM response: {e}\nRaw: {r.text}"
            )

        # Parse strict JSON
        try:
            result = json.loads(message)
        except json.JSONDecodeError as e:
            raise RequirementsLLMError(
                f"LLM output is not valid JSON: {e}\nOutput:\n{message}"
            )

        return result
