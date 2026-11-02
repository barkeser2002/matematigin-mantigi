# Sağlamlaştırma denetimi: doğrulanmış bulgular (kanıt dökümü)

Kaynak: 23.09.2026 ev PC oturumu (`0647ad5c`), iş akışı `wf_0569957b` (8 bulucu + 52 doğrulayıcı + 1 eleştirmen ajan) ve aynı gün tüm depoyu okuyan kıdemli inceleme (HEAD `f1d586f`). Tasarım belgesi: `2026-09-23-saglamlastirma-design.md`. Buradaki numaralar (alan#sıra) denetimin kendi numaralarıdır; tasarımdaki #1–#53 numaralarına içerikten eşlenir.

Yeniden üretim betikleri (`scratchpad/audit`, `scratchpad/review`) PC'de artık yok; her maddenin senaryo, yöntem ve kanıt metni testi yeniden yazmaya yetecek ayrıntıda aşağıda. Metinler denetimin özgün dilinde (İngilizce) bırakıldı. Satır numaraları `f1d586f` içindir.

**Toplam:** 52 bulgu · doğrulama: confirmed 51, uncertain 1 · önem: önemli 25, küçük 22, KRİTİK 5

## Özet tablo

| No | Önem | Başlık | Yer |
|---|---|---|---|
| rec#1 | KRİTİK | If the mic stops delivering mid-lesson, `-shortest` cuts the whole MP4 to the audio length, then the full-length raw video is deleted | `core/recorder.py:184` |
| rec#2 | KRİTİK | Pressing R while the previous recording is still finalising starts a new recording that takes over the paths the old stop thread is still using; the old lesson is never muxed | `ui/main_window.py:172` |
| e2e#1 | KRİTİK | If the mic drops out mid-lesson, `-shortest` cuts the whole video to the audio length, deletes the full-length intermediate file and reports no error | `core/recorder.py:184` |
| app#1 | KRİTİK | The R shortcut starts a new recording while the previous one is still being finalized and muxed. The old lesson is left un-muxed and the UI says 'not recording' while it records | `ui/main_window.py:172` |
| q#1 | KRİTİK | Typing the Turkish ordinal "7." in the editor's Sınıf field kills the whole app, including a running recording | `ui/question_editor.py:216` |
| rec#3 | önemli | Mic problems are reported only after the lesson ends, and only on the board's status line, which can be hidden and is overwritten by the next tool click | `ui/main_window.py:277` |
| rec#4 | önemli | The capture region is fixed at start: pressing Esc or F11, or resizing the window during a recording, makes it record a stale screen area such as the desktop or other apps | `ui/main_window.py:192` |
| rec#6 | önemli | Quitting while recording runs the whole finalise and mux on the GUI thread: roughly a one-minute freeze for a 60-minute lesson, and any error is thrown away | `ui/main_window.py:471` |
| e2e#2 | önemli | R during 'Kayıt kapatılıyor' starts a new recording while the previous stop is still muxing; the two recordings' files get mixed up and the UI shows the wrong state | `ui/main_window.py:172` |
| e2e#3 | önemli | If the mic fails to open, the whole lesson records without audio and nothing tells the teacher at start; at stop the only notice is the status line, which is often hidden | `ui/main_window.py:277` |
| e2e#4 | önemli | On a Mac Retina screen, the '2K' recording is an upscale of a point-resolution capture: mss grabs at nominal (1x) resolution | `core/recorder.py:248` |
| e2e#5 | önemli | After saving in the question editor, pictures disappear from the board in the packaged app and questions gain empty hint cards and empty options | `ui/question_editor.py:222` |
| e2e#6 | önemli | Saving in the question editor while the xlsx is open in Excel crashes the whole app, including a recording in progress (Windows) | `ui/question_editor.py:310` |
| e2e#8 | önemli | The recording region is fixed when recording starts; F11, a window resize or a move during recording records the wrong part of the screen, with no warning | `ui/main_window.py:275` |
| app#2 | önemli | No sys.excepthook: any exception in a slot aborts the whole app mid-lesson and leaves the recording un-muxed | `app.py:68` |
| app#3 | önemli | The capture rectangle is fixed at record start. Esc, F11 or a Settings change during recording silently records the wrong screen region | `ui/main_window.py:187` |
| app#4 | önemli | If the microphone fails to open at record start, the whole lesson records without audio and the only notice is a status-line suffix after stopping (invisible if the status line is hidden) | `ui/main_window.py:282` |
| app#5 | önemli | Closing the app while the background stop or mux is still running: closeEvent waits at most 60 s, then the app exits with _StopWorker still inside recorder.stop() | `ui/main_window.py:474` |
| q#2 | önemli | Kaydet has no error handling: a question file open in Excel (Windows) or a pasted control character aborts the app | `ui/question_editor.py:310` |
| q#3 | önemli | If the question file fails to load, the editor Kaydet overwrites the teacher's real file with the 3 sample questions | `app.py:35` |
| q#5 | önemli | After Kaydet, open-ended questions show empty "A) B) C) D)" and blank extra hint cards until restart | `ui/question_editor.py:222` |
| q#7 | önemli | A corrupt or empty question file crashes the app at launch with no message; the fallback only catches QuestionTemplateError | `app.py:34` |
| pen#2 | önemli | Undo after the board grows restores a smaller bitmap, so new ink in the grown area silently disappears | `ui/canvas.py:151` |
| pen#3 | önemli | Text still in the text box when the question changes is left out of Q1 and stamped onto Q2 | `ui/main_window.py:234` |
| cam#1 | önemli | Clicking 'Kameraları tara' in Settings kills the live webcam stream; after Vazgeç it stays dead | `ui/settings_dialog.py:232` |
| cam#2 | önemli | The app silently shows a different camera than the one selected (stderr-only fallback plus a bare persisted index) | `ui/camera_worker.py:39` |
| cam#4 | önemli | A camera dropout mid-lesson is permanent: no reconnect, and on macOS a frozen frame for about 31 s first | `ui/camera_worker.py:171` |
| geo#1 | önemli | The capture area is fixed when recording starts, so resizing, moving or fullscreening the window afterwards silently records the wrong part of the screen | `ui/main_window.py:275` |
| pkg#1 | önemli | Windows packaged exe: every ffmpeg launch opens a visible console/Terminal window, which stays over the whiteboard for the whole recording | `core/recorder.py:272` |
| pkg#2 | önemli | macOS: denied or not-yet-answered mic permission records pure silence, reported as a successful recording (made likely by a fresh ad-hoc signature on every push) | `core/recorder.py:387` |
| rec#5 | küçük | The '60 fps' recording holds only about 32 unique frames per second on the dev box: mss capture cannot reach 60 fps, and the writer fills the gap with duplicate frames | `core/recorder.py:420` |
| rec#7 | küçük | Video is converted with BT.601 coefficients and carries no colour tags, so players that assume BT.709 for HD shift the ink colours | `core/recorder.py:165` |
| e2e#7 | küçük | Ink undo history carries over between questions: Ctrl+Z on a new question brings back the previous question's drawing and saves it into that question's PNG | `ui/canvas.py:158` |
| app#6 | küçük | Pressing Enter in a Settings text field opens the font file picker instead of applying | `ui/settings_dialog.py:66` |
| q#4 | küçük | Editor save rebuilds the workbook from scratch and silently drops extra columns, other sheets and formatting | `core/question_loader.py:28` |
| q#6 | küçük | Double-clicking or double-tapping a hint card leaves it readable while the app treats it as hidden | `ui/hint_zone.py:288` |
| q#8 | küçük | Numeric, percent and date cells are shown as raw Python values (2,5 -> "2.5", %50 -> "0.5") | `core/question_loader.py:85` |
| pen#1 | küçük | A failed snapshot save on question change kills the app, and the running recording with it | `ui/main_window.py:236` |
| pen#4 | küçük | The current question's board is never saved on app close or question reload, despite the 'Otomatik kaydet: Her 30 sn' toggle | `ui/main_window.py:469` |
| pen#5 | küçük | One undo on a fresh question paints the previous question's whole board over it | `ui/main_window.py:237` |
| pen#6 | küçük | Ink is fixed in board pixels while the zones reflow, so annotations drift when the board is resized | `ui/canvas.py:285` |
| pen#7 | küçük | A missed TabletRelease leaves the pen stuck down, so a hovering pen draws lines | `ui/canvas.py:328` |
| pen#8 | küçük | The text box is hidden behind hint cards, so the teacher types blind | `ui/canvas.py:182` |
| cam#3 | küçük | macOS camera names are paired with the wrong OpenCV indices (ffmpeg order vs OpenCV's uniqueID sort) | `core/cameras.py:98` |
| cam#5 | küçük | Capture resolution is never requested; on macOS the webcam is captured at 480x360 and upscaled into the 2K recording | `ui/camera_worker.py:46` |
| geo#2 | küçük | Every relayout() creates and leaks 8 hidden eye buttons (dict.setdefault builds its default argument every time) | `ui/work_area.py:610` |
| geo#3 | küçük | The 'Ctrl: snap to grid' shortcut does not respond to the Control key on the target Mac | `ui/work_area.py:770` |
| geo#4 | küçük | Pulling a zone's edge outward past the board edge moves the opposite edge instead | `ui/work_area.py:749` |
| geo#5 | küçük | With the HUD frame, edit mode shows draggable BRAND/PRESENTER boxes for widgets that are hidden | `ui/work_area.py:694` |
| pkg#3 | küçük | macOS: denying 'access to Documents folder' makes the .app exit silently at every launch | `app.py:42` |
| pkg#4 | küçük | The release notes' Gatekeeper instruction ('sağ tık > Aç') no longer works on current macOS | `.github/workflows/release.yml:69` |
| pkg#5 | küçük | Info.plist claims macOS 12.0 minimum, but the bundled wheels need macOS 13/14 | `mac/matematigin_mantigi.spec:51` |

## Kayıt (kaydedici, mux, ses) (`rec`)

### rec#1 · KRİTİK · If the mic stops delivering mid-lesson, `-shortest` cuts the whole MP4 to the audio length, then the full-length raw video is deleted

- **Yer:** `src/matematigin_mantigi/core/recorder.py:184`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** After a 60-minute lesson where the mic dropped at minute 20, the teacher gets a 20-minute file. The other 40 minutes of video are deleted and nothing warns them. This is data loss in the product itself, and it is silent.

**Senaryo.** The teacher records with a USB or Bluetooth mic. Partway through the lesson the mic stops sending audio: it is unplugged, AirPods disconnect, or the WAV writer thread dies. AudioCapture.stop() still returns normally with samples > 0. _mux then builds the final file with `-shortest`, so the final MP4 ends where the audio ended. The mux returns rc 0, so lines 404-408 unlink the complete kayit_*.video.mp4 and the WAV. Neither audio_error nor error is set, and the status line reports success.

**Doğrulama yöntemi.** I read recorder.py from start() through _stop_locked(), _stop_audio(), _mux(), mux_args() and audio_rate_correction(), then audio_capture.py (AudioCapture, _callback, _write_loop, stop) and main_window._on_record_stopped. The auditor's fake bypassed AudioCapture entirely, so I did not reuse it. I wrote verify-rec/mic-unplug/repro.py, which runs the REAL AudioCapture and replaces only the sounddevice module (ac._sd). Its InputStream sends 48 kHz callbacks for 1.5 s and then stops, which is what CoreAudio does when a USB mic is unplugged or AirPods drop: stop() and close() still return normally. A second mode keeps the stream alive but makes the WAV writer thread raise OSError after 1.5 s, like a disk error. Both modes run through MssFfmpegRecorder with the synthetic grabber for 5 s at 30 fps, and ffprobe checks the result.

**Kanıt.** Mic unplug mode (real AudioCapture): frames_written=151, last_duration=5.0. error=None, audio_error=None, samples=71040. Only kayit_*.mp4 and kayit_*.log are left in the folder; .video.mp4 and .wav were deleted. ffprobe of the final MP4: video 1.400 s, audio 1.430 s, format 1.430 s.
Writer-death mode: same result. 150 frames were written, the final MP4 is 1.429 s, both errors are None, and the intermediates are deleted. The thread's exception only goes to stderr and never reaches the UI.
Code path, with no guard anywhere:
- mux_args always adds '-shortest' (recorder.py:184).
- _mux only rejects audio.samples <= 0 (recorder.py:387).
- audio_rate_correction returns None when the ppm gap is over 10_000 (recorder.py:196), so nothing stretches the audio. It is also skipped for recordings under 600 s.
- When rc==0 and out exists, the video and WAV are unlinked (recorder.py:404-408).
- main_window._on_record_stopped (main_window.py:302-324) then shows 'Kayıt kaydedildi: …' with no warning, because audio_error is None.
Nothing checks the output duration against last_duration or against the frame count. AudioCapture has no stall watchdog, and its callback does not look at a status flag for device loss. On a real Mac, if the unplugged stream's stop() raised instead of returning, _stop_audio would set audio_error and audio_result=None, and only the video would be kept. That would be safe. …

**Düzeltme taslağı.** recorder.py, mux_args: add 'apad' at the end of the -af chain, so af = [..., 'afade=t=in:st=0:d=0.01', 'apad']. Keep '-shortest'. Missing audio then becomes silence and the output always runs to the full video length, while audio that is longer than the video is still trimmed. As a safety net in MssFfmpegRecorder._mux, before unlinking the intermediates, ffprobe the output (or compare frames_written/fps). If its duration is noticeably shorter than the video's (for example by more than 1 s), keep kayit_*.video.mp4 and the .wav and set audio_error. Separately, in _mux, if audio.duration < last_duration - 2 s, set audio_error = 'Mikrofon kayıt sırasında kesildi (ses X sn / video Y sn)' so the status line warns the teacher. Optionally, AudioCapture._write_loop could catch exceptions into an error attribute that stop() passes back.

### rec#2 · KRİTİK · Pressing R while the previous recording is still finalising starts a new recording that takes over the paths the old stop thread is still using; the old lesson is never muxed

- **Yer:** `src/matematigin_mantigi/ui/main_window.py:172`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The previous lesson has no final MP4, only a raw video and a separate WAV. The user sees a confusing error about a different file, and the UI shows recording as off while it is actually on.

**Senaryo.** The teacher stops a recording with the button or R. The button is disabled and the status line says 'Kayıt kapatılıyor, ses birleştiriliyor…'. The R shortcut is not disabled. _stop_locked clears started_at (recorder.py:301) before the potentially long communicate() and mux, so is_recording is already False. A second R press therefore calls recorder.start(), which overwrites _video_path, last_path, _log_file, _proc and video_t0 while the stop thread is still running. The stop thread then reads self._video_path and self.last_path (recorder.py:317, 385), which now point at the NEW recording. After a 60-minute lesson this window is roughly 45 s or more: I measured the mux of 5 min of 2K60 video at 3.8 s.

**Doğrulama yöntemi.** Read main_window.py (_shortcuts line 172, toggle_recording 272-301, _on_record_stopped 303-324, _StopWorker 34-50) and recorder.py (start 241-284, stop/_stop_locked 286-322, _mux 382-408). Nothing guards the R shortcut. toggle_recording only checks recorder.is_recording and ignores whether a _StopWorker is still running. Recorder.start() does not take _stop_lock. _stop_locked clears started_at at line 301, before communicate(timeout=60) and _mux, and then reads self._video_path, self.last_path and self.video_t0 again (lines 317-321, 385). I wrote the pytest scratchpad/audit/verify-rec/r-race/test_r_race.py and ran it through the repo's conftest (qt_api=pyqt6, offscreen). It uses a real MssFfmpegRecorder with FakeAudioCapture and synthetic_grabber, and fires the real QShortcut("R") via activated.emit(). The only timing aid wraps recorder.subprocess.run with a 3 s sleep, which stands in fo …

**Kanıt.** Output of test_r_race.py:
- The first R starts lesson 1 (kayit_...100000). The second R stops it: the button is disabled and the status line reads 'Kayıt kapatılıyor, ses birleştiriliyor…'.
- A third R during finalisation gives `is_recording after 2nd R: True button enabled: False` and starts lesson 2 (kayit_...100007).
- The old stop thread then muxes lesson 1's WAV with lesson 2's still-open .video.mp4. The mux fails with 'Invalid data found when processing input'. The fallback `video.replace(out)` then raises WinError 32 on 'kayit_...100007.video.mp4' -> 'kayit_...100000.mp4'. That error is the only dialog shown.
- After the worker finishes: `is_recording True`, `toolbar checked False`, and the status line is still on 'Kayıt kapatılıyor…'. Recording 2 runs with no UI indication.
- Files left: kayit_...100000.video.mp4 and kayit_...100000.wav, never merged. `lesson-1 final mp4 exists: False`, and it is still False after recording 2 is stopped.
- On POSIX (the target Mac) the fallback rename would succeed. It would move lesson 2's open, still-growing .video.mp4 onto lesson 1's final name. When lesson 2 later stops, its _mux would not find self._video_path, and video.replace(out) would raise FileNotFoundError, so lesson 2 would not be finalised either. This is inferred from the code and not run on a Mac.
- A second issue in the same code: the old stop thread's _close_log() clos …

**Düzeltme taslağı.** 1. UI guard in src/matematigin_mantigi/ui/main_window.py, MainWindow.toggle_recording: at the top, `w = getattr(self, "_stop_worker", None)`; `if on and w is not None and w.isRunning(): return`. Also skip a second stop while the worker is running, so a double R does not create a second _StopWorker. Alternatively, have the R shortcut do nothing while `not self.toolbar.record_button.isEnabled()`.
2. Recorder guard in src/matematigin_mantigi/core/recorder.py: in MssFfmpegRecorder.start, `if not self._stop_lock.acquire(blocking=False): raise RecorderError("Önceki kayıt hâlâ kapatılıyor")` and release it after setup. As defence in depth, have _stop_locked copy _video_path, last_path, video_t0, _log_file and _log_path into locals before clearing started_at, and pass those to _mux, _close_log and _log_tail, so a later start() cannot redirect the finalisation.

### rec#3 · önemli · Mic problems are reported only after the lesson ends, and only on the board's status line, which can be hidden and is overwritten by the next tool click

- **Yer:** `src/matematigin_mantigi/ui/main_window.py:277`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** A full lesson can be recorded with no sound, and the teacher finds out only when watching it back. This is the silent failure class the owner said is the worst.

**Senaryo.** The configured mic cannot be opened, which sets recorder.audio_error at start (recorder.py:267-268). Or the mic opens but delivers nothing. On this machine 'Mikrofon (Realtek HD Audio Mic input)', 'Input (VB-Audio Point)', 'Hat Girişi' and 'Stereo Karışımı' all open without error and deliver 0 samples. toggle_recording never checks audio_error after start(), so the whole lesson records with no audio indicator. At stop, audio errors go only into the status_label text (main_window.py:322-324), never into a dialog. That label is a hideable board item ('status' in VISIBILITY_KEYS), and _status() replaces its text on the next tool, colour or width change (main_window.py:212, 222).

**Doğrulama yöntemi.** I read the code path: MainWindow.toggle_recording and _on_record_stopped (main_window.py:272-324), _status (228-232) and its callers (134, 135, 203, 212, 222), and the recorder's audio paths (recorder.py:261-268, 370-401). Then I wrote a scratch script at scratchpad/audit/verify-rec/mic-silent/v.py. It builds the real MainWindow with MssFfmpegRecorder, the synthetic grabber and real ffmpeg, plus a fake audio_factory with two modes. Mode "fail": start() raises. Mode "silent": stop() returns AudioResult with samples=0. For each mode the script records about 1.5 s, stops, captures every QMessageBox call, then calls _on_tool(ERASER).

**Kanıt.** The claim reproduces in both modes.

Mode "fail":
- Right after start: rec.is_recording=True and audio_error='Mikrofon açılamadı: PortAudio: Invalid device'.
- No dialog appeared. The status line still showed the normal tool text, so nothing on screen changed.
- After stop there was still no dialog. The status line read 'Kayıt kaydedildi: …kayit_….mp4 · yakalama ~59 kare/sn · UYARI: Mikrofon açılamadı: …'.
- After one _on_tool(ERASER) call it read 'Araç: Silgi · Kalınlık: 4 px · Basınç: XP-Pen' and the warning was gone.

Mode "silent": the same, with 'UYARI: Ses kaydedilemedi (örnek yok)' shown after stop and wiped by the tool click. No dialog at any point.

The code has no guard for this:
- toggle_recording (main_window.py:275-285) catches only RecorderError. It never reads recorder.audio_error after start(), even though the recorder already knows the mic failed (recorder.py:267-268 records the failure and keeps recording without sound).
- _on_record_stopped opens a dialog only for `err` (main_window.py:309-311). audio_err only goes into set_status (322-324).
- The status line is overwritten by _status on every tool, width or colour change (212, 222) and on every pen pressure change (main_window.py:134). So the warning also disappears as soon as the teacher starts the next drawing stroke.
- 'status' can be hidden via apply_ui_settings (main_window.py:418), in which case the wa …

**Düzeltme taslağı.** 1. In main_window.py MainWindow.toggle_recording, right after self.recorder.start() succeeds, check `if self.recorder.audio_error:` and show QMessageBox.warning(self, "Mikrofon", self.recorder.audio_error + " — kayıt SESSİZ sürüyor"). Also let the teacher stop at that point.
2. In _on_record_stopped, when audio_err is set, show QMessageBox.warning(self, "Kayıt sessiz", audio_err) in addition to the status text, instead of only the status text.
3. Optional, to catch the "opens but no samples" case during the lesson: in the existing badge tick handler (_check_recorder), after about 2 s of recording, check that the AudioCapture sample count is still 0. If it is, show a warning or turn the RecordBadge a warning colour, so the teacher sees it mid-lesson and not only at playback.

### rec#4 · önemli · The capture region is fixed at start: pressing Esc or F11, or resizing the window during a recording, makes it record a stale screen area such as the desktop or other apps

- **Yer:** `src/matematigin_mantigi/ui/main_window.py:192`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** From that point the rest of the lesson shows the wrong area, which can include the desktop, other windows or private content, and nothing tells the teacher.

**Senaryo.** The teacher records in full screen and presses Esc, for example to deselect something. When no text box is open and layout edit mode is off, _escape calls showNormal() (main_window.py:192-193). F11 does the same (line 178), as does dragging or resizing the window. recording_rect() is read only once, in toggle_recording (line 275), and the grab rect is baked into the capture thread (recorder.py:248, 283). Nothing updates or stops the recording when the stage moves.

**Doğrulama yöntemi.** Read main_window.py (_shortcuts, _escape, toggle_recording), work_area.py recording_rect/resizeEvent, core/recorder.py MssFfmpegRecorder.start/_grab_loop and app.py. Then wrote verify-rec/stale-rect/run.py. It uses the REAL MssFfmpegRecorder with an injected grabber that logs every rect it is asked to capture, runs offscreen in full screen, presses R (the real shortcut) to start, presses Esc, logs the rects grabbed afterwards, then stops the recording.

**Kanıt.** Output of the scratch run: "recording True stage at start (92, 202, 704, 396, 1.0)". After Esc: "fullscreen False recording True stage now (94, 89, 544, 306, 1.0)". Rects grabbed after Esc: {(92, 202, 704, 396)}. The capture thread keeps grabbing the old screen area. On stop, the status bar reports a normal success ("Kayit kaydedildi: ...mp4 · yakalama ~59 kare/sn") with no warning, so the failure is silent.

Code path, with no guard anywhere:
- main_window.py:187-193: _escape calls showNormal() when no text box is open and edit mode is off. Esc is registered with while_typing=True (line 179), so it is always live.
- main_window.py:178: F11 toggles the window state and does not check recorder.is_recording.
- main_window.py:275 is the only call to recording_rect(). recorder.py:248 builds grab_rect once, and recorder.py:283 passes it into the _loop thread args. The recorder has no API to update the rect.
- work_area.py:625 resizeEvent only calls relayout(). Nothing in MainWindow handles changeEvent, moveEvent or resize to stop or update the recording.

The scenario happens in real use. app.py:53/80 starts the app windowed at 1920x1080, so the teacher has to press F11 to go full screen. Starting the recording before F11 hits the same bug in reverse: the stage grows or moves and the capture stays on the old small area. mss grabs raw screen coordinates on every platform, so after th …

**Düzeltme taslağı.** This is the smallest correct fix, in src/matematigin_mantigi/ui/main_window.py. (1) In _escape and in the F11 lambda in _shortcuts, do not change the window state while self.recorder.is_recording; instead show a brief status message such as "Stop the recording before leaving full screen". (2) As a backstop for window-manager moves and resizes (macOS green button, dragging, a display change), override changeEvent (WindowStateChange), moveEvent and resizeEvent in MainWindow. Keep the rect captured in toggle_recording (self._rec_rect5). If self.recorder.is_recording and record_rect_for(self.work_area.recording_rect()) differs from it, call toggle_recording(False) and show a QMessageBox saying the recording was stopped because the board moved, so the failure is loud and not silent. The alternative, a live-updatable rect in MssFfmpegRecorder._grab_loop, is larger: the ffmpeg input size is fixed at start, so every frame would need rescaling.

### rec#5 · küçük · The '60 fps' recording holds only about 32 unique frames per second on the dev box: mss capture cannot reach 60 fps, and the writer fills the gap with duplicate frames

- **Yer:** `src/matematigin_mantigi/core/recorder.py:420`
- **Doğrulama:** uncertain (yeniden üretildi: False)
- **Öğretmene etkisi:** Recordings are not the promised 60 fps: pen motion and animations judder. On a Retina Mac each grab is about 4x larger, so capture is likely no faster (not verified).

**Senaryo.** The 60 fps requirement depends entirely on mss grabbing the stage at 60 Hz. When a grab takes longer than 16.7 ms, _loop writes the same bytes several times (lines 448-449) to keep the timing. The file is tagged 60 fps, and both the badge and the toolbar say 60 fps (main_window.py:283), but motion judders at the real capture rate. The only hint is 'yakalama ~NN kare/sn' in the status line after stop.

**Doğrulama yöntemi.** I read src/matematigin_mantigi/core/recorder.py: grab_screen (lines 104-113), _grab_loop (410-432), _loop (434-462) and the stop-time status in ui/main_window.py (lines 313-325). To time mss, I wrote scratchpad/audit/verify-rec/fps/grab.py. It could not run: every sct.grab failed with "BitBlt failed", because the console is now at LogonUI and this session is RDP-Tcp#0 with LockApp running. So I could not repeat the live measurement. Instead I ran ffprobe and ffmpeg mpdecimate on the auditor's own outputs in find-rec/out_tp_auto and out_tp_libx264.

**Kanıt.** The mechanism is real and nothing guards against it. _grab_loop only sets `self._latest` once per grab. _loop computes `due = int((now - t0) * fps) - frames_written` and writes the same `data` bytes as many times as needed to keep the output at 60/1. Nothing checks capture_fps during recording. The badge and toolbar keep showing "60 fps". The only hint comes after stop: "yakalama ~NN kare/sn" in the status line (main_window.py:314-315). The auditor's files are 2560x1440 at 60/1 with 900-901 frames. mpdecimate keeps only 156-173 frames, but the screen was mostly static, so that does not measure capture rate either way. The dev-box figure of 32 fps is confounded. `mss.monitors` shows one 1920x1080 "Generic PnP Monitor", which is the RDP virtual display. The console session is locked at LogonUI, and the only interactive session is RDP-Tcp#0. So the 31 ms per BitBlt was measured through RDP's software display path, not a local GPU-backed desktop, and it says little about the target. The target is an Apple Silicon Mac, where mss captures through CoreGraphics at Retina resolution. That path is often slower than 16.7 ms per grab, but I have not verified this. If the Mac grab is slower than 16.7 ms, the file is labelled 60 fps but holds fewer unique frames and motion judders. If it is faster, there is no defect. The recording is never corrupted or out of sync either way: duration, audi …

**Düzeltme taslağı.** Two fixes. First, make the shortfall visible. In MssFfmpegRecorder._loop in core/recorder.py, compute the running capture rate as frames_grabbed divided by elapsed time and expose it. MainWindow._on_tick in ui/main_window.py should then show it on RecordBadge, for example "~32 fps" instead of "60 fps" when it drops below 55. Also raise a warning after stop when capture_fps is below about 0.9 × fps. Second, the real fix: on macOS, replace the mss grabber with a native 60 Hz source. One option is ffmpeg's avfoundation screen input (`-f avfoundation -framerate 60 -capture_cursor 0 -i "<screen idx>:none"` plus a crop filter to the stage rect), started in MssFfmpegRecorder.start. The other is a ScreenCaptureKit stream feeding _latest, so the grab thread is no longer the frame-rate bottleneck.

### rec#6 · önemli · Quitting while recording runs the whole finalise and mux on the GUI thread: roughly a one-minute freeze for a 60-minute lesson, and any error is thrown away

- **Yer:** `src/matematigin_mantigi/ui/main_window.py:471`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The app appears hung for about a minute on quit. A force-quit leaves unmerged .video.mp4 and .wav files, and quit-time recording failures are silent.

**Senaryo.** The teacher closes the window or presses Cmd+Q during a lesson. There is no confirmation. closeEvent calls self.recorder.stop() synchronously. That joins the writer (up to 10 s), runs ffmpeg's faststart finalise (communicate up to 60 s), then the mux (timeout up to 2x the duration). None of it runs on the _StopWorker thread. Afterwards recorder.error and audio_error are never looked at.

**Doğrulama yöntemi.** Read the code path: main_window.py closeEvent (469-479), toggle_recording's stop branch (286-297), _StopWorker (34-49), _on_record_stopped (302-324), and core/recorder.py MssFfmpegRecorder.stop/_stop_locked/_mux (286-406). Then wrote a scratch pytest at C:\Users\bkese\AppData\Local\Temp\claude\C--Users-bkese-Desktop-arayuz-soru-sistemi-metematigin-mantigi\0647ad5c-ac9d-414d-ad34-9375fe87f54d\scratchpad\audit\verify-rec\quit-freeze\test_quit.py. It builds a real MainWindow with a fake recorder where is_recording=True, stop_is_quick=False, and stop() sleeps 3 s and then sets error and audio_error. A 50 ms QTimer counts event-loop ticks, QMessageBox.warning is monkeypatched to count dialogs, and the test calls win.close().

**Kanıt.** Scratch test output: "close returned True after 3.06s; stop ran on thread=MainThread; timer ticks during close=0; warnings shown=0". So closeEvent runs recorder.stop() on the GUI thread, the event loop is frozen for the whole stop (no timer ticks), and the recorder.error / audio_error that stop() set are never shown. Code confirms nothing prevents this:
- closeEvent at main_window.py:470-471 calls `self.recorder.stop()` directly. It ignores `stop_is_quick`, does not use _StopWorker, asks no confirmation, and never reads recorder.error or audio_error.
- MssFfmpegRecorder.stop (recorder.py:286-322) joins the writer (up to 10 s) and waits for ffmpeg to finish encoding and rewrite the file for +faststart (`communicate(timeout=60)`). _mux (382-406) then runs a second full-file ffmpeg pass with its own +faststart, with a timeout of max(120, 2*duration) seconds. For a 60-minute 2K60 lesson (about 7 GB at the auditor's measured rate) that is tens of seconds up to about a minute of beach ball on the GUI thread.
- Errors are dropped. Examples: "ffmpeg hata kodu N", "ffmpeg zamanında kapanmadı", "Ses birleştirilemedi", "Ses kaydedilemedi (örnek yok)". All end up only in attributes on an object that is about to be destroyed.
- What happens if the teacher force-quits during the freeze: a force quit during the video ffmpeg's faststart/communicate phase means _mux never runs. kayit_*.mp4 is n …

**Düzeltme taslağı.** In MainWindow.closeEvent (src/matematigin_mantigi/ui/main_window.py), when self.recorder.is_recording or self._stop_worker is running, don't stop synchronously. Instead:
1. If recording, call `self.toggle_recording(False)`. That starts _StopWorker and shows "Kayıt kapatılıyor, ses birleştiriliyor…".
2. Set a flag `self._close_after_stop = True` and call `e.ignore()`, then return.
3. At the end of _on_record_stopped, show any error or audio warning as it already does (a blocking QMessageBox is fine there). Then, if `_close_after_stop` is set, clear it and call `QTimer.singleShot(0, self.close)`.
Optionally ask a QMessageBox.question first ("Kayıt sürüyor, durdurup çıkılsın mı?"). This keeps the event loop alive, so there is no beach ball and less temptation to force-quit, and it makes quit-time failures visible. It also removes the capped `worker.wait(60000)`, because close is simply deferred until the worker's done signal arrives.

### rec#7 · küçük · Video is converted with BT.601 coefficients and carries no colour tags, so players that assume BT.709 for HD shift the ink colours

- **Yer:** `src/matematigin_mantigi/core/recorder.py:165`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** Coloured ink (red, green, blue) looks visibly different in the published video than on the board.

**Senaryo.** The BGRA frames are converted to yuv420p by swscale's default BT.601 matrix, and the output stream has no colorspace, range or primaries tags. Players and platforms (QuickTime, Safari, YouTube) assume BT.709 for untagged HD or 2K video, so saturated pen colours come out wrong.

**Doğrulama yöntemi.** I read ffmpeg_args (src/matematigin_mantigi/core/recorder.py:155-167) and mux_args (lines 170-185), and grepped all of src/ for colour tagging. My scratch script is verify-rec/color709/c.py under the scratchpad audit folder. It calls the real ffmpeg_args (2560x1440, 60 fps, out_height=1440, libx264) with BGRA frames holding red, green and blue ink. I then ran ffprobe on the stream colour fields, extracted the raw Y/U/V values and decoded them with both the BT.601 and BT.709 matrices. Last, I checked that a BT.709 scale plus setparams chain fixes both the samples and the tags.

**Kanıt.** Using the app's own ffmpeg_args with ffmpeg 7.1.1:
- ffprobe reports only pix_fmt=yuv420p. color_range, color_space, color_primaries and color_transfer are all missing, so the stream is untagged.
- Red ink BGRA(0,0,220) is encoded as Y=72, Cb-128=-33, Cr-128=96. That is the BT.601 limited-range result.
- Decoding with BT.601 gives red=(218,0,0), green=(0,161,0), blue=(0,1,219), which matches the board.
- Decoding with BT.709 gives red=(237,21,0), green=(0,136,0), blue=(0,14,228). Green loses about 25 levels and red shifts toward orange.
- The recorder never adds a scale filter at 2K. out_height == height, so the -vf branch at line 164 is skipped and swscale's implicit default (BT.601) does the conversion.
- mux_args uses -c:v copy and adds no tags, so the final MP4 is untagged as well.
- No colour tags anywhere: grep of src/ for colorspace, color_primaries, bt709, color_range or out_color finds nothing.
- The Mac path is affected too. The swscale conversion to yuv420p happens before any encoder (h264_videotoolbox included), and nothing sets the colour properties.
- Players such as mpv, Chromium and YouTube ingest, which usually assume BT.709 for untagged video at 1280 px width or more, will decode with the wrong matrix and shift the ink colours as shown above.
- The fix works: scale=out_color_matrix=bt709:out_range=tv followed by setparams gives Y=56 and bt709/tv tags on all fo …

**Düzeltme taslağı.** In recorder.py ffmpeg_args, always build the video filter chain instead of only when out_height differs:
  vf = [f"scale=-2:{out_height}:flags=bilinear"] if out_height and out_height != height else []
  vf += ["scale=out_color_matrix=bt709:out_range=tv", "setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv"]
  args += ["-filter_threads", "4", "-vf", ",".join(vf)]
The resize and the matrix change can also be merged into one scale call: scale=-2:H:flags=bilinear:out_color_matrix=bt709:out_range=tv. Also add the output flags -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv as a fallback for encoders that read the codec context, such as videotoolbox. mux_args needs no change, because -c:v copy keeps the tags. Add a test that runs ffprobe on a short recording and asserts color_space=bt709 and that pure red gives Y≈56.

## Uçtan uca ders akışı (`e2e`)

### e2e#1 · KRİTİK · If the mic drops out mid-lesson, `-shortest` cuts the whole video to the audio length, deletes the full-length intermediate file and reports no error

- **Yer:** `src/matematigin_mantigi/core/recorder.py:184`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** Silent loss of most of the recording: 20 of 30 minutes gone with no warning, and the only full copy is deleted automatically. This is the worst defect class for this app.

**Senaryo.** The teacher records a 30-minute lesson with a USB, Bluetooth or AirPods mic selected. The mic stops delivering samples at minute 10 (cable pulled, headset battery dies, Bluetooth drops). The PortAudio callback simply stops, so AudioResult.samples covers only 10 minutes. At stop, _mux runs ffmpeg with `-shortest` (line 184). Output is cut to the audio length, the mux returns 0, and lines 404-408 then unlink the full-length `.video.mp4` and the `.wav`.

**Doğrulama yöntemi.** I read recorder.py (mux_args at lines 170-185, _stop_locked at 294-323, _mux at 382-408), AudioCapture (audio_capture.py lines 115-222) and the UI consumer MainWindow._on_record_stopped (main_window.py lines 303-323). Unlike the auditor, who used a stubbed mic object, I ran the real AudioCapture class with a fake sounddevice module. Its InputStream calls the callback for 1 s and then goes quiet, the way a vanished CoreAudio device behaves, and stop() returns normally. I drove it with the real MssFfmpegRecorder (synthetic grabber, real ffmpeg) for a 6 s recording and checked the final file with ffprobe. Script: C:\Users\bkese\AppData\Local\Temp\claude\C--Users-bkese-Desktop-arayuz-soru-sistemi-metematigin-mantigi\0647ad5c-ac9d-414d-ad34-9375fe87f54d\scratchpad\audit\verify-e2e\mic-dropout\repro.py

**Kanıt.** Output of repro.py: `error: None | audio_error: None | last_duration: 6.00 | audio samples: 47040`, then `files left: ['kayit_...log', 'kayit_...mp4']`, then `final mp4 duration: 0.929000`. About 5 of the 6 recorded seconds are gone. Both the full-length .video.mp4 and the .wav are deleted, and nothing reports an error.

Code path, with no guard anywhere:
1. AudioCapture._callback / _write_loop (audio_capture.py:173-204) only count samples that actually arrive. Nothing checks for a stalled stream: no watchdog, no stream.active check, no finished_callback.
2. AudioCapture.stop (audio_capture.py:206-222) returns samples=what arrived, without comparing it to wall time.
3. recorder._mux (recorder.py:382-408) only checks `samples <= 0`. mux_args always appends `-shortest` (recorder.py:184), so the output is cut to the audio length. ffmpeg exits 0, and lines 404-408 then unlink the intermediate video and the wav.
4. audio_error stays None, so _on_record_stopped (main_window.py:323) shows "Kayıt kaydedildi: ..." with no warning.

The one partial guard: if the real stream.stop() raised on a dead device, _stop_audio would catch it and the full video would be kept. But PortAudio's CoreAudio backend is widely reported to leave the stream "active" with callbacks simply stopping when a USB or Bluetooth input disappears, and stop then returns normally. That is the case reproduced here. The o …

**Düzeltme taslağı.** Four small changes, all in src/matematigin_mantigi/core/recorder.py:

1. In mux_args, append "apad" to the audio filter chain (`af = [..., "afade=...", "apad"]`) and keep `-shortest`. The audio is then padded with silence up to the video's length, `-shortest` ends the file at the video's end, and the video is never shortened.
2. In MssFfmpegRecorder._mux, before running ffmpeg, add a check. If `audio.duration + max(offset, 0) < self.last_duration - 2.0`, set `self.audio_error = f"Mikrofon kayıt sırasında kesildi (~{audio.duration/60:.0f}. dk'dan sonra ses yok)"` so the teacher sees UYARI in the status bar.
3. As a safety net in _mux, delete the intermediate `.video.mp4` only if ffprobe reports the output duration to be at least the video duration minus 1 s. Otherwise keep it and set audio_error.
4. Optionally, in core/audio_capture.py AudioCapture, pass `finished_callback` and compare samples against wall time, so a stall is detected mid-lesson rather than only at stop.

### e2e#2 · önemli · R during 'Kayıt kapatılıyor' starts a new recording while the previous stop is still muxing; the two recordings' files get mixed up and the UI shows the wrong state

- **Yer:** `src/matematigin_mantigi/ui/main_window.py:172`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** Lesson 1 is never merged: its video and audio are left as separate files, or on macOS lesson 2 is saved under lesson 1's name. The toolbar shows the wrong recording state.

**Senaryo.** The teacher stops (toolbar button or R), so the mux runs in _StopWorker for several seconds on a long lesson, then presses R again to continue. The record button is disabled (line 293), but the R shortcut (line 172) calls toggle_recording directly. recorder.is_recording is already False because _stop_locked clears started_at (recorder.py:301) before ffmpeg flush and mux, so start() runs. start() overwrites self._video_path, last_path and _log_file (recorder.py:258-278). The old stop thread's _mux then works on the NEW recording's paths.

**Doğrulama yöntemi.** Read MainWindow.toggle_recording, _StopWorker, _on_record_stopped and the R shortcut (src/matematigin_mantigi/ui/main_window.py:34-50, 172, 272-324), plus MssFfmpegRecorder.start/stop/_stop_locked/_mux (src/matematigin_mantigi/core/recorder.py:241-408). Copied the auditor's script to scratchpad/audit/verify-e2e/restart-race/race.py, added an ffprobe check of the output files, and ran it headless. The script uses the real ffmpeg, a fake mic that writes a WAV, and a stepping clock so each recording gets its own name.

**Kanıt.** Nothing blocks a new start while the old stop is still finishing. The record button is disabled at main_window.py:293, but the R shortcut (line 172) calls toggle_recording(not recorder.is_recording) directly. _stop_locked clears started_at at recorder.py:301, so is_recording is already False. Only after that does it wait for ffmpeg to exit (proc.communicate, up to 60 s) and run _mux, which can take several seconds on a long lesson. start() does not take _stop_lock, and it overwrites _video_path (line 258), _log_path, _log_file, _audio, audio_result, last_path (line 278), video_t0 and error. The old stop thread then reads these shared fields: _mux uses `video, out = self._video_path, self.last_path` (line 385), and _close_log closes the new recording's log handle.

Run output: `stop worker running: True | record button enabled: False`, then `after R: recorder.is_recording = True kayit_20260923-100002.mp4`. The first stop's _mux tried to rename the new, still-open `kayit_...100002.video.mp4` onto `kayit_...100001.mp4`. The two fields were read between line 258 and line 278, so it got the new video path and the old output path. Windows refused with WinError 32, and the app showed a 'Kayıt hatası' dialog in the middle of recording 2.

Final files: `kayit_...100001.video.mp4` (video only, 3.0 s, per ffprobe) and `kayit_...100001.wav` were never merged. `kayit_...100002.mp4` has vide …

**Düzeltme taslağı.** 1. In MainWindow.toggle_recording (src/matematigin_mantigi/ui/main_window.py), return early when on=True and a stop is still in progress: `w = getattr(self, '_stop_worker', None); if on and w is not None and w.isRunning(): return`. Optionally also show the 'Kayıt kapatılıyor…' status.
2. As a second guard in MssFfmpegRecorder.start (src/matematigin_mantigi/core/recorder.py), refuse to start while `self._stop_lock.locked()`, either with a no-op or with RecorderError('Önceki kayıt hâlâ kapatılıyor').
3. In _stop_locked, copy _video_path, last_path, _log_file and _log_path into locals at entry, and pass them to _mux and _close_log. That way a stop can never act on a later recording's paths.

### e2e#3 · önemli · If the mic fails to open, the whole lesson records without audio and nothing tells the teacher at start; at stop the only notice is the status line, which is often hidden

- **Yer:** `src/matematigin_mantigi/ui/main_window.py:277`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** A 30+ minute lesson is recorded without sound, and the teacher only finds out when watching the file. This is the silent-failure class.

**Senaryo.** A mic is selected in Ayarlar, but PortAudio can't open it (device renamed or unplugged, macOS permission problem, PortAudio error). MssFfmpegRecorder.start catches the error, sets audio_error and continues with video only (recorder.py:262-268). toggle_recording (lines 276-285) never checks recorder.audio_error: the badge and 'DURDUR' counter run normally. At stop, _on_record_stopped adds 'UYARI: Mikrofon açılamadı' only to work_area.status_label (lines 322-324), with no dialog. That label is recorded into the video, so teachers hide it via Görünürlük > 'status', and then the warning and even the saved file path are invisible. The same applies out of the box: the default mic setting is '(ses yok)' (settings_dialog.py:145, settings.py:151), so a first-launch recording is silent with no indication.

**Doğrulama yöntemi.** I traced the code from app.build_window through MainWindow.toggle_recording (main_window.py:272-301), MssFfmpegRecorder.start/_stop_locked (recorder.py:241-322) and MainWindow._on_record_stopped (main_window.py:303-324). I also read AudioCapture.start/_pick_device (audio_capture.py:135-171) to see which failures the fallbacks already absorb. Then I wrote a pytest repro at C:\Users\bkese\AppData\Local\Temp\claude\C--Users-bkese-Desktop-arayuz-soru-sistemi-metematigin-mantigi\0647ad5c-ac9d-414d-ad34-9375fe87f54d\scratchpad\audit\verify-e2e\micfail\test_micfail.py. It uses the repo's `window` fixture, a real MssFfmpegRecorder with synthetic_grabber and real ffmpeg, and an audio_factory whose start() raises a PortAudioError-style RuntimeError. The status line is hidden through settings.set_visible('status', False), and QMessageBox.warning/critical/information are patched to record every call …

**Kanıt.** The repro output:
`after start: rec= True audio_error= Mikrofon açılamadı: PortAudioError: ... [PaErrorCode -9996] dialogs= []`
`after stop: dialogs= [] status_visible= False status= Kayıt kaydedildi: ...kayit_...mp4 · yakalama ~60 kare/sn · UYARI: Mikrofon açılamadı: ... file= True`

**The code path:**
- recorder.py:264-268 catches any exception from `_audio_factory(...)`/`.start()`, stores it in `audio_error` and keeps recording video only.
- toggle_recording (main_window.py:276-285) handles only `RecorderError` and never reads `recorder.audio_error`. The badge and the DURDUR counter start as if everything were fine.
- At stop, `_on_record_stopped` shows a dialog only for `err` (the video error). `audio_err` is appended to the text of `work_area.status_label` (322-324). That label can be hidden with the "status" visibility key (main_window.py:418), and then the warning is invisible.
- The mux path is no better: "Ses birleştirilemedi" and "Ses kaydedilemedi (örnek yok)" (recorder.py:388, 397, 401) also end up only in that label.

**Reachability, with caveats:** `_pick_device` falls back from a missing or renamed device name to the PortAudio default, then to the first input. So the "device renamed/unplugged" case in the claim is mostly absorbed. What still reaches this path:
- `sd.InputStream(...)`/`.start()` raising a PortAudioError (device busy or exclusive, unsupported sampl …

**Düzeltme taslağı.** 1. In MainWindow.toggle_recording (main_window.py), right after `self.recorder.start(rect, fps=fps)` succeeds, check `getattr(self.recorder, "audio_error", None)`. If it is set, show `QMessageBox.warning(self, "Mikrofon açılamadı", audio_error + "\n\nKayıt SESSİZ devam ediyor.")`. A better option is a `QMessageBox.question` that lets the teacher stop now and fix the mic.
2. In MainWindow._on_record_stopped, when `audio_err` is set, show a `QMessageBox.warning` naming the saved path and saying it has no audio, instead of only appending it to the status_label text. This also covers the mux-failure messages.
3. Optionally make the badge show a "SES YOK" state when `recorder.audio_device` is set but `recorder._audio` is None.

### e2e#4 · önemli · On a Mac Retina screen, the '2K' recording is an upscale of a point-resolution capture: mss grabs at nominal (1x) resolution

- **Yer:** `src/matematigin_mantigi/core/recorder.py:248`
- **Doğrulama:** confirmed (yeniden üretildi: False)
- **Öğretmene etkisi:** The 2K deliverable has only about 792p of real detail: blurry handwriting and text in every recording on the target MacBook.

**Senaryo.** On macOS, start() passes the logical (point) rect to mss (line 248). mss's darwin backend calls CGWindowListCreateImage with IMAGE_OPTIONS including kCGWindowImageNominalResolution (mss/darwin.py:49), which returns the image at nominal 1x size, not Retina pixels. On a MacBook Pro 14" at its default 1512x982-point scaling, the maximized board stage is 1408x792 pt. So ffmpeg receives 1408x792 frames and `scale=-2:1440` stretches them 1.82x to 2560x1440. The badge still claims 2560×1440.

**Doğrulama yöntemi.** I read the code and followed the whole path from the board to the ffmpeg arguments. First, MssFfmpegRecorder.start (recorder.py:248). Then grab_screen/_new_mss (recorder.py:99-113). Then mss 10.2.0 darwin.py:44-49 and its grab() at lines 227-265. I grepped src/ for any IMAGE_OPTIONS override or any use of dpr on the darwin path and found none. Then I ran a scratch simulation (scratchpad/audit/verify-e2e/retina-nominal/check.py). It sets sys.platform='darwin', passes in RecordRect(52,95,1408,792,dpr=2.0), uses a fake grabber that behaves like nominal-resolution CGWindowListCreateImage (the image is the same size as the rect in points), and records the ffmpeg argv. I could not run a real Retina capture because there is no Mac here.

**Kanıt.** The simulation printed `grab rect: RecordRect(x=52, y=95, width=1408, height=792, dpr=1.0)` and `ffmpeg -s 1408x792 vf scale=-2:1440:flags=bilinear`. So on darwin, recorder.py:248 throws away the Retina dpr of 2.0 on purpose: it builds RecordRect(rect.x, rect.y, rect.width, rect.height, 1.0), a rect in points. mss darwin.grab passes that to `CGWindowListCreateImage(rect, 1, 0, IMAGE_OPTIONS)`. IMAGE_OPTIONS includes kCGWindowImageNominalResolution (1<<4), and mss's own comment says you set IMAGE_OPTIONS = 0 "to turn on scaling" (issue #257). The frame size comes from CGImageGetWidth/Height of the returned image, and start() sizes ffmpeg's `-s` from the first frame (line 253). Nothing in src/ changes mss.darwin.IMAGE_OPTIONS. pyproject allows mss>=9, and the Mac build installs a current mss with the same default. Under Apple's documented meaning of kCGWindowImageNominalResolution (capture at 1x, not at backing-store scale), every Mac recording goes to ffmpeg at point resolution and bilinear scale=-2:1440 blows it up about 1.8x. Every Mac screen's stage in points is narrower than 2560 (for example 1408x792 at 1512x982), so this happens on every recording. The code itself expected 2x frames: the "Retina'da kare ~20 MB" docstring and the test comment at test_recorder.py:49. The one link I did not see on hardware is the exact pixel size CoreGraphics returns with that flag. One Mac c …

**Düzeltme taslağı.** In src/matematigin_mantigi/core/recorder.py, _new_mss() (or grab_screen), when sys.platform == 'darwin', clear the nominal-resolution flag before grabbing: `import mss.darwin as md; md.IMAGE_OPTIONS &= ~(1 << 4)`, or set it to kCGWindowImageBoundsIgnoreFraming | kCGWindowImageShouldBeOpaque. Keep passing the rect in points on darwin, as line 248 does now. CoreGraphics then returns backing-store pixels (2816x1584 for a 1408x792 stage), and scale=-2:1440 downscales to 2560x1440. Add a unit test that monkeypatches mss.darwin and checks the option is cleared. On the real Mac, confirm the grab still keeps up with 60 fps, because 2x frames are 4x the bytes. If it can't, fall back to CGDisplayCreateImageForRect or ScreenCaptureKit, not a nominal-resolution grab.

### e2e#5 · önemli · After saving in the question editor, pictures disappear from the board in the packaged app and questions gain empty hint cards and empty options

- **Yer:** `src/matematigin_mantigi/ui/question_editor.py:222`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** Mid-lesson, question figures disappear and a blank 'hint' card appears until the app is restarted.

**Senaryo.** The teacher opens ✎ Sorular, fixes a typo and presses Kaydet. reload_questions (main_window.py:353-358) puts the dialog's Question objects on the board directly, without reloading the xlsx. Every question visited in the editor was rebuilt by _question_from_form, which has two problems. (a) image is the xlsx-relative 'sorular_gorsel/S07.png' (line 225 via _to_relative), and QuestionZone._set_image checks Path(path).exists() against the process cwd (question_zone.py:381). In the .app the cwd is '/', not ~/Documents/Matematiğin Mantığı, so the picture vanishes. (b) hints and options keep empty strings (lines 222 and 224), so a 3-hint question shows 4 cards (one blank, counter '1 / 4') and a 2-option question shows blank 'C) ' and 'D) '.

**Doğrulama yöntemi.** Read QuestionEditorDialog (_populate, _question_from_form, _to_relative, _commit_current, _save), MainWindow.open_editor/reload_questions/_on_question_changed, QuestionZone.set_question/_set_image/_build_options, HintZone.set_hints, question_loader.load_questions and paths.data_dir. Checked for any os.chdir in src (none). Then ran a headless scratch script (scratchpad/audit/verify-e2e/editor-rt/rt.py). It writes an xlsx plus sorular_gorsel/S07.png in a temp 'Documents/MM' folder, loads it with load_questions, chdirs elsewhere the way a packaged .app starts, opens QuestionEditorDialog and calls _save(), and captures the list that the `saved` signal emits.

**Kanıt.** Loaded: hints=('h1','h2','h3'), options=(), image='C:\...\Documents\MM\sorular_gorsel\S07.png' (absolute, because load_questions at question_loader.py:124 resolves against the xlsx folder). After Kaydet the emitted Question was hints=('h1','h2','h3',''), options=('','','',''), image='sorular_gorsel/S07.png', and Path(image).exists() relative to cwd was False.

Causes:
- question_editor.py:222/224 build 4-element tuples with no filter for empty strings.
- question_editor.py:210 plus _to_relative (235-244) turn the image path into a path relative to the xlsx folder.
- _save (303-312) emits self.questions directly, and main_window.py reload_questions puts that list on the board without reading the xlsx again.
- question_zone.py:177 `_set_image` checks Path(path).exists() against the process cwd. Nothing in src calls chdir, and paths.data_dir() is ~/Documents/Matematiğin Mantığı only when frozen, so in the .app the relative path does not resolve and the image is hidden.
- HintZone.set_hints (hint_zone.py:155) makes one card per entry, empty ones included, and flow.hint_count uses len(hints), so there is a blank 4th card and the counter shows 4.
- _build_options (question_zone.py:190) checks only `if not options`, and a tuple of 4 empty strings passes. An open-ended question with no options therefore shows blank 'A) B) C) D)' labels. This is worse than the auditor claimed, because t …

**Düzeltme taslağı.** In question_editor.py QuestionEditorDialog._save, after write_questions(self.questions_path, self.questions), emit load_questions(self.questions_path) instead of list(self.questions). The board then gets exactly the normalized data a restart would give: empty hints and options filtered out, and the image resolved to an absolute path. As a second safeguard, _question_from_form could filter empties: hints=tuple(t for t in (e.text().strip() for e in self.hint_edits) if t), and the same for options.

### e2e#6 · önemli · Saving in the question editor while the xlsx is open in Excel crashes the whole app, including a recording in progress (Windows)

- **Yer:** `src/matematigin_mantigi/ui/question_editor.py:310`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The app disappears mid-lesson and the recording is not finalized or merged. Excel's lock makes this Windows-only; macOS Excel does not lock the file.

**Senaryo.** The README says to edit questions in Excel, and the ✎ editor writes the same file. With the xlsx open in Excel (which locks it on Windows), Kaydet raises PermissionError from write_questions. The exception is not caught in _save, and nothing in the app sets sys.excepthook. PyQt6 treats an unhandled exception in a slot as fatal, so the process dies. If a recording is running, recorder.stop() and the mux never run: with a mic, the .video.mp4 and an unfinalized .wav are left separate.

**Doğrulama yöntemi.** I read QuestionEditorDialog._save (src/matematigin_mantigi/ui/question_editor.py:303-312), write_questions (core/question_loader.py:25-44), MainWindow.open_editor (ui/main_window.py:345-351) and app.main (app.py:68-81). I also grepped the whole package for excepthook, try/except around write_questions, and faulthandler. Nothing guards the call: no try/except in _save or open_editor, and no sys.excepthook anywhere. Then I wrote verify-e2e/editor-lock/repro.py, adapted from the auditor's setup. It starts a real MssFfmpegRecorder recording and holds the xlsx with CreateFileW(share=0), which is how Excel locks a file. After 2 s it goes through the REAL path: win.open_editor() runs dlg.exec() as a modal loop, and the script clicks save_button inside that loop. I ran it twice. For a control, repro_hook.py is the same script with a sys.excepthook installed.

**Kanıt.** 1. Unpatched run: the process died inside the modal editor with exit code -1073740791 (0xC0000409, the qFatal/abort fail-fast). stderr was empty (0 bytes), so the crash leaves no message at all. The lines "survived save", "open_editor returned" and "app exited normally" never printed. The only thing left on disk was the partial kayit_*.mp4 (ffprobe: 2.32 s) and an empty .log. recorder.stop() and closeEvent (main_window.py:471) never ran.
2. Control run with sys.excepthook set: the hook caught "PermissionError: [Errno 13] Permission denied: ...sorular_sablon.xlsx". It is raised from openpyxl save_workbook -> ZipFile(filename,'w') -> io.open, called from write_questions wb.save (question_loader.py:43), called from _save (question_editor.py:310). After that the app kept running and exited normally with code 0. So the process death comes only from PyQt6 6.11 treating an unhandled exception in a slot as fatal.
3. The xlsx itself stays intact (8613 bytes), because the open fails before truncation. No question data is lost, but the lesson/app state and the recording finalization are lost.
Reachability: README tells the teacher to edit questions in Excel, and the editor writes the same file, so on Windows this happens in normal use. On the target Mac, Excel does not take a mandatory lock. There the same crash needs another OSError from wb.save: a Finder "Locked" (uchg) file, a read-onl …

**Düzeltme taslağı.** In src/matematigin_mantigi/ui/question_editor.py QuestionEditorDialog._save, wrap the write in a try/except. On OSError, show a QMessageBox.warning such as "Soru dosyası kaydedilemedi (Excel'de açık olabilir): {err}" and return without emitting saved or calling accept(), so the dialog stays open and the edits are kept. Apply the same wrap to save_question_image calls in the editor if they are not already guarded. As defense in depth for the recording product, install a sys.excepthook in app.main (src/matematigin_mantigi/app.py) that logs the traceback and shows a message box instead of letting PyQt6 qFatal the process. That way no other stray slot exception can silently kill a recording mid-lesson.

### e2e#7 · küçük · Ink undo history carries over between questions: Ctrl+Z on a new question brings back the previous question's drawing and saves it into that question's PNG

- **Yer:** `src/matematigin_mantigi/ui/canvas.py:158`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The previous question's solution reappears over the new question in the recording, and the per-question PNGs are wrong.

**Senaryo.** The teacher draws on question 1 and presses N. _on_question_leaving saves the PNG and calls canvas.clear() (main_window.py:237). clear() pushes the whole Q1 image onto the undo stack (canvas.py:155-158), so the undo button stays enabled on the blank Q2. One Ctrl+Z, or one too many while fixing a stroke on Q2, puts all of Q1's ink over Q2, on camera. When leaving Q2, that ink is saved as S2_01.png.

**Doğrulama yöntemi.** I read canvas.py (undo/clear/_push_undo) and main_window.py (_on_question_leaving at line 234, reload_questions at line 355, the Ctrl+Z shortcut and the toolbar undo button). No code path empties the undo deque: _undo is only created at canvas.py:61 and only popped in undo(). I wrote my own repro at scratchpad/audit/verify-e2e/undo-leak/v.py, running offscreen with a real MainWindow and QuestionFlow. It covers the more realistic case: draw on Q2, then press Ctrl+Z one more time than needed.

**Kanıt.** canvas.py:155-162: clear() calls _push_undo() before it fills the canvas with transparent, so Q1's whole image goes onto the undo stack. main_window.py:234-237: _on_question_leaving calls canvas.clear() and never clears the history. The toolbar undo button follows historyChanged(can_undo), so it stays enabled on the blank Q2. My repro printed: `Q1 strokes 3`, `Q2 idx 1 empty True can_undo True`, `Q2 strokes after drawing 1`, `after 1 undo 0 empty True`, `after 2nd undo (one too many) 3 => Q1 ink on Q2`, and the snapshots were ['S1_01.png', 'S2_01.png']. So one extra Ctrl+Z while fixing a stroke on Q2 puts Q1's full solution back on the board, on camera. That ink is then saved as Q2's PNG when the teacher leaves Q2. reload_questions (main_window.py:355) has the same leak across a question-set reload. Nothing crashes and the recording file is intact. The problem is wrong content on the board and in the per-question snapshot. The teacher can remove it by undoing again or by clearing the board, but by then it is already in the recording.

**Düzeltme taslağı.** In src/matematigin_mantigi/ui/canvas.py, add `def reset_history(self): self._undo.clear(); self.historyChanged.emit(False, self.is_empty())`. In src/matematigin_mantigi/ui/main_window.py, call `self.canvas.reset_history()` right after `self.canvas.clear()` in `_on_question_leaving`, and also in `reload_questions`. Keep the plain toolbar and Ctrl+Shift+X clear undoable within a question, since undoing a clear there is intended. Add a test: draw, go to the next question, then assert can_undo() is False and undo() leaves the canvas empty.

### e2e#8 · önemli · The recording region is fixed when recording starts; F11, a window resize or a move during recording records the wrong part of the screen, with no warning

- **Yer:** `src/matematigin_mantigi/ui/main_window.py:275`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The rest of the lesson shows a misaligned slice of the desktop or board instead of the board.

**Senaryo.** The teacher presses R in a normal window and then F11 (line 178), or clicks the macOS green full-screen button, or drags or resizes the window, or toggles 'Tahtayı 16:9' in Ayarlar. recording_rect() is sampled once at start (line 275), and the grab thread keeps capturing those old screen coordinates (recorder.py:283). Nothing blocks or warns about moving or resizing while recording.

**Doğrulama yöntemi.** Read MainWindow.toggle_recording (main_window.py:272-301), the F11/Escape shortcuts (main_window.py:178, 186-192), WorkArea.recording_rect/stage_rect (work_area.py:440-459, 629-633) and MssFfmpegRecorder.start/_loop/_grab_loop (core/recorder.py:241-283, 410-441). Grepped src/ for any geometry guard tied to is_recording (setFixedSize on the window, a resize/move/changeEvent override, a disabled F11 while recording) and found none. Wrote a headless repro at C:\Users\bkese\AppData\Local\Temp\claude\C--Users-bkese-Desktop-arayuz-soru-sistemi-metematigin-mantigi\0647ad5c-ac9d-414d-ad34-9375fe87f54d\scratchpad\audit\verify-e2e\rect-fixed\repro.py using NullRecorder and the real MainWindow. Scenario A: go full screen, press R, then press Escape. Scenario B: record in a normal window, then move the window.

**Kanıt.** The recording rectangle is read only once, at main_window.py:275 (`rect = record_rect_for(self.work_area.recording_rect())`). recorder.py:248 turns it into grab_rect, and recorder.py:283 passes it by value to the _loop thread, which hands it to _grab_loop. The thread grabs that same screen rectangle until stop, and the output width and height are also fixed at start. Nothing in the app blocks or reports a geometry change while recording.

Repro output:
A start: RecordRect(x=92, y=202, width=704, height=396); after Esc: fullscreen False, rec True, board RecordRect(x=94, y=69, width=1184, height=666), same? False
B start: RecordRect(x=144, y=119, w=1184, h=666); after move: RecordRect(x=494, y=369, ...), rec True

So recording continues silently while the board is somewhere else on screen.

The auditor's F11 case holds, and there is a more reachable trigger they did not mention. _escape (main_window.py:186-192) does three jobs on one key: it cancels text, then leaves edit mode, then leaves full screen. A teacher recording in full screen who presses Esc one extra time exits full screen. The window drops back to the 1920x1080 size set in app.py:53, clamped to the screen, and the rest of the lesson records the wrong part of the desktop. The macOS green button, dragging the window, and switching 'Tahtayı 16:9' in Ayarlar (aspect_lock changes stage_rect) all cause the same drift. Ther …

**Düzeltme taslağı.** Freeze the window geometry for the length of a recording, in main_window.py:
1. In MainWindow.toggle_recording, after recorder.start succeeds, call `self.setFixedSize(self.size())`. After stop (in the stop branch, or in _on_record_stopped), restore resizing with `self.setMinimumSize(0,0); self.setMaximumSize(16777215,16777215)`.
2. Make the F11 lambda and the full-screen branch of _escape do nothing while `self.recorder.is_recording`. Show a status line instead, e.g. "Kayıt sürerken tam ekran değiştirilemez".
3. Override changeEvent (WindowStateChange) and moveEvent. If recording and `record_rect_for(self.work_area.recording_rect()) != self.recorder.last_rect`, warn loudly (status plus the badge turning a warning color), or stop and restart the recording into a new segment. For a move with no size change there is a cheaper option: store the grab rect on the recorder as a mutable attribute (e.g. `MssFfmpegRecorder.set_origin(x, y)`), have _grab_loop re-read it each frame, and have moveEvent update it.
4. In apply_ui_settings, refuse to change aspect_lock while recording.

## Uygulama çapı (hata, kapanış, pencere) (`app`)

### app#1 · KRİTİK · The R shortcut starts a new recording while the previous one is still being finalized and muxed. The old lesson is left un-muxed and the UI says 'not recording' while it records

- **Yer:** `src/matematigin_mantigi/ui/main_window.py:172`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The previous lesson's final MP4 is never produced; only a video-only file plus a separate WAV remain. The toolbar shows KAYIT (not recording) while a recording is actually running, so the teacher's next R press stops it instead of starting it. Error text is attributed to the wrong recording.

**Senaryo.** The teacher stops a long recording with the toolbar button. toggle_recording (main_window.py:292-297) disables the record button and hands recorder.stop() to _StopWorker. Inside MssFfmpegRecorder._stop_locked, started_at is cleared (recorder.py:301) BEFORE ffmpeg finalizes (+faststart rewrites the whole multi-GB file) and before _mux runs (recorder.py:318). AAC-encoding 20 min of audio alone took 16 s on this box, so this window lasts tens of seconds for a real lesson. During it is_recording is already False, but the R QShortcut (line 172) has no guard for the running _StopWorker. Pressing R calls recorder.start(), which does not take _stop_lock and overwrites _video_path, last_path, _log_file and audio_error. The old worker then muxes using the NEW paths (recorder.py:385) and returns the NEW path (recorder.py:322). _on_record_stopped (main_window.py:303-305) then unchecks the toolbar while the new recording is running. A related case: pressing R during the join phase starts a second _StopWorker that replaces self._stop_worker, so the first worker's exc is never shown.

**Doğrulama yöntemi.** Read main_window.py toggle_recording/_StopWorker/_on_record_stopped/_shortcuts and recorder.py start/stop/_stop_locked/_mux. Wrote a scratch pytest (scratchpad/audit/verify-app/r-during-stop/test_r_during_stop.py) that builds the real MainWindow with a real MssFfmpegRecorder (real ffmpeg, synthetic grabber, fake mic that writes a real 1 s WAV, settings.audio_device="fake"). It fires the real R QShortcut's activated signal to start, waits 1.5 s, fires R to stop (which starts the _StopWorker), waits 0.7 s, then fires R again. A 2 s sleep inside _close_log (after proc.communicate(), before _mux) stands in for the +faststart rewrite of a long lesson. QMessageBox.warning was stubbed to capture dialogs. _mux was wrapped to print the paths it reads.

**Kanıt.** The run confirms the claim. Output:
- After the stop: is_recording False, worker running True, button enabled False. The button is disabled, but the R shortcut (main_window.py:172) has no guard.
- After the second R: is_recording True, last_path kayit_...100002.mp4. start() does not take _stop_lock and overwrites _video_path, last_path, _log_file and audio_error (recorder.py:241-283).
- The old worker's _mux read the NEW paths: video=kayit_...100002.video.mp4, out=kayit_...100002.mp4, wav=kayit_...100001.wav (recorder.py:385).
- The mux failed ("Invalid data found", because the live ffmpeg has no moov yet). The fallback video.replace(out) then raised WinError 32 on the live file. That error came up as a 'Kayıt hatası' dialog, attributed to the wrong recording.
- After the worker finished: is_recording True, but toolbar checked False. _on_record_stopped (main_window.py:303-305) unchecked the toolbar while recording 2 was running.
- Files left for lesson 1: kayit_...100001.video.mp4 + kayit_...100001.wav. The final 100001.mp4 does not exist, so lesson 1 was never muxed and nothing says so.
- Stopping recording 2 muxed it correctly, but audio_error still held the stale 'Ses birleştirilemedi' text from the first mux. audio_error is only reset in start(), so recording 2 shows a false warning.

Why it happens: started_at is cleared at recorder.py:301, before communicate(timeout=60) a …

**Düzeltme taslağı.** Minimal UI fix, in src/matematigin_mantigi/ui/main_window.py, MainWindow.toggle_recording: add an early return at the top when a stop is still running:
`w = getattr(self, "_stop_worker", None); if w is not None and w.isRunning(): return`
Put the same guard in the R shortcut path (it goes through toggle_recording, so the single guard covers both). In _on_record_stopped, set self._stop_worker = None at the end.

Also harden recorder.py:
- MssFfmpegRecorder.start: take self._stop_lock (non-blocking acquire; raise RecorderError("Önceki kayıt hâlâ kapatılıyor") if it is held) so start cannot interleave with _stop_locked.
- _stop_locked: capture video/out/log into locals before clearing started_at, and pass them to _mux, instead of reading self._video_path and self.last_path afterwards.
- stop(): reset audio_error per stop.

### app#2 · önemli · No sys.excepthook: any exception in a slot aborts the whole app mid-lesson and leaves the recording un-muxed

- **Yer:** `src/matematigin_mantigi/app.py:68`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The app vanishes without any message in the middle of a lesson. The recording never gets its audio muxed, and in the packaged .app there is not even a console traceback.

**Senaryo.** main() installs a Qt message handler but no sys.excepthook, and PyQt6 6.11 calls qFatal/abort on an unhandled exception in a slot. Several MainWindow slots can raise in real use. _on_question_leaving (main_window.py:234-236, the N/P keys and next/prev buttons) calls SessionStore.save_snapshot, which deliberately raises OSError when the PNG cannot be written (session_store.py:33), for example on a full disk, which is realistic while a 2K60 recording writes GBs, or an unwritable folder. The layoutChanged lambda (main_window.py:127) calls a non-atomic save_layout with no try. toggle_recording catches only RecorderError, but recorder.start() calls out_dir.mkdir unwrapped (recorder.py:255). closeEvent (main_window.py:469-471) calls recorder.stop(), whose _mux fallback video.replace() can raise.

**Doğrulama yöntemi.** Read app.py:main (lines 67-80): it installs qInstallMessageHandler and nothing else. There is no sys.excepthook anywhere in src/ or tests/ (grep). Installed PyQt6 is 6.11.0. Test 1, verify-app/excepthook/minimal.py: a bare QApplication with a QTimer slot that raises OSError. The process exits with code 127 and 'STILL ALIVE' never prints, so on this PyQt version any unhandled exception in a slot kills the whole app. Test 2, verify-app/excepthook/e2e.py: the real MainWindow and the real MssFfmpegRecorder, with a stub screen grabber and a fake mic that streams to a WAV the way AudioCapture does. It starts recording, draws one stroke, makes QImage.save return False, then emits toolbar.nextRequested, which is the same path the N key and the next button take (flow.questionLeaving -> _on_question_leaving -> SessionStore.save_snapshot, which raises OSError at session_store.py:33). I ran it once …

**Kanıt.** The 'ok' run printed STILL ALIVE and exited 0. After close it had written S1_01.png and the final kayit_*.mp4. The 'fail' run printed 'recording True' and then the process died with exit=127. No 'STILL ALIVE' appeared and nothing was printed to stderr. On disk it left kayit_*.video.mp4 (video only, playable, 1.2 s) and kayit_*.wav at 124,844 bytes whose header still says only 4,800 frames, because stop() never ran. There was no final muxed MP4. So the app disappears silently in the middle of a lesson, and the lesson audio is left in a WAV whose header was never finalized and that was never muxed with the video. Nothing on the path guards against this: _on_question_leaving (main_window.py:234-237) has no try, save_snapshot deliberately raises, and main() installs no hook. The same abort applies to any other slot that raises, for example the layoutChanged lambda that calls save_layout (main_window.py:127) and recorder.start's out_dir.mkdir (recorder.py:255), which toggle_recording does not catch because it only catches RecorderError. The trigger needs a PNG write to fail (disk full, an unwritable or removed session folder, a volume that is not mounted). That is uncommon but it can happen, and the failure is silent and destroys a recording. I re-rate it from critical to important because it needs an I/O fault to set it off. When it does happen it takes the worst path this product …

**Düzeltme taslağı.** 1) In app.py main(), before app.exec(), install a sys.excepthook that logs the traceback to a file in the data folder (and to stderr), shows a non-modal QMessageBox.warning, and returns without re-raising. This keeps PyQt6 from calling qFatal, so the app keeps running and the recording keeps going. 2) Also guard the known I/O slots locally. In MainWindow._on_question_leaving, wrap save_snapshot in try/except OSError, show a status or warning, and still call canvas.clear(). Wrap the layoutChanged lambda (main_window.py:127) in a small _save_layout method that catches OSError. In toggle_recording, catch OSError as well as RecorderError around recorder.start. 3) Optional: in closeEvent, wrap recorder.stop() in try/except so that shutdown still finalizes whatever it can.

