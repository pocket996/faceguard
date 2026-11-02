"""Lightweight cancellation signal; does not load models or terminate other processes."""
class InferenceCancelled(Exception):
    pass
