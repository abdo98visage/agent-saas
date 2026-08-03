from contextvars import ContextVar


correlation_id_context: ContextVar[str | None] = ContextVar("correlation_id", default=None)
trace_id_context: ContextVar[str | None] = ContextVar("trace_id", default=None)


def current_correlation_id() -> str | None:
    return correlation_id_context.get()


def current_trace_id() -> str | None:
    return trace_id_context.get()
