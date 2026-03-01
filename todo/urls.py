"""App URLs"""

# Django
from django.urls import path

# AA Todo App
from todo import views

app_name: str = "todo"  # pylint: disable=invalid-name

urlpatterns = [
    path("", views.index, name="index"),
    path("api/items/group/", views.api_group_items, name="api_group_items"),
    path("api/items/personal/", views.api_personal_items, name="api_personal_items"),
    path(
        "api/items/personal-other/",
        views.api_personal_other_items,
        name="api_personal_other_items",
    ),
    path("claim/<int:item_id>/", views.claim, name="claim"),
    path("unclaim/<int:item_id>/", views.unclaim, name="unclaim"),
    path("delete/<int:item_id>/", views.delete, name="delete"),
    path("done/<int:item_id>/", views.done, name="done"),
]
