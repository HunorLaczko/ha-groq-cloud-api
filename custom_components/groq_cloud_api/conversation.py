"""Conversation support for Groq Cloud."""

from __future__ import annotations

from collections.abc import Callable
import json
from typing import Any, Literal

import groq
from groq._types import NOT_GIVEN
from groq.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageToolCallParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionToolParam,
    ChatCompletionUserMessageParam,
)
from groq.types.chat.chat_completion_message_tool_call_param import Function
from groq.types.shared_params import FunctionDefinition
from voluptuous_openapi import convert

from homeassistant.components import conversation
from homeassistant.components.conversation import (
    AssistantContent,
    ConverseError,
    SystemContent,
    ToolResultContent,
    UserContent,
    async_get_result_from_chat_log,
    trace,
)
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, intent, llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.json import json_dumps

from . import GroqConfigEntry
from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_RETRIES,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    CONF_SUPPORTS_REASONING,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DOMAIN,
    LOGGER,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_RETRIES,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
)

# Max number of back and forth with the LLM to generate a response
MAX_TOOL_ITERATIONS = 10


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GroqConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    agent = GroqConversationEntity(config_entry)
    async_add_entities([agent])


def _format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> ChatCompletionToolParam:
    """Format tool specification."""
    tool_spec = FunctionDefinition(
        name=tool.name,
        parameters=convert(tool.parameters, custom_serializer=custom_serializer),
    )
    if tool.description:
        tool_spec["description"] = tool.description
    return ChatCompletionToolParam(type="function", function=tool_spec)


def _assistant_content_to_message(
    content: AssistantContent,
) -> ChatCompletionAssistantMessageParam:
    """Convert AssistantContent to a Groq assistant message."""
    tool_calls: list[ChatCompletionMessageToolCallParam] = []

    if content.tool_calls:
        tool_calls = [
            ChatCompletionMessageToolCallParam(
                id=tool_call.id,
                function=Function(
                    arguments=json_dumps(tool_call.tool_args),
                    name=tool_call.tool_name,
                ),
                type="function",
            )
            for tool_call in content.tool_calls
        ]

    assistant_message = ChatCompletionAssistantMessageParam(
        role="assistant",
        content=content.content,
    )
    if tool_calls:
        assistant_message["tool_calls"] = tool_calls
    return assistant_message


def _chat_log_to_messages(
    chat_log: conversation.ChatLog,
) -> list[
    ChatCompletionSystemMessageParam
    | ChatCompletionUserMessageParam
    | ChatCompletionAssistantMessageParam
    | ChatCompletionToolMessageParam
]:
    """Convert chat log content to Groq chat completion messages."""
    messages: list[
        ChatCompletionSystemMessageParam
        | ChatCompletionUserMessageParam
        | ChatCompletionAssistantMessageParam
        | ChatCompletionToolMessageParam
    ] = []

    for content in chat_log.content:
        if isinstance(content, SystemContent):
            messages.append(
                ChatCompletionSystemMessageParam(
                    role="system", content=content.content
                )
            )
        elif isinstance(content, UserContent):
            messages.append(
                ChatCompletionUserMessageParam(role="user", content=content.content)
            )
        elif isinstance(content, AssistantContent):
            messages.append(_assistant_content_to_message(content))
        elif isinstance(content, ToolResultContent):
            messages.append(
                ChatCompletionToolMessageParam(
                    role="tool",
                    tool_call_id=content.tool_call_id,
                    content=json_dumps(content.tool_result),
                )
            )

    return messages


