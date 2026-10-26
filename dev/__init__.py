"""Development utilities and debugging tools for Phantom Engine."""

import os
import time
import platform
import logging
from typing import Dict, Any

def collect_system_info() -> Dict[str, Any]:
    """Collect system information for diagnostics."""
    import cv2
    import mediapipe
    import moderngl
    
    return {
        "version": "2.0.0",
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "opencv_version": cv2.__version__,
        "mediapipe_version": getattr(mediapipe, "__version__", "unknown"),
        "moderngl_version": getattr(moderngl, "version", lambda: "unknown")() if hasattr(moderngl, "version") else "unknown",
        "dearpygui_version": "1.0.0",
        "cpu_count": os.cpu_count(),
        "gpu_available": True,
    }

def get_log_level() -> str:
    """Get the current log level."""
    return logging.getLevelName(logging.root.level)

if __name__ == "__main__":
    # Test dev tools
    print("Testing DevTools...")
    info = collect_system_info()
    print("System info:", info)
    print("DevTools module initialized successfully")
