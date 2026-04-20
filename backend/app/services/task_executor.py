import os
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable


class TaskExecutor:
    """线程池任务执行器"""

    def __init__(self, max_workers: int = None):
        self._max_workers = max_workers or int(os.getenv("TASK_MAX_WORKERS", "3"))
        self._pool = ThreadPoolExecutor(max_workers=self._max_workers)

    def submit(self, fn: Callable[..., Any], *args, **kwargs) -> Future:
        return self._pool.submit(fn, *args, **kwargs)

    def shutdown(self, wait: bool = True):
        self._pool.shutdown(wait=wait)


task_executor = TaskExecutor()
