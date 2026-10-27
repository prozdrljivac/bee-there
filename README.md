# BeeThere

## Browser extension

Build, test, and install the Chrome extension by following
[`extension/README.md`](extension/README.md).

## Git hooks

Install the repository hooks after cloning:

```shell
uv run --project backend pre-commit install --hook-type pre-commit --hook-type commit-msg
```

Commit messages must use the Conventional Commits header format:

```text
<type>[optional scope][optional !]: <description>
```

