"""Config flow for Groq Cloud API integration."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any

import groq
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
)

from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    CONF_SUPPORTS_REASONING,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DEFAULT_NAME,
    DEFAULT_OPTIONS,
    DOMAIN,
    GPT_OSS_REASONING_OPTIONS,
    LOGGER,
    QWEN_REASONING_OPTIONS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


async def async_fetch_models(api_key: str, hass: HomeAssistant) -> list[str]:
    """Fetch available models from Groq API."""
    client = groq.AsyncGroq(api_key=api_key, http_client=get_async_client(hass))
    response = await client.models.list()
    model_ids = sorted([model.id for model in response.data if model.id])
    LOGGER.debug("Available models: %s", model_ids)
    return model_ids


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> list[str]:
    """Validate the user input and return available models."""
    try:
        return await async_fetch_models(data[CONF_API_KEY], hass)
    except groq.PermissionDeniedError:
        raise UnauthorizedError


class GroqConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle UI config flow for Groq Cloud API."""

    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        errors: dict[str, str] = {}

        self._async_abort_entries_match(user_input)
        try:
            await validate_input(self.hass, user_input)
        except groq.APIConnectionError:
            errors["base"] = "cannot_connect"
        except groq.AuthenticationError:
            errors["base"] = "invalid_auth"
        except InvalidAPIKey:
            errors["base"] = "invalid_auth"
        except UnauthorizedError:
            errors["base"] = "unauthorized"
        except Exception:
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data=user_input,
                options=DEFAULT_OPTIONS,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return GroqOptionsFlow()


class GroqOptionsFlow(OptionsFlow):
    """Groq Cloud API options flow handler."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            if not user_input.get(CONF_LLM_HASS_API):
                user_input.pop(CONF_LLM_HASS_API, None)
            # Remove reasoning_effort if supports_reasoning is not checked
            if not user_input.get(CONF_SUPPORTS_REASONING):
                user_input.pop(CONF_REASONING_EFFORT, None)
                user_input.pop(CONF_SUPPORTS_REASONING, None)
            return self.async_create_entry(title="", data=user_input)

        # Fetch available models from API
        api_key = self.config_entry.data.get(CONF_API_KEY)
        try:
            available_models = await async_fetch_models(api_key, self.hass)
        except groq.GroqError:
            LOGGER.warning("Failed to fetch models from Groq API, model list will be empty")
            available_models = []

        options: dict[str, Any] | MappingProxyType[str, Any] = (
            self.config_entry.options
        )

        schema = await self._build_options_schema(options, available_models)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )

    async def _build_options_schema(
        self,
        options: dict[str, Any] | MappingProxyType[str, Any],
        available_models: list[str],
    ) -> dict:
        """Build the options schema with model dropdown."""
        hass_apis: list[SelectOptionDict] = [
            SelectOptionDict(
                label=api.name,
                value=api.id,
            )
            for api in llm.async_get_apis(self.hass)
        ]

        # Determine the current/default model
        current_model = options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)

        # If current model is not in available models, use first available
        if available_models and current_model not in available_models:
            LOGGER.warning(
                "Configured model '%s' not available, defaulting to '%s'",
                current_model,
                available_models[0],
            )
            current_model = available_models[0]

        # Build model options for dropdown
        model_options: list[SelectOptionDict] = [
            SelectOptionDict(label=model, value=model)
            for model in available_models
        ]

        # If no models available, fall back to text input
        if not model_options:
            model_selector: Any = str
        else:
            model_selector = SelectSelector(
                SelectSelectorConfig(
                    options=model_options,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )

        # Determine reasoning options based on model
        supports_reasoning = options.get(CONF_SUPPORTS_REASONING, False)
        reasoning_options: list[str] | None = None
        if current_model.startswith("qwen/qwen3-32b"):
            reasoning_options = QWEN_REASONING_OPTIONS
        elif current_model.startswith(
            (
                "openai/gpt-oss-20b",
                "openai/gpt-oss-120b",
                "openai/gpt-oss-safeguard-20b",
            )
        ):
            reasoning_options = GPT_OSS_REASONING_OPTIONS

        # Determine reasoning effort selector
        if reasoning_options:
            selected_reasoning = options.get(CONF_REASONING_EFFORT)
            if selected_reasoning not in reasoning_options:
                selected_reasoning = reasoning_options[0]
            reasoning_selector: Any = SelectSelector(
                SelectSelectorConfig(
                    options=reasoning_options,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
            reasoning_default = selected_reasoning
        else:
            reasoning_selector = TextSelector()
            reasoning_default = options.get(CONF_REASONING_EFFORT, "")

        schema: dict = {
            vol.Optional(
                CONF_PROMPT,
                description={
                    "suggested_value": options.get(
                        CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT
                    )
                },
            ): TemplateSelector(),
            vol.Optional(
                CONF_LLM_HASS_API,
                description={"suggested_value": (
                    [v] if isinstance(v := options.get(CONF_LLM_HASS_API), str) else v
                )},
            ): SelectSelector(SelectSelectorConfig(options=hass_apis, multiple=True)),
            vol.Required(
                CONF_CHAT_MODEL,
                default=current_model,
            ): model_selector,
            vol.Required(
                CONF_MAX_TOKENS,
                default=options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS),
            ): int,
            vol.Required(
                CONF_TOP_P,
                default=options.get(CONF_TOP_P, RECOMMENDED_TOP_P),
            ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
            vol.Required(
                CONF_TEMPERATURE,
                default=options.get(CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE),
            ): NumberSelector(NumberSelectorConfig(min=0, max=2, step=0.05)),
            vol.Optional(
                CONF_SUPPORTS_REASONING,
                default=supports_reasoning,
            ): BooleanSelector(),
        }

        # Only show reasoning effort field if checkbox is checked
        if supports_reasoning:
            schema[vol.Optional(
                CONF_REASONING_EFFORT,
                description={"suggested_value": options.get(CONF_REASONING_EFFORT)},
                default=reasoning_default,
            )] = reasoning_selector

        return schema


class UnknownError(HomeAssistantError):
    """Unknown error."""


class UnauthorizedError(HomeAssistantError):
    """API key valid but doesn't have the rights."""


class InvalidAPIKey(HomeAssistantError):
    """Invalid api_key error."""
