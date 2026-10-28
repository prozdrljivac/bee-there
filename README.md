# BeeThere

## Browser extension

Build, test, and install the Chrome extension by following
[`extension/README.md`](extension/README.md).

## Continuous integration and backend images

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on pull requests
and pushes to `main`:

- **Backend quality:** Ruff lint and format checks, mypy, and pytest with the
  90% coverage threshold. This includes the Docker smoke test for migrations,
  fixture ingestion, API responses, non-root use, and database persistence.
- **Extension tests:** locked npm dependencies, Puppeteer's bundled Chrome,
  and all extension tests, including the clean release journey with the real
  backend. An executable-specific AppArmor rule enables Chrome's sandbox on
  Ubuntu; the tests do not use `--no-sandbox`.
- **Publish backend image:** runs only after both jobs pass on a push to
  `main`. It builds `linux/amd64` and publishes
  `ghcr.io/<owner>/<repository>:sha-<full-commit-sha>`. Pull requests cannot
  publish images. No `latest` tag is published.

The jobs use read-only repository access. Only publishing receives
`packages: write`, using GitHub's built-in `GITHUB_TOKEN`; no personal token
is needed. Actions are pinned to full commit SHAs. Configure branch protection
in GitHub to require **Backend quality** and **Extension tests** before merging.

### Promote a backend image

1. Open the successful `main` workflow run and read the **Backend image**
   job summary. It records the full image tag and registry digest.
2. Decide the GHCR package visibility in GitHub. New packages are private by
   default. An existing package must grant this repository Actions access.
3. Pull the exact release, for example:

   ```shell
   docker pull --platform linux/amd64 ghcr.io/<owner>/<repository>:sha-<full-commit-sha>
   ```

4. Use that release for the API, migration init container, and ingestion job.
   Record both tag and digest. Do not move a SHA tag to another release.
   For strict immutability, deploy `ghcr.io/<owner>/<repository>@sha256:<digest>`:
   registry tags, including SHA-named tags, can be overwritten.
5. Verify the production cluster can pull it before rollout. Private images
   need a read-only package credential in a Kubernetes Secret, not in Git.

Publishing does not deploy the application. GitHub-hosted execution, GHCR
permissions, and production pulls must be verified after the workflow is
pushed. The API domain and package visibility remain deployment decisions.

## Git hooks

Install the repository hooks after cloning:

```shell
uv run --project backend pre-commit install --hook-type pre-commit --hook-type commit-msg
```

Commit messages must use the Conventional Commits header format:

```text
<type>[optional scope][optional !]: <description>
```

