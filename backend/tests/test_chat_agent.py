"""Pure logic of the conversation agent: facts, prompt assembly, reply hygiene and basic mode."""

import pytest

from app.schemas.ai import SKIPPED, ChatTurn, ExtractedFacts
from app.services import chat_agent as agent
from app.services.gemini import make_parser, schema_for


# ======================================================================================
# Facts
# ======================================================================================
@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("where", "  Pune   office ", "Pune office"),
        ("where", "", ""),
        ("where", None, ""),
        ("who", "Unknown", SKIPPED),
        ("who", "n/a", SKIPPED),
        ("what", "unknown", ""),  # WHAT can never count as "skipped"
        ("contact_info", "None", SKIPPED),
        ("who", "none", ""),
        ("when", "skipped", SKIPPED),
        ("evidence", "...", ""),
    ],
)
def test_normalize_fact(field, value, expected):
    assert agent.normalize_fact(field, value) == expected


def test_merge_never_loses_or_downgrades_facts():
    old = {"what": "Officer Raj took a 500 rupee bribe at the border post", "where": "Border post", "who": SKIPPED}
    new = ExtractedFacts(what="bribe", where="", when="Yesterday 3 PM", who="Officer Raj", evidence=SKIPPED)
    merged = agent.merge_facts(old, new)
    assert merged["what"] == old["what"], "a shortened re-statement must not replace the detailed fact"
    assert merged["where"] == "Border post", "empty = keep"
    assert merged["when"] == "Yesterday 3 PM"
    assert merged["who"] == "Officer Raj", "a real answer replaces SKIPPED"
    assert merged["evidence"] == SKIPPED

    again = agent.merge_facts(merged, {"who": SKIPPED, "what": ""})
    assert again["who"] == "Officer Raj", "SKIPPED never overwrites a real value"


def test_basics_logic():
    assert agent.missing_basics({}) == ["what", "where", "when", "who"]
    assert agent.missing_basics({"what": SKIPPED, "where": "x", "when": "y", "who": "z"}) == ["what"]
    assert agent.basics_complete({"what": "w", "where": SKIPPED, "when": SKIPPED, "who": SKIPPED})


def test_state_block_lists_known_and_missing():
    block = agent.state_block({"what": "bribe", "where": SKIPPED}, evidence_count=2)
    assert "- what: bribe" in block and "- where: SKIPPED" in block
    assert "BASICS STILL NEEDED: when, who" in block and "UPLOADED FILES: 2" in block


# ======================================================================================
# Prompt assembly
# ======================================================================================
def test_build_contents_merges_roles_and_attaches_evidence_notes():
    history = [("user", "first"), ("assistant", "a1"), ("user", "u2"), ("user", "u3")]
    contents = agent.build_contents(history, "Image 'x.png': an officer")
    assert [c["role"] for c in contents] == ["user", "model", "user"]
    assert contents[-1]["parts"][0]["text"].startswith("u2\n\nu3\n\n<evidence_notes>")
    assert contents[0]["parts"][0]["text"] == "first"


def test_build_contents_keeps_first_message_when_trimming(monkeypatch):
    monkeypatch.setattr(agent, "MAX_HISTORY_CHARS", 100)
    history = [("user", "the original story " * 3)] + [
        ("assistant" if i % 2 else "user", f"message number {i} " + "x" * 30) for i in range(12)
    ]
    contents = agent.build_contents(history, None)
    assert contents[0]["parts"][0]["text"].startswith("the original story")
    assert len(contents) < len(history)
    assert contents[0]["role"] == "user"


def test_build_contents_starts_with_a_user_turn():
    contents = agent.build_contents([("assistant", "hi"), ("user", "hello")], None)
    assert contents[0]["role"] == "user"


def test_system_prompt_and_schema_are_consistent():
    schema = schema_for(ChatTurn)
    assert set(schema["required"]) == {"reply", "extracted", "asked_about", "ready_to_submit"}
    assert "contact_info" in schema["$defs"]["ExtractedFacts"]["properties"]
    assert "none" in schema["properties"]["asked_about"]["enum"]
    assert "CASE_ID" not in agent.SYSTEM_PROMPT and "PLACEHOLDER" not in agent.SYSTEM_PROMPT


