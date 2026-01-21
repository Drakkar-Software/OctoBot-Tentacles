#  Drakkar-Software OctoBot
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

"""
Base agent class for AI trading mode agents.
"""
import logging
import json
import typing
from abc import ABC, abstractmethod

from tentacles.Trading.Mode.ai_trading_mode.agents.state import AIAgentState


class BaseAgent(ABC):
    """
    Abstract base class for AI trading mode agents.
    Provides common LLM calling functionality - agents only define prompts.
    """
    
    AGENT_NAME: str = "BaseAgent"
    AGENT_VERSION: str = "1.0.0"
    DEFAULT_MODEL = None
    DEFAULT_MAX_TOKENS = 10000
    DEFAULT_TEMPERATURE = 0.3
    MAX_RETRIES = 3
    
    def __init__(self, 
                 name: typing.Optional[str] = None, 
                 model: typing.Optional[str] = None, 
                 max_tokens: typing.Optional[int] = None, 
                 temperature: typing.Optional[float] = None):
        """
        Initialize the agent.
        
        Args:
            name: Agent name for logging.
            model: LLM model to use.
            max_tokens: Maximum tokens for response.
            temperature: Temperature for LLM randomness.
        """
        self.name = name or self.AGENT_NAME
        self.model = model or self.DEFAULT_MODEL
        self.max_tokens = max_tokens or self.DEFAULT_MAX_TOKENS
        self.temperature = temperature or self.DEFAULT_TEMPERATURE
        self.logger = logging.getLogger(f"[AITrading][{self.name}]")
        self._custom_prompt = None
    
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
    async def execute(self, input_data: typing.Any, llm_service) -> typing.Any:
        """
        Execute the agent's primary function.
        
        Args:
            input_data: The input data for the agent to process.
            llm_service: The LLM service instance.
            
        Returns:
            The agent's output.
        """
        pass
    
    async def _call_llm(self, messages: list, llm_service, json_output: bool = True, response_schema=None) -> typing.Any:
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
            Exception: If all retries are exhausted.
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
        raise Exception(f"LLM call failed for agent {self.name} after {self.MAX_RETRIES} retries: {str(last_exception)}")
    
    def format_strategy_data(self, strategy_data: dict) -> str:
        """Format strategy data for inclusion in prompts."""
        if not strategy_data:
            return "No strategy data available."
        return json.dumps(strategy_data, indent=2, default=str)
    
    def format_portfolio(self, portfolio: dict) -> str:
        """Format portfolio data for inclusion in prompts."""
        if not portfolio:
            return "No portfolio data available."
        return json.dumps(portfolio, indent=2, default=str)
    
    def format_orders(self, orders: dict) -> str:
        """Format orders data for inclusion in prompts."""
        if not orders:
            return "No orders data available."
        return json.dumps(orders, indent=2, default=str)
