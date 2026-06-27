"""Constants for the Groq Cloud API integration."""

import logging

from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.helpers import llm

DOMAIN = "groq_cloud_api"

LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Groq Cloud API"
DEFAULT_CONVERSATION_NAME = "Groq Conversation"
CONF_PROMPT = "prompt"
CONF_CHAT_MODEL = "chat_model"
RECOMMENDED_CHAT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
CONF_SUPPORTS_REASONING = "supports_reasoning"
CONF_REASONING_EFFORT = "reasoning_effort"

# Known models with predefined reasoning effort options
QWEN_REASONING_OPTIONS = ["default", "none"]
GPT_OSS_REASONING_OPTIONS = ["low", "medium", "high"]
CONF_MAX_TOKENS = "max_tokens"
RECOMMENDED_MAX_TOKENS = 300
CONF_TOP_P = "top_p"
RECOMMENDED_TOP_P = 1.0
CONF_TEMPERATURE = "temperature"
RECOMMENDED_TEMPERATURE = 1.0
CONF_MAX_RETRIES = "max_retries"
RECOMMENDED_MAX_RETRIES = 0

DEFAULT_OPTIONS = {
    CONF_LLM_HASS_API: llm.LLM_API_ASSIST,
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
    CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
    CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
    CONF_TOP_P: RECOMMENDED_TOP_P,
    CONF_TEMPERATURE: RECOMMENDED_TEMPERATURE,
    CONF_MAX_RETRIES: RECOMMENDED_MAX_RETRIES,
}