### app#3 · önemli · The capture rectangle is fixed at record start. Esc, F11 or a Settings change during recording silently records the wrong screen region

- **Yer:** `src/matematigin_mantigi/ui/main_window.py:187`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** A single stray Esc in fullscreen, or a Settings tweak, makes the rest of the lesson recording show part of the board plus whatever is behind the window (desktop, other apps), still as 'exact 16:9 2K'. The teacher only finds out when watching the file.

**Senaryo.** toggle_recording takes work_area.recording_rect() once and passes it to recorder.start (main_window.py:275-277). Nothing tracks or blocks geometry changes afterwards. While recording, three things move or resize the board: the Escape shortcut (when not typing and not in layout edit it calls showNormal(), lines 187-193), F11 (line 178), and Settings > 'Tahtayı 16:9 oranında tut' or frame style (apply_settings_values -> set_aspect_lock). ffmpeg keeps grabbing the old screen rectangle. No main_window code checks is_recording before these actions.

**Doğrulama yöntemi.** I read main_window.py (_shortcuts, _escape, toggle_recording, apply_settings_values, apply_ui_settings), work_area.py (set_aspect_lock, resizeEvent, recording_rect) and recorder.py start(). Then I ran an extended copy of the auditor's script with offscreen Qt and NullRecorder: verify-app/rect-drift/rect_drift.py under the scratchpad audit folder. It adds a check of the rect right after start and an F11 step.

