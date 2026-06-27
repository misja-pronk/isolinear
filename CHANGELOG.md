# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
