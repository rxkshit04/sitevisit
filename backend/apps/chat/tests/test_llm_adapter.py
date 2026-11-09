from google.genai import types

from apps.chat.llm import to_contents, to_declarations


def test_tool_round_trip_keeps_roles_and_names():
    messages = [
        {"role": "user", "content": "book it"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "c1", "name": "book_slot", "input": {"slot_id": 5}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": '{"booked": true}'}]},
    ]
    out = to_contents(types, messages)
    assert [c.role for c in out] == ["user", "model", "user"]
    assert out[1].parts[0].function_call.name == "book_slot"
    assert out[2].parts[0].function_response.name == "book_slot"
    assert out[2].parts[0].function_response.response == {"booked": True}


def test_non_json_tool_result_is_wrapped():
    messages = [
        {"role": "assistant", "content": [{"type": "tool_use", "id": "c1", "name": "x", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "plain"}]},
    ]
    assert to_contents(types, messages)[1].parts[0].function_response.response == {"result": "plain"}


def test_tool_without_arguments_has_no_parameters():
    decls = to_declarations(
        types, [{"name": "get_free_slots", "description": "x", "input_schema": {"type": "object", "properties": {}}}]
    )
    assert decls[0].parameters is None


def test_enum_and_required_survive():
    tool = {
        "name": "request_human",
        "description": "x",
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string", "enum": ["buyer_request", "other"]}},
            "required": ["reason"],
        },
    }
    params = to_declarations(types, [tool])[0].parameters
    assert params.required == ["reason"]
    assert params.properties["reason"].enum == ["buyer_request", "other"]