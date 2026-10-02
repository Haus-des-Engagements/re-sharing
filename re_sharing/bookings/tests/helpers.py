from unittest.mock import patch


class SequentialExecutor:
    """
    Stand-in for ThreadPoolExecutor in tests.

    Worker threads open their own database connections, which cannot see the
    data of the test transaction. Running the work inline keeps every query on
    the test connection.
    """

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def map(self, function, iterable):
        return map(function, iterable)


def patch_thread_pool():
    return patch("concurrent.futures.ThreadPoolExecutor", SequentialExecutor)
