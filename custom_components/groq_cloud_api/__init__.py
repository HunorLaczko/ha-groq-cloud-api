"""Groq Cloud API integration."""

import groq

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import LOGGER

PLATFORMS = (Platform.CONVERSATION,)

type GroqConfigEntry = ConfigEntry[groq.AsyncClient]


async def async_setup_entry(hass: HomeAssistant, entry: GroqConfigEntry) -> bool:
    """Load entry."""

    LOGGER.info("Setting up %s", entry)

    client = groq.AsyncGroq(api_key=entry.data[CONF_API_KEY])

    # TODO: I get async errors when trying to call the list function. But this would be the proper way to validate the API key.
    # try:
    #     await hass.async_add_executor_job(client.with_options(timeout=10.0).models.list)
    # except groq.AuthenticationError as err:
    #     LOGGER.error("Invalid API key: %s", err)
    #     return False
    # except groq.GroqError as err:
    #     raise ConfigEntryNotReady(err) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Update entry."""
    await hass.config_entries.async_reload(entry.entry_id)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    LOGGER.info("Unloading %s", entry)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