**Kanıt.** The recorder freezes the capture rectangle when recording starts. ffmpeg recorder, recorder.py:248: grab_rect is computed once in start() and passed to the _loop thread as a fixed argument. Nothing updates it later.

main_window.py:275 reads work_area.recording_rect() once. None of these paths check recorder.is_recording:
- _escape (main_window.py:187-193) calls showNormal() when there is no text box and no edit mode.
- F11 (main_window.py:178) toggles fullscreen.
- apply_settings_values -> apply_ui_settings -> work_area.set_aspect_lock / set_frame_style (main_window.py:431-433) calls relayout().

WorkArea.resizeEvent (work_area.py:625) relays out the stage but tells nobody that the recorded region moved.

Run output:
- Right after R: captured RecordRect(x=92, y=202, width=704, height=396) matches live (92, 202, 704, 396). So the post-start badge relayout does not move it.
- After Esc: fullscreen False, board (92, 56, 608, 342), still recording True.
- After aspect lock off in Settings: board (88, 0, 712, 800), recorder still (92, 202, 704, 396).
- After F11: board (90, 2, 612, 450), recording True.
- The status label only shows the normal tool text, so there is no warning.

The frame grab reads a raw screen region, so after the board moves the file contains part of the board plus whatever is behind it. Esc is a key the teacher already uses often (cancelling the text box, leavi …

**Düzeltme taslağı.** Smallest fix is to block board-geometry changes while recording, in src/matematigin_mantigi/ui/main_window.py:
(1) In _escape, drop the `elif self.isFullScreen(): self.showNormal()` branch when self.recorder.is_recording, and set a status message instead ("Kayıt sürerken tam ekrandan çıkılamaz").
(2) Wrap the F11 lambda in a method with the same guard.
(3) In apply_ui_settings, skip set_aspect_lock/set_frame_style while recording and keep the new values in settings. Apply them in _on_record_stopped, or disable those controls in SettingsDialog while recording.
Safety net for the remaining paths (window move/resize): add a WorkArea signal emitted from resizeEvent/moveEvent. MainWindow compares work_area.recording_rect() with recorder.last_rect while recording and, on a mismatch, shows a loud warning (badge/status or QMessageBox). Alternatively it could stop the recording and restart a new segment.

### app#4 · önemli · If the microphone fails to open at record start, the whole lesson records without audio and the only notice is a status-line suffix after stopping (invisible if the status line is hidden)

- **Yer:** `src/matematigin_mantigi/ui/main_window.py:282`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** A full lesson is recorded with no audio (the product requirement is mic audio in sync). The failure is silent at start and at best a small line of text at the end.

**Senaryo.** MssFfmpegRecorder.start() swallows a mic-open failure into recorder.audio_error and keeps recording video only. This happens when the saved USB mic is unplugged or renamed, or the PortAudio device lookup fails. After start(), toggle_recording (lines 276-285) never checks audio_error, so there is no dialog and no badge or toolbar hint. The error surfaces only in _on_record_stopped (lines 322-324), appended to work_area.status_label. That label is hidden whenever the 'status' visibility option is off (apply_ui_settings line 418). Related path: SettingsDialog._list_audio (settings_dialog.py:226-227) falls back to '(ses yok)' when the saved mic is not in the fresh list, and Apply then silently stores audio_device='' for all future recordings.

**Doğrulama yöntemi.** Read MainWindow.toggle_recording and _on_record_stopped (main_window.py:272-324), MssFfmpegRecorder.start/_stop_locked (recorder.py:241-321) and AudioCapture.start/_pick_device (audio_capture.py:135-171). The auditor's repro used a fake audio_factory that always raises, so I wrote my own at scratchpad/audit/verify-app/mic_open_fail/v.py. It uses the REAL AudioCapture and real sounddevice. Part A: a saved mic name that no longer exists. Part B: sd.InputStream patched to raise PortAudioError -9985 ("Device unavailable"), with status visibility off. Both run through the full MainWindow record button, then stop, then ffprobe on the output.

**Kanıt.** Part of the claim is wrong. An unplugged or renamed saved mic does NOT set audio_error. AudioCapture._pick_device (audio_capture.py:154-171) falls back to the PortAudio default input, then to the first listed mic. The real run printed "missing-name -> fallback OK, samples 22932". The scenario is only reached when the stream itself fails to open (PortAudioError from sd.InputStream, e.g. the device is busy or unavailable, an invalid sample rate, or the device disappears between query and open) or when no input device exists at all ("kullanılabilir mikrofon bulunamadı"). The core defect is real on that path, and nothing guards it. recorder.py:264-268 swallows the error into audio_error and keeps recording video only. toggle_recording (main_window.py:274-285) never checks audio_error after start(). The only report is in _on_record_stopped (main_window.py:322-324), which puts "UYARI: ..." into the status label. That label is hidden when visibility 'status' is off (main_window.py:418). Real run: "recording: True | audio_error: Mikrofon açılamadı: Error opening InputStream: Device unavailable [PaErrorCode -9985] | dialogs: []", then "after stop dialogs: [] | status visible: False", then "streams: ['video']". A whole lesson can be recorded with no audio and no visible warning. The settings-dialog part of the claim (_list_audio resetting to "(ses yok)") only happens if the user clicks " …

**Düzeltme taslağı.** In main_window.py MainWindow.toggle_recording, right after a successful self.recorder.start(...), check getattr(self.recorder, "audio_error", None). If it is set, warn loudly and let the user decide. For example, call QMessageBox.question(self, "Mikrofon açılamadı", err + "\nSessiz kayda devam edilsin mi?"). If the answer is No, call self.recorder.stop(), then self.toolbar.set_recording(False), then return. Optionally also mark the RecordBadge (e.g. with a "SESSİZ" label) so the problem stays visible during the lesson. Also, in _on_record_stopped, show audio_err with QMessageBox.warning instead of adding it to the status label, which can be hidden.

### app#5 · önemli · Closing the app while the background stop or mux is still running: closeEvent waits at most 60 s, then the app exits with _StopWorker still inside recorder.stop()

- **Yer:** `src/matematigin_mantigi/ui/main_window.py:474`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** After a long lesson, closing the app right after stopping can end in a crash or abnormal exit. The final MP4 may be missing or incomplete, and the teacher is never told whether the recording was saved.

**Senaryo.** The teacher presses stop at the end of a long lesson, then closes the window. is_recording is already False once _stop_locked reaches ffmpeg finalize and mux (recorder.py:301), so closeEvent skips recorder.stop() and only calls worker.wait(60000). For a lesson of roughly an hour or more, finalize + faststart + AAC mux can exceed 60 s (AAC encode alone measured at 16 s per 20 min of audio here). closeEvent then returns, app.exec() ends, and the process exits while the QThread is still running (abnormal termination). The mux's Python-side finishing steps never run: the fallback rename on mux failure, deleting the .video.mp4/.wav intermediates, and reporting success or error. The GUI is also frozen during the wait with no feedback.

**Doğrulama yöntemi.** I read MainWindow.closeEvent (main_window.py:469-479), toggle_recording and _StopWorker (main_window.py:34-48, 286-297), and MssFfmpegRecorder.stop, _stop_locked and _mux (core/recorder.py:286-408). Nothing upstream guards this. _stop_locked sets started_at=None at recorder.py:301, before proc.communicate(timeout=60) and before _mux. So once the worker gets that far, is_recording is False, closeEvent skips recorder.stop(), and it only calls worker.wait(60000). I didn't find any aboutToQuit hook or other shutdown guard in app.py. The mux subprocess timeout at recorder.py:395 is max(120, 2*duration), so the code itself expects the mux can take longer than 60 s.

Timing: I timed the real mux_args-style command (asetrate + aresample + AAC 160k + faststart) on 60 min of 48 kHz mono WAV with a tiny video. The audio part alone took 42.8 s on this machine. On the Mac, the real mux also has to co …

**Kanıt.** Output of repro.py: "closeEvent wait ms = 60000", then "app.exec returned 0 | worker running: True", then process exit code 127. That is an abnormal termination: the QThread was destroyed while it was still running. Right after exit, the run folder held a partial k.mp4 (3.9 MB), k.video.mp4 and k.wav. The ffmpeg child, now orphaned, kept going. After 20 s, k.mp4 had grown to 18 MB, and ffprobe showed h264 + aac with duration 928 s, so the file was complete. The intermediates k.video.mp4 and k.wav were never deleted, and no success or error was ever reported.

What this means:
(a) The app crashes on quit. On macOS the user would get an "unexpectedly quit" report.
(b) The GUI blocks inside closeEvent for up to 60 s with no feedback, so a teacher may Force Quit and end up in the same state even sooner.
(c) The Python-side finishing steps never run: deleting the intermediates (roughly 7 GB of video plus the WAV per hour-long lesson, left in the session folder and filling the laptop disk over time), the fallback video.replace(out) if the mux fails, and the status/error report.
(d) The final MP4 survives only if the orphaned ffmpeg is allowed to finish. On Windows it was. On macOS the outcome is unverified: if launchd/RunningBoard reaps the app's children when the app process dies, k.mp4 stays partial with no moov atom and cannot be played.
(e) If the 60 s run out while the video ffm …

**Düzeltme taslağı.** Fix this in main_window.py, in MainWindow.closeEvent. Do not block with a timeout. If self._stop_worker is running (or recorder.is_recording was just stopped via the worker), do this:
- set self._close_pending = True
- call e.ignore()
- set_status("Kayıt kaydediliyor, bitince uygulama kapanacak…")
- disable the toolbar/record button
- return

Then, at the end of _on_record_stopped (or on worker.finished), add `if getattr(self, "_close_pending", False): QTimer.singleShot(0, self.close)`. Show any error with QMessageBox first, so the teacher sees whether the file was saved. The next closeEvent will find the worker finished and proceed normally.

Optionally, when is_recording is still True at close, start the same _StopWorker path instead of calling a synchronous recorder.stop() on the GUI thread. That keeps the UI responsive and avoids destroying a running QThread ("QThread: Destroyed while thread is still running", which aborts the process).

### app#6 · küçük · Pressing Enter in a Settings text field opens the font file picker instead of applying

- **Yer:** `src/matematigin_mantigi/ui/settings_dialog.py:66`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** Surprising behaviour mid-lesson: Enter pops a file dialog, which also lands in the recording if it overlaps the board, and the settings are not applied.

**Senaryo.** All QPushButtons in the QDialog are autoDefault and no explicit default is set. On show, Qt makes the first autoDefault button in the focus chain, 'Dosya seç…' (choose_font_button), the default. Typing the presenter name and pressing Enter therefore clicks 'Dosya seç…' and opens the font QFileDialog. The expected action is Uygula (apply).

**Doğrulama yöntemi.** Read settings_dialog.py (the whole __init__ and _apply) and its only caller, MainWindow.open_settings (main_window.py:340-343), which does SettingsDialog(self.settings, self.fam, self) and then dlg.exec(). No code calls setDefault or setAutoDefault anywhere. I copied the auditor's script to scratchpad/audit/verify-app/enter-settings/r.py and added a second case that matches the real caller more closely: the dialog has a parent widget, opens modally, the user clicks into presenter_edit with the mouse, then presses Return. Ran it with QT_QPA_PLATFORM=offscreen and PYTHONPATH=src.

**Kanıt.** Both cases reproduce the bug. After show, the default buttons are ['Dosya seç…'] and focus is on the QScrollArea. Pressing Return in presenter_edit prints "!! file dialog opened: Yazı tipi dosyası", the dialog stays visible and applied stays []. In the parented and modal case with a mouse click into the field, defaults are again ['Dosya seç…'] and Return again opens the font file dialog with applied=0.

How it happens:
1. When the dialog is shown and has no explicit default button, QDialog::setVisible makes the first autoDefault QPushButton in the focus chain the default. Here that is choose_font_button (settings_dialog.py:66), because the font card is the first card.
2. QLineEdit ignores Return, so the key goes up to QDialog::keyPressEvent.
3. QDialog::keyPressEvent clicks the default button, which runs _choose_font and opens a QFileDialog. Settings are not applied.

This logic is in the platform-independent QDialog code. The only check on the button is focusPolicy != NoFocus, so the same should happen on macOS. The scenario is plausible in real use: type a presenter name, then press Enter.

**Düzeltme taslağı.** In SettingsDialog.__init__ (src/matematigin_mantigi/ui/settings_dialog.py), after the buttons are created, call setAutoDefault(False) on every pill button (choose_font, default_font, choose_logo, clear_logo, list_audio, scan, cancel), for example `for b in self.findChildren(QPushButton): b.setAutoDefault(False)`. Then call `self.apply_button.setDefault(True)` so Enter runs _apply. Add a pytest that uses QTest.keyClick(dlg.presenter_edit, Key_Return) and asserts that `applied` fired and no QFileDialog opened (monkeypatch getOpenFileName). pen_settings.py might have the same pattern and is worth checking.

## Soru sistemi ve editör (`q`)

### q#1 · KRİTİK · Typing the Turkish ordinal "7." in the editor's Sınıf field kills the whole app, including a running recording

- **Yer:** `src/matematigin_mantigi/ui/question_editor.py:216`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The app disappears mid-lesson with no message, and every edit made in the editor is lost. The editor stays available while recording (nothing disables editor_button). An abort during a recording means recorder.stop()/_mux never runs, so the final kayit_*.mp4 is never produced. Only the un-muxed .video.mp4 and a .wav whose header was never patched are left (this recording-loss part is read from the code, not run end-to-end).

**Senaryo.** The system locale is Turkish (tr_TR, as on the teacher's Mac with Turkish region). The teacher opens ✎ Sorular and types the class as "7.", which is how an ordinal is written in Turkish. QIntValidator(0, 99) at line 102 uses the locale's group separator "." and accepts "7." as input. The teacher then clicks another question in the list or presses Kaydet. _commit_current calls _question_from_form, and `int(raw)` at line 216 raises ValueError inside a Qt slot. app.py installs no sys.excepthook, so PyQt6 calls qFatal and the process aborts with no dialog. A lone "+" does the same thing in any locale.

**Doğrulama yöntemi.** I read question_editor.py (the validator at line 102, _question_from_form at 214-226, _commit_current at 228-232, and its callers _on_row_changed:190, _add:281, value:300, _save:304), main_window.open_editor (345-351), and app.main. I then wrote a scratch repro at C:\Users\bkese\AppData\Local\Temp\claude\C--Users-bkese-Desktop-arayuz-soru-sistemi-metematigin-mantigi\0647ad5c-ac9d-414d-ad34-9375fe87f54d\scratchpad\audit\verify-q\sinif\repro.py. It installs the app's own qInstallMessageHandler(_qt_message_filter), opens QuestionEditorDialog, types into the Sınıf field with QTest.keyClicks, and then either switches to another row in the list or clicks the real Kaydet button. I ran it with PYTHONPATH=src under offscreen Qt.

**Kanıt.** - **The validator lets the bad text through.** QIntValidator(0, 99) at question_editor.py:102 reports State.Intermediate for both '7.' (tr_TR, where '.' is the group separator) and '+' (in any locale). QLineEdit keeps Intermediate text in the field. On this dev box the default QLocale is already tr_TR.
- **Nothing between the field and `int()` checks the text.** `_question_from_form` (line 216) runs `sinif = int(raw) if raw else None`, and `_commit_current` calls it with no try/except. `_commit_current` is reached from row change, the Ekle button, the Kaydet button and `value()`.
- **Test runs:**
  - '+', then Kaydet: `ValueError: invalid literal for int() with base 10: '+'`, exit 127, 'survived' never printed.
  - '7.', then another row: the same ValueError for '7.', exit 127.
  - Control with '12', then another row: exit 0, prints 'survived'.
- **The app's message handler does not stop the abort.** PyQt6 turns an unhandled slot exception into qFatal, and the process aborts even with the app's custom message handler installed.
- **Nothing catches the exception anywhere in the app.** A grep of src finds no `sys.excepthook`.
- **The editor can be opened while recording.** `editor_button` is enabled only by `questions_path is not None` (main_window.py:103), and `open_editor` runs a modal `exec()` while the recorder keeps going in the background.
- **Recording loss is read from th …

**Düzeltme taslağı.** In question_editor.py `_question_from_form`, parse the class number defensively. Strip everything that is not a digit (`digits = ''.join(ch for ch in raw if ch.isdigit())`), then use `int(digits) if digits else None`, or catch ValueError and treat it as None. Better still, replace QIntValidator with `QRegularExpressionValidator(QRegularExpression(r"\d{0,2}"))` at line 102, so '.' and '+' can never be typed in the first place. As defence in depth, install a `sys.excepthook` in app.main that logs the error and shows a QMessageBox instead of letting PyQt6 call qFatal. That way no other slot exception can kill a running recording.

### q#2 · önemli · Kaydet has no error handling: a question file open in Excel (Windows) or a pasted control character aborts the app

- **Yer:** `src/matematigin_mantigi/ui/question_editor.py:310`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** Pressing Kaydet makes the app vanish silently instead of showing "the file is open in Excel". The teacher loses all edits made in the dialog. If a recording is running, it is never finalized or muxed.

**Senaryo.** _save calls write_questions() with no try/except, and the app has no excepthook. Case 1: on the Windows build, sorular_sablon.xlsx is open in Excel, which denies writes to other programs. wb.save raises PermissionError and PyQt6 qFatal-aborts the app. Case 2 (on Mac too): the teacher pastes question text copied from a PDF or Word that contains a control character such as \x02, \x03 or \x0b. QLineEdit and QPlainTextEdit keep these characters, and openpyxl raises IllegalCharacterError in write_questions, which also aborts.

**Doğrulama yöntemi.** I read QuestionEditorDialog._save (src/matematigin_mantigi/ui/question_editor.py:302-312), write_questions (src/matematigin_mantigi/core/question_loader.py:25-43), MainWindow.open_editor (ui/main_window.py:345-351) and app.main (app.py:68-82). Nothing catches the error: no try/except in _save or open_editor, and grep finds no sys.excepthook anywhere in src. open_editor also does not check recorder.is_recording, so the editor opens during a recording. I then wrote my own repro, scratchpad/audit/verify-q/kaydet/ctrl_demo.py. It builds the real dialog with the real fonts, puts "PDF'den kopya\x03 metin\x0b devam" on the clipboard, pastes it into soru_edit with QPlainTextEdit.paste(), and clicks the real save_button. This is the path that also exists on the Mac.

**Kanıt.** Output of ctrl_demo.py:
  field repr: "PDF'den kopya\x03 metin\x0b devam"
  clicking Kaydet
  exit=127
The paste keeps the control characters in the field. Clicking Kaydet then kills the process with exit 127 and no traceback. The line "SURVIVED" never prints and the event loop never returns. openpyxl raises IllegalCharacterError inside ws.append, and PyQt6 turns an unhandled exception in a slot into qFatal/abort because there is no excepthook. The existing file is not damaged, since the error happens before wb.save, but every edit made in the dialog is lost and the whole app goes down.
The auditor's Windows case (xlsx locked by Excel, PermissionError) goes through the same unguarded call. On the Mac, PermissionError can come another way: the data lives in ~/Documents/Matematiğin Mantığı (paths.data_dir), and macOS can deny the app access to Documents.
The editor is not blocked during a recording (open_editor at main_window.py:345 has no recorder check). So if the teacher fixes a question mid-lesson, the abort also kills the recorder before it finalizes or muxes, and the recording is lost.
I rate it important rather than critical. It crashes loudly, not silently, the xlsx is not corrupted, and it needs specific input: control characters in pasted text, a locked file, or TCC denying access. It still ends the lesson and the recording on a plausible teacher action.

**Düzeltme taslağı.** In question_editor.py QuestionEditorDialog._save, wrap the write:
  try:
      write_questions(self.questions_path, self.questions)
  except (OSError, ValueError) as e:   # PermissionError, openpyxl IllegalCharacterError (a ValueError subclass)
      QMessageBox.critical(self, "Kaydedilemedi", f"Soru dosyası yazılamadı (Excel'de açık olabilir):\n{e}")
      return   # keep the dialog open so no edits are lost
Also, in QuestionEditorDialog._question_from_form, strip illegal characters from each text field with openpyxl.cell.cell.ILLEGAL_CHARACTERS_RE.sub("", text) so a pasted \x03 or \x0b never reaches openpyxl. As defense in depth, have app.main install a sys.excepthook that logs the error and shows a QMessageBox instead of aborting. That keeps any other slot exception from killing a running recording.

### q#3 · önemli · If the question file fails to load, the editor Kaydet overwrites the teacher's real file with the 3 sample questions

- **Yer:** `src/matematigin_mantigi/app.py:35`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The teacher's whole question bank is permanently replaced by 3 demo questions. There is no backup and no confirmation.

**Senaryo.** load_questions rejects the whole file for common reasons: one partially filled row (an id or konu with no soru gives "Satır N: 'soru' boş"), a second sheet being active when the file was last saved (loader reads wb.active), or headers typed as 'İpucu1'/'Sınıf', because 'İ'.lower() gives 'i̇', which does not match 'ipucu1'. app.load_questions_or_samples shows 'Örnek sorularla devam ediliyor' and returns SAMPLE_QUESTIONS. MainWindow is still built with questions_path=template (app.py:52), so the ✎ Sorular editor stays enabled and opens the samples bound to the real path. The teacher opens it to fix the problem and presses Kaydet. write_questions replaces the real file with the samples.

**Doğrulama yöntemi.** I traced the code and ran it end to end. I read app.load_questions_or_samples (app.py:31-36), build_window (app.py:40-54), MainWindow.__init__/open_editor (main_window.py:75, 103, 345-351), QuestionEditorDialog._save (question_editor.py:303-312) and question_loader.load_questions/write_questions. Then I ran a scratch script, scratchpad/audit/verify-q/overwrite/repro.py, through the real app.build_window path (--sorular pointed at a temp xlsx, --kamera-yok). The xlsx had 5 real questions plus a row containing only ['T6']. The script opened QuestionEditorDialog the way open_editor does and called _save().

**Kanıt.** Script output: the warning was "Satır 7: 'soru' boş ... Örnek sorularla devam ediliyor." and the loaded list was the 3 SAMPLE_QUESTIONS. It printed "editor enabled: True", with questions_path set to the real xlsx. After _save(), the file held only the 3 sample questions ('3x + 5 = 20 ise x kaçtır?', 'Kenarları 6 cm…', '2/3 + 1/6…'), and all 5 real questions were gone.

Why nothing stops it:
- load_questions (question_loader.py:~88-125) rejects the whole file on a single row with an empty 'soru'.
- load_questions_or_samples (app.py:31-36) swallows the error and returns list(SAMPLE_QUESTIONS).
- build_window still passes questions_path=template (app.py:52), so editor_button.setEnabled(self.questions_path is not None) is True (main_window.py:103).
- open_editor passes self.flow.questions, which are the samples, bound to the real path (main_window.py:349).
- _save only checks for empty soru text, then calls write_questions (question_editor.py:310), which builds a new Workbook and wb.save()s over the path. There is no backup and no overwrite confirmation.

This is a realistic path. A half-filled row is common in a hand-edited Excel bank, and a teacher who sees the warning would naturally open ✎ Sorular to fix it, or add a question and save.

Severity mitigation: the fallback is loud (a modal warning), and the editor visibly lists only 3 demo questions, so an attentive teacher might …

**Düzeltme taslağı.** In app.py, make load_questions_or_samples return a flag, e.g. (questions, loaded_ok). In build_window, pass questions_path=template only when loaded_ok; otherwise pass None, so the editor is disabled or says "Soru dosyası yüklenemedi; önce dosyayı düzeltin". A lighter alternative: keep the path but have MainWindow store self._questions_from_samples=True. Then in open_editor, or in QuestionEditorDialog._save, refuse to write, or ask for explicit confirmation and first copy the existing file to sorular.xlsx.bak (shutil.copy2) before write_questions. As defense in depth, write_questions (core/question_loader.py) could always keep a .bak of an existing file before overwriting.

### q#4 · küçük · Editor save rebuilds the workbook from scratch and silently drops extra columns, other sheets and formatting

- **Yer:** `src/matematigin_mantigi/core/question_loader.py:28`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** Anything the teacher added to the Excel file beyond the known columns is permanently deleted the first time they use the in-app editor, with no warning.

**Senaryo.** The teacher's sorular_sablon.xlsx has an extra column (e.g. 'cozum' or 'zorluk') or a second sheet (e.g. lesson notes). The loader ignores these, which is fine, but any Kaydet in the ✎ editor calls write_questions. That function creates a new openpyxl.Workbook containing only the 14 known columns and a single 'Sorular' sheet, then writes it over the original.

**Doğrulama yöntemi.** I read question_loader.write_questions and followed its only in-app caller: MainWindow.open_editor (main_window.py:344), then QuestionEditorDialog._save (question_editor.py:310), which calls write_questions(self.questions_path, ...). questions_path is the teacher's real template (app.py build_window: questions_path=template, which in the .app is paths.default_template_path() under ~/Documents). No backup exists before the overwrite: grepping for backup/yedek/.bak in src finds nothing. I then wrote a scratch test at scratchpad/audit/verify-q/extra-cols/test_extra.py. It writes the template, adds column 15 'cozum' with text and a second sheet 'Notlar', loads it, builds QuestionEditorDialog on that path and calls _save(), then reopens the file with openpyxl.

**Kanıt.** After dlg._save() the file's sheets were ['Sorular'] and its header was exactly the 14 ALL_COLUMNS. The 'cozum' column and the 'Notlar' sheet were gone, so the assertion `'Notlar' in wb2.sheetnames` failed. The cause is question_loader.py:28-42: write_questions always builds a fresh `openpyxl.Workbook()` with one 'Sorular' sheet and the 14 known columns, then runs `wb.save(path)` over the original. It keeps nothing from the file on disk: no other sheets, no extra columns, no formatting or cell styles. It also gives no warning and makes no backup.

Worse variant on the same path: if load_questions raises (for example a typo in a required header), app.load_questions_or_samples shows a warning and falls back to SAMPLE_QUESTIONS. questions_path still points at the teacher's file, though. Opening the ✎ editor and pressing Kaydet then overwrites the teacher's whole question bank with the 3 sample questions.

Scope: pdf_import.write_questions writes a new output file, so it is not affected. Recording is not touched.

**Düzeltme taslağı.** In core/question_loader.py, write_questions: if `path` exists, open it with `openpyxl.load_workbook(path)` instead of creating `openpyxl.Workbook()`. Pick the sheet load_questions reads (wb.active). Map the header to column indices and add any missing ALL_COLUMNS at the end of the header. Clear the data rows (ws.delete_rows(2, ws.max_row)) and write each question's values into the known-column indices only. That keeps other sheets, extra columns' headers and formatting. Extra-column values in rows would still need their row kept, so either write row by row in place and leave unknown columns alone, or match rows by id. Only create a fresh workbook when the file does not exist. Also copy the old file to `path.with_suffix('.xlsx.bak')` (shutil.copy2) before saving. Separately, in app.load_questions_or_samples / MainWindow.open_editor: when the load fell back to samples, do not pass the teacher's path to the editor, or warn before overwriting it.

### q#5 · önemli · After Kaydet, open-ended questions show empty "A) B) C) D)" and blank extra hint cards until restart

- **Yer:** `src/matematigin_mantigi/ui/question_editor.py:222`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** After a quick typo fix mid-lesson, the recorded board shows a bogus empty multiple-choice row under an open-ended question, and the hint panel shows empty hint cards ('1 / 4').

**Senaryo.** _question_from_form builds hints and options from all 4 fields, including empty strings, and _save emits that list (line 311). MainWindow.reload_questions (main_window.py:353-358) feeds it straight into the flow instead of reloading from disk. For every question the editor committed (always at least the one visible when saving), QuestionZone._build_options sees a non-empty 4-tuple of '' and renders 'A) ', 'B) ', 'C) ', 'D) '. HintZone creates 4 cards, with blank ones among them, and the counter and hint navigation count them. The file on disk is correct, because the loader filters blanks, so the defect only shows in the running session.

**Doğrulama yöntemi.** I traced the path from QuestionEditorDialog._question_from_form (question_editor.py:214-226) through _save (:305-313) and the saved signal, then MainWindow.open_editor/reload_questions (main_window.py:345-359), QuestionFlow.set_questions (question_flow.py:77-84), QuestionZone._build_options (question_zone.py:186-200) and HintZone.set_hints (hint_zone.py:150). None of these strip blank strings; only the file loader does. I then reproduced it through the real MainWindow using the repo's `window` fixture. The test loads an open-ended question (2 hints, no options), monkeypatches QuestionEditorDialog.exec to fix a typo and click the real Kaydet button, then calls window.open_editor(). Scratch test: C:\Users\bkese\AppData\Local\Temp\claude\C--Users-bkese-Desktop-arayuz-soru-sistemi-metematigin-mantigi\0647ad5c-ac9d-414d-ad34-9375fe87f54d\scratchpad\audit\verify-q\blank-save\test_blank_save.py …

**Kanıt.** Test output: BEFORE (cards=2, option labels=[], hint_count=2, options row visible=False). AFTER (cards=4, option labels=['A) ','B) ','C) ','D) '], hint_count=4, options row visible=True). The in-memory question in the flow has hints ('i1','i2','','') and options ('','','',''). load_questions on the file just written returns ('i1','i2') and (), so the disk copy is correct and only the running session is wrong. Nothing upstream guards this. `_build_options` only checks `if not options`, and a 4-tuple of '' is truthy. `set_hints` makes one card per entry, and `hint_count()` is `len(current.hints)`. After reload the flow goes back to index 0, and that is the question the editor always commits (the one showing when the dialog opens). So the bad render appears on the board right after Kaydet. It also affects the stock SAMPLE questions, which have 3 hints: saving adds a blank 4th card. It stays until the app restarts.

**Düzeltme taslağı.** In src/matematigin_mantigi/ui/question_editor.py, change QuestionEditorDialog._question_from_form to drop blanks, the same way the loader does: `hints=tuple(t for t in (e.text().strip() for e in self.hint_edits) if t)` and `options=tuple(t for t in (e.text().strip() for e in self.option_edits) if t)`. _populate already pads back to 4 fields, so the editor still works. Also add a regression test: MainWindow.open_editor, then Kaydet on an open-ended question, then assert question_zone.option_labels == [] and len(hint_zone.cards) == the number of hints that are not blank.

### q#6 · küçük · Double-clicking or double-tapping a hint card leaves it readable while the app treats it as hidden

- **Yer:** `src/matematigin_mantigi/ui/hint_zone.py:288`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** A hint or answer the teacher meant to keep hidden is readable in the recording. The next click then does nothing visible, because it only flips the state to 'revealed', which confuses the teacher.

**Senaryo.** The first press reveals the card and starts the 300 ms un-blur timer. QWidget's default mouseDoubleClickEvent calls mousePressEvent, so a double-click (or a pen double-tap) toggles the card straight back to hidden. apply(revealed=False, BLUR) installs a new blur effect but never stops _fade_timer. _fade_step then keeps un-blurring the new effect and finally calls setGraphicsEffect(None). The flow state and card.revealed say hidden, but the text is fully legible until something calls _refresh again, such as hint navigation.

**Doğrulama yöntemi.** I read HintCard.apply, _fade_step and mousePressEvent in src/matematigin_mantigi/ui/hint_zone.py. The file has 204 lines, so the cited line 288 is off; the real lines are 56-97. I also traced the wiring: main_window.py:151 connects revealToggled to flow.toggle_reveal, main_window.py:144 connects hintRevealChanged to hint_zone.set_revealed and then _refresh, and zone.py handles click-through and tablet ignore. There is no debounce or double-click guard anywhere on that path. I then wrote scratch tests in C:\Users\bkese\AppData\Local\Temp\claude\C--Users-bkese-Desktop-arayuz-soru-sistemi-metematigin-mantigi\0647ad5c-ac9d-414d-ad34-9375fe87f54d\scratchpad\audit\verify-q\dblhint\test_dbl.py. They use the real MainWindow fixture with the CLICK tool active and reveal_anim_ms=300, and run under offscreen Qt with qt_api=pyqt6.

**Kanıt.** Test 1 sent QTest.mouseDClick to the window handle. That input goes through QGuiApplication's own double-click detection, the same path real OS or pen input takes. The card received the Qt6 sequence Press, Release, DblClick, Release. There is no second Press, so the DblClick calls mousePressEvent through QWidget's default handler, and that is the second toggle. Immediately after, the state was flow=False, card=False, QGraphicsBlurEffect radius 9. After 700 ms it was flow=False, card.revealed=False, graphicsEffect=None, so the text is fully unblurred while the app says it is hidden.
Test 2 sent widget-level press, release and dblclick, with the same result.
Test 3 called flow.toggle_reveal() twice 40 ms apart, which is the same as pressing the Return key twice quickly (main_window.py _return_key). It ended flow=False with effect=None.
Root cause: apply() at hint_zone.py:71-74 (the revealed=False, BLUR branch) installs a new QGraphicsBlurEffect but never stops _fade_timer. _fade_step (lines 79-90) then fades the new effect's radius toward 0 and calls setGraphicsEffect(None) at line 90. Only BLUR mode is affected, and BLUR is the default. REDACT removes the effect, so _fade_step stops itself. This is reachable in real use: a mouse double-click, an XP-Pen double-tap (in CLICK mode, zone.py ignores the tablet event and Qt synthesizes mouse events, which include DblClick), or Return …

**Düzeltme taslağı.** In src/matematigin_mantigi/ui/hint_zone.py, HintCard.apply: when revealed is False, call self._fade_timer.stop() before installing the blur effect or the redact style. For example, put `if not revealed: self._fade_timer.stop()` right after `self.revealed = revealed`. Optionally, also add HintCard.mouseDoubleClickEvent that only calls e.accept(), so a double-click or double-tap counts as one toggle instead of two.

### q#7 · önemli · A corrupt or empty question file crashes the app at launch with no message; the fallback only catches QuestionTemplateError

- **Yer:** `src/matematigin_mantigi/app.py:34`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** Launched from Finder, the app bounces and quits with no explanation, so there is no lesson and no recording. The teacher has no idea which file to fix.

**Senaryo.** load_questions_or_samples catches only QuestionTemplateError. If sorular_sablon.xlsx is 0 bytes, truncated or not a zip, openpyxl.load_workbook (question_loader.py:92) raises zipfile.BadZipFile. That can happen because write_questions/wb.save writes the target in place (question_loader.py:42): it truncates first, so a save interrupted by the abort in finding 2, a full disk or a sync conflict leaves a broken file. The same happens if the file is an .xls renamed to .xlsx. The exception propagates out of build_window before any window exists. The .app is built with console=False, so the traceback goes nowhere.

**Doğrulama yöntemi.** I read src/matematigin_mantigi/app.py (load_questions_or_samples, build_window, main), __main__.py, core/question_loader.py (write_questions, ensure_template, load_questions), paths.py, ui/question_editor.py _save and mac/matematigin_mantigi.spec. I searched src for excepthook or broader handlers and found none on the startup path. I wrote the scratch script audit/verify-q/corrupt/repro.py, which calls load_questions_or_samples on three files: a 0-byte .xlsx, an OLE/.xls header renamed to .xlsx, and a real template truncated to half its size. I also ran the whole app with `python -m matematigin_mantigi --sorular <empty.xlsx> --kamera-yok` under offscreen Qt.

**Kanıt.** All three cases raise instead of falling back: "0-byte -> RAISES zipfile BadZipFile File is not a zip file", and the xls-renamed and truncated-half cases raise the same error. A full `python -m matematigin_mantigi` run died with a `zipfile.BadZipFile` traceback and exit=1 before any window appeared.

The code path: app.py:31-36 catches only QuestionTemplateError. question_loader.py:92 calls openpyxl.load_workbook with no guard, so BadZipFile and also KeyError, InvalidFileException, OSError and PermissionError escape. build_window (app.py:44) runs before win.show(). There is no sys.excepthook anywhere in src. mac/matematigin_mantigi.spec:37 sets console=False, so in the .app the traceback goes nowhere.

The broken file can happen in real use. The file lives in ~/Documents/Matematiğin Mantığı (paths.py:30), which the teacher edits by hand and which iCloud "Desktop & Documents" often syncs. write_questions (question_loader.py:42, called from question_editor.py:310 and pdf_import.py:36) saves in place with wb.save and no temp-file-and-rename, so a crash or power loss mid-save leaves a truncated file. ensure_template does not rewrite an existing broken file, so every relaunch fails the same way until the teacher finds and deletes the file, and nothing tells them which file it is.

Severity: the trigger is uncommon, but when it happens no lesson can start, nothing is recorded, and th …

**Düzeltme taslağı.** 1. In app.py load_questions_or_samples, widen the except to `except Exception as err:`. Show a QMessageBox.warning that names the file path and the error type ("Soru dosyası okunamadı: <path> ... Örnek sorularla devam ediliyor"), then return list(SAMPLE_QUESTIONS). Keep the QuestionTemplateError message wording as it is.

2. Optionally, to stop the file breaking in the first place, change question_loader.write_questions to save to `path.with_suffix('.xlsx.tmp')` and then `os.replace(tmp, path)`, so an interrupted save cannot truncate the real file.

3. Add a pytest that calls load_questions_or_samples on a 0-byte .xlsx, with QMessageBox.warning monkeypatched, and asserts it returns the sample questions.

### q#8 · küçük · Numeric, percent and date cells are shown as raw Python values (2,5 -> "2.5", %50 -> "0.5")

- **Yer:** `src/matematigin_mantigi/core/question_loader.py:85`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** Math content on the recorded board differs from the spreadsheet. A percent option shows as a decimal, so it can be a wrong or misleading answer choice, and decimals use the non-Turkish point.

**Senaryo.** Excel stores what a Turkish teacher types in a cell as typed values. "2,5" becomes float 2.5, "%50" becomes 0.5 with a percent format, and "1/2" may become a date. _text() just calls str(v), so the board shows '2.5' instead of '2,5', '0.5' instead of '%50', and something like '2026-02-01 00:00:00' for an auto-dated fraction. It ignores what Excel displays and Turkish decimal notation.

**Doğrulama yöntemi.** I read question_loader.py in full: load_questions opens the workbook with data_only=True and passes every cell through _text() -> str(v). I checked the callers with grep. question_zone.py:116 and _build_options draw q.options and the answer text exactly as loaded; nothing reformats them. question_editor.py:203/209 fills its fields from the same loaded strings and saves them back with write_questions. I wrote a scratch script (scratchpad/audit/verify-q/numeric/repro.py) that creates an xlsx the way Turkish-locale Excel stores what the teacher types: cevap=2.5 (format 0.0), b=0.5 (format 0%), c=datetime(2026,2,1) (format d.mmm, which is what typing "1/2" becomes), and d=25. I loaded it with PYTHONPATH=src.

**Kanıt.** Output: cevap: '2.5'; options: ('2.5', '0.5', '2026-02-01 00:00:00', '25'). question_loader.py:84-85 `def _text(v): return "" if v is None else str(v).strip()` ignores number_format and Turkish decimal notation, and nothing upstream guards against it. Excel stays a real input path: the module is the "Excel şablonu" loader, the template is sorular_sablon.xlsx, and pdf_import writes to it. When the teacher types in Excel, the cells are stored as typed numbers. So on the recorded board "2,5" shows as "2.5", "%50" shows as "0.5" (a different and wrong-looking answer choice), and "1/2" shows as "2026-02-01 00:00:00". There is a second effect: if the teacher opens the file in the in-app question editor and saves, write_questions writes these wrong strings back as text, and the original formatting is lost for good. Mitigation: questions entered only through the in-app editor are stored as strings and are not affected. It does not crash and it does not touch the recording.

**Düzeltme taslağı.** In src/matematigin_mantigi/core/question_loader.py, give _text a cell-aware mode. Stop passing values_only=True to iter_rows so each cell's number_format is available. Then: for a datetime, output a d/m fraction-style string, or better, warn with QuestionTemplateError hinting that the column should be formatted as Text. For a float/int whose number_format contains '%', output f"%{v*100:g}". For any other float, output f"{v:g}".replace('.', ','). For an int, output str(v). Apply this only to value columns (soru, ipucu*, cevap, a-d), and keep id and sinif as they are. Optionally, also set number_format='@' (Text) on the data columns in write_questions so that new templates keep what the teacher types verbatim.

## Tuval, kalem, araçlar (`pen`)

### pen#1 · küçük · A failed snapshot save on question change kills the app, and the running recording with it

- **Yer:** `src/matematigin_mantigi/ui/main_window.py:236`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** A per-question PNG is a convenience, but its failure takes down the whole app mid-lesson with no message. The ffmpeg/audio session is never stopped through MainWindow.closeEvent, so the mic WAV is never muxed and the lesson recording is cut off. Realistic triggers are narrow (disk nearly full during a long 2K60 session, a revoked Documents permission), but the consequence is the worst defect class.

**Senaryo.** The teacher is recording and presses Sonraki (or N). _on_question_leaving calls SessionStore.save_snapshot, and any OSError there propagates out of the Qt slot: mkdir failing (permission, a path that exists as a file) at session_store.py:30, or image.save() returning False (e.g. a full disk) and hitting the raise at session_store.py:31. app.py installs no sys.excepthook, so PyQt6 turns the unhandled slot exception into qFatal/abort().

**Doğrulama yöntemi.** Read main_window.py:234-237 (_on_question_leaving, connected at :137 to flow.questionLeaving; also reached through the 'N' QShortcut at :170), core/session_store.py:27-34, app.py main()/build_window, and recorder.start (recorder.py:241-280). Wrote my own repro, separate from the auditor's: verify-pen/snapcrash/repro.py. It builds MainWindow with a real SessionStore and draws one stroke. It forces the image.save()==False branch, the one a full disk would hit, by pre-creating the target <id>_01.png as a directory. Then it presses Sonraki, both by clicking toolbar.next_button and by pressing the N shortcut. A control run used a clean store. A third run wrapped the script with a Python sys.excepthook to capture the traceback.

**Kanıt.** Control run: 'SURVIVED index 1', exit 0. Fault run, button click: process died with exit 0xC0000409 (abort), no 'SURVIVED' printed. Fault run, N key: also 0xC0000409. With a sys.excepthook installed, the same run survives (index 1, loop rc 0) and the traceback shows 'OSError: PNG yazılamadı: ...\S1_01.png' raised at session_store.py:33 from main_window.py:236 _on_question_leaving. So the claim holds: an unhandled exception in a PyQt6 slot calls qFatal because nothing installs an excepthook (grep for excepthook in src finds nothing, and app.py main() sets none). Nothing guards the save_snapshot call. Reachability is narrower than the auditor says. MssFfmpegRecorder.start mkdirs the same store.session_dir (recorder.py:255, app.py:50), and build_window runs paths.ensure_user_data() at startup, so a permission problem or a path-is-a-file problem on the session dir shows up before or at recording start, not on question change. The realistic mid-lesson trigger is a full disk (image.save returns False). The ffmpeg recording writes to that same disk, so it is failing at roughly the same moment anyway. What the crash adds: the app disappears without a message and the board state is lost. Clean stop/mux through closeEvent never runs, so the .wav is left un-muxed next to .video.mp4. The same abort also hits teachers who are not recording.

**Düzeltme taslağı.** In MainWindow._on_question_leaving (src/matematigin_mantigi/ui/main_window.py:234), wrap the save_snapshot call in try/except OSError, then show the error without blocking: a status line or a non-modal warning such as 'Tahta görüntüsü kaydedilemedi: {err}'. Then continue to canvas.clear() and the question change. As a safety net, install a sys.excepthook in app.main() (src/matematigin_mantigi/app.py) that logs the traceback and shows a warning instead of letting PyQt6 abort. That way no other slot exception can kill an in-progress recording.

### pen#2 · önemli · Undo after the board grows restores a smaller bitmap, so new ink in the grown area silently disappears

- **Yer:** `src/matematigin_mantigi/ui/canvas.py:151`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** On camera, the pen stops leaving ink in the right or bottom part of the board. Nothing warns the teacher, and it lasts until the next window resize. Anything written there is also missing from the saved snapshot.

**Senaryo.** The teacher draws a stroke. The board then grows: F11 or the macOS zoom button, turning the frame off, HUD to Classic (smaller band), or dragging to a higher-dpr screen. _ensure_layers enlarges _strokes, but the undo stack still holds the old, smaller QImage. After Ctrl+Z, undo() assigns that small image back to _strokes, and _ensure_layers runs only from resizeEvent, so nothing regrows it. Every stroke drawn to the right of or below the old size is painted outside the image and clipped. is_empty() still reports ink, and snapshot_image() also comes out at the old size.

**Doğrulama yöntemi.** I read canvas.py (undo, _push_undo, _ensure_layers, resizeEvent, snapshot_image) and its callers: work_area.relayout calls board.setGeometry(inner_rect); main_window binds F11 to showFullScreen/showNormal, Ctrl+Z to canvas.undo, and _on_question_leaving to save_snapshot(canvas.snapshot_image()). app.py starts the window with a plain win.show(), not fullscreen. I then wrote and ran scratchpad/audit/verify-pen/undo-grow/repro.py with offscreen Qt: a 400x300 canvas, one stroke, a resize to 1200x800, one undo, then a new stroke at (700..900, 600..700).

**Kanıt.** Repro output: 'grown img QSize(1200, 800)', then 'after undo img QSize(400, 300)', then 'stored at (800,650)? False is_empty False snapshot QSize(400, 300)'. The cause is in canvas.py:148-153. undo() does `self._strokes, self._stroke_count = self._undo.pop()` and restores the QImage copied before the board grew. It never calls _ensure_layers. _ensure_layers (canvas.py:275-283) runs only from __init__ and resizeEvent (286), so nothing grows the image back until the widget is resized again. _draw_segment paints into that smaller _strokes, so ink outside the old size is dropped. The pen still counts the stroke (_stroke_count += 1), so is_empty() is False and the undo button stays on. There is no guard: the undo stack survives resizes and question changes, because clear() also pushes onto it. Real path: the app opens windowed (app.py:80). The teacher draws, presses F11 or the macOS zoom button (relayout calls board.setGeometry with a bigger inner rect), then presses Ctrl+Z. From then on the right and bottom strip of the board takes no ink, live and in the recording, until the next resize. When the question changes, _on_question_leaving saves the smaller snapshot_image, so the ink in that strip is lost from the saved snapshot too.

**Düzeltme taslağı.** In src/matematigin_mantigi/ui/canvas.py, DrawingCanvas.undo(): right after popping, call `self._ensure_layers(self.size())` before `self.update()`. _grown() copies the restored smaller image into a new image at the current size, so the old content stays and the whole board takes ink again. This change is enough because _ensure_layers only ever grows the image, and the overlay is not part of the undo stack. Add a regression test: resize, stroke, grow, undo, then assert strokes_image().size() >= board size times dpr and that a stroke drawn in the grown area is stored.

### pen#3 · önemli · Text still in the text box when the question changes is left out of Q1 and stamped onto Q2

- **Yer:** `src/matematigin_mantigi/ui/main_window.py:234`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** Q1's written answer is missing from its snapshot, then shows up on the next question in the recording, so the teacher has to erase it on camera.

**Senaryo.** With the Yazı tool, the teacher clicks the board and types an answer ('x = 5'), then clicks the toolbar Sonraki button instead of pressing Enter. The N shortcut is suppressed while typing, but the button is not. _on_question_leaving snapshots and clears the canvas without calling canvas.commit_text() or cancel_text(). The QLineEdit stays visible with the text, and the next Enter or click commits it onto question 2's board.

**Doğrulama yöntemi.** I read canvas.py (set_tool 84-87, begin_text 167-182, commit_text 184-190), main_window.py (_on_question_leaving 234-237, _typing/_shortcuts 154-172, reload_questions 353-359) and QuestionFlow.select (question_flow.py:86-95). Then I wrote my own pytest, scratchpad/audit/verify-pen/textpending/test_textpending.py, using the real MainWindow fixture in offscreen mode. The steps: pick the Yazı tool, mouse-click the canvas at (300,300), type 'x = 5' into text_edit, click toolbar.next_button, press N, then mouse-click the canvas at (800,600) as a teacher starting to write on Q2 would.

**Kanıt.** Output: `idx 1 edit visible True text 'x = 5' snaps [] typing True`, then `after N idx 1`, then `after board click: idx 1 empty False ink 68 strokes 1`.

1. The Sıradaki soru button is not guarded by _typing(); only the QShortcut path is. QuestionFlow.select emits questionLeaving, and _on_question_leaving (main_window.py:234-237) only checks canvas.is_empty(), which counts committed strokes, and then calls clear(). No commit_text() or cancel_text() is called, so Q1 gets no snapshot (snaps []).
2. The QLineEdit (a child of the canvas) stays visible with 'x = 5' over question 2. It appears in the recording as soon as Q2 is shown.
3. While the box is visible, _typing() is True, so N, P, Space, R, H and the tool keys all do nothing. The teacher's keyboard navigation looks dead.
4. The Yazı tool is still active. The first click on Q2's board calls begin_text, which calls commit_text() (canvas.py:169-171) and draws 'x = 5' at the old Q1 position onto Q2 (stroke_count 1, ink 68). Pressing Enter does the same. reload_questions (main_window.py:355) has the same gap.

Nothing upstream prevents this. set_tool only commits when the tool changes away from TEXT, and the button needs no tool change. Ctrl+Z (allowed while typing) can remove the text, and nothing is lost from the video file. But it puts wrong content on camera and has to be fixed live, and Q1's session snapshot, which is saved …

**Düzeltme taslağı.** In main_window.py MainWindow._on_question_leaving, finish any open text entry before the emptiness check: `if self.canvas.text_edit.isVisible(): self.canvas.commit_text()`. Also add a public `Canvas.finish_text()` wrapper that commits only when the box is visible. That way Q1's typed answer is included in its snapshot and then cleared along with the canvas. In reload_questions, call `self.canvas.cancel_text()` (or finish_text) before `self.canvas.clear()`. Add a regression test: type in the text box, click toolbar.next_button, then assert that text_edit is hidden, the Q1 snapshot exists, and the canvas is empty after a board click on Q2.

### pen#4 · küçük · The current question's board is never saved on app close or question reload, despite the 'Otomatik kaydet: Her 30 sn' toggle

- **Yer:** `src/matematigin_mantigi/ui/main_window.py:469`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The final (often most important) question's board silently has no PNG. The teacher believes autosave covers it, so the loss goes unnoticed until later.

**Senaryo.** Snapshots are written only in _on_question_leaving. The last question worked in a lesson is never left, so when the teacher quits (Cmd+Q, or closing the window) closeEvent stops the recorder and shuts down the webcam but does not snapshot the canvas. reload_questions (main_window.py:353-356, after saving in the question editor) also calls canvas.clear() without a snapshot. The pen settings dialog advertises autosave 'Her 30 sn ve soru değişiminde' (pen_settings.py:88) and defaults it on, but no 30 s timer exists and PenSettings.autosave is read nowhere.

**Doğrulama yöntemi.** Read main_window.py (_on_question_leaving 234-237, reload_questions 353-358, closeEvent 469-479), question_flow.py select()/next_question (questionLeaving is emitted only when the index changes), session_store.py, and app.py (no aboutToQuit hook). Grepped src for every use of autosave and QTimer. Then ran the auditor's scratch script offscreen (QT_QPA_PLATFORM=offscreen PYTHONPATH=src python scratchpad/audit/find-pen/close_snap.py). It drives the real MainWindow: draw on Q1, click next, draw on Q2, win.close().

**Kanıt.** Script output: 'autosave setting: True' and 'files after closing the app: ['S1_01.png']'. So Q1 was saved when it was left, and nothing was written for Q2 even though its board had ink.

- The only call to save_snapshot is in _on_question_leaving (main_window.py:236). That handler runs only on flow.questionLeaving, which QuestionFlow.select emits only when i != self._index (question_flow.py:89-90).
- closeEvent (main_window.py:469-479) stops the recorder, stops the webcam and syncs settings. It never snapshots the canvas.
- app.py has no aboutToQuit or lastWindowClosed handler.
- reload_questions (main_window.py:353-355) calls self.canvas.clear() with no snapshot first, so saving in the question editor also discards the current board silently.
- PenSettings.autosave (default True in models.py:96) is only read and written in settings.py:185 and pen_settings.py. No behaviour depends on it, and there is no 30 s timer.
- The dialog tells the teacher 'Her 30 sn ve soru değişiminde' (pen_settings.py:88). The plan doc (docs/superpowers/plans/2026-09-04-gorunus-demosu.md:5319) lists 'autosave and crash recovery' as a future plan, so the 30 s part was deferred on purpose. Even so, the shipped UI claims it works, and save-on-close is missing whatever the setting says.

Severity re-rating: the pen strokes are part of the recorded screen, so the lesson video (the product) is not affected. …

**Düzeltme taslağı.** In src/matematigin_mantigi/ui/main_window.py, add a helper _snapshot_current() that does: if self.flow.questions and not self.canvas.is_empty(), call self.session_store.save_snapshot(self.flow.questions[self.flow.index].id, self.canvas.snapshot_image()), wrapped in try/except OSError that shows a warning. Call it:
- at the top of closeEvent, before the recorder is stopped;
- at the top of reload_questions, before self.canvas.clear();
- optionally from _on_question_leaving, to reuse it.

Separately, either add a QTimer(30000) in MainWindow.__init__ that calls _snapshot_current when settings.pen().autosave is on and the canvas has changed since the last save, or change the pen_settings.py:88 caption to 'Soru değişiminde ve kapanışta' so the UI stops advertising a 30 s autosave that does not exist.

### pen#5 · küçük · One undo on a fresh question paints the previous question's whole board over it

- **Yer:** `src/matematigin_mantigi/ui/main_window.py:237`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** A reflexive undo on a new question puts the old question's solution into the recording and duplicates it under the wrong question in the session folder.

**Senaryo.** On question change, _on_question_leaving calls canvas.clear(), and clear() pushes the whole previous board onto the undo stack (canvas.py:158). On the new question the ↶ button is enabled even though nothing has been drawn. A single Ctrl+Z, the button, or an express-key double press restores Q1's complete working over Q2's question text. If the teacher then moves on, that restored ink is saved again as S2_01.png.

**Doğrulama yöntemi.** I read canvas.py (clear, undo, _push_undo) and main_window.py (_on_question_leaving at 234-237, the Ctrl+Z shortcut at 167, undoRequested at 116, historyChanged to set_undo_enabled at 133, reload_questions at 355). Nothing upstream clears the undo deque when the question changes. I then wrote a pytest repro using the repo's conftest `window` fixture: scratchpad/audit/verify-pen/undo-cross/test_undo_cross.py with its own pytest.ini (qt_api=pyqt6). The test draws a stroke on Q1, clicks work_button and then next_button, sends one real Ctrl+Z keyClick to the window, and advances to the next question again.

**Kanıt.** Output: 'idx 1 empty True undo enabled True', then after a single Ctrl+Z 'after ctrl+z empty False ink alpha 255', and after the next question the session folder holds ['S1_01.png', 'S2_01.png']. S2_01 is Q1's ink. Cause: main_window.py:237 `self.canvas.clear()` goes to canvas.py:154-161. clear() calls `self._push_undo()` before filling the board, and nothing ever resets `self._undo` (deque maxlen 30) on a question change. canvas.py:148 undo() pops that entry back. historyChanged(can_undo=True) enables the undo button on the fresh question. reload_questions (main_window.py:355) has the same leak after an editor save: undo can bring back the old board over the reloaded question list. The earlier strokes of Q1 (up to 30 entries) also stay reachable from Q2. Severity is minor for this user. The failure is visible, not silent: the teacher sees the old ink appear and can clear it. But while recording, the old solution flashes into the new question's footage, and if the teacher does not notice before moving on, a wrong S2_01.png is saved. There is no crash and the recording is not lost.

**Düzeltme taslağı.** In canvas.py, add a method `reset_board()` (or `clear(keep_history=False)`) that fills _strokes with transparent, sets _stroke_count = 0, calls `self._undo.clear()`, cancels any open text edit, calls update(), and emits historyChanged(False, True). Call it from MainWindow._on_question_leaving (main_window.py:237) and MainWindow.reload_questions (main_window.py:355) in place of canvas.clear(). Leave the user-facing clear button and Ctrl+Shift+X on the undoable clear(). Add a test_main_window test: after next_button, `not window.canvas.can_undo()` and the undo button is disabled.

### pen#6 · küçük · Ink is fixed in board pixels while the zones reflow, so annotations drift when the board is resized

- **Yer:** `src/matematigin_mantigi/ui/canvas.py:285`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** After a window-size change mid-lesson, everything the teacher marked on hints or the question points at the wrong place on camera, and part of the ink may vanish past the edge.

**Senaryo.** relayout() (work_area.py:468-478) re-places the question and hint zones proportionally to inner_rect, but resizeEvent only grows the strokes bitmap and keeps ink at absolute pixels from the board's top-left. The board size changes whenever the window does. One easy trigger mid-lesson is a stray Esc, which exits fullscreen when no text box or edit mode is active (main_window.py:187-193). Others are F11, the macOS zoom button, frame or aspect toggles in Settings, and moving to another display. After any of these, circles and underlines on hint cards or question words no longer sit on them, and ink beyond the new board edge is clipped from view.

**Doğrulama yöntemi.** I read the code path: canvas.py:275-287 (_ensure_layers/resizeEvent only grow the bitmap), work_area.py:468-478 (relayout places zones with pixel_rect proportional to inner_rect), work_area.py:625-627 (resizeEvent calls relayout), and main_window.py:178/187-193 (F11 and Esc toggle fullscreen). No code rescales or re-anchors the ink when the board size changes; Canvas.clear is the only other thing that touches _strokes. I copied the auditor's drift.py to scratchpad/audit/verify-pen/drift/, added a MacBook-like case, and ran it offscreen with PYTHONPATH=src.

**Kanıt.** The auditor's numbers reproduce exactly. At 1920x1080 the board is 1772x974 and hint card 0 is at x=917. At 1600x1000 the board is 1452x794 and the card is at x=757. At 1280x800 it is 1132x614 and x=597. At 2400x1400 it is 2252x1244 and x=1157. The question label rewraps from width 737 to 577, 417 and 977. The underline drawn at 1920x1080 stays at y=120, x=114..851 every time, so it is no longer under the rewrapped text or beside the moved hint cards.

Two things limit the claim:
(1) The stage snaps to 32x18 steps, so small size changes do not move anything. A MacBook-like window going from 1512x982 to 1512x929 (menu bar and title bar) kept the same 1356x740 board. Only the board's position changed, and the ink moves with it because it is a child widget. Drift only happens when the stage step k changes or inner_rect changes. That covers a large windowed/fullscreen difference, a move to a projector or another display, and the aspect-lock or frame toggles in Settings.
(2) Ink past the new edge is only hidden, not lost. _strokes never shrinks (it is still 2252x1244 at the end), so the ink comes back when the board grows again.

The path is still reachable in real use. The app starts windowed (app.py:53 resize(1920,1080), app.py:80 show()), and F11, Esc (main_window.py:193) and the macOS green button all switch between fullscreen and windowed. When k changes, every circle or underl …

**Düzeltme taslağı.** In Canvas.resizeEvent (src/matematigin_mantigi/ui/canvas.py:285), remember the previous logical board size. When a non-empty canvas changes size, scale _strokes by new_w/old_w with QImage.scaled and SmoothTransformation, and scale every image on the _undo stack the same way. Because the stage is locked to 16:9, the scale is uniform. The zones come from pixel_rect proportional to inner_rect, so hint cards and question zones line up again. Only the rewrapped question text can be slightly off. Alternatively, call the same rescale from WorkArea.relayout only when inner.size() actually changes, which also covers the aspect and frame toggles. Also clear _overlay (the laser trail) on resize.

### pen#7 · küçük · A missed TabletRelease leaves the pen stuck down, so a hovering pen draws lines

- **Yer:** `src/matematigin_mantigi/ui/canvas.py:328`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** Stray lines follow the hovering pen across the board during recording until the teacher taps the pen again. A barrel-button release cuts a stroke short.

**Senaryo.** _tablet_down is cleared only by a TabletRelease the canvas processes while the tool is not CLICK. If the teacher switches to Tıkla mid-stroke (key '6', or an XP-Pen express key mapped to it), canvas.tabletEvent returns early at line 317 and Zone.tabletEvent stops forwarding, so the release is dropped. The same happens if a modal QMessageBox (e.g. the recorder error dialog from _check_recorder) opens while the pen is down. Back on a drawing tool, every hover TabletMove (tablet tracking is on) passes the `if self._tablet_down` check and extend_stroke draws. e.buttons() is never checked, and mouse input is also refused (mousePressEvent line 341). A related case: releasing the barrel button while the tip is still down arrives as a TabletRelease and ends the stroke early (line 330).

**Doğrulama yöntemi.** Read DrawingCanvas.tabletEvent (canvas.py:316-336), set_tool (canvas.py:84-87), Zone.tabletEvent (zone.py:64-72), MainWindow._on_tool and the digit shortcuts (main_window.py:164-166, 206-211). The auditor's test sent events straight to the canvas, so I wrote my own scratch test (verify-pen/stuck/test_stuck.py). It sends QTabletEvents to the top-level window handle, which goes through Qt's real QWidgetWindow tablet-grab routing and does not target the canvas directly. The run had a control stroke, then a stroke with a tool switch to CLICK in the middle (shortcut 6 = Tool.CLICK), then a switch back to PEN, then hover moves with buttons=NoButton and pressure 0.

**Kanıt.** Output of the routed run:
- Control: `down False ink 14 -> 14`. A normal stroke followed by hovering adds no ink.
- CLICK in mid-stroke: the release comes back `accepted False`, and `down True` stays set.
- After switching back to PEN, 30 hover moves take ink from 28 to 287. The hovering pen draws a line.
- A mouse press afterwards is refused (`mouse_down False`).

The reason is that canvas.py:317 returns early while tool==CLICK, so the TabletRelease never clears `_tablet_down`. Nothing else resets it: set_tool does not end the stroke, and TabletMove (line 327-329) never checks `e.buttons()`.

This is reachable in real use. Digit shortcut '6' is registered through QShortcut on the main window (main_window.py:166), and it fires on key or express-key input while the pen tip is still down. A second route is a modal QMessageBox opening mid-stroke. `_check_recorder` runs `toggle_recording(False)`, and when the stop fails `_on_record_stopped` shows `QMessageBox.warning` (main_window.py:310). Qt drops tablet events aimed at a window blocked by a modal. I did not run this path because it goes through the platform event layer; I traced it only.

The barrel case follows the same code path. A TabletRelease for RightButton while the tip is still down goes into the release branch at line 330-333 without checking `e.button()`, which clears `_tablet_down` and ends the stroke. That depends on …

**Düzeltme taslağı.** In src/matematigin_mantigi/ui/canvas.py DrawingCanvas.tabletEvent:
(1) In the TabletMove branch, check the buttons before extending: `if self._tablet_down and not (e.buttons() & Qt.MouseButton.LeftButton): self._tablet_down = False; self.end_stroke()`. Otherwise call extend_stroke as before. This closes the hover-draw hole whatever caused the release to be lost, including the modal dialog.
(2) In the TabletRelease branch, end the stroke only when `e.button() == Qt.MouseButton.LeftButton`, or when `not (e.buttons() & LeftButton)`, so a barrel-button release no longer cuts the stroke.
(3) In DrawingCanvas.set_tool, when `_tablet_down` or `_mouse_down` is set, clear both flags and call end_stroke() before changing the tool, so switching to CLICK mid-stroke closes the stroke cleanly.

### pen#8 · küçük · The text box is hidden behind hint cards, so the teacher types blind

- **Yer:** `src/matematigin_mantigi/ui/canvas.py:182`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The teacher sees nothing appear while typing over the hints, which is confusing on camera, and a typo can't be caught until the text is already committed.

**Senaryo.** text_edit is a child of DrawingCanvas, and relayout() calls board.lower() and raises the zones above it (work_area.py:471-480). Committed text and ink render above the hint cards through the InkLayer, but the live QLineEdit sits below the opaque hint cards and the webcam. With the Yazı tool, clicking on a hint card to annotate it opens the box underneath the card: the typed text and caret are invisible until Enter.

**Doğrulama yöntemi.** Read canvas.py begin_text (168-182), zone.py event forwarding, and work_area.py relayout z-order (471-480). Wrote an independent scratch script (verify-pen/textcover/v.py) that builds the real MainWindow offscreen, picks the Yazı (TEXT) tool, and sends a real left-click QMouseEvent to the HintZone at the centre of hint card 1. This is the same path a click or pen tap takes. It then types "x=5" with QTest.keyClicks, walks WorkArea's sibling stack to see which widget is on top over the text box, and grabs the composited region.

**Kanıt.** The click is reachable with no guard. In draw modes Zone.mousePressEvent/_forward_mouse (zone.py:40-58) and tabletEvent forward the press to the board. DrawingCanvas.begin_stroke then calls begin_text for Tool.TEXT (canvas.py:113-116). text_edit is created as QLineEdit(self), a child of DrawingCanvas (canvas.py:76). Its raise_() at canvas.py:182 only reorders it among the canvas's own children. It cannot rise above the canvas's siblings. relayout() calls board.lower() (work_area.py:472), and the zones, InkLayer and webcam are raised above the board. Script output: "visible True hasFocus-ish True", "text x=5", "fraction of text box area covered by a sibling above canvas: 1.00", "canvas index 0 hint index 53". The hint card is painted opaque by its stylesheet (#hintCard background #fff4d6). The composited crop (crop.png) shows only the hint cards. There is no dashed box, no caret and no "x=5". So the teacher types blind until Enter. On Enter the committed text is drawn through InkLayer and does appear above the cards. The same thing happens over the question zone and, fully hidden, under the webcam panel. It is not a crash and nothing is lost. But it is wrong state shown live and in the recording, and the teacher has no way to see or fix a typo before commit.

**Düzeltme taslağı.** In canvas.py DrawingCanvas: make the text box a child of the canvas's parent (the WorkArea), not of the canvas. For example, in __init__ use `self.text_edit = QLineEdit(parent if parent is not None else self)`. In begin_text, map the position into that parent: `top_left = self.mapTo(self.text_edit.parentWidget(), QPoint(int(pos.x()), int(pos.y()) - self.text_edit.height() // 2)); self.text_edit.move(top_left)`, then `show(); raise_(); setFocus()`. Because raise_() now runs among the WorkArea's children, the box ends up above the zones, InkLayer and webcam. commit_text/draw_text keep using the canvas-local _text_pos, so nothing else changes. Alternatively, WorkArea.relayout() could re-raise canvas.text_edit after the webcam when the box is visible, but that only works if the box is reparented as well.

## Kamera (`cam`)

### cam#1 · önemli · Clicking 'Kameraları tara' in Settings kills the live webcam stream; after Vazgeç it stays dead

- **Yer:** `src/matematigin_mantigi/ui/settings_dialog.py:232`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** A routine action in the settings dialog silently breaks the webcam mid-lesson. If the teacher cancels, the teacher disappears from the board and any ongoing recording until the app is restarted or the eye button is toggled.

**Senaryo.** The webcam panel is live. The teacher opens ⚙ Ayarlar and clicks 'Kameraları tara'. _scan_cameras runs core.cameras.list_cameras() on the GUI thread. It opens and releases every index 0..5, including the device the CameraWorker already holds. On this Windows box (DSHOW, OBS Virtual Camera at index 1), releasing the scan's second handle kills the worker's capture. Every read() after that fails, the worker gives up after 31 misses, and the board shows 'Kamera akışı kesildi · Kamera izni / bağlantı kontrol edin' instead of the teacher. Uygula with the same index happens to recover it, because apply_ui_settings calls start() on the finished worker. Vazgeç does not, so the webcam stays dead for the rest of the lesson unless the teacher knows to toggle the layout-edit eye button. If a recording is running, the error text goes into the recording. There is a second path: on a webcam driver that refuses a second open while busy, the active camera is missing from the scan result. Then findData(current) returns -1 and line 239 silently selects the first other camera, so pressing Uygula for any unrelated setting switches cameras.

**Doğrulama yöntemi.** I read settings_dialog._scan_cameras (lines 229-240), cameras.list_cameras (lines 79-100), camera_worker.OpenCvSource/CameraWorker.run (misses > 30 leads to "Kamera akışı kesildi" and the loop breaks), WebcamPanel.start/_on_error, and MainWindow.open_settings/apply_settings_values/apply_ui_settings. Nothing skips the index the live worker already holds, and nothing pauses the worker during the scan. Vazgeç calls reject() and nothing restarts the worker. The only restart path is apply_ui_settings -> webcam_panel.start().
I ran two scratch repros under scratchpad\audit\verify-cam\scan\.
(1) bare.py uses bare cv2 DSHOW on index 1 (OBS Virtual Camera). With no second handle it read 60/60 frames. After a second open+release of the same index it read 0/60, and after list_cameras() it also read 0/60. Opening a different index did no harm (60/60).
(2) e2e.py builds the real MainWindow with a rea …

**Kanıt.** The Vazgeç path failed in 5/5 runs. The stream had about 94-107 frames before the scan, only 13-17 frames (ones already in flight) in the 6 s after the dialog, then has_camera=False and worker running=False. The placeholder read 'Kamera akışı kesildi · Kamera izni / bağlantı kontrol edin', and nothing brings the stream back.

The Uygula path recovers only if the worker has already died before the click, because apply_ui_settings -> WebcamPanel.start() returns early while the worker is still running. In one run with an immediate Uygula the stream also stayed dead (15 frames, has_camera False).

A worse result the auditor did not report: in 3 of about 10 runs the whole process died with a native crash during the scan, exit 127. The output was 'Windows fatal exception: access violation' in the worker thread at camera_worker.py:64 (self._cap.read()) while the GUI thread was at cameras.py:96 (cap.release() in list_cameras), followed by 0xc0000374 heap corruption in camera_worker.py:69 release. So on the dev box, a routine click can kill the app mid-lesson and mid-recording, not just the webcam.

The second path (a busy device missing from the scan) comes straight from the code. If `current` is not among the scanned indices, `findData` returns -1, and `setCurrentIndex(0)` at settings_dialog.py:239 silently selects another camera. Uygula then sees v.camera_index != s.camera_index and …

**Düzeltme taslağı.** Never open the device the live worker holds.

1. core/cameras.py `list_cameras`: add a `skip: set[int] = frozenset()` parameter and `continue` for those indices.

2. MainWindow.open_settings: pass the live index to SettingsDialog, e.g. `SettingsDialog(self.settings, self.fam, self, live_index=self.webcam_panel.worker._source.index if self.webcam_panel.has_camera else None)`. A small accessor on WebcamPanel is cleaner than reading `_source`.

3. SettingsDialog._scan_cameras:
- call `list_cameras(skip={live_index})`;
- insert the live camera as its own entry labeled "(kullanımda)" so findData(current) always succeeds;
- if findData still returns -1, keep `current` as an explicit "(bulunamadı)" item instead of falling back to index 0.

An alternative is to pause the webcam (webcam_panel.shutdown()) before the scan and call start() after it. That is simpler, but it blanks the webcam in any running recording for the length of the scan, so the skip approach is better.

### cam#2 · önemli · The app silently shows a different camera than the one selected (stderr-only fallback plus a bare persisted index)

- **Yer:** `src/matematigin_mantigi/ui/camera_worker.py:39`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The lesson is recorded with the wrong camera (for example the laptop's built-in camera instead of the green-screen camera) and nothing tells the teacher. A lost recording is the worst outcome for this app.

**Senaryo.** The saved choice is only an int (settings.py:87-89 'camera/index'), and OpenCvSource.open() tries [index, 0, 1, 2, 3], taking the first one that yields a frame. Case 1: the teacher's chosen external webcam is unplugged, late to enumerate, or failing at launch. The app then opens the FaceTime camera, OBS Virtual Camera or another device instead. The only notice is a print to stderr (line 52), which a packaged .app (console=False) never shows. The panel reports has_camera=True and settings still claims the old index. Case 2: the device set changes between lessons, for example OBS installed or a second camera plugged in. On macOS, OpenCV orders devices by uniqueID, so a new device can sort in front of the chosen one. The stored int then points at a different physical camera and the recording shows the wrong view with no warning. This fallback also defeats open_retries: a camera that fails on the first attempt is never retried, because another index has already won.

**Doğrulama yöntemi.** Read OpenCvSource.open (src/matematigin_mantigi/ui/camera_worker.py:26-59), CameraWorker._open_with_retries/run (:143-190), WebcamPanel._on_opened/_on_error (webcam_panel.py:237-242), MainWindow camera wiring (main_window.py:86-89, 373-377), Settings.camera_index (core/settings.py:87-89), SettingsDialog camera combo and scan (settings_dialog.py:161, 229-240), core/cameras.py, and both PyInstaller specs. Ran a scratch script (scratchpad/audit/verify-cam/fallback/repro.py) with PYTHONPATH=src on the dev box.

**Kanıt.** Reproduced. list_cameras() -> [(1, 'OBS Virtual Camera')]. OpenCvSource(3).open() -> True with actual index 1, and the only notice was the stderr line 'Kamera 3 açılmadı, 1 kullanılıyor' from camera_worker.py:52. Both specs set console=False (mac/matematigin_mantigi.spec:37, windows/matematigin_mantigi_win.spec:38), so a packaged app drops that line. I found no guard anywhere downstream. The worker's `opened` signal carries only (w, h), and WebcamPanel._on_opened just sets has_camera=True. The substituted index (self.index = index at :53) is never sent back to MainWindow or Settings, so settings keeps 'camera/index' = the old value and the settings dialog still shows 'Kamera N (kayıtlı)'. The persisted choice is a bare int, with no device name or uniqueID (settings.py:87-89). main_window.py:86-87 builds the source from that int. On macOS, OpenCV's AVFoundation backend orders devices by uniqueID, so plugging in a new device or installing OBS can move the int onto a different physical camera. The fallback also defeats the retry logic: _open_with_retries (open_retries=15 in main_window.py:89) only retries when open() returns False. So a chosen USB webcam that is slow to enumerate at launch loses right away to index 0 (FaceTime) or another device, and is never retried. One mitigating factor: the live feed shows on the board, so the teacher may notice a clearly different view. But a …

**Düzeltme taslağı.** Smallest fix, in camera_worker.py: in OpenCvSource.open(), remove the silent substitution. Try only self.index by default, so that _open_with_retries keeps retrying the chosen camera and a failure reaches the user through cameraError ('Kamera bulunamadı · ...' placeholder). Keep the scan as an explicit opt-in, for example OpenCvSource(index, fallback=False). If the fallback stays, make it visible. Add a `substituted` attribute to OpenCvSource. Have CameraWorker.run emit a new signal (or a cameraError-style warning) after a successful open where source.index != the requested index. In WebcamPanel, connect it to a persistent overlay such as 'Kamera N yok, M gösteriliyor' via view.set_placeholder or overlay_label. Hardening (optional): store the device name next to the index in core/settings.py (camera/name, taken from CameraInfo.name in SettingsDialog._scan_cameras). At startup in MainWindow, resolve the name back to its current index with core.cameras.list_camera_names, and warn when the name is missing.

### cam#3 · küçük · macOS camera names are paired with the wrong OpenCV indices (ffmpeg order vs OpenCV's uniqueID sort)

- **Yer:** `src/matematigin_mantigi/core/cameras.py:98`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The camera picker's names cannot be trusted on the target machine. The teacher selects the green-screen webcam by name and records with a different camera.

**Senaryo.** list_cameras() labels OpenCV index i with the i-th name from `ffmpeg -f avfoundation -list_devices`. OpenCV's AVFoundation backend (cap_avfoundation_mac.mm, startCaptureDevice) builds its device list and then sorts it by uniqueID (`sortedArrayUsingComparator ... [d1.uniqueID compare:d2.uniqueID]`) before indexing it with cameraNum. FFmpeg's libavdevice/avfoundation.m lists devices in AVCaptureDeviceDiscoverySession order and does not sort them. With two or more cameras (FaceTime HD plus a USB webcam, OBS Virtual Camera, or a Continuity iPhone when exposed), the scan labels can therefore name the wrong device, for example '0: FaceTime HD Camera' when index 0 is actually the USB webcam. The teacher picks by name and gets the other camera. Tests only cover Windows/dshow parsing and a caller-supplied names list, so this pairing is never checked.

**Doğrulama yöntemi.** Read cameras.py and its only caller (settings_dialog.py:229-239 _scan_cameras, which does addItem(cam.label, cam.index)). Fetched upstream OpenCV 4.x cap_avfoundation_mac.mm and FFmpeg master libavdevice/avfoundation.m to check the device-order claim. Installed opencv is 4.13.0 and pyproject needs >=4.8, so the Mac build uses the version that sorts. Wrote a scratch simulation (scratchpad/audit/verify-cam/macorder/sim.py). It feeds real ffmpeg-format avfoundation output through list_camera_names(platform='darwin'), stubs cv2.VideoCapture so index i opens the i-th device in uniqueID order (as OpenCV does), and runs the real list_cameras().

**Kanıt.** Upstream OpenCV startCaptureDevice collects devicesWithMediaType(Video)+(Muxed). It then sorts them with `sortedArrayUsingComparator ... [d1.uniqueID compare:d2.uniqueID]` and runs `mCaptureDevice = devices[cameraNum]`. FFmpeg's getDevicesWithMediaType returns `[captureDeviceDiscoverySession devices]` unsorted and prints `[index]` in that order. The two index spaces are different. cameras.py:98 `name = names[index] if index < len(names) else ""` pairs them as if they were the same, and nothing downstream fixes this: settings_dialog._scan_cameras stores cam.index as the combo data and shows cam.label. Realistic uniqueIDs are "47B4B64B...F4B5" for the Apple Silicon FaceTime camera and "0x14100000046d082d" for a USB UVC webcam (0x + locationID + VID/PID). Because '0' < '4', the USB webcam sorts to OpenCV index 0 while ffmpeg prints FaceTime as [0]. Simulation output:
label: 0: FaceTime HD Camera (1280x720) | actual device opened at this index: HD Pro Webcam C920
label: 1: HD Pro Webcam C920 (1920x1080) | actual device opened at this index: FaceTime HD Camera
The names are swapped, and each name is shown next to the other camera's resolution. The only hardware-dependent assumption is the real uniqueID strings; the ordering logic on both sides is taken from upstream source. Re-rated severity: the wrong choice shows up at once in the live webcam panel after Uygula, before any recordi …

**Düzeltme taslağı.** In src/matematigin_mantigi/core/cameras.py, list_cameras(): on darwin, stop pairing names positionally with OpenCV indices. Smallest fix: when sys.platform == 'darwin', pass name='' so the label becomes 'Kamera N (WxH)'. The resolution still helps tell the cameras apart and nothing is mislabeled. For correct names, get devices with uniqueIDs in OpenCV's order, e.g. via pyobjc AVFoundation: build devicesWithMediaType_(Video)+(Muxed), sort by uniqueID(), and use localizedName() at index i. Add a test that feeds a darwin names list and asserts the names are not paired by ffmpeg position.

### cam#4 · önemli · A camera dropout mid-lesson is permanent: no reconnect, and on macOS a frozen frame for about 31 s first

- **Yer:** `src/matematigin_mantigi/ui/camera_worker.py:171`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** A momentary camera glitch during a recorded lesson freezes the teacher's image for about half a minute, then leaves an error message on the recorded board for the rest of the lesson.

**Senaryo.** The run loop counts consecutive failed read()s and after 31 it emits 'Kamera akışı kesildi' and exits. Nothing ever re-opens the camera: open_retries only covers the initial open, and the panel's _on_error just shows a placeholder. So a USB hiccup, a loose cable or a brief device reset permanently removes the webcam from the board and the recording, even after the camera comes back. On macOS each failed read blocks for OpenCV AVFoundation's 1 s grabFrame timeout. That means about 31 s of a silently frozen last frame of the teacher (has_camera still True, nothing on screen) before the error text appears on the board. The only recovery paths are the layout-edit eye toggle or Settings > Uygula, and neither is signposted.

**Doğrulama yöntemi.** I read CameraWorker.run and _open_with_retries (camera_worker.py:143-191), and in webcam_panel.py I read WebcamPanel._make_worker, start, shutdown, _on_error and set_source_factory. In main_window.py I read the open_retries=15 wiring and the apply_ui_settings start/shutdown path. Then I wrote a scratch repro at C:\Users\bkese\AppData\Local\Temp\claude\C--Users-bkese-Desktop-arayuz-soru-sistemi-metematigin-mantigi\0647ad5c-ac9d-414d-ad34-9375fe87f54d\scratchpad\audit\verify-cam\dropout\repro.py. It builds a real WebcamPanel with open_retries=15, like production, on a fake source. The source gives frames for 1 s, then goes 'unplugged' for 5 s: each read() blocks 0.1 s and returns None, standing in for AVFoundation's grab timeout scaled 10x down. After that it gives frames again. The run lasted 9 s, with QT_QPA_PLATFORM=offscreen and PYTHONPATH=src.

**Kanıt.** Repro output: `error after unplug at [(3.4, 'Kamera akışı kesildi')]` and then `opens 1 running False has_camera False`, even though the source had been producing frames again for 3 s. The error came 3.4 s after the unplug in the scaled run, about 34 s at real speed if each failed read blocks 1 s. source.open() ran exactly once, so nothing tried to reconnect.

Code path:
- camera_worker.py:169-173 counts misses, and at misses > 30 it emits cameraError and breaks out of the loop. The finally block releases the source and the thread ends.
- _open_with_retries (143-156) is only called once, at the top of run().
- WebcamPanel._on_error (webcam_panel.py:240-242) only sets has_camera=False and shows a placeholder. It does not restart anything.
- The only things that start the camera again are apply_ui_settings, i.e. Settings > Uygula or the layout-edit eye toggle (main_window.py:457-459), and set_source_factory when the camera index changes. No retry timer exists anywhere.
- Until the error fires, CameraView keeps painting the last frame, so the recording shows a frozen teacher image.

Two corrections to the claim:
- has_camera is never read anywhere in src (only assigned), so its being True during the freeze has no effect the user can see.
- The ~31 s freeze depends on OpenCV AVFoundation's per-grab timeout (about 1 s in cap_avfoundation_mac.mm) and I could not measure it without a …

**Düzeltme taslağı.** In camera_worker.py CameraWorker.run: when misses > 30, stop breaking out of the loop. Instead emit cameraError("Kamera akışı kesildi") once, call self._source.release(), then go back into self._open_with_retries(). Use an unbounded or long retry count and check self._abort between attempts, so stop() still ends the thread. When a reopen succeeds, reset misses=0 and announced=False so opened is emitted again. In webcam_panel.py WebcamPanel._on_opened, clear the placeholder (self.view.set_placeholder(None) or its equivalent) so the live feed comes back.

To shorten the frozen-frame window on macOS: also emit the error, or show a 'Kamera bekleniyor…' placeholder, after a time limit (for example, no frame for more than 2 s measured with time.monotonic()), instead of only after the fixed count of 31 misses.

Add a test with a fake source that drops out and comes back, and assert that frames resume without calling start() again.

### cam#5 · küçük · Capture resolution is never requested; on macOS the webcam is captured at 480x360 and upscaled into the 2K recording

- **Yer:** `src/matematigin_mantigi/ui/camera_worker.py:46`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The teacher's image in the product recording is visibly soft or blocky next to the sharp 2K board.

**Senaryo.** OpenCvSource never sets CAP_PROP_FRAME_WIDTH/HEIGHT. OpenCV's macOS backend sets `mCaptureSession.sessionPreset = AVCaptureSessionPresetMedium` (480x360 on Mac cameras), and Windows DSHOW defaults to 640x480. CameraWorker also downsizes every frame to out_width=640 (line 103), and set_out_width is never called by anything. In a 2560x1440 recording the default webcam zone is about 640x430 physical px (3/12 x 3/10 of the board), so the camera image is upscaled from 360p. It gets worse if the teacher enlarges the zone. The scan label shows '(480×360)', but nothing in the app lets the teacher change it.

**Doğrulama yöntemi.** I read camera_worker.py (OpenCvSource.open, CameraWorker.run), the one place a worker is built (webcam_panel.py:96 `_make_worker`), CameraView.paintEvent, cameras.list_cameras and recorder.py. Grep found no CAP_PROP_* anywhere in src, and set_out_width has no callers. I pulled the OpenCV 4.x macOS backend source (cap_avfoundation_mac.mm) to check the preset. The scratch script at scratchpad/audit/verify-cam/capres/t.py feeds a fake 1920x1080 FrameSource into a real CameraWorker (offscreen Qt) and records what frameReady emits.

**Kanıt.** 1) Reproduced on the dev box. A fake 1080p source gives `opened 1920 1080`, but every emitted frame is `(640, 360)`. CameraWorker.__init__ defaults out_width=640 (camera_worker.py:103). run() always calls resize_to_width(frame, self._out_width) (line 180). The only constructor call, webcam_panel.py:96, never passes out_width, and nothing calls set_out_width (line 136). So even with a fixed capture resolution, the webcam image is capped at 640 px wide on every platform.
2) OpenCvSource.open (lines 36-59) opens with cv2.VideoCapture(index, backend) and does a test read. It never calls cap.set(CAP_PROP_FRAME_WIDTH/HEIGHT); grep finds no CAP_PROP in src. In OpenCV 4.x cap_avfoundation_mac.mm, startCaptureDevice does `mCaptureSession.sessionPreset = AVCaptureSessionPresetMedium;`, and non-Windows uses CAP_ANY, which is AVFoundation on the Mac. On the Mac the source is therefore Medium-preset, typically 480x360.
3) The panel draws with drawImage and KeepAspectRatio (webcam_panel.py:52-55), which scales up to the zone size. recorder.py:164 scales the grabbed rect to 1440 high. The default webcam zone is PanelGeom(9,7,3,3), 3/12 of the board width, about 600 px in a 2560 output. At the default size a 640-wide frame is roughly 1:1, and a 480x360 Mac frame is upscaled about 1.2-1.25x, so it is slightly soft. The zones can be resized (clamp_free / drag). If the teacher enlarges the webcam …

**Düzeltme taslağı.** (a) camera_worker.py OpenCvSource.open: after cap.isOpened() and before the test read, call cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920) and cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080). On Windows DSHOW also set CAP_PROP_FOURCC to MJPG so 30 fps holds. Apply the same in cameras.list_cameras so the scan label shows the real size. (b) Remove the fixed 640 cap. In WebcamPanel, on resize and at start, call self.worker.set_out_width(int(self.view.width() * self.view.devicePixelRatioF())) so frames are downscaled only to the panel's physical size, never below it. This also keeps the chroma-key cost in proportion to the panel size. Alternatively, raise the default out_width in CameraWorker.__init__ to 1280.

