# Architecture

Isolinear follows a **hexagonal / DDD** design. Dependencies point **inward**, and all I/O sits behind domain ports, so the domain is fully unit-testable with no network.

```
src/isolinear/
  domain/          model, rules + ports (SecretStore, WorkspaceConnector,
                   ProfileStore, BundleStore)
  application/     use-cases (WorkspaceService, OnboardingService) + read model
  infrastructure/  adapters — the ONLY place the Databricks SDK is imported
  interface/       Textual presentation — no business logic, no infra imports
  app.py           composition root (wires it all together)
```

## Layers

- **`domain/`** — the model, rules, and ports (`SecretStore`, `WorkspaceConnector`, `ProfileStore`, `BundleStore`). It imports nothing outward.
- **`application/`** — use-cases (`WorkspaceService`, `OnboardingService`) and a read model that the interface consumes.
- **`infrastructure/`** — the adapters that implement the domain ports. This is the **only** place the Databricks SDK is imported.
- **`interface/`** — the Textual presentation. It holds no business logic and never imports infrastructure; it talks only to `application/` services. Theming lives in `interface/theme.py` and `styles.tcss`.
- **`app.py`** — the composition root that wires every layer together.

!!! note "The interface never imports the SDK"
    The boundary is strict: the UI talks to application services, application talks to domain ports, and only `infrastructure/` reaches for the Databricks SDK or the network. This is what keeps the domain testable without a workspace.

## Threading

Blocking I/O is kept **off the UI thread**. Services run in worker threads via `asyncio.to_thread`, so the terminal UI stays responsive while the SDK talks to Databricks.
