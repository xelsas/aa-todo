"""Database models for the todo app."""

# Django
from typing import Any

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models
from django.db.models import F, Q
from django.db.models.query import QuerySet
from django.utils.translation import gettext_lazy as _

from todo.constants import PERM_FULL_ACCESS


def todo_group_visibility_q(prefix: str = "") -> Q:
    """Visibility rules for groups that can be used in todo."""

    q = Q(**{f"{prefix}authgroup__hidden": False})
    if apps.is_installed("securegroups"):
        q |= Q(**{f"{prefix}smartgroup__isnull": False})
    return q


def selectable_todo_groups() -> QuerySet[Group]:
    """Return groups that can be selected for todo items."""

    return Group.objects.filter(todo_group_visibility_q()).distinct()


def is_group_selectable_for_todo(group_id: int) -> bool:
    """Return whether a group is selectable for todo items."""

    return (
        Group.objects.filter(pk=group_id)
        .filter(todo_group_visibility_q(prefix=""))
        .exists()
    )


class General(models.Model):
    """Meta model for app permissions"""

    class Meta:
        """Meta definitions"""

        managed = False
        default_permissions = ()
        permissions = (
            ("basic_access", _("Can access this app")),
            ("full_access", _("Can fully access this app")),
        )


class TodoStatus(models.TextChoices):
    """Status values for todo items"""

    OPEN = "open", _("Open")
    DONE = "done", _("Done")


class TodoItemQuerySet(models.QuerySet["TodoItem"]):
    """Custom query helpers for todo item visibility."""

    def with_related(self) -> "TodoItemQuerySet":
        return self.select_related("group", "created_by", "claimed_by", "done_by")

    def for_api_list(self) -> "TodoItemQuerySet":
        """Return queryset with related models and default API ordering."""

        return self.with_related().order_by(
            F("deadline").asc(nulls_last=True), "created_at"
        )

    def group_items_visible_to(self, user: Any) -> "TodoItemQuerySet":
        qs = self.filter(group__isnull=False)
        if user.has_perm(PERM_FULL_ACCESS):
            return qs
        return qs.filter(Q(group__in=user.groups.all()) | Q(claimed_by=user))

    def personal_items_for_user(self, user: Any) -> "TodoItemQuerySet":
        return self.filter(group__isnull=True, created_by=user)

    def personal_other_items_for_user(self, user: Any) -> "TodoItemQuerySet":
        if user.has_perm(PERM_FULL_ACCESS):
            return self.filter(group__isnull=True).exclude(created_by=user)
        return self.none()


class TodoItem(models.Model):
    """A todo item tied directly to an auth group"""

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="todo_items",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    deadline = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="todo_items_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="todo_items_claimed",
    )
    claimed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=8, choices=TodoStatus.choices, default=TodoStatus.OPEN
    )
    done_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="todo_items_done",
    )
    done_at = models.DateTimeField(null=True, blank=True)
    objects = TodoItemQuerySet.as_manager()

    class Meta:
        """Meta definitions"""

        ordering = ["created_at"]
        default_permissions = ()

    def _creator_can_still_access_group_item(self) -> bool:
        """Return whether original creator still has access to this group item."""

        if self.group_id is None or self.created_by is None:
            return False
        return self.can_access(self.created_by)

    def can_access(self, user: Any) -> bool:
        """Return whether user may perform item actions."""

        if self.group_id is None:
            if user.has_perm(PERM_FULL_ACCESS):
                return True
            return bool(self.created_by_id == user.id)

        if user.has_perm(PERM_FULL_ACCESS):
            return True

        return bool(
            user.groups.filter(pk=self.group_id).exists()
            or self.claimed_by_id == user.id
        )

    def can_delete(self, user: Any) -> bool:
        """Return whether user may delete this todo item."""

        if user.has_perm(PERM_FULL_ACCESS):
            return True

        if (
            self.group_id is not None
            and not self._creator_can_still_access_group_item()
        ):
            return bool(user.groups.filter(pk=self.group_id).exists())

        if self.created_by_id != user.id:
            return False

        return bool(self.status != TodoStatus.DONE and self.claimed_by_id is None)

    def can_claim(self, user: Any) -> bool:
        """Return whether user may claim this todo item."""

        return bool(
            self.can_access(user)
            and self.status != TodoStatus.DONE
            and self.claimed_by_id is None
        )

    def can_unclaim(self, user: Any) -> bool:
        """Return whether user may unclaim this todo item."""

        return bool(
            self.can_access(user)
            and self.status != TodoStatus.DONE
            and self.claimed_by_id is not None
            and (user.has_perm(PERM_FULL_ACCESS) or self.claimed_by_id == user.id)
        )

    def can_done(self, user: Any) -> bool:
        """Return whether user may mark this todo item as done."""

        return bool(self.can_access(user) and self.status != TodoStatus.DONE)
