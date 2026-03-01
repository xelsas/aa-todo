"""App Forms"""

# Django
from typing import TYPE_CHECKING, Any, cast

from django import forms
from django.utils.translation import gettext_lazy as _

# AA Todo App
from todo.constants import PERM_FULL_ACCESS
from todo.models import TodoItem, selectable_todo_groups

if TYPE_CHECKING:
    from django.contrib.auth.models import Group

    _TodoModelFormBase = forms.ModelForm[TodoItem]
    _GroupFieldType = forms.ModelChoiceField[Group]
else:
    _TodoModelFormBase = forms.ModelForm
    _GroupFieldType = forms.ModelChoiceField


class TodoItemCreateForm(_TodoModelFormBase):
    """Form for creating todo items"""

    class Meta:
        model = TodoItem
        fields = ("group", "title", "description")

    def __init__(self, *args: Any, user: Any = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        group_field = cast(_GroupFieldType, self.fields["group"])
        group_field.required = False
        visible_groups = selectable_todo_groups().order_by("name")
        if user is None:
            group_field.queryset = visible_groups
        elif user.has_perm(PERM_FULL_ACCESS):
            group_field.queryset = visible_groups
        else:
            group_field.queryset = visible_groups.filter(user=user)
        group_field.empty_label = _("Personal (no group)")
