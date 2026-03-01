"""Todo tests"""

# Standard Library
from unittest.mock import MagicMock, patch

# Alliance Auth
from allianceauth.tests.auth_utils import AuthUtils

# Django
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

# AA Todo App
from todo.forms import TodoItemCreateForm
from todo.models import TodoItem, TodoStatus, todo_group_visibility_q


class TestTodo(TestCase):
    """Todo app tests"""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.group_alpha = Group.objects.create(name="Alpha")
        cls.group_alpha.authgroup.hidden = False
        cls.group_alpha.authgroup.save()
        cls.group_bravo = Group.objects.create(name="Bravo")
        cls.group_bravo.authgroup.hidden = False
        cls.group_bravo.authgroup.save()
        cls.group_hidden = Group.objects.create(name="Hidden")
        cls.group_hidden.authgroup.hidden = True
        cls.group_hidden.authgroup.save()

        cls.basic_perm = Permission.objects.get(
            codename="basic_access", content_type__app_label="todo"
        )
        cls.full_perm = Permission.objects.get(
            codename="full_access", content_type__app_label="todo"
        )

        user_model = get_user_model()
        cls.user_alpha = user_model.objects.create_user(username="user_alpha")
        cls.user_alpha.user_permissions.add(cls.basic_perm)
        cls.user_alpha.groups.add(cls.group_alpha)
        AuthUtils.add_main_character(
            cls.user_alpha,
            "Alpha Main",
            "1000001",
            corp_id="2001",
            corp_name="Alpha Corp",
            corp_ticker="ALPHA",
        )

        cls.user_bravo = user_model.objects.create_user(username="user_bravo")
        cls.user_bravo.user_permissions.add(cls.basic_perm)
        cls.user_bravo.groups.add(cls.group_bravo)
        AuthUtils.add_main_character(
            cls.user_bravo,
            "Bravo Main",
            "1000002",
            corp_id="2002",
            corp_name="Bravo Corp",
            corp_ticker="BRAVO",
        )

        cls.user_admin = user_model.objects.create_user(username="user_admin")
        cls.user_admin.user_permissions.add(cls.basic_perm, cls.full_perm)
        AuthUtils.add_main_character(
            cls.user_admin,
            "Admin Main",
            "1000003",
            corp_id="2003",
            corp_name="Admin Corp",
            corp_ticker="ADMIN",
        )

    def login(self, user):
        self.client.force_login(user)

    def get_json(self, url_name, user, **params):
        self.login(user)
        response = self.client.get(reverse(url_name), params)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_create_item_limited_to_user_groups(self):
        # A basic_access user should be able to create items for groups they belong to.
        self.login(self.user_alpha)
        response = self.client.post(
            reverse("todo:index"),
            {
                "group": self.group_alpha.id,
                "title": "Alpha task",
                "description": "alpha",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TodoItem.objects.count(), 1)

        # The same user should NOT be able to create items for groups they do not belong to.
        response = self.client.post(
            reverse("todo:index"),
            {
                "group": self.group_bravo.id,
                "title": "Bravo task",
                "description": "bravo",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(TodoItem.objects.count(), 1)

    def test_index_filters_items_for_group_or_claimed(self):
        # Create items in different groups, plus one item claimed by the user.
        item_alpha = TodoItem.objects.create(
            group=self.group_alpha,
            title="Alpha only",
            created_by=self.user_alpha,
        )
        item_bravo = TodoItem.objects.create(
            group=self.group_bravo,
            title="Bravo only",
            created_by=self.user_bravo,
        )
        item_claimed = TodoItem.objects.create(
            group=self.group_bravo,
            title="Claimed by alpha",
            created_by=self.user_bravo,
            claimed_by=self.user_alpha,
        )

        # The group-items API should include user's groups and items they claimed.
        payload = self.get_json("todo:api_group_items", self.user_alpha)
        item_ids = {item["id"] for item in payload["results"]}

        self.assertIn(item_alpha.id, item_ids)
        self.assertIn(item_claimed.id, item_ids)
        self.assertNotIn(item_bravo.id, item_ids)

    def test_full_access_sees_all_and_can_create_any_group(self):
        # Seed items in different groups to verify full_access visibility.
        TodoItem.objects.create(
            group=self.group_alpha,
            title="Alpha task",
            created_by=self.user_alpha,
        )
        TodoItem.objects.create(
            group=self.group_bravo,
            title="Bravo task",
            created_by=self.user_bravo,
        )

        # full_access users should see all items regardless of group membership.
        payload = self.get_json("todo:api_group_items", self.user_admin)
        self.assertEqual(payload["total_items"], 2)

        # full_access users should be able to create items for any group.
        response = self.client.post(
            reverse("todo:index"),
            {
                "group": self.group_bravo.id,
                "title": "Admin bravo",
                "description": "admin",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TodoItem.objects.count(), 3)

    def test_claim_requires_group_or_full_access(self):
        # Create an item in a group the first user does not belong to.
        item = TodoItem.objects.create(
            group=self.group_bravo,
            title="Claim me",
            created_by=self.user_bravo,
        )

        # A user outside the group should be blocked from claiming it.
        self.login(self.user_alpha)
        response = self.client.post(reverse("todo:claim", args=[item.id]))
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertIsNone(item.claimed_by)

        # A user inside the group should be able to claim it.
        self.login(self.user_bravo)
        response = self.client.post(reverse("todo:claim", args=[item.id]))
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.claimed_by, self.user_bravo)

    def test_done_requires_group_or_claimed(self):
        # Create an item claimed by user_alpha even though it belongs to group_bravo.
        item = TodoItem.objects.create(
            group=self.group_bravo,
            title="Finish me",
            created_by=self.user_bravo,
            claimed_by=self.user_alpha,
        )

        # The claimant should be allowed to mark it done even if not in the group.
        self.login(self.user_alpha)
        response = self.client.post(reverse("todo:done", args=[item.id]))
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.status, TodoStatus.DONE)
        self.assertEqual(item.done_by, self.user_alpha)

    def test_unclaim_rules(self):
        # Set up a claimed item to validate unclaim rules.
        item = TodoItem.objects.create(
            group=self.group_bravo,
            title="Unclaim me",
            created_by=self.user_bravo,
            claimed_by=self.user_alpha,
        )

        # A non-claimant without full_access cannot unclaim the item.
        self.login(self.user_bravo)
        response = self.client.post(reverse("todo:unclaim", args=[item.id]))
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.claimed_by, self.user_alpha)

        # The claimant can unclaim their own item.
        self.login(self.user_alpha)
        response = self.client.post(reverse("todo:unclaim", args=[item.id]))
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertIsNone(item.claimed_by)

        # full_access users can unclaim items regardless of claimant.
        item.claimed_by = self.user_bravo
        item.save(update_fields=["claimed_by"])

        self.login(self.user_admin)
        response = self.client.post(reverse("todo:unclaim", args=[item.id]))
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertIsNone(item.claimed_by)

    def test_unclaim_blocked_when_done(self):
        # Done items should not be unclaimable even by the claimant.
        item = TodoItem.objects.create(
            group=self.group_alpha,
            title="Done item",
            created_by=self.user_alpha,
            claimed_by=self.user_alpha,
            status=TodoStatus.DONE,
        )

        # Attempting to unclaim should leave the item unchanged.
        self.login(self.user_alpha)
        response = self.client.post(reverse("todo:unclaim", args=[item.id]))
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.claimed_by, self.user_alpha)

    def test_delete_rules_for_basic_user(self):
        # Creator can delete an open and unclaimed item.
        item_open = TodoItem.objects.create(
            group=self.group_alpha,
            title="Delete me",
            created_by=self.user_alpha,
        )
        self.login(self.user_alpha)
        response = self.client.post(reverse("todo:delete", args=[item_open.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TodoItem.objects.filter(pk=item_open.pk).exists())

        # Creator cannot delete a claimed item.
        item_claimed = TodoItem.objects.create(
            group=self.group_alpha,
            title="Claimed item",
            created_by=self.user_alpha,
            claimed_by=self.user_alpha,
        )
        response = self.client.post(reverse("todo:delete", args=[item_claimed.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TodoItem.objects.filter(pk=item_claimed.pk).exists())

        # Creator cannot delete a done item.
        item_done = TodoItem.objects.create(
            group=self.group_alpha,
            title="Done item",
            created_by=self.user_alpha,
            status=TodoStatus.DONE,
            done_by=self.user_alpha,
        )
        response = self.client.post(reverse("todo:delete", args=[item_done.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TodoItem.objects.filter(pk=item_done.pk).exists())

        # Non-creator without full_access cannot delete another user's item.
        item_other = TodoItem.objects.create(
            group=self.group_alpha,
            title="Not your item",
            created_by=self.user_alpha,
        )
        self.login(self.user_bravo)
        response = self.client.post(reverse("todo:delete", args=[item_other.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TodoItem.objects.filter(pk=item_other.pk).exists())

    def test_delete_rules_for_full_access_user(self):
        # full_access can delete any item regardless of creator, claim, or status.
        item_claimed = TodoItem.objects.create(
            group=self.group_alpha,
            title="Claimed by someone",
            created_by=self.user_alpha,
            claimed_by=self.user_alpha,
        )
        item_done = TodoItem.objects.create(
            group=self.group_bravo,
            title="Already done",
            created_by=self.user_bravo,
            status=TodoStatus.DONE,
            done_by=self.user_bravo,
        )

        self.login(self.user_admin)
        response = self.client.post(reverse("todo:delete", args=[item_claimed.id]))
        self.assertEqual(response.status_code, 302)
        response = self.client.post(reverse("todo:delete", args=[item_done.id]))
        self.assertEqual(response.status_code, 302)

        self.assertFalse(TodoItem.objects.filter(pk=item_claimed.pk).exists())
        self.assertFalse(TodoItem.objects.filter(pk=item_done.pk).exists())

    def test_personal_items_visibility_and_creation(self):
        # Users can create personal items (no group selected).
        self.login(self.user_alpha)
        response = self.client.post(
            reverse("todo:index"),
            {
                "group": "",
                "title": "Personal alpha",
                "description": "private",
            },
        )
        self.assertEqual(response.status_code, 302)
        personal_item = TodoItem.objects.get(title="Personal alpha")
        self.assertIsNone(personal_item.group)
        self.assertEqual(personal_item.created_by, self.user_alpha)

        # Personal items are visible to creator and full_access only.
        payload = self.get_json("todo:api_personal_items", self.user_alpha)
        self.assertIn(personal_item.id, {item["id"] for item in payload["results"]})

        payload = self.get_json("todo:api_personal_items", self.user_bravo)
        self.assertNotIn(personal_item.id, {item["id"] for item in payload["results"]})
        payload = self.get_json("todo:api_group_items", self.user_bravo)
        self.assertNotIn(personal_item.id, {item["id"] for item in payload["results"]})

        payload = self.get_json("todo:api_personal_items", self.user_admin)
        self.assertNotIn(personal_item.id, {item["id"] for item in payload["results"]})
        payload = self.get_json("todo:api_personal_other_items", self.user_admin)
        self.assertIn(personal_item.id, {item["id"] for item in payload["results"]})

    def test_personal_items_claim_done_access(self):
        # A personal item should only be claimable/done by creator or full_access user.
        personal_item = TodoItem.objects.create(
            group=None,
            title="Private item",
            created_by=self.user_alpha,
        )

        self.login(self.user_bravo)
        response = self.client.post(reverse("todo:claim", args=[personal_item.id]))
        self.assertEqual(response.status_code, 302)
        personal_item.refresh_from_db()
        self.assertIsNone(personal_item.claimed_by)

        response = self.client.post(reverse("todo:done", args=[personal_item.id]))
        self.assertEqual(response.status_code, 302)
        personal_item.refresh_from_db()
        self.assertEqual(personal_item.status, TodoStatus.OPEN)

        self.login(self.user_alpha)
        response = self.client.post(reverse("todo:claim", args=[personal_item.id]))
        self.assertEqual(response.status_code, 302)
        personal_item.refresh_from_db()
        self.assertEqual(personal_item.claimed_by, self.user_alpha)

        self.login(self.user_admin)
        response = self.client.post(reverse("todo:done", args=[personal_item.id]))
        self.assertEqual(response.status_code, 302)
        personal_item.refresh_from_db()
        self.assertEqual(personal_item.status, TodoStatus.DONE)

    def test_hidden_groups_not_available_for_creation(self):
        # Hidden groups should not be selectable by normal users.
        self.login(self.user_alpha)
        response = self.client.post(
            reverse("todo:index"),
            {
                "group": self.group_hidden.id,
                "title": "Hidden group task",
                "description": "should fail",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TodoItem.objects.filter(title="Hidden group task").exists())

        # Hidden groups should also not be selectable by full_access users.
        self.login(self.user_admin)
        response = self.client.post(
            reverse("todo:index"),
            {
                "group": self.group_hidden.id,
                "title": "Hidden group admin task",
                "description": "should fail",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            TodoItem.objects.filter(title="Hidden group admin task").exists()
        )

    def test_hidden_group_items_not_listed_or_actionable(self):
        # Hidden-group items should not be listed, even for full_access users.
        hidden_item = TodoItem.objects.create(
            group=self.group_hidden,
            title="Hidden existing item",
            created_by=self.user_alpha,
        )

        self.login(self.user_admin)
        response = self.client.get(reverse("todo:api_group_items"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            hidden_item.id, {item["id"] for item in response.json()["results"]}
        )

        # Hidden-group items should not be claimable by non-full users,
        # even if the user is a member of that group.
        self.user_alpha.groups.add(self.group_hidden)
        self.login(self.user_alpha)
        response = self.client.post(reverse("todo:claim", args=[hidden_item.id]))
        self.assertEqual(response.status_code, 302)
        hidden_item.refresh_from_db()
        self.assertIsNone(hidden_item.claimed_by)

    def test_api_personal_other_requires_full_access(self):
        self.login(self.user_alpha)
        response = self.client.get(reverse("todo:api_personal_other_items"))
        self.assertEqual(response.status_code, 403)

    def test_api_pagination_is_independent_per_endpoint(self):
        for idx in range(12):
            TodoItem.objects.create(
                group=self.group_alpha,
                title=f"Group task {idx}",
                created_by=self.user_alpha,
            )
        for idx in range(7):
            TodoItem.objects.create(
                group=None,
                title=f"My personal task {idx}",
                created_by=self.user_alpha,
            )
        for idx in range(6):
            TodoItem.objects.create(
                group=None,
                title=f"Other personal task {idx}",
                created_by=self.user_bravo,
            )

        group_page_1 = self.get_json(
            "todo:api_group_items", self.user_admin, page=1, page_size=5
        )
        group_page_2 = self.get_json(
            "todo:api_group_items", self.user_admin, page=2, page_size=5
        )
        personal_page_1 = self.get_json(
            "todo:api_personal_items", self.user_alpha, page=1, page_size=3
        )
        other_page_1 = self.get_json(
            "todo:api_personal_other_items", self.user_admin, page=1, page_size=4
        )

        self.assertEqual(group_page_1["page"], 1)
        self.assertEqual(group_page_1["page_size"], 5)
        self.assertTrue(group_page_1["has_next"])
        self.assertEqual(len(group_page_1["results"]), 5)
        self.assertEqual(group_page_2["page"], 2)
        self.assertEqual(group_page_2["page_size"], 5)

        self.assertEqual(personal_page_1["page"], 1)
        self.assertEqual(personal_page_1["page_size"], 3)
        self.assertEqual(len(personal_page_1["results"]), 3)

        self.assertEqual(other_page_1["page"], 1)
        self.assertEqual(other_page_1["page_size"], 4)
        self.assertEqual(len(other_page_1["results"]), 4)

    def test_securegroups_visibility_q_includes_smartgroup(self):
        # When securegroups is installed, hidden groups are allowed if they are SmartGroups.
        with patch("todo.models.apps.is_installed", return_value=True):
            q = todo_group_visibility_q(prefix="group__")

        self.assertEqual(q.connector, "OR")
        self.assertIn(("group__authgroup__hidden", False), q.children)
        self.assertIn(("group__smartgroup__isnull", False), q.children)

    def test_form_uses_selectable_todo_groups(self):
        # Form should source group choices from the model visibility helper.
        mock_groups = MagicMock()
        mock_groups.order_by.return_value = mock_groups
        with patch(
            "todo.forms.selectable_todo_groups", return_value=mock_groups
        ) as select_groups_mock:
            form = TodoItemCreateForm(user=self.user_admin)

        self.assertTrue(select_groups_mock.called)
        self.assertTrue(mock_groups.order_by.called)
        self.assertIsNotNone(form.fields["group"].queryset)
