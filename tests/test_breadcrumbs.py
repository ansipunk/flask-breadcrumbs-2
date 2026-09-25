# SPDX-FileCopyrightText: 2013, 2014, 2015, 2016 CERN, 2026 ansipunk.
# SPDX-License-Identifier: BSD-3-Clause

import pytest
from flask import Blueprint, Flask, render_template_string
from flask_menu import Menu

from flask_breadcrumbs import (
    Breadcrumbs,
    current_breadcrumbs,
    current_path,
    default_breadcrumb_root,
    register_breadcrumb,
)

breadcrumbs_tpl = """
{%- for breadcrumb in breadcrumbs -%}
{{ breadcrumb.text}},{{ breadcrumb.url}};
{%- endfor -%}
"""


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["DEBUG"] = True
    app.config["TESTING"] = True
    app.logger.disabled = True
    return app


@pytest.fixture
def breadcrumb_app(app):
    """Prepare a breadcrumb tree with nested routes and a blueprint."""
    Breadcrumbs(app, init_menu=True)

    @app.route("/test")
    @register_breadcrumb(app, ".", "Test")
    def test():
        return "test"

    @app.route("/level2")
    @register_breadcrumb(app, ".level2", "Level 2")
    def level2():
        return "level2"

    @app.route("/level3")
    @register_breadcrumb(app, ".level2.level3", "Level 3")
    def level3():
        return "level3"

    @app.route("/level3B")
    @register_breadcrumb(app, "breadcrumbs.level2.level3B", "Level 3B")
    def level3B():
        return render_template_string(breadcrumbs_tpl)

    @app.route("/missing")
    def missing():
        return "missing"

    foo = Blueprint("foo", "foo", url_prefix="/foo")

    @foo.route("/")
    @register_breadcrumb(foo, ".bar", "Bar")
    def bar():
        return "bar"

    @foo.route("/baz")
    @register_breadcrumb(foo, ".baz", "Baz")
    def baz():
        return render_template_string(breadcrumbs_tpl)

    @foo.route("/missing")
    def missing2():
        return "missing2"

    app.register_blueprint(foo)
    return app


@pytest.fixture
def foo(breadcrumb_app):
    return breadcrumb_app.blueprints["foo"]


def test_simple_app(breadcrumb_app):
    Breadcrumbs(breadcrumb_app, init_menu=True)
    with breadcrumb_app.test_client() as client:
        client.get("/test")
        assert current_path == "breadcrumbs"
        assert current_breadcrumbs[-1].url == "/test"


def test_default_breadcrumb_root(breadcrumb_app):
    with breadcrumb_app.test_client() as client:
        client.get("/foo/")
        assert current_path == "breadcrumbs.foo.bar"
        assert current_breadcrumbs[-1].url == "/foo/"

    with breadcrumb_app.test_client() as client:
        client.get("/foo/baz")
        assert current_path == "breadcrumbs.foo.baz"
        assert current_breadcrumbs[-1].url == "/foo/baz"


def test_set_default_breadcrumb_root_different_from_blueprint_name(breadcrumb_app, foo):
    default_breadcrumb_root(foo, ".fooo")

    with breadcrumb_app.test_client() as client:
        client.get("/foo/")
        assert current_path == "breadcrumbs.fooo.bar"
        assert current_breadcrumbs[-1].url == "/foo/"

    with breadcrumb_app.test_client() as client:
        client.get("/foo/baz")
        assert current_path == "breadcrumbs.fooo.baz"
        assert current_breadcrumbs[-1].url == "/foo/baz"


def test_set_default_breadcrumb_root_as_dot(breadcrumb_app, foo):
    default_breadcrumb_root(foo, ".")

    with breadcrumb_app.test_client() as client:
        client.get("/foo/")
        assert current_path == "breadcrumbs.bar"
        assert current_breadcrumbs[-1].url == "/foo/"

    with breadcrumb_app.test_client() as client:
        client.get("/foo/baz")
        assert current_path == "breadcrumbs.baz"
        assert current_breadcrumbs[-1].url == "/foo/baz"


def test_missing_breadcrumbs_detection(breadcrumb_app):
    with breadcrumb_app.test_client() as client:
        client.get("/missing")
        assert current_path == "breadcrumbs"
        assert current_breadcrumbs[-1].url == "/test"

    with breadcrumb_app.test_client() as client:
        client.get("/foo/missing")
        assert current_path == "breadcrumbs.foo"
        assert current_breadcrumbs[-1].url == "#"


def test_template_context(breadcrumb_app, foo):
    default_breadcrumb_root(foo, "breadcrumbs")

    with breadcrumb_app.test_client() as client:
        response = client.get("/level3B")
        assert (
            response.data.decode("utf8")
            == "Test,/test;Level 2,/level2;Level 3B,/level3B;"
        )

    with breadcrumb_app.test_client() as client:
        response = client.get("/foo/baz")
        assert response.data.decode("utf8") == "Test,/test;Baz,/foo/baz;"


def test_without_menu(app):
    with pytest.raises(RuntimeError):
        Breadcrumbs(app, init_menu=False)


def test_init_menu(app):
    Breadcrumbs(app)
    assert "menu" in app.extensions


def test_create_menu_first(app):
    Menu(app)
    entry = app.extensions["menu"]
    # It must reuse the existing menu extension.
    Breadcrumbs(app, init_menu=False)
    assert entry == app.extensions["menu"]
