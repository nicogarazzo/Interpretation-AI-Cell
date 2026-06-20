"""
config.py — Load shared YAML configurations for the v2 pipeline.

Reads environment, consensus rules, token budgets, and glossary from shared/*.yml.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "shared"
PROFILES = ROOT / "profiles"
CORPUS = ROOT / "corpus" / "runs"
TEMPLATE = CORPUS / ".template"

ALL_AGENTS = ["translator", "wittgenstein", "quine", "frege", "koehn", "cho", "vaswani"]
PHILOSOPHERS = ["wittgenstein", "quine", "frege"]
SCIENTISTS = ["koehn", "cho", "vaswani"]


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_environment() -> dict:
    """Load shared/environment.yml and return the active environment config."""
    data = _load_yaml(SHARED / "environment.yml")
    active = data.get("active", "production")
    env = data.get(active, {})
    env["_active"] = active
    return env


def load_consensus_config() -> dict:
    """Load shared/consensus-config.yml."""
    data = _load_yaml(SHARED / "consensus-config.yml")
    return data.get("consensus", data)


def load_token_budget() -> dict:
    """Load shared/token-budget.yml."""
    return _load_yaml(SHARED / "token-budget.yml")


def load_glossary() -> dict:
    """Load shared/glossary.yml."""
    return _load_yaml(SHARED / "glossary.yml")


def get_model_for_agent(agent_name: str) -> str:
    """Return the model ID for the given agent based on the active environment."""
    env = load_environment()
    active = env["_active"]
    budget = load_token_budget()
    agent_cfg = budget.get("agents", {}).get(agent_name, {})

    if active == "production":
        return agent_cfg.get("model_prod", "claude-sonnet-4-20250514")
    else:
        return agent_cfg.get("model_test", "glm-4.7-flash")


def get_max_tokens(agent_name: str) -> int:
    """Return the max output tokens for the given agent."""
    budget = load_token_budget()
    agent_cfg = budget.get("agents", {}).get(agent_name, {})
    return agent_cfg.get("max_tokens_per_invocation", 4096)


def get_pricing(agent_name: str) -> dict:
    """Return pricing info for the agent's current tier."""
    env = load_environment()
    active = env["_active"]
    budget = load_token_budget()
    agent_cfg = budget.get("agents", {}).get(agent_name, {})

    if active == "production":
        tier = agent_cfg.get("tier_prod", "sonnet")
        pricing = budget.get("pricing", {}).get("anthropic", {}).get(tier, {})
    else:
        tier = agent_cfg.get("tier_test", "flash")
        pricing = budget.get("pricing", {}).get("z-ai", {}).get(tier, {})

    return {
        "tier": tier,
        "input_per_1m": pricing.get("input_per_1m", 0.0),
        "output_per_1m": pricing.get("output_per_1m", 0.0),
    }
