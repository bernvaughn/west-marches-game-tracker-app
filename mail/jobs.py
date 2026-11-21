"""Job registry for periodic email tasks."""

_jobs: dict[str, callable] = {}


def register_job(name: str, fn: callable) -> None:
    """Register a job function. Replaces any existing job with the same name."""
    _jobs[name] = fn


def registered_jobs() -> list[tuple[str, callable]]:
    """Return a list of (name, fn) for all registered jobs."""
    return list(_jobs.items())