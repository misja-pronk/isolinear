# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- The scopes pane now scales out to fit long scope names. A fixed `max-width`
  cap was clamping it even when the terminal had plenty of room, truncating long
  names and clipping the secret-count column; the cap is now proportional (50%
  of the row) so it grows with the terminal but never dominates a narrow one.

## [0.2.3] - 2026-06-30

### Changed

- Panel widths: the scopes and secrets panes each size to their own content
  (as wide as they need, no wider), and the detail pane fills the remaining
  space — so the inspector gets the room instead of the secrets list hogging it.

## [0.2.2] - 2026-06-30

### Fixed

- The scopes pane now sizes to the longest scope name (within bounds), so long
  scope names are no longer clipped while the detail pane keeps a usable width.
- Docs screenshots refreshed; the screenshot export now has a dark background
  (no white margin) so it reads well in dark-mode docs.

## [0.2.1] - 2026-06-30

### Fixed

- The three browser panes now share the row's width responsively: the detail
  pane grows with the terminal (and scopes flexes within bounds) instead of the
  secrets pane absorbing all the slack while detail stayed pinned narrow.

## [0.2.0] - 2026-06-30

A full UI redesign and an onboarding rework.

### Added

- **Graphite** — a calm, near-neutral default theme. Each browser section
  (scopes / secrets / detail) carries its own accent colour on its border,
  title, and selection; the violet / amber / phosphor skins remain optional.
- **Asset-bundle onboarding** — a `databricks.yml` in the working directory is
  parsed and its target workspace is offered as the pre-selected default.
- **Sortable tables** — click a column header or press `s` to sort the scopes
  and secrets tables, with a ↑ / ↓ indicator on the active column.
- **Permission colour-coding** — READ / WRITE / MANAGE are coloured by privilege
  across the permissions modal, the authorization overview, and the detail pane.
- An example `examples/databricks.yml` so the bundle source is easy to try, and a
  `CLAUDE.md` documenting the toolchain.

### Changed

- Onboarding is a single workspace picker that labels where each workspace comes
  from (`databricks.yml` / `~/.databrickscfg` / a typed URL).
- The detail pane is a fuller inspector: identity → your access + the scope's
  ACLs → the value.
- Modals share one layout — title, content, actions at the bottom; key-driven
  dialogs show a key hint, button dialogs put the shortcut in the button.
- The authorization overview drops the redundant Write / Manage columns and
  sorts scopes by your effective privilege.
- Calmer chrome throughout: no LCARS glyphs, colour blocks, or the "decrypt"
  reveal animation; quiet status copy.

### Removed

- Account-level workspace discovery (pick a cloud, paste an Account ID). Connect
  via a saved profile, an asset bundle, or a workspace URL instead.

### Fixed

- The scope-list selection highlight never rendered (the stylesheet used the
  wrong `--highlight` class instead of Textual's `-highlight`).
- The revealed-value card's right border was clipped by the detail-pane scroll
  gutter.
- Secret values, scope/secret/principal names, and error messages containing
  square brackets no longer crash rendering (they were parsed as Rich markup).
- Refreshing or sorting the scopes table no longer resets the selected secret or
  hides a revealed value; sorting the secrets table keeps the cursor in place.
- A `databricks.yml` whose default target has a templated host still falls back
  to the top-level `workspace.host`.
- The footer no longer goes stale after drilling into a scope with Enter.

## [0.1.0]

Initial release.

### Added

- Three-pane terminal browser for Databricks scopes, secrets, and ACLs.
- Onboarding: OAuth browser login by workspace URL, account-level workspace
  discovery (AWS / Azure / GCP), and saved `~/.databrickscfg` profiles.
- Create / edit / delete secrets, create / delete scopes, and manage scope
  permissions (ACLs).
- Reveal & copy secret values (fetched lazily; never bulk-loaded).
- Authorization overview of your effective permission per scope.
- Fuzzy filter (`/`), command palette (`ctrl+p`), vim + arrow navigation.
- Pre-loads and caches scopes/secrets/ACLs on startup.
- Three switchable themes (violet, amber Okudagram, phosphor green).

[Unreleased]: https://github.com/misja-pronk/isolinear/compare/v0.2.3...HEAD
[0.2.3]: https://github.com/misja-pronk/isolinear/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/misja-pronk/isolinear/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/misja-pronk/isolinear/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/misja-pronk/isolinear/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/misja-pronk/isolinear/releases/tag/v0.1.0
