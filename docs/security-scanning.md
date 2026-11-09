# Security scanning

CI uses Trivy **v0.76.2**, installed by a commit-pinned setup action.
The shared policy is in [`trivy.yaml`](../trivy.yaml). The entry point is
[`scripts/scan-security.sh`](../scripts/scan-security.sh).

## Coverage and failure policy

- **Project security:** scans the repository for known vulnerabilities in
  `backend/uv.lock` and `extension/package-lock.json`, supported infrastructure
  configuration (currently the backend Dockerfile), and exposed secrets.
  Development dependencies are included, including extension build/test tools.
- **Backend image security and publish:** builds `linux/amd64`, loads it into
  Docker, and scans installed OS/application packages and secrets. This runs
  on pull requests and pushes to `main`, after quality and project checks pass.
- Both checks block on **HIGH or CRITICAL** findings. Vulnerabilities without
  an available fix still block. Scan errors also fail the job.
- Each scan first saves JSON for **all severities**, then applies the blocking
  policy to that saved report. No second scan or database update is needed.
- Reports reflect reviewed exceptions and directory exclusions. Generated
  dependencies, build output, local caches, and graphify output are excluded;
  source files and lockfiles remain in scope. These exclusions apply only to
  filesystem scans, not image scans, so runtime virtual environments are checked.
  Trivy does not scan Git history.
- License checks and SBOM generation are not enabled.

The image job logs into GHCR only on pushes to `main`, after scanning succeeds.
It pushes the **same local image** that passed the scan; there is no rebuild
between scanning and publishing. Pull requests cannot publish images.

Configure GitHub branch protection to require **Project security** and
**Backend image security and publish**, as well as the existing quality checks.
Adding the workflow does not configure branch protection automatically.

## Reports

The `trivy-project` and `trivy-image` workflow artifacts contain JSON reports.
They are uploaded even when the severity gate fails and retained for seven days.
A scan error can prevent report creation; inspect the failed step's log.

Reports can contain sensitive details from secret findings. Restrict access as
needed, and never copy real credentials into issues or review comments. Rotate
exposed credentials immediately; deleting a file or ignoring a finding is not a
remedy for a leaked credential.

## Run locally

Install the pinned [Trivy release](https://github.com/aquasecurity/trivy/releases/tag/v0.76.2)
and run from the repository root:

```shell
trivy --version
bash scripts/scan-security.sh fs . .trivy-reports/project.json

docker build --platform linux/amd64 -t bee-there:security backend
TRIVY_IMAGE_SRC=docker bash scripts/scan-security.sh \
  image bee-there:security .trivy-reports/image.json
```

Exit code `0` means the configured gate passed. A nonzero code means findings
blocked the gate or scanning failed. Read the log to distinguish these cases.
The first scan needs network access to download security data. A database
failure must be fixed, not bypassed with an empty report or `continue-on-error`.
Local reports are ignored by Git and excluded from subsequent project scans.

## Review exceptions

[`.trivyignore.yaml`](../.trivyignore.yaml) starts with **no exceptions**.
Do not add blanket exclusions or disable a scanner to make CI green.

For each proposed exception:

1. Verify the finding, affected path, severity, and available fix.
2. Explain why it is a false positive or why the team accepts the risk.
3. Record the owner, review/issue link, and expiry date in a review comment
   and the `statement` field. The user must approve repository changes.
4. Restrict the exception to the finding ID and affected path when possible.
5. Set a short expiry, then remove it when fixed or no longer justified.

Example structure only; replace every placeholder before use:

```yaml
vulnerabilities:
  - id: CVE-YYYY-NNNNN
    paths:
      - backend/uv.lock
    statement: "Reason; owner: NAME; review: ISSUE-URL"
    expired_at: YYYY-MM-DD
misconfigurations: []
secrets: []
```

Use the matching `misconfigurations` or `secrets` list for those finding types.
Never add a real leaked credential as an exception. Report totals are computed
*after* active exceptions, so review the ignore file alongside the report.

## Validation limits

Trivy checks supported artifacts against known advisory data and rules. A clean
scan is not proof of security and does not replace tests, review, live API
security testing, runtime monitoring, or full-history secret scanning.
GitHub-hosted execution, image scanning, registry access, and branch protection
must be verified after this workflow is pushed.

References: [Trivy configuration](https://github.com/aquasecurity/trivy/blob/v0.76.2/docs/guide/references/configuration/config-file.md),
[filtering and exceptions](https://github.com/aquasecurity/trivy/blob/v0.76.2/docs/guide/configuration/filtering.md),
[report conversion](https://github.com/aquasecurity/trivy/blob/v0.76.2/docs/guide/references/configuration/cli/trivy_convert.md).
