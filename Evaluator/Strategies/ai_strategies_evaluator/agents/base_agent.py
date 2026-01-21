#  Drakkar-Software OctoBot-Tentacles
#  Copyright (c) Drakkar-Software, All rights reserved.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3.0 of the License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library.
import typing
import json
import logging
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """Abstract base class for LLM-powered agents with common configuration and functionality."""

    DEFAULT_MODEL = None
    DEFAULT_MAX_TOKENS = 10000
    DEFAULT_TEMPERATURE = 0.3
    MAX_RETRIES = 3

    def __init__(self, name: str, model=None, max_tokens=None, temperature=None):
        self.name = name
        self.model = model or self.DEFAULT_MODEL
        self.max_tokens = max_tokens or self.DEFAULT_MAX_TOKENS
        self.temperature = temperature or self.DEFAULT_TEMPERATURE
        self.evaluator_type = None  # Optional: associated evaluator type
        self._custom_prompt = None
        self.logger = logging.getLogger(f"[Agent][{self.name}]")

    @property
    def prompt(self) -> str:
        """Get the agent's prompt, allowing override via config."""
        return self._custom_prompt or self._get_default_prompt()

    @prompt.setter
    def prompt(self, value: str):
        """Allow custom prompt override."""
        self._custom_prompt = value

    @abstractmethod
    def _get_default_prompt(self) -> str:
        """Return the default prompt for this agent type."""
        pass

    @abstractmethod
    async def execute(self, input_data, llm_service) -> typing.Any:
        """Execute the agent's primary function."""
        pass

    async def _call_llm(self, messages, llm_service, json_output=True, response_schema=None):
        """
        Common LLM calling method with error handling and automatic retries.
        
        Args:
            messages: List of message dicts with 'role' and 'content'.
            llm_service: The LLM service instance.
            json_output: Whether to parse response as JSON.
            response_schema: Optional Pydantic model or JSON schema for structured output.
            
        Returns:
            Parsed JSON dict or raw string response.
            
        Raises:
            RuntimeError: If all retries are exhausted.
        """
        last_exception = None
        
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = await llm_service.get_completion(
                    messages=messages,
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    json_output=json_output,
                    response_schema=response_schema,
                )
                if json_output:
                    return json.loads(response.strip())
                return response.strip()
            except (json.JSONDecodeError, ValueError, KeyError, AttributeError) as e:
                last_exception = e
                if attempt < self.MAX_RETRIES:
                    self.logger.warning(
                        f"LLM call failed on attempt {attempt}/{self.MAX_RETRIES} for agent {self.name}: {str(e)}. Retrying..."
                    )
                else:
                    self.logger.error(
                        f"LLM call failed on final attempt {attempt}/{self.MAX_RETRIES} for agent {self.name}: {str(e)}"
                    )
        
        # All retries exhausted
        raise RuntimeError(f"LLM call failed for agent {self.name} after {self.MAX_RETRIES} retries: {str(last_exception)}")