def test_chat_turn_parsing_is_lenient_about_shapes():
    parse = make_parser(ChatTurn)
    turn = parse('{"reply": " Hello ", "extracted": {"what": ["a", "b"], "where": null}, "asked_about": "WHERE", "ready_to_submit": false}')
    assert turn.reply == "Hello" and turn.extracted.what == "a; b" and turn.extracted.where == "" and turn.asked_about == "where"
    assert parse('{"reply": "x", "asked_about": "something odd"}').asked_about == "none"
    with pytest.raises(Exception):
        parse('{"reply": "   "}')
    with pytest.raises(Exception):
        parse('{"extracted": {}}')


# ======================================================================================
# Reply hygiene
# ======================================================================================
def test_clean_reply_removes_credentials_and_fences():
    text = "```json\n{}\n``` Your Case ID is BCN100000000009 and CASE_ID_PLACEHOLDER, SECRET_KEY_PLACEHOLDER."
    cleaned = agent.clean_reply(text)
    assert "BCN1000" not in cleaned and "PLACEHOLDER" not in cleaned and "```" not in cleaned


def test_clean_reply_bounds_length_and_never_returns_empty():
    long = "This is a sentence. " * 200
    out = agent.clean_reply(long)
    assert len(out) <= agent.MAX_REPLY_CHARS and out.endswith(".")
    assert agent.clean_reply("   ") == "Thank you, I've noted that."


# ======================================================================================
# Basic mode
# ======================================================================================
def walk(messages: list[str], evidence_count: int = 0):
    facts, pending, last = {}, None, None
    for message in messages:
        last = agent.basic_turn(facts, message, pending, evidence_count)
        facts, pending = last.facts, last.asked_about
        assert last.mode == "basic" and last.notice
    return last


def test_basic_mode_walks_through_every_field_in_order():
    first = agent.basic_turn({}, "A clerk demanded money for a licence", None, 0)
    assert first.facts == {"what": "A clerk demanded money for a licence"} and first.asked_about == "where"
    result = walk(["A clerk demanded money", "City office, Pune", "Last Monday 11am", "Mr Shah", "no", "no", "no"])
    assert result.ready_to_submit and result.facts["who"] == "Mr Shah" and result.facts["evidence"] == SKIPPED


def test_basic_mode_what_cannot_be_skipped():
    result = agent.basic_turn({}, "no", None, 0)
    assert result.asked_about == "what" and "what" not in result.facts and not result.ready_to_submit


def test_basic_mode_skips_unknowns_and_honours_early_finish():
    result = walk(["Bribe at the toll plaza", "don't know", "skip", "not sure", "that's all"])
    assert result.ready_to_submit
    assert [result.facts[k] for k in ("where", "when", "who")] == [SKIPPED] * 3


def test_basic_mode_finish_before_basics_does_not_submit():
    result = walk(["Bribe at the toll plaza", "that's all"])  # 'that's all' answers WHERE -> skipped, but WHEN/WHO still open
    assert not result.ready_to_submit and result.asked_about == "when"


def test_basic_mode_uploaded_files_count_as_evidence():
    result = walk(["Bribe at the toll plaza", "NH44 toll", "Tuesday 9am", "toll operator", "no", "no"], evidence_count=2)
    assert result.facts["evidence"].startswith("Uploaded (2 files)") and result.ready_to_submit


def test_basic_mode_yes_to_optional_questions_asks_for_the_content():
    facts = {"what": "w", "where": "x", "when": "y", "who": "z", "evidence": SKIPPED}
    ask = agent.basic_turn(facts, "yes", "contact_info", 0)
    assert "contact details you would like to share" in ask.reply and "contact_info" not in ask.facts
    more = agent.basic_turn({**facts, "contact_info": SKIPPED}, "yes", "other_details", 0)
    assert "go ahead" in more.reply
    added = agent.basic_turn({**facts, "contact_info": SKIPPED}, "He also threatened me", "other_details", 0)
    assert "anything else" in added.reply.lower() and added.facts["other_details"] == "He also threatened me" and not added.ready_to_submit


@pytest.mark.parametrize("message", ["no", "No.", "nope", "skip", "N/A", "no thanks", "I don't know", "nothing", "no idea"])
def test_negative_detection(message):
    assert agent.is_negative(message)


@pytest.mark.parametrize("message", ["Officer Raj", "yes", "near the notice board", "I know him"])
def test_not_negative(message):
    assert not agent.is_negative(message)


@pytest.mark.parametrize("message", ["that's all", "I'm done", "no, that's all", "nothing else", "submit", "No I am done"])
def test_finish_detection(message):
    assert agent.wants_to_finish(message)
