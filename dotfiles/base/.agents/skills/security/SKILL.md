---
name: security
description: "Apply when code handles untrusted input that reaches an interpreter, secrets or credentials, authentication or authorization, cryptography, or a network trust decision. Skip paths and FFI (use os-boundaries), local-only tools with no untrusted input, and internal calls between trusted parts."
---

# Security

Fix what a realistic attacker can reach, in proportion to what they would gain. Hardening nobody can exploit is cost, not safety.

- **Name the attacker and the asset first,** in one line: who controls the input or reaches the port, and what they would gain. A personal tool on the owner's machine, with no untrusted input and no shared secret, has no finding. Say so and stop.
- **Match the deployment.** A local CLI, a LAN service, an internet-facing service, and a multi-tenant system warrant different defenses. Do not borrow the strictest.
- **Untrusted input never becomes code.** Parameterize queries, pass argv arrays instead of shell strings, escape at the output context, and parse untrusted data with formats that cannot execute (not pickle, not `eval`). Bound the size and depth of what you accept.
- **Secrets stay out of the repo, logs, argv, URLs, and error messages.** Load them from the environment or the vault. A leaked secret is rotated, not just removed.
- **Authorize on the server, on every request, deny by default.** Logging in is not permission. Check that the caller owns the object they name.
- **Use vetted crypto with its defaults.** Do not invent a scheme, mode, or token format. Use the OS random source for anything unguessable, a password hash (argon2, scrypt, bcrypt) for passwords, and constant-time comparison for secrets.
- **Never disable verification to make something work.** TLS certificate checks stay on, and a signature check stays enforced.
- **Errors tell the caller what to fix, not how the system is built.** Keep stack traces and internals in logs.
- **Maximal hardening is a mode you are asked for.** Absent that request, add no layers, config knobs, or checks on trusted internal callers. When asked, threat-model first, then defend in depth.

**The test:** what can a stranger who controls this input, or reaches this port, do that the owner did not intend?

Test the exploit, not the happy path: the hostile input is rejected, the unauthorized caller is refused, and the secret does not appear in output.

**Report:** the attacker and asset assumed, the risks closed, and the risks knowingly accepted and why.
