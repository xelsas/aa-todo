"""App views."""

from __future__ import annotations

# Django
from typing import Any, cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.handlers.wsgi import WSGIRequest
from django.core.paginator import Page, Paginator
from django.db.models import F, QuerySet
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import formats, timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

# AA Todo App
from todo.constants import CACHE_CONTROL_NO_STORE, PERM_BASIC_ACCESS, PERM_FULL_ACCESS
from todo.forms import TodoItemCreateForm
from todo.models import TodoItem, TodoStatus

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


def _parse_positive_int(
    raw_value: Any, *, default: int, max_value: int | None = None
) -> int:
    """Return a validated positive integer."""

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    if value < 1:
        return default
    if max_value is not None and value > max_value:
        return max_value
    return value


def _json_no_store(data: dict[str, Any], *, status: int = 200) -> JsonResponse:
    """Create a JSON response with no-store cache directive."""

    response = JsonResponse(data, status=status)
    response["Cache-Control"] = CACHE_CONTROL_NO_STORE
    return response


def _paginate_queryset(
    request: WSGIRequest, items_qs: QuerySet[TodoItem]
) -> tuple[Page[TodoItem], int, Paginator[TodoItem]]:
    """Paginate item queryset based on request query params."""

    # Each list on the page keeps its own page state, so pagination must be
    # driven by request params for every API call.
    page = _parse_positive_int(request.GET.get("page"), default=1)
    page_size = _parse_positive_int(
        request.GET.get("page_size"),
        default=DEFAULT_PAGE_SIZE,
        max_value=MAX_PAGE_SIZE,
    )
    paginator = Paginator(items_qs, page_size)
    return paginator.get_page(page), page_size, paginator


def _serialize_item(item: TodoItem, user: Any) -> dict[str, Any]:
    """Serialize item data for the todo list API."""

    is_full_access = user.has_perm(PERM_FULL_ACCESS)
    is_claimed_by_user = item.claimed_by_id == user.id
    is_done = item.status == TodoStatus.DONE

    can_claim = not is_done and item.claimed_by_id is None
    can_unclaim = (
        not is_done
        and item.claimed_by_id is not None
        and (is_full_access or is_claimed_by_user)
    )
    can_done = not is_done
    can_delete = item.can_delete(user)
    # Frontend receives explicit action flags so it can render controls without
    # re-implementing permission/state logic.

    return {
        "id": item.id,
        "group_name": item.group.name if item.group else None,
        "title": item.title,
        "description": item.description,
        "created_at_display": formats.date_format(
            timezone.localtime(item.created_at), "SHORT_DATETIME_FORMAT", use_l10n=True
        ),
        "deadline_display": (
            formats.date_format(item.deadline, "SHORT_DATE_FORMAT", use_l10n=True)
            if item.deadline
            else None
        ),
        "created_by": str(item.created_by) if item.created_by else None,
        "claimed_by": str(item.claimed_by) if item.claimed_by else None,
        "done_by": str(item.done_by) if item.done_by else None,
        "status": item.status,
        "status_display": item.get_status_display(),
        "can_claim": can_claim,
        "can_unclaim": can_unclaim,
        "can_done": can_done,
        "can_delete": can_delete,
        "urls": {
            "claim": reverse("todo:claim", args=[item.id]),
            "unclaim": reverse("todo:unclaim", args=[item.id]),
            "done": reverse("todo:done", args=[item.id]),
            "delete": reverse("todo:delete", args=[item.id]),
        },
    }


def _paginated_items_response(
    request: WSGIRequest, items_qs: QuerySet[TodoItem], user: Any
) -> JsonResponse:
    """Build paginated todo items response payload."""

    page_obj, page_size, paginator = _paginate_queryset(request, items_qs)
    data = {
        "results": [_serialize_item(item, user) for item in page_obj.object_list],
        "page": page_obj.number,
        "page_size": page_size,
        "total_pages": paginator.num_pages,
        "total_items": paginator.count,
        "has_next": page_obj.has_next(),
        "has_prev": page_obj.has_previous(),
    }
    return _json_no_store(data)


def _get_item_for_action(
    request: WSGIRequest, user: Any, item_id: int
) -> tuple[TodoItem | None, HttpResponse | None]:
    """Fetch item and verify access for mutating actions."""

    item = get_object_or_404(TodoItem, pk=item_id)
    if not item.can_access(user):
        messages.error(request, _("You do not have access to this item."))
        return None, redirect("todo:index")
    return item, None


def _todo_ui_config(user: Any) -> dict[str, Any]:
    """Return frontend config consumed by static todo JS."""

    # Keep UI strings and endpoint URLs in one payload to avoid duplicating
    # template constants inside the static JS module.
    return {
        "has_personal_other": user.has_perm(PERM_FULL_ACCESS),
        "urls": {
            "group": reverse("todo:api_group_items"),
            "personal": reverse("todo:api_personal_items"),
            "personal_other": reverse("todo:api_personal_other_items"),
        },
        "i18n": {
            "fallback_value": _("-"),
            "unclaim": _("Unclaim"),
            "claim": _("Claim"),
            "done": _("Done"),
            "delete": _("Delete"),
            "no_group_items": _("No group todo items yet."),
            "no_personal_items": _("No personal todo items yet."),
            "no_other_personal_items": _("No personal items from other users."),
            "loading_items": _("Loading items..."),
            "failed_load_items": _("Failed to load items."),
            "failed_load_items_status": _("Failed to load items (%(status)s)."),
            "page_meta": _("Page %(page)s of %(total_pages)s (%(total_items)s total)"),
            "prev": _("Prev"),
            "next": _("Next"),
        },
    }


