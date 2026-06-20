"""Tests for agent prompt assembly."""

import pytest

from v2.agents import build_system_prompt, list_agents
from v2.config import ALL_AGENTS, PHILOSOPHERS, SCIENTISTS


def test_list_agents_returns_all_profiles():
    agents = list_agents()
    for a in ALL_AGENTS:
        assert a in agents, f"Missing agent profile: {a}"


@pytest.mark.parametrize("agent_name", ALL_AGENTS)
def test_build_system_prompt_succeeds(agent_name):
    prompt = build_system_prompt(agent_name)
    assert isinstance(prompt, str)
    assert len(prompt) > 100, f"Prompt for {agent_name} is too short"


@pytest.mark.parametrize("agent_name", ALL_AGENTS)
def test_kanban_protocol_stripped(agent_name):
    prompt = build_system_prompt(agent_name)
    assert "kanban_complete" not in prompt.lower(), f"Kanban reference in {agent_name}"
    assert "kanban_block" not in prompt.lower(), f"Kanban reference in {agent_name}"
    assert "kanban_show" not in prompt.lower(), f"Kanban reference in {agent_name}"
    assert "Kanban Worker Protocol" not in prompt, f"Kanban heading in {agent_name}"


@pytest.mark.parametrize("agent_name", ALL_AGENTS)
def test_v2_output_protocol_present(agent_name):
    prompt = build_system_prompt(agent_name)
    assert "Output Protocol (v2)" in prompt, f"Missing v2 protocol in {agent_name}"


def test_translator_includes_skills():
    prompt = build_system_prompt("translator")
    assert "## SKILL:" in prompt
    assert "example-client" in prompt
    assert "glossary-enforcement" in prompt


def test_translator_includes_glossary():
    prompt = build_system_prompt("translator")
    assert "Canonical EN-DE Glossary" in prompt
    assert "kuenstliche Intelligenz" in prompt.lower() or "Kuenstliche Intelligenz" in prompt


@pytest.mark.parametrize("philosopher", PHILOSOPHERS)
def test_philosopher_includes_skills(philosopher):
    prompt = build_system_prompt(philosopher)
    assert "## SKILL:" in prompt, f"No skills in {philosopher}"


@pytest.mark.parametrize("philosopher", PHILOSOPHERS)
def test_philosopher_verdict_instructions(philosopher):
    prompt = build_system_prompt(philosopher)
    assert '"approve"' in prompt or "'approve'" in prompt
    assert '"revise"' in prompt or "'revise'" in prompt
    assert '"block"' in prompt or "'block'" in prompt


def test_frege_has_sinn_bedeutung_skill():
    prompt = build_system_prompt("frege")
    assert "sinn-bedeutung" in prompt.lower()


def test_wittgenstein_has_idiom_skill():
    prompt = build_system_prompt("wittgenstein")
    assert "idiom-localization" in prompt.lower()


def test_quine_has_ambiguity_skill():
    prompt = build_system_prompt("quine")
    assert "ambiguity-scoring" in prompt.lower()
