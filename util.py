from typing import Any


def fqn(obj: Any) -> str:
    """
    Get the fully qualified name of an object.
    """

    cls = obj if isinstance(obj, type) else obj.__class__
    if cls.__module__ == "builtins":
        return cls.__qualname__
    return f"{cls.__module__}.{cls.__qualname__}"
