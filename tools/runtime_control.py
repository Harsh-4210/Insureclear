"""Cooperative stage-boundary controls; in-flight calls are not interrupted."""
import os
import time


class PipelineCancelled(RuntimeError): pass
class PipelineTimedOut(RuntimeError): pass
class PipelineBudgetExceeded(RuntimeError): pass


def usage_delta(before, after):
    result = {key: after[key] for key in ("provider", "model", "groq_configured_key_count") if key in after}
    for key in ("total_calls", "total_tokens", "total_retries", "total_429s", "total_time_seconds"):
        result[key] = max(0, after.get(key, 0) - before.get(key, 0))
    result["total_time_seconds"] = round(result["total_time_seconds"], 3)
    result["avg_time_per_call"] = round(result["total_time_seconds"] / result["total_calls"], 3) if result["total_calls"] else 0
    result["usage_scope"] = "case"
    return result


class RuntimeControl:
    def __init__(self, cancelled=None, seconds=None, clock=time.monotonic, stats=None, initial=None):
        self.cancelled = cancelled or (lambda: False)
        self.clock, self.started = clock, clock()
        self.seconds = float(seconds if seconds is not None else os.getenv("INSURECLEAR_CASE_TIMEOUT_SECONDS", "300"))
        self.max_calls = int(os.getenv("INSURECLEAR_CASE_MAX_CALLS", "20"))
        self.max_tokens = int(os.getenv("INSURECLEAR_CASE_MAX_TOKENS", "60000"))
        if self.seconds <= 0 or self.max_calls < 1 or self.max_tokens < 1:
            raise ValueError("Case time/call/token limits must be positive")
        self.stats, self.initial = stats, initial or (stats() if stats else {})

    def check(self):
        if self.cancelled():
            raise PipelineCancelled("Case cancellation requested")
        if self.clock() - self.started >= self.seconds:
            raise PipelineTimedOut("Case time limit reached at a stage boundary")
        if self.stats:
            usage = usage_delta(self.initial, self.stats())
            if usage["total_calls"] >= self.max_calls or usage["total_tokens"] >= self.max_tokens:
                raise PipelineBudgetExceeded("Case provider budget reached at a stage boundary")
