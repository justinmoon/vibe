from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture
def cli_test_env(monkeypatch: pytest.MonkeyPatch):
    import vibe.cli as cli

    calls: list[SimpleNamespace] = []

    monkeypatch.setattr(cli, "ensure_tmux_available", lambda: None)
    monkeypatch.setattr(cli, "inside_tmux", lambda: True)
    monkeypatch.setattr(cli, "configure_tmux", lambda _: None)
    monkeypatch.setattr(cli, "run_duo", lambda cfg: (_ for _ in ()).throw(RuntimeError("run_duo should not be called")))
    monkeypatch.setattr(cli, "run_duo_review", lambda cfg: (_ for _ in ()).throw(RuntimeError("run_duo_review should not be called")))

    def fake_run_single(cfg):
        calls.append(SimpleNamespace(cfg=cfg))

    monkeypatch.setattr(cli, "run_single", fake_run_single)
    return calls


def test_single_selection_uses_oc_agent(monkeypatch: pytest.MonkeyPatch, cli_test_env):
    import vibe.cli as cli

    def fake_prompt_selection():
        return "single", ("oc", "gpt-test-model")

    monkeypatch.setattr(cli, "prompt_agent_selection", fake_prompt_selection)

    cli.main(["inspect the repo"])

    assert cli_test_env, "run_single should be invoked exactly once"
    cfg = cli_test_env[0].cfg
    assert cfg.agent_cmd == "oc"
    assert cfg.selected_model == "gpt-test-model"
