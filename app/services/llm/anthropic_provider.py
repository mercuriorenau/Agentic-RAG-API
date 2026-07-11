from typing import Any

from anthropic import AsyncAnthropic

from app.core.config import Settings, get_settings
from app.services.llm.base import ChatMessage, ChatResult, ToolCall, ToolSpec


class AnthropicProvider:
    def __init__(self, settings: Settings | None = None, model_name: str | None = None) -> None:
        self.settings = settings or get_settings()
        self.model_name = model_name or self.settings.anthropic_chat_model
        self.client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)

    async def chat_with_tools(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec],
        *,
        temperature: float = 0.2,
    ) -> ChatResult:
        system_parts = [m.content or "" for m in messages if m.role == "system" and m.content]
        conversation = [_to_anthropic_message(m) for m in messages if m.role != "system"]

        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "max_tokens": 2048,
            "messages": conversation,
            "temperature": temperature,
        }
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)
        if tools:
            kwargs["tools"] = [_to_anthropic_tool(tool) for tool in tools]

        response = await self.client.messages.create(**kwargs)

        content_text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                content_text_parts.append(block.text)
            elif block.type == "tool_use":
                arguments = block.input if isinstance(block.input, dict) else {}
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=arguments))

        content = "\n".join(content_text_parts).strip() or None
        return ChatResult(content=content, tool_calls=tool_calls)


def _to_anthropic_tool(tool: ToolSpec) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.parameters,
    }


def _to_anthropic_message(message: ChatMessage) -> dict[str, Any]:
    if message.role == "tool":
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id or "",
                    "content": message.content or "",
                }
            ],
        }

    if message.role == "assistant" and message.tool_calls:
        content: list[dict[str, Any]] = []
        if message.content:
            content.append({"type": "text", "text": message.content})
        for call in message.tool_calls:
            content.append(
                {
                    "type": "tool_use",
                    "id": call.id,
                    "name": call.name,
                    "input": call.arguments,
                }
            )
        return {"role": "assistant", "content": content}

    return {"role": message.role, "content": message.content or ""}
