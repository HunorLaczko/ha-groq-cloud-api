# Groq Cloud API integration for Home Assistant 🏠

This is a custom integration for using Groq Cloud API in the Assist pipeline, reducing the workload on the Home Assistant server.

Groq Cloud provides multiple models like Llama 3.1, Gemma2, Groq for free! And no card required! (For now...)

## Requirements 📖

- Home Assistant `2026.9.0` or newer 🏠
- An GroqCloud account 👤  --> You can create one [here](https://console.groq.com/login)
- An `API Key` 🔑 --> You can generate one [here](https://console.groq.com/keys)

## How to install ⚙️

Before configuring the integration you must first install the `custom_integration`. You can do it through HACS or manually

### HACS ✨

1. **Add** ➕ [this repository](https://my.home-assistant.io/redirect/hacs_repository/?owner=HunorLaczko&repository=ha-groq-cloud-api&category=integration) to your HACS repositories:

    - **Click** on this link ⤵️

      [![Add Repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=HunorLaczko&repository=ha-groq-cloud-api&category=integration)

    - Or **copy** this url ⤵️ and paste into your HACS custom repostories

      ```url
      https://github.com/HunorLaczko/ha-groq-cloud-api
      ```

2. **Install** 💻 the `Groq Cloud API` integration
3. **Restart** 🔁 Home Assistant

### Manual Install ⌨️

1. **Download** this repository
2. **Copy** everything inside the `custom_components` folder into your Home Assistant's `custom_components` folder.
3. **Restart** Home Assistant

## Configuration 🔧

For the options check out the OpenAI Conversation integration [here](https://www.home-assistant.io/integrations/openai_conversation).

For the available models check out [Groq Cloud](https://console.groq.com/docs/models).

### Reasoning Effort 🧠

Some models support a "reasoning effort" parameter that controls how much computation the model uses for reasoning tasks. To enable this:

1. Check the **"Model supports reasoning effort"** toggle in the integration options. (Make sure you only turn it on for models that support it, otherwise the API will return an error)
2. Submit, then open the configuration again. A reasoning effort field will appear:
   - For **Qwen models** (e.g., `qwen/qwen3-32b`): A dropdown with options `default` or `none`
   - For **GPT-OSS models** (e.g., `openai/gpt-oss-20b`, `openai/gpt-oss-120b`): A dropdown with options `low`, `medium`, or `high`
   - For **other models**: A text field where you can enter a custom value

If the toggle is not enabled, no reasoning effort parameter will be sent to the API.

### Home Assistant Dashboard 💻

- Configure the integration by **clicking here** ⤵️

  [![Add Repository to HACS](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=groq_cloud_api)

- Or navigate to your `Devices & services` page and click `+ Add Integration`


### Acknowledgements

The code base is mostly identical [OpenAI Conversation integration](https://github.com/home-assistant/core/blob/dev/homeassistant/components/openai_conversation), just using the official Groq library instead of OpenAI.
  
The Readme and HACS setup is based on [Fabio's excellent work](https://github.com/fabio-garavini/ha-groq-whisper-stt-api) with the Groq Whisper integration. Check out his other works as well!
