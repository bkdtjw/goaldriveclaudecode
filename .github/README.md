# GitHub Notes

This project keeps GitHub-specific notes in this folder.

## Publishing Default

In this environment, prefer the GitHub API for publishing updates.

Reason:
- `git push` over HTTPS has hit repeat TLS handshake failures here.
- Repeating device-flow login or token-based retries is noisy and wasteful.

Default rule:
- Prefer GitHub REST API upload/update flows for repo publishing tasks.
- Do not hardcode tokens in the repo.
- Reuse existing local credentials when available.
- Only fall back to normal Git push when the TLS path is confirmed working.
