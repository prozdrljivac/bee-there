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
- **Project security:** Trivy checks dependencies (including development
  dependencies), infrastructure configuration, and secrets.
- **Backend image security and publish:** after the other jobs pass, builds
  `linux/amd64` and scans it with Trivy. Only pushes to `main` publish the exact
  scanned image as `ghcr.io/<owner>/<repository>:sha-<full-commit-sha>`.
  Pull requests scan but cannot publish. No `latest` tag is published.

Trivy blocks HIGH and CRITICAL findings, including unfixed vulnerabilities.
All-severity JSON reports are saved as workflow artifacts for seven days.
See [security scanning](docs/security-scanning.md) for local commands,
coverage, and the reviewed exception policy.

The jobs use read-only repository access. Only the image job receives
`packages: write`; registry login and publishing run only on pushes to `main`,
using GitHub's built-in `GITHUB_TOKEN`. No personal token is needed.
Actions are pinned to full commit SHAs. Configure branch protection in GitHub
to require **Backend quality**, **Extension tests**, **Project security**, and
**Backend image security and publish** before merging.

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