class GroqConversationEntity(
    conversation.ConversationEntity, conversation.AbstractConversationAgent
):
    """Groq conversation agent."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: GroqConfigEntry) -> None:
        """Initialize the agent."""
        self.entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Groq",
            model="Groq Cloud",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        if self.entry.options.get(CONF_LLM_HASS_API):
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from Home Assistant."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Process the user input and call the API."""
        options = self.entry.options

        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                options.get(CONF_LLM_HASS_API),
                options.get(CONF_PROMPT),
                user_input.extra_system_prompt,
            )
        except ConverseError as err:
            return err.as_conversation_result()

        llm_api = chat_log.llm_api
        tools: list[ChatCompletionToolParam] | None = None
        if llm_api:
            tools = [
                _format_tool(tool, llm_api.custom_serializer) for tool in llm_api.tools
            ]
            # Fix #25: Groq API limits tools to 128 per request
            if len(tools) > 128:
                LOGGER.warning(
                    "Too many tools (%d) for Groq API, truncating to 128",
                    len(tools),
                )
                tools = tools[:128]

        messages = _chat_log_to_messages(chat_log)

        LOGGER.debug("Prompt: %s", messages)
        LOGGER.debug("Tools: %s", tools)
        trace.async_conversation_trace_append(
            trace.ConversationTraceEventType.AGENT_DETAIL,
            {"messages": messages, "tools": llm_api.tools if llm_api else None},
        )

        client = self.entry.runtime_data

        # To prevent infinite loops, we limit the number of iterations
        tools_fallback_attempted = False
        for _iteration in range(MAX_TOOL_ITERATIONS):
            try:
                model = options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)
                model_kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "tools": tools or NOT_GIVEN,
                    "max_tokens": options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS),
                    "top_p": options.get(CONF_TOP_P, RECOMMENDED_TOP_P),
                    "temperature": options.get(CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE),
                    "user": chat_log.conversation_id,
                }

                # Only add reasoning parameters if supports_reasoning is enabled
                if options.get(CONF_SUPPORTS_REASONING):
                    reasoning_effort = options.get(CONF_REASONING_EFFORT)
                    if model.startswith("qwen/qwen3-32b"):
                        model_kwargs["reasoning_format"] = "hidden"
                        model_kwargs["reasoning_effort"] = reasoning_effort or "default"
                    elif model.startswith(
                        (
                            "openai/gpt-oss-20b",
                            "openai/gpt-oss-120b",
                            "openai/gpt-oss-safeguard-20b",
                        )
                    ):
                        model_kwargs["include_reasoning"] = False
                        if reasoning_effort:
                            model_kwargs["reasoning_effort"] = reasoning_effort
                    elif reasoning_effort:
                        # For other models, just pass reasoning_effort if provided
                        model_kwargs["reasoning_effort"] = reasoning_effort

                result = await client.chat.completions.create(**model_kwargs)
            except groq.BadRequestError as err:
                # Fix #20: Smaller models may produce malformed tool calls;
                # retry once without tools as a text-only fallback.
                if (
                    "tool_use_failed" in str(err)
                    and not tools_fallback_attempted
                    and tools
                ):
                    LOGGER.warning(
                        "Groq returned tool_use_failed error, retrying without "
                        "tools: %s",
                        err,
                    )
                    tools_fallback_attempted = True
                    tools = None
                    continue
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    f"Sorry, I had a problem talking to Groq: {err}",
                )
                return conversation.ConversationResult(
                    response=intent_response, conversation_id=chat_log.conversation_id
                )
            except groq.AuthenticationError as err:
                # Fix #27: Better auth error messaging
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    "Sorry, Groq authentication failed. Please check your API key "
                    "for leading/trailing whitespace or incorrect format.",
                )
                return conversation.ConversationResult(
                    response=intent_response, conversation_id=chat_log.conversation_id
                )
            except groq.APIStatusError as err:
                # Fix #19: Better error messaging for rate limit / payload errors
                error_str = str(err)
                if err.status_code == 413 or "rate_limit_exceeded" in error_str:
                    intent_response = intent.IntentResponse(
                        language=user_input.language
                    )
                    intent_response.async_set_error(
                        intent.IntentResponseErrorCode.UNKNOWN,
                        "Sorry, Groq rejected the request. "
                        "Try reducing max_tokens in the integration options or "
                        "upgrading your Groq API tier.",
                    )
                    return conversation.ConversationResult(
                        response=intent_response,
                        conversation_id=chat_log.conversation_id,
                    )
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    f"Sorry, I had a problem talking to Groq: {err}",
                )
                return conversation.ConversationResult(
                    response=intent_response, conversation_id=chat_log.conversation_id
                )
            except groq.GroqError as err:
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    f"Sorry, I had a problem talking to Groq: {err}",
                )
                return conversation.ConversationResult(
                    response=intent_response, conversation_id=chat_log.conversation_id
                )

            LOGGER.debug("Response %s", result)
            response = result.choices[0].message

            groq_tool_calls = response.tool_calls or []
            assistant_tool_calls = [
                llm.ToolInput(
                    id=tool_call.id,
                    tool_name=tool_call.function.name,
                    tool_args=json.loads(tool_call.function.arguments),
                )
                for tool_call in groq_tool_calls
            ]

            assistant_content = AssistantContent(
                agent_id=self.entity_id,
                content=response.content,
                tool_calls=assistant_tool_calls or None,
            )

            messages.append(_assistant_content_to_message(assistant_content))

            if not assistant_tool_calls:
                chat_log.async_add_assistant_content_without_tools(assistant_content)
                break

            for tool_call in assistant_tool_calls:
                LOGGER.debug(
                    "Tool call: %s(%s)", tool_call.tool_name, tool_call.tool_args
                )

            if llm_api is None:
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    "Tool call requested but no LLM API configured",
                )
                return conversation.ConversationResult(
                    response=intent_response,
                    conversation_id=chat_log.conversation_id,
                )

            async for tool_result_content in chat_log.async_add_assistant_content(
                assistant_content
            ):
                LOGGER.debug(
                    "Tool response: %s -> %s",
                    tool_result_content.tool_name,
                    tool_result_content.tool_result,
                )
                messages.append(
                    ChatCompletionToolMessageParam(
                        role="tool",
                        tool_call_id=tool_result_content.tool_call_id,
                        content=json_dumps(tool_result_content.tool_result),
                    )
                )

        return async_get_result_from_chat_log(user_input, chat_log)
