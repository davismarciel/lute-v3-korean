"""Generic app hook compatibility, including Lute's supported Python 3.8 API."""
from flask import Flask
from types import SimpleNamespace
import pytest
from lute.plugins import init_app_plugins


@pytest.mark.parametrize("legacy", [False, True])
def test_installed_navigation_and_absent_plugins_are_generic(monkeypatch, legacy):
    app = Flask(__name__)
    entry = SimpleNamespace(
        name="fixture",
        load=lambda: lambda app: [{"label": "Study fixture", "url": "/fixture"}],
    )

    class Entries(list):
        def select(self, group):
            return list(self) if group == "lute.plugin.app" else []

    monkeypatch.setattr(
        "lute.plugins.entry_points",
        lambda: {"lute.plugin.app": [entry]} if legacy else Entries([entry]),
    )
    init_app_plugins(app)
    with app.test_request_context():
        context = {}
        app.update_template_context(context)
        assert context["plugin_navigation"] == [
            {"label": "Study fixture", "url": "/fixture"}
        ]


def test_failed_optional_plugin_does_not_break_the_reader(monkeypatch):
    def failed(app):
        raise RuntimeError("optional extension unavailable")

    monkeypatch.setattr(
        "lute.plugins.entry_points",
        lambda: {
            "lute.plugin.app": [SimpleNamespace(name="broken", load=lambda: failed)]
        },
    )
    app = Flask(__name__)
    init_app_plugins(app)

    @app.route("/")
    def reader():
        return "reader available"

    assert app.test_client().get("/").data == b"reader available"
