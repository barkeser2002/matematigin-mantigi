"""İki offscreen ekranda sentetik kamera/ffmpeg ölçümü; gerçek donanım testi değildir."""
import argparse
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QTimer, QEventLoop
from PyQt6.QtWidgets import QApplication
from matematigin_mantigi.ui import camera_worker as cw
from matematigin_mantigi.ui.webcam_panel import WebcamPanel, CameraView
from matematigin_mantigi.ui.main_window import _Preview
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.core.chroma_key import ChromaParams
from matematigin_mantigi.core.recorder import MssFfmpegRecorder, RecordRect, RecorderState

parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True)
parser.add_argument('--seconds', type=float, default=6)
parser.add_argument('--source-width', type=int, default=1280,
                    help='Sentetik kamera genişliği (küçük kaynakla zamanlayıcı maliyetini ayır)')
parser.add_argument('--full', action='store_true')
a = parser.parse_args()
app = QApplication([])
assert len(app.screens()) == 2
metrics = defaultdict(list)
painted = defaultdict(set)
sampling = False


def timed(name, fn):
    def call(*args, **kw):
        start = time.perf_counter()
        try:
            return fn(*args, **kw)
        finally:
            if sampling:
                metrics[name].append((time.perf_counter() - start) * 1000)
    return call


for name in ['resize_to_width', 'apply_chroma_key_bgra', 'to_qimage_bgra', 'to_qimage_bgr']:
    setattr(cw, name, timed(name, getattr(cw, name)))
old_paint = CameraView.paintEvent


def measure_paint(self, event):
    name = 'paint_preview' if isinstance(self, _Preview) else 'paint_panel'
    timed(name, old_paint)(self, event)
    if sampling and self._frame is not None:
        painted[name].add(self._frame.cacheKey())


CameraView.paintEvent = measure_paint
cw.CameraWorker._deliver = timed('worker_deliver', cw.CameraWorker._deliver)
WebcamPanel._on_frame = timed('gui_receive', WebcamPanel._on_frame)


class Source:
    def __init__(self):
        self.opens = 0
        w, h = a.source_width, max(1, round(a.source_width * 9 / 16))
        self.frame = np.full((h, w, 3), (30, 200, 40), np.uint8)
        self.frame[h // 4:h * 3 // 4, w // 3:w * 2 // 3] = (20, 20, 220)

    def open(self):
        self.opens += 1
        return True

    def read(self):
        return self.frame

    def release(self):
        pass


results = []
for chroma, external in [(True, False), (True, True), (False, False), (False, True)]:
    source = Source()
    panel = WebcamPanel(FontFamilies('Arial', 'Arial', False), lambda: source,
                        ChromaParams(), chroma_enabled=chroma)
    panel.setGeometry(1500, 700, 320, 240)
    panel.show()
    preview = _Preview()
    preview.setGeometry(1920, 0, 1920, 1080)
    panel.frameReady.connect(preview.set_frame)
    panel.placeholderChanged.connect(preview.set_placeholder)
    if external:
        preview.show()
    delivered = [0]
    preview_delivered = [0]
    distinct = set()

    def on_frame(img):
        if sampling:
            delivered[0] += 1
            if external and preview._frame.cacheKey() == img.cacheKey():
                preview_delivered[0] += 1

    panel.frameReady.connect(on_frame)
    panel.start()
    warm = QEventLoop()
    QTimer.singleShot(1000, warm.quit)
    warm.exec()
    metrics.clear()
    painted.clear()
    lags = []
    last = [time.monotonic()]

    def heartbeat():
        now = time.monotonic()
        lags.append(max(0, (now - last[0]) * 1000 - 10))
        last[0] = now

    beat = QTimer()
    beat.setInterval(10)
    beat.timeout.connect(heartbeat)
    w, h = (1920, 1080) if a.full else (640, 360)
    frame = np.full((h, w, 4), 255, np.uint8)

    def grab(rect):
        if sampling:
            distinct.add(delivered[0])
        frame[10:70, 10:100, :3] = delivered[0] % 255
        return frame.copy()

    folder = Path(a.output).with_suffix('') / f'{chroma}-{external}'
    rec = MssFfmpegRecorder(lambda: folder, fps=30, grabber=grab, out_height=0)
    rec.start(RecordRect(0, 0, w, h), fps=30)
    assert rec.state is RecorderState.RECORDING
    first_written = rec.frames_written
    t0 = last[0] = time.monotonic()
    sampling = True
    beat.start()
    loop = QEventLoop()
    QTimer.singleShot(round(a.seconds * 1000), loop.quit)
    loop.exec()
    sampling = False  # finalize ve kapanış kareleri hiçbir fps/maliyet sayacına girmez
    duration = time.monotonic() - t0
    assert rec.state is RecorderState.RECORDING
    running_written = rec.frames_written - first_written
    camera_width = panel.view._frame.width() if panel.view._frame else None
    beat.stop()
    summary = {name: {'mean_ms': statistics.mean(v), 'p95_ms': float(np.percentile(v, 95)),
                      'calls': len(v)} for name, v in metrics.items() if v}
    result = {'chroma': chroma, 'preview': external, 'camera_width': camera_width,
              'source_width': a.source_width, 'seconds': duration,
              'camera_fps': delivered[0] / duration,
              'preview_delivered_fps': preview_delivered[0] / duration,
              'board_drawn_fps': len(painted['paint_panel']) / duration,
              'preview_drawn_fps': len(painted['paint_preview']) / duration,
              'record_fps': running_written / duration,
              'grab_unique_camera_frames': len(distinct), 'opens': source.opens,
              'heartbeat_p95_ms': float(np.percentile(lags, 95)),
              'heartbeat_max_ms': max(lags), 'timing': summary}
    panel.shutdown()
    assert panel.worker.wait(2000)
    path = rec.stop()
    result.update(frames_written=rec.frames_written, warning=rec.video_warning,
                  record_error=rec.error, path=str(path))
    results.append(result)
    print(json.dumps(result), flush=True)
    panel.close()
    preview.close()
    app.processEvents()
Path(a.output).write_text(json.dumps(results, indent=2))
