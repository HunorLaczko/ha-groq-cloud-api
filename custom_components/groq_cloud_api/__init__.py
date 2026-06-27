"""Groq Cloud API integration."""

from __future__ import annotations

import groq

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType

from .const import CONF_MAX_RETRIES, DOMAIN, LOGGER

PLATFORMS = (Platform.CONVERSATION,)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type GroqConfigEntry = ConfigEntry[groq.AsyncClient]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Groq Cloud API."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GroqConfigEntry) -> bool:
    """Set up Groq Cloud API from a config entry."""
    LOGGER.debug("Setting up %s", entry)

    client = groq.AsyncGroq(
        api_key=entry.data[CONF_API_KEY],
        http_client=get_async_client(hass),
        max_retries=entry.options.get(CONF_MAX_RETRIES, 0),
    )

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: GroqConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: GroqConfigEntry) -> bool:
    """Unload a config entry."""
    LOGGER.debug("Unloading %s", entry)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
