"""Config flow for GroqCloud Whisper integration."""

from __future__ import annotations

from typing import Any
from types import MappingProxyType

import groq

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_LLM_HASS_API
from homeassistant.helpers import llm
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TemplateSelector,
)

from . import LOGGER
from .const import (
    CONF_PROMPT,
    CONF_TEMPERATURE,
    DEFAULT_NAME,
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DOMAIN,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
    }
)

RECOMMENDED_OPTIONS = {
    CONF_RECOMMENDED: True,
    CONF_LLM_HASS_API: llm.LLM_API_ASSIST,
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
}


async def validate_input(hass: HomeAssistant, data: dict[str, Any]):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    client = groq.AsyncGroq(api_key=data[CONF_API_KEY])
    await hass.async_add_executor_job(client.with_options(timeout=10.0).models.list)


class GroqConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle UI config flow."""

    VERSION = 1
    MINOR_VERSION = 0

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Handle initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )
        
        errors = {}

        try:
            await validate_input(self.hass, user_input)
        except groq.APIConnectionError:
            errors["base"] = "cannot_connect"
        except groq.AuthenticationError:
            errors["base"] = "invalid_auth"
        except Exception:
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title="GroqCloud",
                data=user_input,
                options=RECOMMENDED_OPTIONS,
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return GroqOptionsFlow(config_entry)
    


class GroqOptionsFlow(OptionsFlow):
    """Groq Cloud config flow options handler."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.last_rendered_recommended = config_entry.options.get(
            CONF_RECOMMENDED, False
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        options: dict[str, Any] | MappingProxyType[str, Any] = self.config_entry.options

        if user_input is not None:
            if user_input[CONF_RECOMMENDED] == self.last_rendered_recommended:
                if user_input[CONF_LLM_HASS_API] == "none":
                    user_input.pop(CONF_LLM_HASS_API)
                return self.async_create_entry(title="", data=user_input)

            # Re-render the options again, now with the recommended options shown/hidden
            self.last_rendered_recommended = user_input[CONF_RECOMMENDED]

            options = {
                CONF_RECOMMENDED: user_input[CONF_RECOMMENDED],
                CONF_PROMPT: user_input[CONF_PROMPT],
                CONF_LLM_HASS_API: user_input[CONF_LLM_HASS_API],
            }

        schema = groq_config_option_schema(self.hass, options)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )


def groq_config_option_schema(
    hass: HomeAssistant,
    options: dict[str, Any] | MappingProxyType[str, Any],
) -> dict:
    """Return a schema for Groq Cloud completion options."""
    hass_apis: list[SelectOptionDict] = [
        SelectOptionDict(
            label="No control",
            value="none",
        )
    ]
    hass_apis.extend(
        SelectOptionDict(
            label=api.name,
            value=api.id,
        )
        for api in llm.async_get_apis(hass)
    )

    schema = {
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
            description={"suggested_value": options.get(CONF_LLM_HASS_API)},
            default="none",
        ): SelectSelector(SelectSelectorConfig(options=hass_apis)),
        vol.Required(
            CONF_RECOMMENDED, default=options.get(CONF_RECOMMENDED, False)
        ): bool,
    }

    if options.get(CONF_RECOMMENDED):
        return schema

    schema.update(
        {
            vol.Optional(
                CONF_CHAT_MODEL,
                description={"suggested_value": options.get(CONF_CHAT_MODEL)},
                default=RECOMMENDED_CHAT_MODEL,
            ): str,
            vol.Optional(
                CONF_MAX_TOKENS,
                description={"suggested_value": options.get(CONF_MAX_TOKENS)},
                default=RECOMMENDED_MAX_TOKENS,
            ): int,
            vol.Optional(
                CONF_TOP_P,
                description={"suggested_value": options.get(CONF_TOP_P)},
                default=RECOMMENDED_TOP_P,
            ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
            vol.Optional(
                CONF_TEMPERATURE,
                description={"suggested_value": options.get(CONF_TEMPERATURE)},
                default=RECOMMENDED_TEMPERATURE,
            ): NumberSelector(NumberSelectorConfig(min=0, max=2, step=0.05)),
        }
    )
    return schema