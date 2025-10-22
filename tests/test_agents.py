from __future__ import annotations

import os
from pathlib import Path

from vibe.agents import build_oc_command


def test_build_oc_command_places_model_before_prompt(monkeypatch, tmp_path):
    temp_file = tmp_path / "msg.txt"

    def fake_mkstemp(prefix):
        fd = os.open(temp_file, os.O_CREAT | os.O_RDWR)
        return fd, str(temp_file)

    monkeypatch.setattr("vibe.agents.tempfile.mkstemp", fake_mkstemp)

    command = build_oc_command("ctx", "prompt", "test-model")

    assert "--model test-model -p \"$(cat " in command
    assert "&& rm -f {}".format(temp_file) in command
    assert temp_file.read_text() == "ctx\n\nprompt"
