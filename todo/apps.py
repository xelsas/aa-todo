"""App Configuration"""

# Django
from django.apps import AppConfig

# AA Todo App
from todo import __version__


class TodoConfig(AppConfig):
    """App Config"""

    name = "todo"
    label = "todo"
    verbose_name = f"Todo App v{__version__}"
