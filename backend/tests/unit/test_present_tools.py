"""show_table and ask_choice: the agent can put a table or answer buttons in the chat. The server cuts them to a safe size."""
from app.services.agent import blocks as blocks_mod, context
from app.services.agent.tools import TOOLS, ask_choice, show_table


def test_table_is_cut_to_a_safe_size_and_becomes_a_block():
    result = show_table(None, {"title": "Columns", "columns": [f"c{i}" for i in range(12)], "rows": [[str(i)] * 12 for i in range(40)]})
    assert len(result["columns"]) == 8 and len(result["rows"]) == 20 and all(len(r) == 8 for r in result["rows"])
    [block] = blocks_mod.blocks_from_result("show_table", result, None)
    assert block["type"] == "table" and block["title"] == "Columns"


def test_choices_keep_at_most_five_short_options():
    result = ask_choice(None, {"question": "Which column?", "options": ["a", "b", "c", "d", "e", "f", " "]})
    assert result["options"] == ["a", "b", "c", "d", "e"]
    [block] = blocks_mod.blocks_from_result("ask_choice", result, None)
    assert block["type"] == "choices" and block["question"] == "Which column?"


def test_choices_with_no_usable_option_make_no_block():
    assert blocks_mod.blocks_from_result("ask_choice", {"question": "q", "options": []}, None) == []


def test_both_tools_are_offered_on_the_working_steps_only():
    assert {"show_table", "ask_choice"} <= set(context.tool_names("described")) & set(TOOLS)
    assert "show_table" not in context.tool_names("done")


def test_chart_needs_matching_numbers_and_keeps_a_known_kind():
    from app.services.agent.tools import show_chart
    ok = show_chart(None, {"title": "t", "kind": "pie", "labels": ["a", "b"], "values": [1, "2.5"]})
    assert ok["kind"] == "bar" and ok["values"] == [1.0, 2.5]
    assert "error" in show_chart(None, {"title": "t", "kind": "bar", "labels": ["a", "b"], "values": [1]})
    assert "error" in show_chart(None, {"title": "t", "kind": "bar", "labels": ["a"], "values": ["x"]})
    [block] = blocks_mod.blocks_from_result("show_chart", ok, None)
    assert block["type"] == "chart"


def test_diagram_rejects_scripts_links_and_init_directives():
    from app.services.agent.tools import show_diagram
    good = show_diagram(None, {"title": "Flow", "mermaid": "flowchart LR\n  A[Data] --> B[Test]"})
    assert good["source"].startswith("flowchart")
    for bad in ("flowchart LR\n A --> B\n click A href \"http://x\"", "%%{init: {}}%%\nflowchart LR\n A-->B", "hello", "flowchart LR\n" + "A-->B\n" * 400):
        assert "error" in show_diagram(None, {"title": "t", "mermaid": bad})


def test_links_only_go_to_known_pages():
    from app.services.agent.tools import show_links
    r = show_links(None, {"items": [{"label": "Billing", "to": "billing"}, {"label": "Evil", "to": "https://x.test"}, {"label": "Pay", "to": "pay"}]})
    assert r == {"items": [{"label": "Billing", "href": "/account/billing"}]}
    assert "error" in show_links(None, {"items": [{"label": "x", "to": "nowhere"}]})
