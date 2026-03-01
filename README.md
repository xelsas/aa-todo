# aa-todo

A small, practical todo app for Alliance Auth, built as a personal side project.

## What It Does

- Creates and manages todo lists
- Adds, updates, and tracks todo items
- Supports basic and full-access permissions

## Install (Development)

```bash
pip install -e aa-todo
```

## Install (Production)

```bash
pip install git+https://github.com/xelsas/aa-todo
```

## Setup

1. Add `todo` to `INSTALLED_APPS`.
2. Run migrations:

```bash
python manage.py migrate
```

3. Restart Alliance Auth services.

## Permissions

- `todo.basic_access`
  - Can open the todo app and use standard actions.
  - Can see group todos for their own groups.
  - Can see and manage their own personal todos.
  - Can claim/unclaim/complete items they can access, following item state rules.
- `todo.full_access`
  - Includes everything in `todo.basic_access`.
  - Can see todos across all visible groups.
  - Can see personal todos created by other users.
  - Can create todos for any visible group.
  - Can unclaim and delete items with elevated permissions.
