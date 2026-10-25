"""Vendored third-party sources used by pinact.

Only :mod:`pinact._vendor.yaml` (pure-Python PyYAML, no C extension) lives
here. It is imported as ``pinact._vendor.yaml`` so it can never shadow, or be
shadowed by, a site-packages ``yaml``.
"""
