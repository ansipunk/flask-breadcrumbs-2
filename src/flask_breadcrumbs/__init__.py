# SPDX-FileCopyrightText: 2013, 2014, 2015, 2016 CERN, 2026 ansipunk.
# SPDX-License-Identifier: BSD-3-Clause

"""Provide support for generating site breadcrumb navigation.

Depends on `flask_menu` extension.
"""

__all__ = ["Breadcrumbs"]

from collections.abc import Callable
from inspect import getfullargspec
from typing import Any, Protocol, TypedDict, TypeVar, cast

from flask import Blueprint, Flask, current_app, request
from flask.blueprints import BlueprintSetupState
from flask.sansio.blueprints import Blueprint as BlueprintBase
from flask.typing import RouteCallable
from flask_menu import Menu, current_menu
from werkzeug.local import LocalProxy


class BreadcrumbObject(Protocol):
    """Breadcrumb with text and URL attributes."""

    @property
    def text(self) -> str: ...

    @property
    def url(self) -> str: ...


class BreadcrumbDict(TypedDict):
    """Breadcrumb represented as a dictionary."""

    text: str
    url: str


type BreadcrumbEntry = BreadcrumbObject | BreadcrumbDict


View = TypeVar("View", bound=Callable[..., object])


def default_breadcrumb_root(app: Flask | Blueprint, path: str) -> None:
    """Register default breadcrumb path for all endpoints in this blueprint.

    :param app: The Flask or Blueprint object.
    :param path: Path in the menu hierarchy.
        It should start with '.' to be relative to breadcrumbs root.
    """
    if path.startswith("."):
        # Path relative to breadcrumb root
        bl_path = LocalProxy(lambda: (breadcrumb_root_path + path).strip("."))
    else:
        bl_path = path

    setattr(app, "__breadcrumb__", bl_path)  # noqa: B010 - Flask has no typed slot


