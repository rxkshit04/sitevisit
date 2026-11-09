import os


class LLMError(Exception):
    """Anything that stops the model from answering: no key, timeout, API error."""


class AnthropicClient:
    """Thin wrapper so the agent never touches the SDK directly (and tests can swap it)."""

    def __init__(self):
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=key, timeout=20.0, max_retries=1)
        self.model = os.environ.get("LLM_MODEL", "claude-sonnet-5-5")

    def complete(self, *, system, messages, tools=None, max_tokens=600):
        kwargs = dict(model=self.model, max_tokens=max_tokens, system=system, messages=messages)
        if tools:
            kwargs["tools"] = tools
        try:
            response = self._client.messages.create(**kwargs)
        except self._anthropic.APIError as exc:
            raise LLMError(str(exc)) from exc
        blocks = []
        for b in response.content:
            if b.type == "text":
                blocks.append({"type": "text", "text": b.text})
            elif b.type == "tool_use":
                blocks.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
        return blocks


def get_client():
    return AnthropicClient()