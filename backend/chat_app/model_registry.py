DEFAULT_CHAT_MODEL = "openai.gpt-5.2"

SUPPORTED_CHAT_MODELS = {
    "openai.gpt-5.2": {
        "name": "GPT-5.2",
        "provider": "openai",
        "family": "OpenAI",
    },
    "openai.gpt-5.2-2025-12-11": {
        "name": "GPT-5.2 2025-12-11",
        "provider": "openai",
        "family": "OpenAI",
    },
    "openai.gpt-5.2-chat-latest": {
        "name": "GPT-5.2 Chat Latest",
        "provider": "openai",
        "family": "OpenAI",
    },
    "openai.gpt-5.2-pro": {
        "name": "GPT-5.2 Pro",
        "provider": "openai",
        "family": "OpenAI",
    },
    "openai.gpt-5.2-pro-2025-12-11": {
        "name": "GPT-5.2 Pro 2025-12-11",
        "provider": "openai",
        "family": "OpenAI",
    },
    "xai.grok-4": {
        "name": "Grok 4",
        "provider": "xai",
        "family": "xAI",
    },
    "xai.grok-4-1-fast-non-reasoning": {
        "name": "Grok 4.1 Fast Non-Reasoning",
        "provider": "xai",
        "family": "xAI",
    },
    "xai.grok-4-1-fast-reasoning": {
        "name": "Grok 4.1 Fast Reasoning",
        "provider": "xai",
        "family": "xAI",
    },
    "xai.grok-4-fast-non-reasoning": {
        "name": "Grok 4 Fast Non-Reasoning",
        "provider": "xai",
        "family": "xAI",
    },
    "xai.grok-4-fast-reasoning": {
        "name": "Grok 4 Fast Reasoning",
        "provider": "xai",
        "family": "xAI",
    },
    "xai.grok-code-fast-1": {
        "name": "Grok Code Fast 1",
        "provider": "xai",
        "family": "xAI",
    },
}


def is_supported_chat_model(model_id: str) -> bool:
    return model_id in SUPPORTED_CHAT_MODELS