@login_required
@permission_required(PERM_BASIC_ACCESS)
def index(request: WSGIRequest) -> HttpResponse:
    """Render todo index and handle todo creation."""

    user = cast(Any, request.user)

    if not user.groups.exists() and not user.has_perm(PERM_FULL_ACCESS):
        messages.warning(
            request,
            _(
                "You are not a member of any groups. You can still create personal todos."
            ),
        )

    if request.method == "POST":
        form = TodoItemCreateForm(request.POST, user=user)
        if form.is_valid():
            item = form.save(commit=False)
            item.created_by = user
            item.save()
            messages.success(request, _("Todo item created."))
            return redirect("todo:index")
        messages.error(request, _("Please fix the errors below and try again."))
    else:
        form = TodoItemCreateForm(user=user)

    context = {"form": form, "todo_ui_config": _todo_ui_config(user)}
    return render(request, "todo/index.html", context)


@login_required
@permission_required(PERM_BASIC_ACCESS)
@require_POST
def claim(request: WSGIRequest, item_id: int) -> HttpResponse:
    """Claim a todo item."""

    user = cast(Any, request.user)
    item, response = _get_item_for_action(request, user, item_id)
    if response:
        return response
    assert item is not None

    if item.status == TodoStatus.DONE:
        messages.info(request, _("This item is already done."))
    elif item.claimed_by is None:
        item.claimed_by = user
        item.claimed_at = timezone.now()
        item.save(update_fields=["claimed_by", "claimed_at"])
        messages.success(request, _("Todo item claimed."))
    else:
        messages.info(request, _("This item is already claimed."))

    return redirect("todo:index")


@login_required
@permission_required(PERM_BASIC_ACCESS)
@require_POST
def done(request: WSGIRequest, item_id: int) -> HttpResponse:
    """Mark a todo item as done."""

    user = cast(Any, request.user)
    item, response = _get_item_for_action(request, user, item_id)
    if response:
        return response
    assert item is not None

    if item.status == TodoStatus.DONE:
        messages.info(request, _("This item is already marked done."))
    else:
        if item.claimed_by is None:
            item.claimed_by = user
            item.claimed_at = timezone.now()
        item.status = TodoStatus.DONE
        item.done_by = user
        item.done_at = timezone.now()
        item.save(
            update_fields=[
                "claimed_by",
                "claimed_at",
                "status",
                "done_by",
                "done_at",
            ]
        )
        messages.success(request, _("Todo item marked done."))

    return redirect("todo:index")


@login_required
@permission_required(PERM_BASIC_ACCESS)
@require_POST
def unclaim(request: WSGIRequest, item_id: int) -> HttpResponse:
    """Unclaim a todo item."""

    user = cast(Any, request.user)
    item, response = _get_item_for_action(request, user, item_id)
    if response:
        return response
    assert item is not None

    if item.status == TodoStatus.DONE:
        messages.info(request, _("This item is already marked done."))
    elif item.claimed_by is None:
        messages.info(request, _("This item is not claimed."))
    elif user.has_perm(PERM_FULL_ACCESS) or item.claimed_by == user:
        item.claimed_by = None
        item.claimed_at = None
        item.save(update_fields=["claimed_by", "claimed_at"])
        messages.success(request, _("Todo item unclaimed."))
    else:
        messages.error(request, _("You can only unclaim items you claimed."))

    return redirect("todo:index")


@login_required
@permission_required(PERM_BASIC_ACCESS)
@require_POST
def delete(request: WSGIRequest, item_id: int) -> HttpResponse:
    """Delete a todo item."""

    user = cast(Any, request.user)
    item = get_object_or_404(TodoItem, pk=item_id)

    if item.can_delete(user):
        item.delete()
        messages.success(request, _("Todo item deleted."))
    else:
        messages.error(request, _("You do not have permission to delete this item."))

    return redirect("todo:index")


@login_required
@permission_required(PERM_BASIC_ACCESS)
@require_GET
def api_group_items(request: WSGIRequest) -> JsonResponse:
    """Return group items visible to the current user."""

    user = cast(Any, request.user)
    items_qs = (
        TodoItem.objects.group_items_visible_to(user)
        .with_related()
        .order_by(F("deadline").asc(nulls_last=True), "created_at")
    )
    return _paginated_items_response(request, items_qs, user)


@login_required
@permission_required(PERM_BASIC_ACCESS)
@require_GET
def api_personal_items(request: WSGIRequest) -> JsonResponse:
    """Return personal items owned by the current user."""

    user = cast(Any, request.user)
    items_qs = (
        TodoItem.objects.personal_items_for_user(user)
        .with_related()
        .order_by(F("deadline").asc(nulls_last=True), "created_at")
    )
    return _paginated_items_response(request, items_qs, user)


@login_required
@permission_required(PERM_BASIC_ACCESS)
@require_GET
def api_personal_other_items(request: WSGIRequest) -> JsonResponse:
    """Return personal items created by other users for full-access users."""

    user = cast(Any, request.user)
    if not user.has_perm(PERM_FULL_ACCESS):
        return _json_no_store({"detail": _("Forbidden")}, status=403)

    items_qs = (
        TodoItem.objects.personal_other_items_for_user(user)
        .with_related()
        .order_by(F("deadline").asc(nulls_last=True), "created_at")
    )
    return _paginated_items_response(request, items_qs, user)
