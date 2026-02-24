import time
from contextlib import contextmanager

@contextmanager
def timed(stage_name: str, trace: list):
    t0 = time.perf_counter()
    trace.append({"stage": stage_name, "status": "start"})
    try:
        yield
        dt = int((time.perf_counter() - t0) * 1000)
        trace.append({"stage": stage_name, "status": "ok", "ms": dt})
    except Exception as e:
        dt = int((time.perf_counter() - t0) * 1000)
        trace.append({"stage": stage_name, "status": "error", "ms": dt, "error": str(e)})
        raise