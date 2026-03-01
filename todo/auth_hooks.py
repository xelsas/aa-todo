"""Hook into Alliance Auth"""

# Django
# Alliance Auth
from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook
from django.utils.translation import gettext_lazy as _

from todo import urls

# AA Todo App
from todo.constants import PERM_BASIC_ACCESS


class TodoMenuItem(MenuItemHook):
    """This class ensures only authorized users will see the menu entry"""

    def __init__(self):
        # setup menu entry for sidebar
        MenuItemHook.__init__(
            self,
            _("Todo"),
            "fas fa-cube fa-fw",
            "todo:index",
            navactive=["todo:"],
        )

    def render(self, request):
        """Render the menu item"""

        if request.user.has_perm(PERM_BASIC_ACCESS):
            return MenuItemHook.render(self, request)

        return ""


@hooks.register("menu_item_hook")
def register_menu():
    """Register the menu item"""

    return TodoMenuItem()


@hooks.register("url_hook")
def register_urls():
    """Register app urls"""

    return UrlHook(urls, "todo", r"^todo/")
