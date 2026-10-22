import json
from collections import deque
from functools import lru_cache

import tiktoken
from fastapi import HTTPException


SOURCE_FIELDS = ("chunk_id", "title", "kind", "court", "citation", "decision_date", "locator", "text")


@lru_cache(maxsize=2)
def encoding_for(model):
    name = "o200k_harmony" if not model or model.startswith("openai/gpt-oss-") else "cl100k_base"
    try:
        return tiktoken.get_encoding(name)
    except Exception as exc:
        raise HTTPException(503, "The request tokenizer could not be loaded. Check the server's network connection and retry.") from exc


def messages_for(system, task, data, schema, model=None):
    compact = dict(data)
    for key in ("sources", "case_passages", "authority_passages"):
        if key in compact:
            compact[key] = [{field: source[field] for field in SOURCE_FIELDS if field in source}
                            for source in compact[key]]
    request = {"task": task, "input": compact}
    if model not in {"openai/gpt-oss-20b", "openai/gpt-oss-120b"}:
        request["required_schema"] = schema.model_json_schema()
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(request, ensure_ascii=False, separators=(",", ":"))},
    ]


def response_format_for(schema, model):
    if model not in {"openai/gpt-oss-20b", "openai/gpt-oss-120b"}:
        return {"type": "json_object"}
    definition = schema.model_json_schema()

    def require_properties(node):
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            for value in node.values():
                require_properties(value)
        elif isinstance(node, list):
            for value in node:
                require_properties(value)

    require_properties(definition)
    return {"type": "json_schema", "json_schema": {
        "name": schema.__name__, "strict": True, "schema": definition,
    }}


def input_tokens(messages, model, schema=None):
    # Count the complete serialised prompt and reserve room for chat framing.
    payload = {"messages": messages, "response_format": response_format_for(schema, model)} if schema else messages
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return len(encoding_for(model).encode(text, disallowed_special=())) + 256


def select_sources(system, task, data, schema, sources, source_key, settings, allow_empty=False):
    base = {**data, source_key: []}
    if input_tokens(messages_for(system, task, base, schema, settings.model), settings.model, schema) > settings.max_input_tokens:
        raise HTTPException(413, "The case facts or question exceed the AI input budget. Shorten them and retry; confirmed facts are never silently truncated.")

    # Round-robin across documents while retaining relevance order within each document.
    groups = {}
    for source in sources:
        key = source.get("document_id", source["chunk_id"])
        groups.setdefault(key, deque()).append(source)
    selected = []
    queues = list(groups.values())
    while any(queues):
        for queue in queues:
            if not queue:
                continue
            source = queue.popleft()
            candidate = {**data, source_key: [*selected, source]}
            if input_tokens(messages_for(system, task, candidate, schema, settings.model), settings.model, schema) <= settings.max_input_tokens:
                selected.append(source)
    if sources and not selected and not allow_empty:
        raise HTTPException(413, "No complete source passage fits alongside these case facts or this question. Shorten the facts or question and retry.")
    return selected, len(selected) < len(sources)
