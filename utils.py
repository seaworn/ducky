class Singleton:
    _cls = None
    _instance = None

    def __init__(self, cls):
        self._cls = cls

    def __call__(self, *args, **kwargs):
        if not isinstance(self._instance, self._cls):
            self._instance = self._cls(*args, **kwargs)
        return self._instance