## Düzen ve geometri (`geo`)

### geo#1 · önemli · The capture area is fixed when recording starts, so resizing, moving or fullscreening the window afterwards silently records the wrong part of the screen

- **Yer:** `src/matematigin_mantigi/ui/main_window.py:275`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The recording, which is the product, is wrong from that point on (off-centre crop or captured desktop), and nobody finds out until the video is watched.

**Senaryo.** The teacher starts recording in a normal window and then does any one of these: presses F11 (bound at main_window.py:178 and allowed while recording) or the macOS green fullscreen button; drags or resizes the window; or turns the 16:9 aspect lock off in Settings (apply_ui_settings -> set_aspect_lock). WorkArea.stage_rect() moves or changes size, but the recorder keeps grabbing the rectangle it was given at start. The rest of the lesson records a stale crop: part of the board, the dark side bands or other windows. The output is still a valid 2560x1440 file and no error is raised.

**Doğrulama yöntemi.** I read toggle_recording (main_window.py:272-301), the F11/Escape shortcuts (main_window.py:178, 192-193), apply_ui_settings -> work_area.set_aspect_lock (main_window.py:431, work_area.py:328-333), WorkArea.recording_rect (work_area.py:629-633), and MssFfmpegRecorder.start, _loop and _grab_loop (recorder.py:241-284, 410-440). I checked for any guard: no resizeEvent, moveEvent or changeEvent in MainWindow, and nothing blocks F11, Esc-to-normal or the aspect-lock change while recording. I then ran a pytest probe using the repo's real `window` fixture (MainWindow with NullRecorder, offscreen), saved at C:\Users\bkese\AppData\Local\Temp\claude\C--Users-bkese-Desktop-arayuz-soru-sistemi-metematigin-mantigi\0647ad5c-ac9d-414d-ad34-9375fe87f54d\scratchpad\audit\verify-geo\stale-rect\test_stale.py. It starts recording, then resizes the window, moves it and toggles aspect_lock through apply_ui_set …

