# Security Policy

## How Isolinear handles secrets

- **Secret values are never persisted.** They're read on demand via the
  Databricks SDK (`get_secret`) and held only in memory for the current session.
- **Reveal is lazy.** Values are fetched only when you explicitly reveal or copy
  one — they are not bulk-pulled during the startup cache warm.
- **Saved profiles store no secrets.** When you save a connection, Isolinear
  writes only a `host` and `auth_type = external-browser` to `~/.databrickscfg`
  (the same thing `databricks auth login` does). Authentication is delegated to
  the Databricks SDK's unified auth / OAuth token cache.
- **The SDK boundary is isolated.** Only the `infrastructure/` layer touches the
  Databricks SDK or the network.

Copying a value places it on your system clipboard — clear it afterwards if you
share your machine.

## Supported versions

The latest released version on PyPI is supported. Please upgrade before
reporting an issue.

## Reporting a vulnerability

Please report security issues **privately**:

- Open a [GitHub Security Advisory](https://github.com/misja-pronk/isolinear/security/advisories/new), or
- email **misja@prorexconsultancy.nl**.

Do not open a public issue for security reports. You'll get an acknowledgement
as soon as possible, and we'll coordinate a fix and disclosure with you.
