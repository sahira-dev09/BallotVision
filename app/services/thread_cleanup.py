"""Keep background QThreads alive until run() has returned.

Widgets must not own these threads. Closing a dialog or the main window
otherwise destroys the QThread while OCR is still inside run(), which is the
"Destroyed while thread is still running" warning.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QEventLoop, QThread, Qt
from PySide6.QtWidgets import QApplication

_LIVE: list[QThread] = []
_HOOKS: list = []
_HOOKED = False
_SHUTTING_DOWN = False


def is_shutting_down() -> bool:
    return _SHUTTING_DOWN


def register_shutdown_hook(callback) -> None:
    if callback not in _HOOKS:
        _HOOKS.append(callback)


def unregister_shutdown_hook(callback) -> None:
    try:
        _HOOKS.remove(callback)
    except ValueError:
        pass


def retain_until_finished(worker: QThread) -> None:
    """Hold a running worker until run() returns.

    The QThread stays parented to the application. It is not deleted from the
    finished signal, because the dialog that started it may still hold the
    Python wrapper. A finished thread is safe for the application to destroy.
    """
    app = QApplication.instance()
    global _HOOKED
    if app is not None and not _HOOKED:
        app.aboutToQuit.connect(shutdown_background_workers)
        _HOOKED = True
    if worker not in _LIVE:
        _LIVE.append(worker)

    def _release() -> None:
        try:
            _LIVE.remove(worker)
        except ValueError:
            pass

    worker.finished.connect(_release, Qt.ConnectionType.QueuedConnection)


def shutdown_background_workers(timeout_ms: int = 15000) -> None:
    """Cancel in-flight OCR and wait until each worker's run() returns.

    The wait is capped. QThread.terminate() is not used. When the cap is hit,
    a still-running worker stays referenced so it is not destroyed mid-run.
    """
    global _SHUTTING_DOWN
    if _SHUTTING_DOWN:
        return
    _SHUTTING_DOWN = True
    for callback in list(_HOOKS):
        try:
            callback()
        except RuntimeError:
            pass
    for worker in list(_LIVE):
        if _running(worker):
            worker.requestInterruption()
    from app.services.ocr_service import cancel_active_ocr

    app = QApplication.instance()
    deadline = time.monotonic() + max(0, timeout_ms) / 1000
    while any(_running(worker) for worker in _LIVE):
        cancel_active_ocr()
        if time.monotonic() >= deadline:
            break
        for worker in list(_LIVE):
            if _running(worker):
                worker.wait(100)
        if app is not None:
            app.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
    for worker in list(_LIVE):
        if _running(worker):
            worker.setParent(None)
    if app is not None:
        app.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)


def _running(worker: QThread) -> bool:
    try:
        return worker.isRunning()
    except RuntimeError:
        return False