**Kanıt.** Probe output:
- At start: RecordRect(x=90, y=83, w=1312, h=738).
- After win.resize(1000,700): the live stage is (98,100,896,504). The recorder still holds (90,83,1312,738) and is_recording is True.
- After win.move(300,200): the live stage is (398,300,896,504).
- After the aspect-lock toggle: the live stage is (390,202,912,700) and is_recording is still True.

In code, toggle_recording reads work_area.recording_rect() only once (main_window.py:275). MssFfmpegRecorder.start freezes grab_rect (recorder.py:248) and passes it by value to the writer thread (recorder.py:283), which passes it on to _grab_loop (recorder.py:440). _grab_loop grabs that same rect every frame (recorder.py:420). The output w and h are also fixed from the first frame (recorder.py:253), so a larger stage is cropped and a smaller one captures other windows or the desktop. No error or status message is produced, and the file is still a valid 2560x1440 MP4.

All of these triggers are reachable in real use while recording: F11 (main_window.py:178), Escape leaving fullscreen (main_window.py:192), the macOS green button or window drag/resize (nothing handles them), and Settings -> aspect lock. The most natural path is pressing R and then F11 or Esc. After that, the rest of the lesson is recorded silently at the wrong crop.

Severity is set to important, not critical, because it only happens after the teacher chang …

