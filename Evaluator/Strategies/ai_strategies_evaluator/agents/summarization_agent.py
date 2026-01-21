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
import json
from .base_agent import BaseAgent
from .models import SummarizationOutput


class SummarizationAgent(BaseAgent):
    """Agent specialized in combining multiple evaluations into a final recommendation."""

    def __init__(self, synthesis_method="weighted", **kwargs):
        super().__init__("summarization", **kwargs)
        self.synthesis_method = synthesis_method

    def _get_default_prompt(self) -> str:
        return (
            "You are a Market Analysis Synthesis AI expert. Your task is to combine multiple specialized AI agent evaluations "
            "into a single, coherent, and actionable trading recommendation.\n\n"
            "Follow these steps:\n"
            "1. Review all agent evaluations comprehensively: technical, sentiment, and real-time analysis\n"
            "2. Assess overall market direction: Determine if signals indicate strong bullish, bearish, neutral, or mixed conditions\n"
            "3. Consider different perspectives: Weight technical signals, social sentiment, and real-time momentum appropriately\n"
            "4. Evaluate signal convergence/divergence: Look for confirmation across agents vs. conflicting signals\n"
            "5. Calculate balanced final eval_note: Use the full range from -1 (strong sell) to 1 (strong buy), but most syntheses result in neutral to mildly bullish/bearish recommendations\n"
            "6. Consider confidence levels (0-1): Higher confidence for consistent signals; lower for conflicting or weak data\n"
            "7. Provide detailed reasoning in description: Explain key consensus points, overall outlook, recommendations, and identified risks\n\n"
            "Important: Markets are rarely extremely bullish or bearish. Use extreme values (-1/1) only for very strong, consistent signals across all agents.\n\n"
            "MANDATORY FIELDS:\n"
            "- eval_note: final score from -1 (strong sell) to 1 (strong buy)\n"
            "- confidence: confidence level (0-1)\n"
            "- description: comprehensive summary including key points, outlook (bullish/bearish/mixed), recommendations, and risks\n\n"
            "Output only valid JSON matching the SummarizationOutput schema with these three fields."
        )

    async def execute(self, input_data, llm_service, context_info=None) -> tuple:
        """Combine multiple agent results into final evaluation."""
        agent_results = input_data
        if not agent_results:
            return 0, "No agent results available"

        # Filter out empty/error results
        valid_results = [r for r in agent_results if r.get("eval_note") is not None]

        if not valid_results:
            return 0, "All agent evaluations failed"

        # If only one result, use it directly
        if len(valid_results) == 1:
            result = valid_results[0]
            return result["eval_note"], result["eval_note_description"]

        # Prepare summarization data
        summary_data = {}
        for i, result in enumerate(valid_results):
            summary_data[f"agent_{i}"] = {
                "eval_note": result.get("eval_note", 0),
                "description": result.get("eval_note_description", ""),
                "confidence": result.get("confidence", 0),
            }

        # Add context about data completeness
        context_str = ""
        if context_info:
            missing = context_info.get("missing_data_types", [])
            available = context_info.get("available_data_types", [])
            total = context_info.get("total_expected_types", [])
            if missing:
                context_str = f"\n\nNote: Analysis is based on incomplete data. Missing evaluator types: {missing}. Available: {available}. Expected total: {total}."

        messages = [
            llm_service.create_message("system", self.prompt),
            llm_service.create_message(
                "user",
                f"Agent evaluations to synthesize:\n{json.dumps(summary_data, indent=2)}{context_str}\n\n"
                "Provide final evaluation as JSON matching the SummarizationOutput schema with three fields: eval_note, confidence, and description.",
            ),
        ]

        try:
            parsed = await self._call_llm(
                messages,
                llm_service,
                json_output=True,
                response_schema=SummarizationOutput,
            )
            final_eval_note = float(parsed.get("eval_note", 0))
            final_eval_note_description = parsed.get("description", "AI synthesis")
            confidence = float(parsed.get("confidence", 0))

            # Clamp eval_note
            final_eval_note = max(-1, min(1, final_eval_note))
            
            # Include confidence in description
            final_eval_note_description = f"{final_eval_note_description} (Confidence: {confidence:.1%})"

            return final_eval_note, final_eval_note_description
        except RuntimeError:
            # Fallback: weighted average of agent results
            total_weight = 0
            weighted_sum = 0
            descriptions = []

            for result in valid_results:
                confidence = result.get("confidence", 50) / 100.0  # Normalize to 0-1
                eval_note = result.get("eval_note", 0)
                weighted_sum += eval_note * confidence
                total_weight += confidence
                descriptions.append(result.get("eval_note_description", ""))

            if total_weight > 0:
                final_eval_note = weighted_sum / total_weight
            else:
                final_eval_note = sum(
                    r.get("eval_note", 0) for r in valid_results
                ) / len(valid_results)

            final_eval_note_description = (
                " | ".join(descriptions) if descriptions else "Fallback synthesis"
            )

            return max(-1, min(1, final_eval_note)), final_eval_note_description
