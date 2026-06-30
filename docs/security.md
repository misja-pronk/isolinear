# Security

Isolinear is designed so that secret material is exposed as little as possible and is never written to disk.

## Security model

- **Values are never persisted.** Secret values are read on demand via the Databricks SDK and held only in memory for the duration of the session. They are never written to disk or to a cache.
- **Reveal is lazy.** Values are not bulk-pulled at startup. A value leaves Databricks only when you explicitly reveal or copy it.
- **Saved profiles store no secrets.** A saved profile writes only the `host` and `auth_type = external-browser` to `~/.databrickscfg`. Authentication is delegated to the Databricks SDK's unified auth / OAuth token cache — Isolinear never handles or stores a token itself.
- **The SDK boundary is isolated.** Only the `infrastructure/` layer touches the Databricks SDK or the network. The rest of the application — including the entire UI — has no path to the network.

!!! warning "Clipboard"
    Copying a value places it on your system clipboard. If you share your machine, clear the clipboard after you're done.

## Reporting a vulnerability

Please report security issues **privately** — not in a public issue.

- Open a [GitHub Security Advisory](https://github.com/misja-pronk/isolinear/security/advisories/new), or
- Email [misja@prorexconsultancy.nl](mailto:misja@prorexconsultancy.nl).

!!! danger "Do not file a public issue"
    Public issues are visible to everyone and can expose users before a fix is available. Always use one of the private channels above.
