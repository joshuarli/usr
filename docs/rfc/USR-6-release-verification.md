# USR-6: Release assets are installed without publisher verification

Status: draft

Date: 2026-10-13

## Summary

`dl` installs binaries from release archives without verifying publisher signatures or trusted digests. This RFC records which trust root should authorize those assets.

## Motivation

TLS and GitHub ETags identify the downloaded response and detect changes, but they do not prove that an asset was published by the intended maintainer. macOS quarantine removal and ad-hoc signing do not add publisher authentication.

## Design

Require an authenticity check before installation. Candidate trust roots include publisher signatures or attestations tied to the expected repository identity, or reviewed digests stored in this repository and updated alongside release versions. Assets without a check would fail closed or remain unsupported.

## Alternatives considered

- Trust GitHub TLS and account security as the current implementation does. This preserves automatic updates but leaves compromised publisher accounts or release assets able to supply executable code.
- Verify signatures or attestations from each upstream publisher. This provides publisher identity where the release process supports it, but coverage may vary.
- Store expected digests in the repository. This gives reviewable pins but requires a trusted process for updating every digest and may constrain automatic newest-release selection.

## Open questions

- Must every downloaded executable have a publisher-authenticated signature, or are repository-reviewed digests sufficient?
- Should `dl` fail when a publisher has no supported verification method, or keep an explicit exception list?
- Should automatic newest-release selection remain enabled for assets that can be verified?

## Decision

Pending owner decision. Prefer a publisher-authenticated signature or attestation tied to the expected repository identity, and fail closed when no trusted verification is available.
