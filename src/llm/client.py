"""
LLM client abstraction layer.

Wraps OpenAI (or any provider) with retry logic, timeouts, and
structured output support.
"""

import json
import logging
from typing import Optional

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    LLM client with retry logic and structured output support.

    Uses OpenAI by default, but the interface is provider-agnostic.
    """

    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=lambda retry_state: logger.warning(
            "LLM call failed (attempt %d), retrying: %s",
            retry_state.attempt_number,
            retry_state.outcome.exception(),
        ),
    )
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """
        Generate a text response from the LLM.

        Args:
            system_prompt: System-level instructions.
            user_prompt: The actual content/question.
            temperature: Sampling temperature (lower = more deterministic).
            max_tokens: Maximum response length.

        Returns:
            The generated text response.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content
        logger.debug(
            "LLM response: model=%s, tokens=%d/%d",
            self.model,
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
        )
        return content

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((Exception,)),
    )
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> dict:
        """
        Generate a structured JSON response from the LLM.

        Uses OpenAI's JSON mode for reliable structured output.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        logger.debug(
            "LLM JSON response: model=%s, tokens=%d/%d",
            self.model,
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
        )
        return json.loads(content)
