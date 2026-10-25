"""Self-contained GitHub Actions SHA pinner, linter, and autofixer.

The executable entry point is the ``pinact`` launcher; this package holds the
implementation so the launcher stays a small path shim. Layout keeps one
concept per module: :mod:`pinact.pinning` owns ``uses:`` discovery and SHA
resolution, :mod:`pinact.lint` owns findings, :mod:`pinact.cli` owns dispatch.
Vendored PyYAML lives under :mod:`pinact._vendor` and is imported nowhere
else, so the tool runs under ``python3 -I`` with no site packages.
"""
