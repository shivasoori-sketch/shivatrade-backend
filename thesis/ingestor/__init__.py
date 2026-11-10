"""Feed ingestor package (avoid circular imports — import submodules directly)."""

from thesis.ingestor.capture import CaptureSession, attach_capture, replay_capture

__all__ = [
    "CaptureSession",
    "attach_capture",
    "replay_capture",
]
