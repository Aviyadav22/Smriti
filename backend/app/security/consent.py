"""User consent management for privacy compliance.

Provides the INSERT statement pattern used by auth.py for recording
user consent. The standalone record/check/revoke functions have been
removed as dead code — the consent INSERT is used inline in auth.py.
"""
