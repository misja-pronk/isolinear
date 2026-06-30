# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/misja-pronk/isolinear/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/misja-pronk/isolinear/releases/tag/v0.1.0