class Breadcrumbs(Menu):
    """Breadcrumb organizer for a Flask application."""

    def __init__(self, app: Flask | None = None, init_menu: bool = True) -> None:
        """Initialize Breadcrumb extension.

        :param app: The Flask object to configure.
        :param init_menu: If Flask-Menu should be initialized.
        """

        super().__init__()
        self.init_menu = init_menu

        if app:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Configure an application. This registers a `context_processor`.

        :param app: The Flask object to configure.
        """

        app.config.setdefault("BREADCRUMBS_ROOT", "breadcrumbs")
        app.context_processor(Breadcrumbs.breadcrumbs_context_processor)

        self.app = app

        # Follow the Flask guidelines on usage of app.extensions
        if not hasattr(app, "extensions"):
            app.extensions = {}
        if "menu" not in app.extensions:
            if self.init_menu:
                super().init_app(app)
            else:
                raise RuntimeError("Flask-Breadcrumbs is not initialized.")

    @staticmethod
    def current_path() -> str:
        """Determine current location in menu hierarchy.

        Backend function for current_path proxy.
        """
        # str(...) because __breadcrumb__ can hold a LocalProxy
        if hasattr(current_function, "__breadcrumb__"):
            return str(getattr(current_function, "__breadcrumb__", ""))

        return Breadcrumbs.get_path(current_blueprint._get_current_object())

    @staticmethod
    def breadcrumbs() -> list[BreadcrumbEntry]:
        """Backend function for breadcrumbs proxy.

        :return: A list of breadcrumbs.
        """
        # Construct breadcrumbs using their dynamic lists
        breadcrumb_list: list[BreadcrumbEntry] = []

        for entry in current_menu.list_path(breadcrumb_root_path, current_path) or []:
            breadcrumb_list += entry.dynamic_list

        return breadcrumb_list

    @staticmethod
    def breadcrumbs_context_processor() -> dict[str, LocalProxy[list[BreadcrumbEntry]]]:
        """Add variable ``breadcrumbs`` to template context.

        It contains the list of menu entries to render as breadcrumbs.
        """
        return {"breadcrumbs": current_breadcrumbs}

    @staticmethod
    def get_path(app: Flask | BlueprintBase) -> str:
        """Return path to root of application's or bluerpint's branch."""
        return str(
            getattr(
                app,
                "__breadcrumb__",
                breadcrumb_root_path
                + ("." + app.name if isinstance(app, Blueprint) else ""),
            )
        )


def register_breadcrumb(
    app: Flask | Blueprint,
    path: str,
    text: str,
    order: int = 0,
    endpoint_arguments_constructor: Callable[[], dict[str, Any]] | None = None,
    dynamic_list_constructor: Callable[[], list[BreadcrumbEntry]] | None = None,
) -> Callable[[View], View]:
    """Decorate endpoints that should be displayed as a breadcrumb.

    :param app: Application or Blueprint which owns the function.
    :param path: Path to this item in menu hierarchy
        ('breadcrumbs.' is automatically added).
    :param text: Text displayed as link.
    :param order: Index of item among other items in the same menu.
    :param endpoint_arguments_constructor: Function returning dict of
        arguments passed to url_for when creating the link.
    :param dynamic_list_constructor: Function returning a list of
        breadcrumbs to be displayed by this item. Every object should
        have 'text' and 'url' properties/dict elements.
    """
    # Resolve blueprint-relative paths
    if path.startswith("."):

        def _evaluate_path() -> str:
            """Lazy path evaluation."""
            bl_path = Breadcrumbs.get_path(app)
            return (bl_path + path).strip(".")

        func_path = LocalProxy(_evaluate_path)

    else:
        func_path = path

    # Get standard menu decorator
    menu_decorator = _register_menu(
        app,
        func_path,
        text,
        order,
        endpoint_arguments_constructor=endpoint_arguments_constructor,
        dynamic_list_constructor=dynamic_list_constructor,
    )

    def breadcrumb_decorator(func: View) -> View:
        """Apply standard menu decorator and assign breadcrumb."""
        setattr(func, "__breadcrumb__", func_path)  # noqa: B010 - view has no typed slot

        return menu_decorator(func)

    return breadcrumb_decorator


def _lookup_current_function() -> RouteCallable | None:
    """Return current view function for request endpoint."""
    return current_app.view_functions.get(request.endpoint)


def _lookup_current_blueprint() -> Flask | BlueprintBase:
    """Return current :class:`~flask.Blueprint` instance.

    Alternatively return :class:`~flask.Flask` application object when no
    blueprint is activated during request.
    """
    return current_app.blueprints.get(
        request.blueprint, cast("LocalProxy[Flask]", current_app)._get_current_object()
    )  # pylint: disable=W0212


def _lookup_breadcrumb_root_path() -> str:
    """Backend function for breadcrumb_root_path proxy."""
    return cast(str, current_app.config.get("BREADCRUMBS_ROOT"))


def _register_menu(
    app: Flask | Blueprint,
    path: LocalProxy[str] | str,
    text: str,
    order: int = 0,
    endpoint_arguments_constructor: Callable[[], dict[str, Any]] | None = None,
    dynamic_list_constructor: Callable[[], list[BreadcrumbEntry]] | None = None,
) -> Callable[[View], View]:
    """Register a menu entry before the application's first request.

    Flask no longer has a before-first-request hook. A one-time before-request
    callback also lets relative paths resolve after the app is initialized.
    """

    def menu_decorator(view: View) -> View:
        expected_args = getfullargspec(view).args
        view_name = cast(str, getattr(view, "__name__"))  # noqa: B009 - not on Callable

        def add_registration(flask_app: Flask, endpoint: str) -> None:
            registered = False

            @flask_app.before_request
            def register_item() -> None:
                nonlocal registered
                if registered:
                    return

                # Evaluate blueprint-relative paths inside the request context.
                item = current_menu.submenu(str(path))
                item.register(
                    endpoint,
                    text,
                    order,
                    endpoint_arguments_constructor=endpoint_arguments_constructor,
                    dynamic_list_constructor=dynamic_list_constructor,
                    expected_args=expected_args,
                )
                registered = True

        if isinstance(app, Blueprint):

            @app.record
            def register_blueprint(state: BlueprintSetupState) -> None:
                endpoint = f"{state.name_prefix}.{state.name}.{view_name}".lstrip(".")
                add_registration(cast(Flask, state.app), endpoint)
        else:
            add_registration(app, view_name)

        return view

    return menu_decorator


# Proxies
# pylint: disable-msg=C0103


#: A proxy for the current function.
current_function = LocalProxy(_lookup_current_function)

#: A proxy for the current blueprint or application object.
current_blueprint = LocalProxy(_lookup_current_blueprint)

#: A proxy for breadcrumbs root element path.
breadcrumb_root_path = LocalProxy(_lookup_breadcrumb_root_path)

#: A proxy for detecting current breadcrumb path.
current_path = LocalProxy(Breadcrumbs.current_path)

#: A proxy for current breadcrumbs list.
current_breadcrumbs = LocalProxy(Breadcrumbs.breadcrumbs)
# pylint: enable-msg=C0103
