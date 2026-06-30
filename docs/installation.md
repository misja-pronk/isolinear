# Installation

## Requirements

- **Python ≥ 3.11**
- A modern terminal on **macOS**, **Linux**, or **Windows**

Isolinear is distributed on PyPI. No configuration is required before you install or run it — connection details are gathered interactively on launch.

## Install

=== "uvx"

    Run the latest version once, ephemerally, without installing anything:

    ```sh
    uvx isolinear
    ```

=== "uv tool"

    Install `isolinear` (and the `iso` alias) onto your `PATH`:

    ```sh
    uv tool install isolinear
    ```

=== "pipx"

    Run once, or install persistently:

    ```sh
    pipx run isolinear
    ```

    ```sh
    pipx install isolinear
    ```

## Running

Once installed, launch the app with either command:

```sh
isolinear
```

```sh
iso
```

Both open the workspace picker. See [Connecting](connecting.md) for what happens next.

## Upgrading

=== "uvx"

    `uvx` always fetches the latest published version, so there is nothing to upgrade. To refresh a cached run:

    ```sh
    uvx isolinear@latest
    ```

=== "uv tool"

    ```sh
    uv tool upgrade isolinear
    ```

=== "pipx"

    ```sh
    pipx upgrade isolinear
    ```

!!! note "No config needed up front"
    Isolinear ships with sensible defaults and discovers your workspaces at runtime. You do not need to create a config file, set environment variables, or store a token before the first launch.
