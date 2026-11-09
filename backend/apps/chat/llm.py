import json
import os
from importlib import import_module


class LLMError(Exception):
    """Anything that stops the model from answering: no key, timeout, quota, API error."""


def _schema(types, s):
    kind = str(s.get("type", "string")).upper()
    kw = {"type": kind}
    if s.get("description"):
        kw["description"] = s["description"]
    if s.get("enum"):
        kw["enum"] = list(s["enum"])
    if kind == "OBJECT":
        kw["properties"] = {k: _schema(types, v) for k, v in s.get("properties", {}).items()}
        if s.get("required"):
            kw["required"] = list(s["required"])
    return types.Schema(**kw)


def to_declarations(types, tools):
    """Turn the agent's tool list (JSON-schema style) into Gemini function declarations."""
    out = []
    for t in tools or []:
        schema = t.get("input_schema") or {}
        kw = {"name": t["name"], "description": t.get("description", "")}
        # Gemini rejects an object schema with no properties, so tools without arguments omit it.
        if schema.get("properties"):
            kw["parameters"] = _schema(types, schema)
        out.append(types.FunctionDeclaration(**kw))
    return out


def _as_dict(content):
    try:
        value = json.loads(content) if isinstance(content, str) else content
    except ValueError:
        value = content
    return value if isinstance(value, dict) else {"result": value}


def to_contents(types, messages):
    """Turn the agent's message list into Gemini contents (roles: user / model)."""
    names = {}  # tool_use id -> tool name, needed to label tool results
    contents = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        content = m["content"]
        if isinstance(content, str):
            parts = [types.Part(text=content)]
        else:
            parts = []
            for b in content:
                kind = b.get("type")
                if kind == "text":
                    if b.get("text"):
                        parts.append(types.Part(text=b["text"]))
                elif kind == "tool_use":
                    names[b["id"]] = b["name"]
                    # The raw part carries Gemini's thought signature; send it back unchanged.
                    parts.append(
                        b.get("_part")
                        or types.Part(function_call=types.FunctionCall(name=b["name"], args=b.get("input") or {}))
                    )
                elif kind == "tool_result":
                    parts.append(
                        types.Part.from_function_response(
                            name=names.get(b["tool_use_id"], "tool"), response=_as_dict(b.get("content"))
                        )
                    )
        if parts:
            contents.append(types.Content(role=role, parts=parts))
    return contents


class GeminiClient:
    """Thin wrapper so the agent never touches the SDK directly (and tests can swap it)."""

    def __init__(self):
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise LLMError("GEMINI_API_KEY is not set")
        genai = import_module("google.genai")
        types = import_module("google.genai.types")

        self._types = types
        self._client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=20000))
        self.model = os.environ.get("LLM_MODEL", "gemini-2.5-flash")

    def complete(self, *, system, messages, tools=None, max_tokens=600):
        t = self._types
        cfg = {"system_instruction": system, "max_output_tokens": max_tokens}
        budget = os.environ.get("LLM_THINKING_BUDGET", "0")
        if budget != "":  # thinking tokens would otherwise eat the small output budget
            cfg["thinking_config"] = t.ThinkingConfig(thinking_budget=int(budget))
        decls = to_declarations(t, tools)
        if decls:
            cfg["tools"] = [t.Tool(function_declarations=decls)]
            cfg["automatic_function_calling"] = t.AutomaticFunctionCallingConfig(disable=True)
        try:
            resp = self._client.models.generate_content(
                model=self.model, contents=to_contents(t, messages), config=t.GenerateContentConfig(**cfg)
            )
        except Exception as exc:  # quota, timeout, bad key, network: all handled the same way
            raise LLMError(str(exc)[:300]) from exc

        candidate = (resp.candidates or [None])[0]
        parts = (candidate.content.parts if candidate and candidate.content else None) or []
        blocks = []
        for i, p in enumerate(parts):
            if getattr(p, "thought", False):
                continue
            if p.function_call:
                fc = p.function_call
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": fc.id or f"call_{i}_{fc.name}",
                        "name": fc.name,
                        "input": dict(fc.args or {}),
                        "_part": p,
                    }
                )
            elif p.text:
                blocks.append({"type": "text", "text": p.text})
        return blocks


def get_client():
    return GeminiClient()