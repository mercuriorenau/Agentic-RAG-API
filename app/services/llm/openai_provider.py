import json
from typing import Any

from openai import AsyncOpenAI

from app.core.config import Settings, get_settings
from app.services.llm.base import ChatMessage, ChatResult, ToolCall, ToolSpec


class OpenAIProvider:
    def __init__(self, settings: Settings | None = None, model_name: str | None = None) -> None:
        self.settings = settings or get_settings()
        self.model_name = model_name or self.settings.chat_model
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)

    async def chat_with_tools(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec],
        *,
        temperature: float = 0.2,
    ) -> ChatResult:
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[_to_openai_message(message) for message in messages],
            tools=[_to_openai_tool(tool) for tool in tools] if tools else None,
            temperature=temperature,
        )
        choice = response.choices[0].message
        tool_calls: list[ToolCall] = []
        for call in choice.tool_calls or []:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                ToolCall(id=call.id, name=call.function.name, arguments=arguments)
            )
        return ChatResult(content=choice.content, tool_calls=tool_calls)


def _to_openai_tool(tool: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _to_openai_message(message: ChatMessage) -> dict[str, Any]:
    if message.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id or "",
            "content": message.content or "",
        }

    payload: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments),
                },
            }
            for call in message.tool_calls
        ]
    return payload
