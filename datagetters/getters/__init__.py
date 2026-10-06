"""Автовиявлення: будь-який клас-нащадок DataGetter у цій теці підхоплюється сам."""

import importlib
import pkgutil

from .base import DataGetter, Query  # noqa: F401


def discover() -> list[DataGetter]:
    for module in pkgutil.iter_modules(__path__):
        if module.name != "base":
            importlib.import_module(f"{__name__}.{module.name}")
    return [cls() for cls in DataGetter.__subclasses__()]