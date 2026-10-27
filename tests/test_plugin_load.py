"""Load the repo through Hermes's real plugin loader, as ``hermes plugins install`` lays it out."""

from __future__ import annotations

import io
import shutil
import tomllib

import pytest
from wap_helpers import ROOT


def test_real_loader_registers_the_platform(hermes_home):
    target = hermes_home / "plugins" / "whatsapp-agent-platform"
    shutil.copytree(
        ROOT,
        target,
        ignore=shutil.ignore_patterns(".git", ".github", "tests", "__pycache__", ".venv", "*.pyc"),
    )
    (hermes_home / "config.yaml").write_text("plugins:\n  enabled:\n    - whatsapp-agent-platform\n", encoding="utf-8")

    import hermes_cli.plugins as plugins
    from gateway.platform_registry import platform_registry

    plugins._reset_plugin_managers_for_tests()
    try:
        plugins.discover_plugins(force=True)
        entry = platform_registry.get("whatsapp_agent_platform")
        assert entry is not None and entry.source == "plugin"
        assert entry.plugin_name == "whatsapp-agent-platform"
        assert entry.cron_deliver_env_var == "WHATSAPP_AGENT_PLATFORM_HOME_CHANNEL"
        assert callable(entry.standalone_sender_fn)
    finally:
        plugins._reset_plugin_managers_for_tests()


def test_install_prompt_masks_the_api_key(hermes_home, monkeypatch):
    import hermes_cli.plugins_cmd as plugins_cmd
    from rich.console import Console

    if not hasattr(plugins_cmd, "_prompt_plugin_env_vars"):
        pytest.skip("this Hermes no longer prompts for requires_env in plugins_cmd")
    text = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
    try:
        import yaml

        manifest = yaml.safe_load(text)
    except ImportError:  # Hermes main ships ruamel.yaml, not PyYAML
        from ruamel.yaml import YAML

        manifest = YAML(typ="safe").load(text)
    used = []

    def answer(kind):
        return lambda _prompt: used.append(kind) or "test-key"

    # Hermes 0.21.4 defines the prompt in plugins_cmd; main moved it to plugins_cmd_install (re-exported here).
    prompt_env_vars = plugins_cmd._prompt_plugin_env_vars
    for namespace in (vars(plugins_cmd), prompt_env_vars.__globals__):
        monkeypatch.setitem(namespace, "line_input", answer("echoed"))
        monkeypatch.setitem(namespace, "masked_secret_prompt", answer("masked"))
    prompt_env_vars(manifest, Console(file=io.StringIO()))
    assert used == ["masked"]


def test_pyproject_declares_no_python_packages():
    document = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    # Any of these makes Hermes's package manager treat the plugin as installing packages.
    assert document["project"]["dependencies"] == []
    assert not any(document["project"].get("optional-dependencies", {}).values())
    assert not any(document.get("dependency-groups", {}).values())
    assert "build-system" not in document