**Düzeltme taslağı.** Smallest safe fix, in src/matematigin_mantigi/ui/main_window.py:
(a) While self.recorder.is_recording, make the F11 shortcut and the fullscreen branch of _escape do nothing and show a status message ("Kayıt sürerken pencere boyutu değiştirilemez").
(b) Add resizeEvent, moveEvent and changeEvent (QEvent.WindowStateChange) overrides to MainWindow. Each one compares record_rect_for(self.work_area.recording_rect()) with self.recorder.last_rect while recording. On a mismatch, call self.toggle_recording(False) and show a QMessageBox warning, so the failure is loud instead of silent.
(c) In apply_settings_values, postpone the aspect_lock change while recording.

Better fix, if retargeting is wanted: add MssFfmpegRecorder.retarget(rect) in core/recorder.py. It stores the new grab rect (using physical() on win32) under _latest_lock. _grab_loop reads that rect on every iteration and resizes the frame to the fixed (w, h), for example with cv2.resize, before writing. MainWindow's resize, move and state-change handlers then call retarget.

### geo#2 · küçük · Every relayout() creates and leaks 8 hidden eye buttons (dict.setdefault builds its default argument every time)

- **Yer:** `src/matematigin_mantigi/ui/work_area.py:610`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** Memory keeps growing during a session. Each slider sweep or live window resize adds tens of MB that are never freed, so a long day of lessons, including ones being recorded, runs the app ever larger with a growing risk of slowdown or being killed for memory.

**Senaryo.** `btn = self._eye_buttons.setdefault(key, self._make_eye_button(key))` calls _make_eye_button on every call, even when the key already has a button. Each call creates a styled QPushButton parented to WorkArea that is hidden and never deleted. _sync_eye_buttons runs at the end of every relayout(): every window resize event, every apply_ui_settings (2 relayouts), every eye-button click, every font-slider tick, and recording start and stop.

**Doğrulama yöntemi.** Read work_area.py:540-623 and the relayout call sites. Wrote a scratch probe at C:\Users\bkese\AppData\Local\Temp\claude\C--Users-bkese-Desktop-arayuz-soru-sistemi-metematigin-mantigi\0647ad5c-ac9d-414d-ad34-9375fe87f54d\scratchpad\audit\verify-geo\eyeleak\probe.py. It builds a WorkArea with all ZONE_KEYS zones the same way tests/test_work_area.py does, then counts QPushButton children after repeated relayout() calls and real resize events. Ran it offscreen with PYTHONPATH=src.

