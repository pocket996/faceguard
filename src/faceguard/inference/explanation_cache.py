"""Bounded, serialized explanation models; no ML imports during UI startup."""
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
import threading


def explanation_key(target='positive_logit', kind='gradcam'):
    return target if kind == 'gradcam' else kind + ':' + target


class ExplanationModelCache:
    def __init__(self, capacity=2):
        if capacity < 1:
            raise ValueError('Explanation cache capacity must be positive')
        self.capacity = capacity
        self._models = OrderedDict()
        self._lock = threading.RLock()
        self.loads = 0

    @contextmanager
    def borrow(self, checkpoint, sha256, device, check_cancel=lambda: None):
        # A cached model's temporary hooks must never be shared by two forwards.
        while not self._lock.acquire(timeout=.05):
            check_cancel()
        try:
            check_cancel()
            key = (str(Path(checkpoint).resolve()), sha256, str(device))
            if key not in self._models:
                while len(self._models) >= self.capacity:
                    self._models.popitem(last=False)
                from .core import load_detector
                loaded = load_detector(checkpoint, device)
                check_cancel()
                self._models[key] = loaded
                self.loads += 1
            self._models.move_to_end(key)
            yield self._models[key]
        finally:
            self._lock.release()

    def clear(self):
        with self._lock:
            self._models.clear()

    def __len__(self):
        with self._lock:
            return len(self._models)
