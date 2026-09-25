"""Registration against current Flask and Flask-Menu APIs."""

import pytest
from flask import Blueprint, Flask
from flask_menu import Menu, current_menu

from flask_breadcrumbs import (
    Breadcrumbs,
    current_breadcrumbs,
    default_breadcrumb_root,
    register_breadcrumb,
)


@pytest.fixture
def app():
    return Flask(__name__)


def test_app_registration_before_menu_initialization(app):
    @app.route("/item/<int:item_id>")
    @register_breadcrumb(app, ".item", "Item")
    def item(item_id):
        entries = list(current_breadcrumbs)
        return f"{entries[-1].text}:{entries[-1].url}"

    Breadcrumbs(app)
    with app.test_client() as client:
        for _ in range(2):
            response = client.get("/item/7")
            assert response.status_code == 200
            assert response.text == "Item:/item/7"

    with app.app_context():
        entry = current_menu.submenu("breadcrumbs.item")
        assert entry._endpoint == "item"


def test_blueprint_registration_before_menu_initialization(app):
    bp = Blueprint("items", __name__)
    default_breadcrumb_root(bp, ".section")

    @bp.route("/item/<int:item_id>")
    @register_breadcrumb(
        bp,
        ".item",
        "Item",
        endpoint_arguments_constructor=lambda: {"item_id": 9},
        dynamic_list_constructor=lambda: [{"text": "Dynamic", "url": "/dynamic"}],
    )
    def item(item_id):
        entries = list(current_breadcrumbs)
        return str(entries[-1])

    app.register_blueprint(bp, name="renamed")
    Breadcrumbs(app)
    with app.test_client() as client:
        assert client.get("/item/7").text == "{'text': 'Dynamic', 'url': '/dynamic'}"

    with app.test_request_context("/item/7"):
        entry = current_menu.submenu("breadcrumbs.section.item")
        assert entry._endpoint == "renamed.item"
        assert entry.url == "/item/9"


def test_external_menu(app):
    Menu(app)
    Breadcrumbs(app, init_menu=False)

    @app.route("/")
    @register_breadcrumb(app, ".home", "Home")
    def home():
        return list(current_breadcrumbs)[-1].text

    assert app.test_client().get("/").text == "Home"