**Kanıt.** work_area.py:610 is `btn = self._eye_buttons.setdefault(key, self._make_eye_button(key))`. Python evaluates the default argument before setdefault is called, so _make_eye_button runs on every _place_eye_button call. That function (work_area.py:540-553) builds `QPushButton("👁", self)` parented to WorkArea, sets a stylesheet, hides it and connects a lambda. When the key already exists, setdefault throws the new button away, but the Qt parent keeps it alive, so it is never freed. _sync_eye_buttons (called at line 515, the end of relayout) places one button per zone and per item. Probe output: `dict 8 children 36`, then `after 100 relayout: children 836` (+8 per relayout), then `after 50 resizes: children 1236` (+8 per resize event). So resizeEvent reaches the leak with no guard in between, and relayout is also called from many setters in work_area.py (lines 229, 253, 274, 282, 303, 332, 356, 371, 399) and from main_window.py:285/288. The dict stays at 8 entries, so the real buttons still work and nothing looks wrong to the user: the leak is silent. Re-rated severity: memory grows by about 8 hidden styled widgets (roughly 200 KB) per relayout. In a normal lesson the window is mostly left alone, but a single window drag or a font-slider sweep adds hundreds to thousands of widgets, and the extra siblings make raise_() and child iteration slower. It builds up over a long session. I do …

**Düzeltme taslağı.** In src/matematigin_mantigi/ui/work_area.py, _place_eye_button: replace the setdefault with a lazy create, for example `btn = self._eye_buttons.get(key)` and then `if btn is None: btn = self._eye_buttons[key] = self._make_eye_button(key)`. Add a regression test in tests/test_work_area.py: call relayout() N times and assert that len(wa.findChildren(QPushButton)) does not change.

### geo#3 · küçük · The 'Ctrl: snap to grid' shortcut does not respond to the Control key on the target Mac

- **Yer:** `src/matematigin_mantigi/ui/work_area.py:770`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** On the target machine the documented snap shortcut appears broken. The teacher has to guess that Command is the actual key.

**Senaryo.** The edit bar tells the user 'Ctrl: ızgaraya yapıştır' (work_area.py:191). On macOS, Qt maps the physical Control key to MetaModifier and Command to ControlModifier (the app does not set AA_MacDontSwapCtrlAndMeta). Holding Control while dragging or releasing a zone therefore never matches the ControlModifier checks at lines 724 and 770. The grid does not light up, the zone is saved with free positioning instead of snapping, and on macOS Ctrl+click can additionally be treated as a right click.

**Doğrulama yöntemi.** I read the drag and release handlers in src/matematigin_mantigi/ui/work_area.py (mousePressEvent :705, mouseMoveEvent :714-759, mouseReleaseEvent :761-781) and the edit-bar hint at :191. I searched src/ for AA_MacDontSwapCtrlAndMeta, MetaModifier and any Mac-specific modifier handling and found none. I then wrote a scratch pytest at C:\Users\bkese\AppData\Local\Temp\claude\C--Users-bkese-Desktop-arayuz-soru-sistemi-metematigin-mantigi\0647ad5c-ac9d-414d-ad34-9375fe87f54d\scratchpad\audit\verify-geo\macctrl\test_macctrl.py. It reuses make() and cells() from tests/test_work_area.py, drags the webcam zone off-grid in edit mode, and releases once with ControlModifier (what Cocoa sends for Command) and once with MetaModifier (what Cocoa sends for the physical Control key). The layout it emits shows the difference. My assertion helper used the wrong field names, so the pytest itself reports fa …

**Kanıt.** Scratch run output:
- ControlModifier: PanelGeom(col=7, row=7, col_span=3, row_span=3). Snapped.
- MetaModifier: PanelGeom(col=7.243, row=7.004, col_span=2.997, row_span=2.996). Free position, not snapped.

Code: work_area.py:724 `self._snap_active = bool(e.modifiers() & Qt.KeyboardModifier.ControlModifier)` and :770 `ctrl = bool(e.modifiers() & Qt.KeyboardModifier.ControlModifier)`. Nothing in the app checks MetaModifier. No AA_MacDontSwapCtrlAndMeta is set anywhere in src/, so Qt's standard macOS mapping applies: Command gives ControlModifier and the Control key gives MetaModifier. The label at :191 says "Ctrl: ızgaraya yapıştır".

On the Mac, holding the physical Control key during a drag therefore never lights the grid (:724) and never snaps on release (:770). The zone is saved through lm.free_rect. There is a second effect: Qt's Cocoa plugin turns a Control+left-press into a right-button press. If the teacher holds Control before clicking, mousePressEvent (:706, LeftButton only) starts no drag at all. Only Command snaps.

I could not observe the key mapping on a real Mac. It is documented Qt platform behaviour, and the scratch run shows the app ignores MetaModifier. The existing test tests/test_work_area.py:187 only covers ControlModifier.

Severity: minor. Layout editing happens in edit mode, not during a recording. There is no data loss: the zone is saved in a free posit …

**Düzeltme taslağı.** In src/matematigin_mantigi/ui/work_area.py, add one module-level constant, for example `_SNAP_MOD = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier`. Use it in WorkArea.mouseMoveEvent (:724) and WorkArea.mouseReleaseEvent (:770), so either the Command or the Control key snaps on the Mac. In the edit-bar label (:191), show "⌘/Ctrl" when sys.platform == "darwin". The Control-press-as-right-click issue remains, so the Mac hint should name ⌘ first. Add a test to tests/test_work_area.py that releases with MetaModifier and expects a snapped PanelGeom.

### geo#4 · küçük · Pulling a zone's edge outward past the board edge moves the opposite edge instead

- **Yer:** `src/matematigin_mantigi/ui/work_area.py:749`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The layout editor changes the zone on the side the teacher did not grab, can push panels over each other (ipucu over soru), and saves that result.

**Senaryo.** The default zones touch the board edges: soru is at the top-left, ipucu at the top-right and webcam at the bottom-right. When the user grabs an edge that sits on the board boundary and pulls it slightly outward (a common overshoot), the resize code grows w or h first. The live clamp then shifts x or y back inside the board without shrinking the size, so the opposite edge, which the user did not touch, moves by the overshoot. The result is saved to duzen.json on release.

**Doğrulama yöntemi.** Read WorkArea.mouseMoveEvent/mouseReleaseEvent (src/matematigin_mantigi/ui/work_area.py:714-781) and lm.free_rect/clamp_free. Then wrote a pytest probe at C:\Users\bkese\AppData\Local\Temp\claude\C--Users-bkese-Desktop-arayuz-soru-sistemi-metematigin-mantigi\0647ad5c-ac9d-414d-ad34-9375fe87f54d\scratchpad\audit\verify-geo\edge-overshoot\test_overshoot.py. It reuses tests/test_work_area.make() (1832x1080), checks that _hit() returns the single-edge mode (n/e/s), and drives real press, move and release through qtbot (offscreen, PYTEST_QT_API=pyqt6).

**Kanıt.** Board inner rect (l,t,r,b) = (30,53,1801,1026).

Drags:
- soru, n edge, dy=-30: before (30,53,908,433), live (30,53,908,463), after release (30,53,908,463). The bottom edge moved down 30 px and the top edge did not move.
- ipucu, e edge, dx=+40: before (923,53,1801,433), after (883,53,1801,433). The left edge moved 40 px left and now overlaps soru's right edge at 908.
- webcam, s edge, dy=+50: before (1370,745,1801,1026), after (1370,695,1801,1026). The top edge moved up 50 px.

The layoutChanged payload holds the wrong values, for example soru row_span=4.30 (was 4.0) and ipucu col=5.73, so the bad geometry is persisted.

Cause: for edge modes, lines 729-736 grow w/h first. The zone clamp at 745-750 only caps w/h at the full inner size and then slides x/y back inside the board, so the overshoot moves the edge the user did not grab. free_rect/clamp_free on release does not undo it, because the rect is already inside the board.

The upstream _hit guard does not prevent this: default zones sit flush with the board edges, and the edge handle is reachable with a normal grab.

**Düzeltme taslağı.** In WorkArea.mouseMoveEvent (src/matematigin_mantigi/ui/work_area.py), inside `if key in self._zones:`, clamp resize modes edge by edge instead of sliding the rect. Keep the current slide clamp only for mode == "move". For resize modes, work with the edges:

```python
l, t, r, b = x, y, x + w, y + h
if "w" in mode: l = max(l, inner.left())
if "n" in mode: t = max(t, inner.top())
if "e" in mode: r = min(r, inner.x() + inner.width())
if "s" in mode: b = min(b, inner.y() + inner.height())
x, y, w, h = l, t, r - l, b - t
```

The MIN_FREE_W/H logic that already runs before this keeps the opposite edge anchored. Add a test next to test_edit_mode_resize_from_nw_corner_moves_and_resizes: drag soru's n edge 30 px up and assert that bottom() is unchanged.

### geo#5 · küçük · With the HUD frame, edit mode shows draggable BRAND/PRESENTER boxes for widgets that are hidden

- **Yer:** `src/matematigin_mantigi/ui/work_area.py:694`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The edit mode shows editable targets that do nothing visible, and dragging them quietly moves the brand plate or presenter name for when the Classic frame is used again.

**Senaryo.** With the HUD style and frame_titles on, _apply_chrome hides self.brand and self.name_label because the HUD band draws those texts itself. The overlay (lines 91-101) and _hit (lines 694-698) only check the _visible settings cache, not whether the widget is actually shown. Edit mode therefore draws dashed 'BRAND' and 'PRESENTER' boxes with eye buttons at the hidden plates' positions, and dragging them moves an invisible widget. Nothing on the board changes, yet a new item position is written to duzen.json. That position takes effect later if the style is switched back to Classic.

**Doğrulama yöntemi.** Read WorkArea._apply_chrome (work_area.py:313-326), the overlay paint loop (work_area.py:91-101), _hit (work_area.py:694-698), mousePress/Move/ReleaseEvent (work_area.py:705-781) and FRAME_SPECS (frames.py:275-278; HUD has draws_brand=True, draws_presenter=True). Wrote verify-geo/hud-hidden/repro.py and repro2.py under the scratchpad audit folder. They build a WorkArea with all zones at 1832x1080, set the presenter name, switch to FrameStyle.HUD, turn edit mode on, then send real press/move/release QMouseEvents at the centre of each hidden plate. Afterwards they switch back to CLASSIC and read the positions.

**Kanıt.** The claim holds, and the repro showed one more effect.

The code path has no guard:
- `_apply_chrome` hides `self.brand` and `self.name_label` whenever the HUD style draws those texts and frame_titles is on.
- The overlay (lines 93-96) and `_hit` (lines 695-696) only check the `self._visible` cache, never whether the widget is actually shown.
- `_sync_eye_buttons` also places eye buttons for both plates.

Repro output:
- Brand: `visible False geo (586,27,660,40)`, hit ('brand','move'), eye button visible. After the drag the geometry is (386,177,660,40), `_item_pos` goes from None to ItemPos(0.209,0.146), and layoutChanged is emitted, so the position is saved to duzen.json.
- Presenter: `visible False geo (1459,704,308,28)`, hit ('presenter','move'). After the drag the geometry is (1259,854), `_item_pos` is set, and layoutChanged is emitted again.
- Nothing visible changes on the board during these drags.
- After `set_frame_style(CLASSIC)`, both plates reappear at the dragged positions: brand at (386,177), presenter at (1259,854).

Extra effect (repro2): the invisible brand plate, now at (386,177), sits inside the 'soru' zone. `_hit` at that point returns ('brand','move') instead of a soru move. Items are checked after zones and take priority over zone move and single-edge hits. So in HUD edit mode, an invisible 660x40 strip steals drags meant for the question zone.

Why the sev …

**Düzeltme taslağı.** In src/matematigin_mantigi/ui/work_area.py, add a helper `_item_editable(key)` that returns False when `_visible.get(key, True)` is False, or when key is "brand"/"presenter" and `_chrome_state()` says the active style draws that text (i.e. `(spec.draws_brand if key == "brand" else spec.draws_presenter) and titles_on`). Use it in `WorkArea._hit`'s item loop (skip the item) and in the overlay `paintEvent` item loop (skip the item: no dashed box and no ghost, because the HUD band already shows that text). Keep the eye buttons: the brand/presenter eyes still control the HUD band text via `_visible` (paintEvent line ~797-798). Optionally move each eye button to the band text position. Add a test: after HUD plus edit mode, `_hit(brand.geometry().center())` is None and dragging there leaves `_item_pos` unchanged.

## Paketleme ve platform (`pkg`)

### pkg#1 · önemli · Windows packaged exe: every ffmpeg launch opens a visible console/Terminal window, which stays over the whiteboard for the whole recording

- **Yer:** `src/matematigin_mantigi/core/recorder.py:272`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** On the Windows build, recordings can contain a black terminal window over the board, the window takes focus from the pen UI, and closing it kills the recording. Fix: pass creationflags=subprocess.CREATE_NO_WINDOW on win32 to all four ffmpeg calls.

**Senaryo.** You build with windows/matematigin_mantigi_win.spec (console=False, line 38), so the exe is a GUI-subsystem program. ffmpeg-win-x86_64-v7.1.exe is a console-subsystem program. None of the ffmpeg calls pass creationflags=CREATE_NO_WINDOW or a hidden STARTUPINFO: recorder.py:272 (the recording Popen), :140 (detect_encoder probes, up to 3), :395 (mux) and cameras.py:53 (device list). So Windows gives each ffmpeg its own new console. On Windows 11 that is a Windows Terminal window. When the teacher presses Record, a black terminal window appears on the screen and stays open until the recording stops. mss copies raw screen pixels (BitBlt), so wherever that window covers the whiteboard it goes into the MP4. If the teacher closes the window, ffmpeg is killed and the recording aborts. Up to three more windows flash during encoder detection, and another one appears during the mux at stop.

**Doğrulama yöntemi.** First I read the four subprocess call sites: recorder.py:140 (detect_encoder probe), recorder.py:272 (the recording Popen), recorder.py:395 (the mux at stop) and cameras.py:53 (camera device list). I also read windows/matematigin_mantigi_win.spec, windows/build_win.ps1 and .github/workflows/release.yml. The Windows exe is a real shipped deliverable: release.yml builds and releases it on every push to main, and the spec sets console=False, so the exe is a GUI program. The ffmpeg binary comes from imageio_ffmpeg.get_ffmpeg_exe(), which returns ffmpeg-win-x86_64-v7.1.exe, a console program. None of the calls pass creationflags or STARTUPINFO. Then I wrote my own probe at scratchpad/audit/verify-pkg/console/probe.py and ran it under C:\Python313\pythonw.exe, which is also a GUI program, the same as the packaged exe. It starts ffmpeg exactly the way recorder.py:272 does (Popen with stdin=PIPE …

**Kanıt.** Probe output (verify-pkg/console/out.txt):
  parent=C:\Python313\pythonw.exe exe=...\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe
  flags=0 new_visible={4587894: ('CASCADIA_HOSTING_WINDOW_CLASS', (18, 26, 1147, 661))}
  flags=134217728 new_visible={}
With the flags the code uses today, a visible Windows Terminal window about 1129x635 opens and stays open for as long as ffmpeg runs, which is the whole recording. With CREATE_NO_WINDOW no window appears.
Nothing in the app prevents this. grep finds no creationflags, STARTUPINFO or CREATE_NO_WINDOW anywhere in src/. The app window has no WindowStaysOnTopHint (grep finds only showFullScreen via F11 in main_window.py:178), so the new console comes up in front of the whiteboard and takes focus.
The capture is mss/BitBlt of the screen rect, so any part of the board the console covers goes into the MP4. Closing the console ends ffmpeg, and the recording is lost.
detect_encoder (recorder.py:140), the mux (recorder.py:395) and the camera list (cameras.py:53) use subprocess.run and flash the same kind of window briefly.
Dev runs and the 341 tests miss this because python.exe already has a console and the child ffmpeg reuses it.
The macOS .app, which is the main target, is not affected: macOS has no per-process console windows.

**Düzeltme taslağı.** Add a module-level constant in src/matematigin_mantigi/core/recorder.py: `_NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}`. Pass `**_NO_WINDOW` to four calls:
- subprocess.run in detect_encoder's runner (line 140)
- subprocess.Popen in MssFfmpegRecorder.start (line 272)
- subprocess.run in the mux method (line 395)
- the subprocess.run lambda in core/cameras.py (line 53); import the constant there or define it the same way.
Optionally add a test that monkeypatches sys.platform or checks the constant on win32 and asserts every call receives the flag.

### pkg#2 · önemli · macOS: denied or not-yet-answered mic permission records pure silence, reported as a successful recording (made likely by a fresh ad-hoc signature on every push)

- **Yer:** `src/matematigin_mantigi/core/recorder.py:387`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** A whole lesson can be saved with no voice while the app reports success. This is a silent loss of the product. Fix: check AVCaptureDevice authorizationStatus for audio before recording and/or warn when the WAV peak stays at 0. Longer term, sign with a stable identity so grants survive updates.

**Senaryo.** The .app is ad-hoc signed. The CI log shows 'Code signing identity: None', and release.yml:6-7 publishes a new build on every push to main, even docs/graph-only commits. TCC ties a grant for an ad-hoc app to its cdhash, so after every update the macOS mic grant no longer matches. The mic prompt then appears only when AudioCapture.start opens the PortAudio stream (audio_capture.py:150-152), i.e. after the teacher has pressed Record. While the prompt is open, or permanently if 'Don't Allow' is clicked (or permission was turned off in Settings), CoreAudio still opens the input stream and delivers zero-filled buffers. It raises no error. The only failure check is `audio.samples <= 0` (recorder.py:387), and zeros count as samples. So the mux succeeds, audio_error stays None, and main_window._on_record_stopped (main_window.py:303-324) shows 'Kayıt kaydedildi' with no warning. There is no level or silence check anywhere in src (grep for peak/rms/level/silent finds nothing).

**Doğrulama yöntemi.** Read recorder.py start/_stop_audio/_mux (lines 262-268, 371-387), audio_capture.py start/_callback/stop, and main_window._on_record_stopped (303-324). Grepped src for any level, peak, silence or permission guard and found none. Checked mac/matematigin_mantigi.spec (NSMicrophoneUsageDescription is present, so the prompt appears rather than a crash), release.yml (on: push to main, every push), and the CI log for run 34678489460 ('Code signing identity: None', and no codesign step in build_mac.sh or the workflows). Wrote scratchpad/audit/verify-pkg/silent-mic/repro.py. It runs the REAL AudioCapture and the REAL MssFfmpegRecorder. Only the sounddevice module is swapped for a fake whose InputStream opens without error and calls the callback with int16 zero blocks, which is how a TCC-denied mic looks to a CoreAudio client. Then ran ffprobe and volumedetect on the output.

**Kanıt.** Repro output: 'error None audio_error None samples 140640'. ffprobe shows streams video and audio. volumedetect gives mean_volume -91.0 dB and max_volume -91.0 dB, which is digital silence. The temp .wav and .video.mp4 were deleted after the mux, so nothing raw is left to recover. In recorder.py:387 the only audio failure check is `audio.samples <= 0 or not audio.path.exists()`, and zero-valued samples pass it. In main_window.py:315-324, when audio_error is None the status line reads 'Kayıt kaydedildi: …' with no 'UYARI', and no QMessageBox is shown. So the app-side path is fully traced and reproduced, with no guard anywhere. The Mac side (a denied or pending TCC mic delivers zero buffers with no PortAudio error, and each ad-hoc rebuild changes the cdhash so the earlier grant no longer matches) is documented macOS behavior and fits the unsigned CI build, but I could not observe it on this Windows box. The prompt is also first triggered only inside AudioCapture.start, after Record is pressed (audio_capture.py:150-152). So even on a fresh install the teacher sees the TCC dialog mid-start. Clicking 'Don't Allow' there, or dismissing it late, gives a silent lesson that is reported as a success. What would settle the Mac half: on a Mac, turn the app's mic permission off in System Settings > Privacy > Microphone, record 10 s, and run volumedetect. max_volume of -91 dB with no warning …

**Düzeltme taslağı.** 1) core/audio_capture.py AudioCapture: track peak in _callback (`self.peak = max(self.peak, int(np.abs(indata).max()))`, updated cheaply per block) and add `peak: int = 0` to AudioResult, filled in stop(). 2) core/recorder.py MssFfmpegRecorder._stop_audio (or _mux): if audio_result.peak == 0 (or below a very small threshold such as 8/32767 over the whole take), set self.audio_error = "Mikrofon hiç ses almadı (macOS mikrofon izni kapalı olabilir: Sistem Ayarları > Gizlilik > Mikrofon)". Keep muxing so the file stays valid. 3) ui/main_window.py _on_record_stopped: when audio_err is set, show a QMessageBox.warning instead of only appending to the status line. Better still, during recording let _check_recorder poll the live peak after about 3 s and flash the badge or a warning while the lesson can still be saved. 4) Optional, on macOS: trigger the mic prompt at app launch (open and close a short sd.InputStream, or call AVCaptureDevice.requestAccessForMediaType_ via pyobjc) so the TCC dialog never appears after Record is pressed. Longer term, sign the app with a stable Developer ID in mac.yml/release.yml so grants survive updates.

### pkg#3 · küçük · macOS: denying 'access to Documents folder' makes the .app exit silently at every launch

- **Yer:** `src/matematigin_mantigi/app.py:42`
- **Doğrulama:** confirmed (yeniden üretildi: True)
- **Öğretmene etkisi:** The app never opens and gives no reason. Catch OSError in ensure_user_data/build_window and show a QMessageBox, or fall back to ~/Library/Application Support or ~/Movies, which are not TCC-protected.

**Senaryo.** In the frozen app, data_dir() is ~/Documents/Matematiğin Mantığı (paths.py:30). ~/Documents is TCC-protected, so the first Finder launch (and, with ad-hoc signing, the first launch after each new build) shows 'would like to access files in your Documents folder'. If the teacher clicks 'Don't Allow', ensure_user_data() -> target.mkdir() (paths.py:37) raises PermissionError(EPERM). Nothing around build_window() or main() catches it, and no excepthook or log file is installed. The windowed (console=False) PyInstaller app on macOS just exits with no dialog. TCC remembers the denial, so every later launch does the same until the user finds the toggle in System Settings > Privacy > Files and Folders.

**Doğrulama yöntemi.** I read paths.py, app.py (build_window/main), __main__.py and mac/matematigin_mantigi.spec, and grepped src for any guard. Then I ran a scratch script at C:\Users\bkese\AppData\Local\Temp\claude\C--Users-bkese-Desktop-arayuz-soru-sistemi-metematigin-mantigi\0647ad5c-ac9d-414d-ad34-9375fe87f54d\scratchpad\audit\verify-pkg\docs-denied\repro.py. It sets sys.frozen=True, points Path.home at a scratch folder and makes mkdir under Documents raise PermissionError(EPERM), which is what TCC returns after 'Don't Allow'. It then calls the real app.main(["x","--kamera-yok"]) under the offscreen Qt platform.

**Kanıt.** The script prints: 'UNCAUGHT from main -> PermissionError [Errno 1] Operation not permitted: ...\home\Documents\Matematiğin Mantığı'. The exception escapes app.main() before win.show().

Nothing on the path catches it:
- paths.py:30 sets data_dir() to Path.home()/"Documents"/APP_FOLDER_NAME when frozen.
- paths.py:37 calls target.mkdir(parents=True, exist_ok=True) with no try.
- app.py:42 calls paths.ensure_user_data() inside build_window with no try.
- app.py:79 calls build_window with no try in main.
- __main__.py is just sys.exit(main(sys.argv)).

grep finds no sys.excepthook, faulthandler or log file anywhere in src. mac/matematigin_mantigi.spec:37 sets console=False, so stderr goes nowhere visible. PyInstaller's windowed bootloader on macOS shows no error dialog for an unhandled exception (only the Windows bootloader does), so the Dock icon bounces and the app quits.

The spec's info_plist has no NSDocumentsFolderUsageDescription. That doesn't matter much, because the Documents prompt appears without it. What matters is that TCC remembers a denial, so the app fails the same way on every later launch until the teacher finds System Settings > Privacy & Security > Files and Folders. Ad-hoc signed rebuilds can prompt again, so the path comes back after new builds.

The whole path runs in the real .app launched from Finder; I simulated only the TCC denial itself.

Severity is m …

**Düzeltme taslağı.** Change app.build_window (src/matematigin_mantigi/app.py:41-42) to wrap paths.ensure_user_data() in `try: ... except OSError as err:`. In the except branch, show QMessageBox.critical saying the Documents folder is not accessible and naming System Settings > Privacy & Security > Files and Folders > Matematiğin Mantığı > Documents. Then either return a non-zero exit from main, or fall back to a non-TCC folder: have paths.data_dir() use ~/Library/Application Support/Matematiğin Mantığı and use that for the rest of the session. Optionally, add a sys.excepthook in main() that shows a QMessageBox with the traceback, so no other startup exception in the windowed .app is silent either. Also add "NSDocumentsFolderUsageDescription" to info_plist in mac/matematigin_mantigi.spec so the prompt explains why the app needs Documents access.

### pkg#4 · küçük · The release notes' Gatekeeper instruction ('sağ tık > Aç') no longer works on current macOS

- **Yer:** `.github/workflows/release.yml:69`
- **Doğrulama:** confirmed (yeniden üretildi: False)
- **Öğretmene etkisi:** On first install from a release, the documented path fails and the teacher is stuck unless they know the Settings or xattr route. Update the body to 'Sistem Ayarları > Gizlilik ve Güvenlik > Yine de Aç' plus the xattr command.

**Senaryo.** The release zip holds an ad-hoc-signed, non-notarized app. When it is downloaded in a browser it gets the quarantine flag. Since macOS 15 Sequoia, Apple removed the Control-click > Open override for such apps. The dialog offers only 'Done' / 'Move to Trash', and the user must go to System Settings > Privacy & Security > 'Open Anyway' (or run xattr -dr com.apple.quarantine). The release body tells the owner only to right-click > Open. The xattr alternative appears only in the build_mac.sh echo (line 39), which a downloader never sees.

**Doğrulama yöntemi.** I read .github/workflows/release.yml (release body, zip step), mac/build_mac.sh and the README's install and permissions sections, and grepped the repo for every Gatekeeper/quarantine instruction. I also checked the macOS CI log for run 34678489460 to see how the app is signed. I checked the path end to end against Apple's documented macOS 15 Gatekeeper change. I could not run it on a real Mac.

**Kanıt.** - release.yml:69 is the only install text on the release page: "aç, .app'i Uygulamalar'a taşı (imzasız: sağ tık > Aç)". It gives no Settings path and no xattr command.
- The CI log shows the app is built on macos-14-arm64 with PyInstaller reporting "Code signing identity: None". So the app is ad-hoc/linker-signed only, and no notarization step exists anywhere in release.yml or mac.yml.
- release.yml:47 zips with ditto. A browser download of that zip gets com.apple.quarantine, and Archive Utility copies the flag onto the unzipped .app.
- Apple's macOS 15 Sequoia note (Aug 2024): users can no longer Control-click to override Gatekeeper for software that is not correctly signed or notarized. They must go to System Settings > Privacy & Security > Open Anyway.
- So on 15.x or 26.x the documented right-click > Aç path gives no Open button.
- The fallbacks exist but are hard to find:
  - build_mac.sh:39 only echoes during a local build.
  - README:95 is in the build-from-source section.
  - README:112 is under "if the permission dialog never appears".
  - README:129, in the Release section itself, repeats only "sağ tık > Aç".
- Two things weaken the claim:
  - It depends on the teacher's Mac running macOS 15 or later. That is very likely for an Apple Silicon MacBook Pro in 2026, but I have not verified it.
  - If the owner fetches builds with `gh run download` or `gh release download` …

**Düzeltme taslağı.** Edit the release body in .github/workflows/release.yml (job `release`, step "Yayınla", line 69) so the macOS line reads roughly: "macOS: zip'i aç, .app'i Uygulamalar'a taşı. İlk açılışta engellenirse: Sistem Ayarları > Gizlilik ve Güvenlik > 'Yine de Aç' (macOS 15+), ya da Terminal'de: xattr -dr com.apple.quarantine \"/Applications/Matematiğin Mantığı.app\"". Update the same instruction in README.md:95 and :129 and in the mac/build_mac.sh:39 echo. The only real fix, removing the prompt altogether, is Developer ID signing plus notarytool notarization in the macos job. That needs a paid Apple account, which is out of scope.

