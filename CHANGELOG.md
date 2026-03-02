# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [In Development] - Unreleased

## [0.0.1] - 2026-02-22

### Added

- New `aa-todo` Alliance Auth plugin package based on the example plugin structure.
- Todo item model with per-group ownership, claim tracking, and done tracking.
- Access permissions for `basic_access` and `full_access`.
- Single-page todo management UI to create, claim, unclaim, and mark items done.
- Visibility and action rules for group members and claimed items, with `full_access` bypass.
- Unit test coverage for create/list/claim/done/unclaim behavior and permission rules.
- Optional `deadline` field for todo items, including create-form input and API/UI display.

### Changed

- App/package/module naming migrated from `example` to `todo`.
- Plugin metadata and docs updated for `aa-todo`.
- Removed inherited git/GitHub-specific repository and tooling artifacts from this app.
