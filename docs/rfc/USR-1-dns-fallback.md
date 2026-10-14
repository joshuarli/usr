# USR-1: The local DNS cache falls back to Cloudflare in the clear

Status: draft

Date: 2026-10-13

## Summary

The macOS resolver list includes localhost and `1.1.1.1`. If Unbound stops, macOS can send DNS queries directly to Cloudflare over plain DNS. This RFC records the choice between availability and avoiding that fallback.

## Motivation

The current fallback is explicit in `macos/setup-macos`. The setup prioritizes continued name resolution, while the fallback bypasses the local resolver and does not encrypt DNS traffic.

## Design

Choose one resolver policy for the stopped-Unbound case. The available policies are to keep the current plain DNS fallback, remove it and fail DNS until Unbound returns, or configure an encrypted upstream and retain a fallback through that resolver.

## Alternatives considered

- Keep `1.1.1.1` as the system fallback. This preserves availability and exposes queries to the network path and Cloudflare.
- Remove the fallback. This avoids direct plain DNS but makes name resolution fail when Unbound is unavailable.
- Route fallback queries through an encrypted resolver. This preserves more availability but adds resolver configuration and another dependency.

## Open questions

- Is continued DNS availability more important than avoiding a plain DNS fallback?
- Should the system resolver use a separate encrypted fallback if Unbound stops?

## Decision

Pending owner decision.
