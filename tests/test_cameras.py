import numpy as np


def test_list_cameras_reports_frame_giving_indices(monkeypatch):
    import cv2
    from matematigin_mantigi.core import cameras

    class FakeCapture:
        def __init__(self, index, backend):
            self.index = index
        def isOpened(self):
            return self.index in (1, 3)
        def read(self):
            return (True, np.zeros((480, 640, 3), np.uint8)) if self.index in (1, 3) else (False, None)
        def release(self):
            pass

    monkeypatch.setattr(cv2, "VideoCapture", FakeCapture)
    cams = cameras.list_cameras(max_index=5)
    assert [(c.index, c.width, c.height) for c in cams] == [(1, 640, 480), (3, 640, 480)]
    assert cams[0].label == "Kamera 1 (640×480)"


def test_list_cameras_empty(monkeypatch):
    import cv2
    from matematigin_mantigi.core import cameras

    class Dead:
        def __init__(self, *a): pass
        def isOpened(self): return False
        def read(self): return (False, None)
        def release(self): pass

    monkeypatch.setattr(cv2, "VideoCapture", Dead)
    assert cameras.list_cameras(max_index=3) == []