### pkg#5 · küçük · Info.plist claims macOS 12.0 minimum, but the bundled wheels need macOS 13/14

- **Yer:** `mac/matematigin_mantigi.spec:51`
- **Doğrulama:** confirmed (yeniden üretildi: False)
- **Öğretmene etkisi:** Only matters if the teacher's Mac is not updated. It shows up as a silent launch failure instead of macOS's clear 'requires macOS 14' message. Set LSMinimumSystemVersion to 14.0 (or pin wheels).

**Senaryo.** LSMinimumSystemVersion is '12.0', so Finder lets the app launch on macOS 12/13. The CI build (run 34678489460) collected numpy-2.5.3-cp312-cp312-macosx_14_0_arm64.whl (Accelerate NEWLAPACK build) and opencv_python-5.0.0.93-...-macosx_13_0_arm64.whl. On macOS 12 (and likely early 13), importing numpy/cv2 fails at load time. With console=False there is no error UI, so the app bounces and quits.

**Doğrulama yöntemi.** Read mac/matematigin_mantigi.spec, mac/build_mac.sh, .github/workflows/release.yml and mac.yml, src/matematigin_mantigi/__main__.py and app.py imports. Grepped the real CI log (`gh run view 34678489460 --log`, macos job) for the wheels it installed. Queried the PyPI JSON API (metadata only, nothing downloaded) for the macOS arm64 wheels published for numpy 2.5.3, opencv-python 5.0.0.93 and PyQt6-Qt6 6.11.2. I could not run the app on macOS 12 or 13 because that needs a real Mac.

**Kanıt.** 1) mac/matematigin_mantigi.spec:51 sets "LSMinimumSystemVersion": "12.0". README.md:133 also says "macOS 12+". So Finder/LaunchServices will open the app on Monterey and Ventura without the usual "requires a newer macOS" block.
2) Both release.yml and mac.yml build on runs-on: macos-14 with setup-python 3.12 via mac/build_mac.sh. That script runs pip install -e .[dev,pdf] with no pins and no MACOSX_DEPLOYMENT_TARGET or --platform control. The CI log of run 34678489460 (macos job) shows "Successfully installed ... numpy-2.5.3 opencv-python-5.0.0.93 ..." from numpy-2.5.3-cp312-cp312-macosx_14_0_arm64.whl and opencv_python-5.0.0.93-cp37-abi3-macosx_13_0_arm64.whl. PyInstaller bundles those binaries as they are.
3) PyPI lists two arm64 cp312 wheels for numpy 2.5.3: macosx_11_0_arm64 (OpenBLAS) and macosx_14_0_arm64. The runner is on macOS 14, so pip picks the 14_0 wheel. That is numpy's Accelerate/NEWLAPACK build, and numpy documents it as macOS >= 14 only. opencv-python 5.0.0.93 ships only a macosx_13_0 arm64 wheel, so its floor is 13 even before numpy is considered.
4) The import path has no guard. __main__.py imports matematigin_mantigi.app. app.py:14 imports core.recorder, which runs `import numpy as np` at recorder.py:20. app.py:18 imports ui.camera_worker, which runs `import cv2` / numpy at lines 10-11. All of this happens at module import time, before main() and before any Q …

**Düzeltme taslağı.** In mac/matematigin_mantigi.spec, BUNDLE(info_plist=...), change "LSMinimumSystemVersion" from "12.0" to "14.0" so it matches the numpy macosx_14_0 wheel the macos-14 runner actually bundles. macOS then shows its own "requires macOS 14" message instead of a silent bounce. Change README.md:133 from "macOS 12+" to "macOS 14+" to match. The alternative, if older macOS matters: in mac/build_mac.sh, force the OpenBLAS numpy wheel (for example pip install --only-binary=:all: --platform macosx_11_0_arm64 numpy) and set LSMinimumSystemVersion to 13.0 because of opencv-python 5.x. The version bump is the smaller, correct fix.

## Eleştirmenin bulduğu boşluklar (ikinci tur için)

### Screen capture failing partway through a recording (the video freezes silently)

No auditor tested a grabber that starts failing after recording has begun. _grab_loop (recorder.py:419-423) swallows every exception forever: `except Exception: time.sleep(0.005); continue`. The writer then keeps writing the last good frame, `failed` and `error` stay unset, and _check_recorder (main_window.py:326-329) only looks at `failed`, so the badge keeps counting and the final status says 'Kayıt kaydedildi'. I demonstrated this in scratchpad/audit/critic/grab_fail.py: the grabber raises after 1 s, recording runs 4 s. Result: failed=False, error=None, 121 frames written, only 30 grabbed, and the file is 3/4 frozen frame with no warning. A real trigger showed up while I worked: with this Windows session locked, mss BitBlt raises 'Windows graphics function failed: BitBlt' for any rect. At start() that error is loud (recorder.py:249-252); mid-recording it is silent. Triggers to confirm in round 2: Windows lock screen or UAC secure desktop, and on macOS display sleep, screen lock, fast user switch, or Screen Recording permission being revoked. Also decide the fix: count consecutive failures, or check for stale frames.

Dosyalar: `src/matematigin_mantigi/core/recorder.py`, `src/matematigin_mantigi/ui/main_window.py`

### MP4 finalisation is fragile and there is no disk-space check or crash recovery (a hard stop loses the whole lesson)

The video ffmpeg writes a non-fragmented MP4 with +faststart (recorder.py:161-166), so the moov index is only written at a clean exit. I demonstrated that a hard-killed ffmpeg leaves a file that ffprobe rejects with 'moov atom not found' (scratchpad/audit/critic/killed.mp4). The recorder can cause this itself: _stop_locked calls proc.communicate(timeout=60) and then proc.kill() (recorder.py:310-313). The +faststart pass moves the whole file after encoding, so on a long lesson or a slow or nearly-full disk a kill during that pass corrupts the recording. Other paths nobody examined: disk full mid-lesson (ffmpeg dies, the pipe breaks, the teacher is told, but everything recorded so far is unplayable and _mux then fails on it), power or battery loss, and kernel panic. start() never checks free space (recorder.py:254-259), although at about 7 GB/h (videotoolbox at 16M) the mux needs roughly twice that. The data folder is ~/Documents, which is often iCloud-synced on Macs. No launch-time recovery exists for orphaned kayit_*.video.mp4 and .wav pairs left by the abort paths other auditors found. NOTE: to kill the demo ffmpeg I ran `taskkill /F /IM ffmpeg.exe`. It also terminated a second ffmpeg.exe (PID 24472 or 43144) that was not mine, at about 12:12. If a parallel audit's recording test failed then, this is the cause.

Dosyalar: `src/matematigin_mantigi/core/recorder.py`, `src/matematigin_mantigi/paths.py`, `src/matematigin_mantigi/app.py`

### Wrong or missing audio source with no warning: fresh-install default, and fallback when the saved mic is missing

The packaging auditor passed this to the recorder auditor, who never reported it. The default record/audio_device is '' (settings.py:151), so recorder.py:258 records video only and sets no audio_error. On a fresh install, the whole first lesson records with no audio track, and neither start nor stop warns. The status line only says 'Kayıt kaydedildi' (main_window.py:302-324). The Mikrofon combo lists devices only after 'Ses aygıtlarını listele' is pressed (settings_dialog.py:144-148, 216-225). When the saved mic, such as a USB lavalier, is unplugged or renamed, AudioCapture._pick_device (audio_capture.py:143-160) quietly falls back to the PortAudio default, usually the laptop's built-in mic, and sets no audio_error. The teacher believes the lavalier recorded. This is the same pattern as the confirmed camera fallback, but on the audio side, which nobody owned. Side note: on this dev box, PortAudio exposes input devices only through WDM-KS, the lowest-ranked host API.

Dosyalar: `src/matematigin_mantigi/core/settings.py`, `src/matematigin_mantigi/core/audio_capture.py`, `src/matematigin_mantigi/core/recorder.py`, `src/matematigin_mantigi/ui/settings_dialog.py`, `src/matematigin_mantigi/ui/main_window.py`

### System or display sleep and suspend during a recording

Nothing prevents idle display sleep or system sleep while recording. There is no IOPMAssertion, caffeinate or SetThreadExecutionState anywhere in src/ or mac/. Under the default '(ses yok)' setting, no CoreAudio I/O runs either, so nothing incidentally holds the system awake. MacBook defaults turn the display off after a few minutes without input, which can happen while the teacher talks to the camera without touching the pen. Nobody examined what CGWindowListCreateImage or BitBlt return for a sleeping or locked display (see the frozen-frame gap), or what happens across a suspend. After a suspend, the writer's catch-up (`due = int((now - t0) * fps) - frames_written`, recorder.py:448-449) writes the whole sleep duration as duplicate frames in one burst if monotonic time counts sleep, while the PortAudio stream either has a gap or dies. That shifts A/V alignment after the gap, and the mux's `-shortest` then truncates. This needs a real-hardware check and a decision on sleep inhibition while recording.

Dosyalar: `src/matematigin_mantigi/core/recorder.py`, `src/matematigin_mantigi/core/audio_capture.py`, `src/matematigin_mantigi/ui/main_window.py`

### Webcam lip-sync inside the recording (a cross-subsystem seam nobody owned)

Audio is aligned to the writer's screen-capture clock (video_t0 against first_sample_monotonic, recorder.py:391-393). The teacher's face, however, reaches the recorded pixels only after camera sensor and driver latency, OpenCV buffering, CameraWorker's read → resize → chroma (12-19 ms) → sleep-to-period loop (camera_worker.py:163-189), a queued Qt signal, a widget paint, and then the mss grab. Nothing compensates for that pipeline, and no auditor measured it. The recorder auditor explicitly skipped A/V offset accuracy, and the webcam auditor skipped how the recorder captures the webcam region. Audio leading video by more than about 100 ms is noticeable on a talking head. Round 2 could timestamp synthetic camera frames to quantify the in-app part on the dev box (OBS Virtual Camera, U850 mic), and ideally run a clapper test.

Dosyalar: `src/matematigin_mantigi/ui/camera_worker.py`, `src/matematigin_mantigi/ui/webcam_panel.py`, `src/matematigin_mantigi/core/recorder.py`

### What actually ends up in the recorded frame

Nobody inspected recorded frames for content other than the board. The recording is a raw screen grab of the board rect, so anything drawn over it is recorded. That includes the question editor dialog, which shows correct answers and all hints and can be opened mid-recording (open_editor has no is_recording guard), the Settings dialog, QMessageBox warnings, macOS notification banners, the macOS 15 screen-capture privacy reminder, and the menu bar and title bar that slide in at the top edge in native macOS fullscreen. Conversely, neither mss backend captures the mouse or pen cursor (BitBlt without cursor compositing, CGWindowListCreateImage), so where the teacher hovers or points with the pen tool cursor (cursors.py) never appears in the video. Round 2 should record a short session with the real app (needs an unlocked desktop) and check the frames. It should also decide whether the editor and settings should be blocked or warned about while recording.

Dosyalar: `src/matematigin_mantigi/ui/main_window.py`, `src/matematigin_mantigi/core/recorder.py`, `src/matematigin_mantigi/ui/question_editor.py`, `src/matematigin_mantigi/ui/cursors.py`

### macOS target: questions every auditor deferred, plus F11

Every subsystem left the same Mac questions open, and they add up to the product's main risk. (1) Whether imageio-ffmpeg's arm64 binary has h264_videotoolbox. If not, detect_encoder falls back to libx264 ultrafast at 1440p60. The writer-backpressure test (find-rec/behind.py) ran only on Windows. If encode throughput E stays below 60 fps, frames_written grows at E per second, the video comes out shorter than wall time, and A/V drift grows linearly (T*(1-E/60)); `-shortest` then trims the audio. The status line would show only capture fps. (2) Whether TCC prompts for Screen Recording, mic, Documents and camera appear over the board during the first recording. (3) Whether Cmd+Q runs closeEvent. (4) Native fullscreen. The only fullscreen shortcut, F11 (main_window.py:178, README 'F11 tam ekran'), is taken by macOS's default 'Show Desktop' binding on Mac keyboards, so on the target the teacher can reach fullscreen only with the green button, which interacts with the confirmed fixed-record-rect bug. (5) XP-Pen behaviour. Round 2 without a Mac could read the CI macOS job log (gh run view --log) for encoder and dylib evidence, and write a precise on-Mac checklist for Barış.

Dosyalar: `src/matematigin_mantigi/core/recorder.py`, `src/matematigin_mantigi/ui/main_window.py`, `mac/matematigin_mantigi.spec`, `.github/workflows/mac.yml`, `README.md`

### Full-length (30-60 min) recording with the real app

Every recorder run in this audit lasted seconds to a few minutes and used fakes or offscreen Qt. Nobody has recorded a lesson-length session with the real app. Mic clock drift (the 100 ppm floor in audio_rate_correction) is unmeasured, as are memory growth (30 full-board undo copies at about 20 MB each at dpr 2; 8 leaked eye buttons per relayout, which runs on every record start and stop), stop and mux time against the 60 s ffmpeg kill and the 60 s closeEvent wait on a real 60-minute file, and whether the output plays with correct A/V at the end. This can be run on the dev box. Caveat: the Windows session is currently locked, and mss BitBlt fails for every rect until it is unlocked, so round 2 must run it while the desktop is unlocked. I measured GUI-thread wake-up jitter under a 2400x1350 at 60 fps recorder load: p99 about 7.5 ms, max 9 ms, which is acceptable, so ink latency from GIL contention is not a gap.

Dosyalar: `src/matematigin_mantigi/core/recorder.py`, `src/matematigin_mantigi/core/audio_capture.py`, `src/matematigin_mantigi/ui/canvas.py`, `src/matematigin_mantigi/ui/work_area.py`, `src/matematigin_mantigi/ui/main_window.py`

## Kıdemli inceleme (tüm depo, f1d586f) — tam metin

### Review of "Matematiğin Mantığı" at f1d586f

**Scope and method.** I read every module under `src/`, the packaging specs, both workflows, the README and the plan, and skimmed the test suite. I did the review myself, in passes: recording path, UI/interaction, editor/persistence, packaging, then tests. The suite passes: **340 passed, 1 skipped**. The skip is `test_grab_screen_returns_bgra`, because BitBlt fails in a non-interactive session.

I confirmed the main defects with throwaway scripts in `scratchpad/review/`. The checkout was not modified. Code paths below are relative to `C:\Users\bkese\Desktop\arayuz-soru-sistemi-metematigin-mantigi\src\matematigin_mantigi\`.

#### Strengths

- **Recorder design.** Capture and writing run on separate threads, and the writer duplicates frames to keep pace with the wall clock, so video length always equals real time. ffmpeg's stderr goes to a log file, so a full pipe cannot hang it. The ffmpeg input queue is small on purpose. Hardware encoders are probed with a real 2-frame encode before use, with libx264 as the fallback.
- **Audio design.** Microphone capture runs in-process through PortAudio with a deep queue. The time of the first sample is measured using the ADC timestamp, and clock drift is corrected only when it is clearly measurable. `wave` rewrites the WAV header on every write, so the WAV survives a crash. If the app dies, ffmpeg gets end-of-input and finishes the video file.
- **Real integration tests.** The recorder tests drive the real ffmpeg, and one checks that audio and video durations match within 150 ms. The recording and mux tests through the main window cover the async stop path when everything goes right.
- **Exact 16:9.** `stage_rect()` (`ui/work_area.py:440-459`) builds the stage in 32×18 steps and aligns it to the screen-scale denominator. That guarantees an exact 16:9 image with even pixel sizes at 100/125/150/175/200% scaling. This is better than the plan's rounding approach, and the comment explains why.
- **Old layouts keep loading.** `from_json` converts values to float, and loading applies no pixel minimum, so old `duzen.json` files with integer cells still work.
- **Webcam thread handling.** Worker retire/reclaim with a cap on pending workers handles a wedged camera driver carefully.
- **Pen click fix.** The fix for pen clicks in the Tıkla tool is correct and tested with real `QTabletEvent`s.
- **Toolbar tiers.** Tier thresholds were measured rather than guessed, and the record button stays outside the scroll area.

#### Issues

#### Critical (must fix)

**1. A microphone dropout silently cuts the lesson video short and deletes the full-length original.**
- Where: `core/recorder.py:184` (`-shortest`) and `core/recorder.py:400-408`.
- What happens: the mux ends at whichever stream is shorter. Success is judged only by `returncode == 0 and out.exists()`, and then the full-length `.video.mp4` is deleted.
- Demo (`demo_short_audio.py`): 4.0 s recorded, the audio stops after 1 s. The final file is **0.95 s long**, `error=None`, `audio_error=None`, the intermediate is deleted, and the status line says "Kayıt kaydedildi".
- Triggers: a USB or Bluetooth microphone unplugged or dropping out, the PortAudio stream stopping, the WAV writer thread dying on a disk error, or queue drops.
- Why it matters: a mic dropout at minute 20 of a 60-minute lesson leaves 20 minutes of video and permanently deletes the other 40, with no warning.
- Fix:
  - Pad the audio: add `apad` to the `-af` chain so `-shortest` ends on the video.
  - Delete the intermediates only after checking that the muxed duration is close to the video duration.
  - Warn when `audio_result.duration` is much shorter than `last_duration`.

**2. Pressing R while a recording is still finalizing starts a new one on shared state, so the first recording is never muxed.**
- Where: `ui/main_window.py:172` (R shortcut), `ui/main_window.py:293`, `core/recorder.py:241-284` and `core/recorder.py:301` / `core/recorder.py:314-318`.
- What happens: during stop, the toolbar button is disabled, but the R shortcut is not. `_stop_locked` sets `started_at=None` before the slow ffmpeg finalize and mux, so `start()` passes its `is_recording` check. It then overwrites `_video_path`, `last_path`, `_log_file`, `audio_error` and `video_t0` while the first stop is still using them.
- Demo (`demo_recorder_race.py`, Windows):
  - The second `start()` is accepted.
  - The first stop tries to mux the *second* recording's in-progress `.video.mp4` ("moov atom not found").
  - `video.replace(out)` then raises `PermissionError`.
  - The first recording's final `.mp4` is never produced; its `.video.mp4` and `.wav` are left orphaned.
  - The second stop reports a stale `audio_error`.
  - In the UI, `_on_record_stopped` would show "Kayıt hatası" and set the toolbar to "not recording" while recording #2 is running.
- On macOS (inferred, I could not run it there): the rename succeeds underneath the running ffmpeg. The `+faststart` second pass reopens the output by name, so recording #2 would most likely finish without a moov atom, meaning it would be unplayable too.
- Why it's realistic: for a 60-minute lesson the finalize and mux rewrite several GB and take many seconds, and "stop, then start the next segment" is a natural workflow.
- Fix: give the recorder an explicit IDLE → RECORDING → FINALIZING state held under a lock. `start()` must refuse to start (loudly) while FINALIZING. Guard the R shortcut the same way as the button. Snapshot the per-recording paths into locals at the start of `_stop_locked`.

#### Important (should fix)

**3. Any exception in a Qt slot kills the whole app mid-lesson.**
- Where: no `sys.excepthook` is installed anywhere (`app.py`), and PyQt6 aborts on an unhandled exception in a slot.
- Demo (`demo_slot_abort.py`): with the xlsx locked the way Excel locks it on Windows, pressing Kaydet in the editor ends the process with exit code 0xC0000409.
- Other unguarded slot paths:
  - `ui/question_editor.py:310` and `ui/question_editor.py:250` (file writes and copies).
  - `core/session_store.py:32-33`, which raises deliberately and is reached on every N via `ui/main_window.py:236`.
  - `ui/main_window.py:127` (`save_layout`).
  - `ui/main_window.py:278`, which catches only `RecorderError`, so a `mkdir` `OSError` escapes.
  - `ui/camera_worker.py:165-191`, where `run()` has no guard, so an OpenCV error on an odd frame would abort.
- Fix: install an excepthook that logs to a file in the data folder and shows a non-modal warning instead of aborting. Wrap the file-writing slots.

**4. Capture failures are swallowed forever, so the video can freeze silently.**
- Where: `core/recorder.py:419-423`.
- Demo (second half of `demo_recorder_race.py`): the grabber dies after 5 frames. Recording continues on a frozen frame with `error=None` and `failed=False`. The only hint is "yakalama ~3 kare/sn" in the status line after stop.
- Fix: count consecutive failures, and after about 2 s set `failed`/`error` so `_check_recorder` stops the recording loudly.

**5. The capture rectangle is fixed at start, so one keystroke can make the rest of the lesson record the wrong area.**
- Where: `ui/main_window.py:275` fixes the rectangle. `ui/main_window.py:178` (F11) and `ui/main_window.py:187-193` (Esc → `showNormal()`) are unguarded, and so are window moves/resizes and the aspect-lock setting.
- Why it matters: Esc is a reflex key. In full screen it silently misaligns the capture for the rest of the lesson.
- Fix: block the full-screen toggles and aspect-lock changes while recording, or watch move/resize/screen changes and warn loudly (or move the capture rectangle; the output size can stay fixed). Also check at record start that the stage is fully on one screen; `app.py:53` always opens a 1920×1080 window, which is larger than the MacBook screen.

**6. Microphone selection can silently use the wrong or a silent device.**
- `_pick_device` (`core/audio_capture.py:154-171`) quietly falls back to the default input when the saved name isn't found.
- PortAudio's device list is cached when the library loads, so a mic plugged in after launch is never found and is never listed by "Ses aygıtlarını listele". The recording then uses the internal mic.
- There is no level check. On macOS, a denied microphone permission gives an all-zero track with no warning (expected macOS behaviour, not tested here).
- Fix: re-initialise PortAudio before listing or resolving devices. Store the device actually opened in `AudioResult` and show it. Warn on silent audio, and on stalled sample growth during recording.

**7. After saving in the question editor, question images disappear from the board in the packaged app.**
- Where: `ui/question_editor.py:210` and `ui/question_editor.py:225` emit relative `sorular_gorsel/...` paths. `ui/question_zone.py:177` resolves them against the process's current directory, which is `/` for a Finder-launched `.app`.
- Demo (`demo_editor_image.py`): the image is shown before Kaydet and hidden after it.
- It passes in development only because the current directory there is the xlsx folder.
- Fix: resolve relative to `questions_path.parent` before emitting `saved`, the same way `load_questions` does.

**8. Every layout pass creates 8 layout-editor eye buttons that are never deleted.**
- Where: `ui/work_area.py:610`. `dict.setdefault(key, self._make_eye_button(key))` evaluates the factory every time, and each button is parented to WorkArea.
- Demo (`demo_eye_leak.py`): 66 buttons after startup with only 8 tracked, 1,666 after 200 resizes, 3,122 after one sweep of the font slider.
- Impact: CPU cost is modest (0.8 ms → 1.8 ms per layout pass at 37k children), but growth is unbounded.
- Fix: create the button only if the key is missing.

**9. The intermediate video is not crash-resistant, and it is rewritten for nothing.**
- Where: `core/recorder.py:166`. `.video.mp4` is a plain MP4 whose index (moov) is written only at the end, so a power loss or killed ffmpeg loses the whole lesson.
- `+faststart` on that intermediate adds a full multi-GB rewrite that the later remux throws away, and it lengthens the window in Critical #2.
- Nothing recovers leftover `.video.mp4`/`.wav` pairs after a crash.
- Fix: use fragmented MP4 (`+frag_keyframe+empty_moov`) or MKV for the intermediate, with no faststart. Scan for orphaned pairs at startup and offer to mux them.

**10. Tests miss the failure paths.** Nothing covers: starting during finalize, audio shorter than video, persistent capture failure, image paths after an editor save when the current directory differs, slot exceptions, or eye-button count after layout passes. Every issue above slipped through for this reason.

#### Minor

- **Closing during a recording** (`ui/main_window.py:469-474`): the recording is finalized synchronously on the UI thread with no "Kayıt sürüyor" confirmation. That can freeze the app for tens of seconds, and the 60 s cap on waiting for the stop worker can be exceeded.
- **Encoder backlog** (`core/recorder.py:448-449`): catch-up after a slow encoder is unbounded. If the 10 s join at stop times out, the writer thread later reports a spurious "ffmpeg borusu kapandı" error.
- **Failed audio start leaks** (`core/audio_capture.py:143-152`): if `InputStream` raises, the writer thread and the open WAV file are leaked.
- **Lost camera stop** (`ui/camera_worker.py:159`): `run()` resets `_abort`, so a `stop()` issued before the thread starts is lost.
- **File name collisions**: file stamps have one-second resolution, so two recordings started in the same second overwrite each other.
- **Badge size**: with "Doğal" resolution the badge shows the logical size, not the real one (`ui/main_window.py:282`).
- **Pen dialog does nothing (please confirm this is intentional):** the pressure curve, smoothing, min/max width, nib and "Otomatik kaydet" settings are saved but never used. `ui/canvas.py:251` uses a fixed pressure curve. Only Keras is documented as a draft.
- **Editor rewrite side effects**:
  - The editor rewrites the workbook from scratch, dropping any extra sheets or formatting.
  - Questions never opened in the editor get absolute image paths.
  - `reload_questions` clears the board without saving a snapshot and resets the lesson to question 1.
- **Camera scan** (`ui/settings_dialog.py:229-240`): it runs on the UI thread. On Windows the camera in use may not appear in the list, and the selection then silently switches to index 0.
- **Copies under the GIL**: about 8.5 ms per 2816×1584 frame of copying happens while holding Python's lock (measured with `bench_copies.py` on this Windows box). At 30–60 captures per second that competes with the pen. Using `shot.raw` and writing a memoryview removes two of the three copies.
- **Mixed-DPI monitors**: `RecordRect.physical()` is wrong on a secondary monitor with a different scale on Windows (affects the dev box only).
- **Dependencies and build pinning**:
  - `pyproject.toml` says `PyQt6>=6.6`, but the dark-mode fix needs 6.8+.
  - Dependencies are unpinned while every push produces a release; the mss 10 compatibility shim shows the drift risk is real.
  - The release action is pinned by tag, not commit SHA.
- **Release noise**: `release.yml` also builds for chore and graph-refresh pushes; `graphify-out/` (9.9 MB) is tracked in git.
- **README**:
  - Lines 135 and 137 are stale: mss is not a "next version" feature, and the Info.plist strings already exist.
  - Line 168 ("izin verilmezse kare siyah gelir") is untested.
  - Nothing explains what to do with leftover `.video.mp4`/`.wav` files.
- **Status line**: it sits inside the recorded area and is on by default. It updates at pen-hover rate and shows the full file path after a stop.
- **Loose typing**: the `Recorder` protocol doesn't declare the attributes that `MainWindow` reads through `getattr`, so type checking can't catch drift.

#### Recommendations

- Treat "no silent failures" as a health check on every badge tick: frames being captured, audio samples growing, encoder not falling behind, capture rectangle unchanged. Surface problems loudly in the toolbar, which is outside the recording.
- Before relying on the app for real lessons, do a 60-minute test run on the target MacBook. Measure capture rate, memory growth, pen latency during recording, and finalize time.

#### Plan alignment

All nine plan items are present. The deviations I saw are justified and documented:
- Stage built from 32×18 steps.
- Item positions relative to the stage, not the whole window.
- Measured toolbar thresholds (950/790).
- `FrameContext` gained `stage` and dropped `logo`.

I found no problems with the plan itself. Its recording checks focus on resolution and alignment and don't cover failures, which is where Critical 1 and 2 sit.

#### Assessment

**Ready to merge?** With fixes.

**Reasoning:** The architecture is sound and well tested for the success path. However, there are two confirmed ways to lose recordings that are easy to hit: a mic dropout cuts the lesson short and deletes the original, and pressing R while a recording is finalizing breaks the previous recording. Several silent-failure and crash paths remain. Both Critical fixes are small and local and should land before the app is used for a real lesson; the Important items should follow soon after.

Note on the memory rules: no `[Hafıza: ...]` blocks were injected into this session (hafıza gelmedi). I did not update the BarisOS memory files; that is left to the main session.
