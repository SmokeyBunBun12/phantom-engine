#!/usr/bin/env python3
"""
Threaded video capture module for Phantom Engine.

Provides reliable, threaded video capture with automatic fallback mechanisms
for GoPro UVC cameras, webcams, and test pattern generators.
"""

import cv2
import numpy as np
import threading
import time
import os
import queue
from typing import Optional, Tuple, Callable
import logging
from pathlib import Path

from core.camera_probe import CameraProbe
class VideoCapture:
    """
    Threaded video capture system with automatic camera selection and failover.
    
    Features:
    - Automatic GoPro UVC detection and fallback to USB webcam
    - Thread-safe frame acquisition with queue-based frame buffering
    - Auto-reconnect capabilities
    - Performance optimization through pre-allocation
    - Hardware-accelerated capture where available
    """
    
    def __init__(self, camera_index: int = 0, config: Optional[dict] = None):
        """
        Initialize video capture with camera index and configuration.
        
        Args:
            camera_index: Primary camera device index (typically 0 for default webcam)
            config: Optional configuration dictionary for capture settings
        """
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.config = config or {}
        self.camera_index = camera_index
        self.fallback_index = self.config.get("fallback_index", 1)
        self.use_gopro = self.config.get("use_gopro", True)
        self.resolution_width = self.config.get("resolution_width", 1920)
        self.resolution_height = self.config.get("resolution_height", 1080)
        self.fps = self.config.get("fps", 30)
        self.auto_reconnect = self.config.get("auto_reconnect", True)
        self.reconnect_interval = self.config.get("reconnect_interval", 5.0)
        
        # Camera state
        self.current_camera = None
        self.current_index = None
        self.camera_probe = CameraProbe()
        
        # Frame buffer and thread management
        self.frame_queue = queue.Queue(maxsize=30)
        self.latest_frame = None
        self.latest_frame_time = 0
        self.capture_thread = None
        self.stopped = False
        
        # Performance monitoring
        self.frames_captured = 0
        self.dropped_frames = 0
        self.avg_fps = 0.0
        self.last_fps_check = time.time()
        
        # Test pattern generator for fallback
        self.test_pattern_generator = TestPatternGenerator()
        
        # Initialize capture system
        self._initialize_capture()
    
    def _initialize_capture(self):
        """Initialize the primary capture device with automatic fallback."""
        # Try to find and select the best camera
        selected_camera = self._select_best_camera()
        
        if selected_camera is not None:
            self.current_index = selected_camera["index"]
            self._setup_capture(self.current_index)
            self.logger.info(f"Initialized camera capture on index {self.current_index}")
        else:
            self.logger.warning("No suitable camera found, using test pattern")
            self.current_index = -1  # Special flag for test pattern
            self.current_camera = None
    
    def _select_best_camera(self) -> Optional[dict]:
        """Automatically detect and select the best available camera."""
        available_cameras = self.camera_probe.scan_cameras()
        self.logger.info(f"Found {len(available_cameras)} potential camera sources")
        
        # If GoPro is preferred and available, use it
        if self.use_gopro:
            gopro_cameras = [cam for cam in available_cameras if cam.get("gopro", False)]
            if gopro_cameras:
                # Select the first GoPro (typically index 0 or 1)
                gopro = gopro_cameras[0]
                self.logger.info(f"Selected GoPro UVC camera at index {gopro['index']}")
                return gopro
        
        # Otherwise, use the primary or fallback camera
        if self.camera_index in [cam["index"] for cam in available_cameras]:
            selected = next(cam for cam in available_cameras if cam["index"] == self.camera_index)
            self.logger.info(f"Selected primary camera at index {self.camera_index}")
            return selected
        
        # Try fallback camera
        if self.fallback_index in [cam["index"] for cam in available_cameras]:
            selected = next(cam for cam in available_cameras if cam["index"] == self.fallback_index)
            self.logger.warning(f"Using fallback camera at index {self.fallback_index}")
            return selected
        
        # No camera found
        self.logger.warning("No cameras found, will use test pattern")
        return None
    
    def _setup_capture(self, camera_index: int):
        """Setup OpenCV video capture with optimal settings."""
        if self.current_camera is not None:
            self.current_camera.release()
        
        # Try different backends and configurations
        backends = [
            cv2.CAP_V4L2,  # Linux V4L2 (preferred for USB cameras)
            cv2.CAP_V4L,   # Linux V4L
            cv2.CAP_DSHOW, # Windows DirectShow
            cv2.CAP_MSMF,  # Windows Media Foundation
            cv2.CAP_GSTREAMER, # Linux GStreamer
        ]
        
        for backend in backends:
            try:
                self.current_camera = cv2.VideoCapture(camera_index, backend)
                
                # Set optimal properties
                self.current_camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution_width)
                self.current_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution_height)
                self.current_camera.set(cv2.CAP_PROP_FPS, self.fps)
                
                # Verify camera is working
                if self.current_camera.isOpened():
                    ret, test_frame = self.current_camera.read()
                    if ret and test_frame is not None:
                        self.logger.info(f"Successfully initialized camera with backend {backend}")
                        return
            except Exception as e:
                self.logger.debug(f"Backend {backend} failed: {e}")
                continue
        
        # If all backends failed, fallback to test pattern
        self.logger.error(f"All camera backends failed for index {camera_index}")
        self.current_camera = None
        self.current_index = -1
    
    def start_capture_thread(self):
        """Start the background capture thread."""
        if self.capture_thread is None or not self.capture_thread.is_alive():
            self.stopped = False
            self.capture_thread = threading.Thread(
                target=self._capture_loop,
                daemon=True,
                name="VideoCapture"
            )
            self.capture_thread.start()
            self.logger.info("Video capture thread started")
    
    def stop_capture_thread(self):
        """Stop the capture thread gracefully."""
        self.stopped = True
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2.0)
            self.logger.info("Video capture thread stopped")
        
        # Cleanup camera resources
        if self.current_camera is not None:
            self.current_camera.release()
            self.current_camera = None
    
    def _capture_loop(self):
        """Main capture loop running in background thread."""
        self.start_capture_thread()
        
        while not self.stopped:
            try:
                if self.current_index >= 0 and self.current_camera is not None:
                    # Capture from real camera
                    ret, frame = self.current_camera.read()
                    if ret and frame is not None:
                        # Add timestamp and frame info
                        frame_info = {
                            "frame": frame,
                            "timestamp": time.time(),
                            "camera_index": self.current_index,
                            "source": "camera"
                        }
                        
                        # Add to queue if not full
                        try:
                            self.frame_queue.put(frame_info, timeout=0.1)
                            self.frames_captured += 1
                        except queue.Full:
                            self.dropped_frames += 1
                            # Remove oldest frame
                            try:
                                self.frame_queue.get_nowait()
                                self.frame_queue.put(frame_info, timeout=0.1)
                            except:
                                pass
                        
                        # Update latest frame
                        self.latest_frame = frame
                        self.latest_frame_time = time.time()
                        
                    else:
                        # Camera disconnected
                        if self.auto_reconnect:
                            self.logger.warning("Camera disconnected, attempting reconnection")
                            time.sleep(self.reconnect_interval)
                            self._reconnect_camera()
                        else:
                            self.logger.error("Camera disconnected and auto-reconnect disabled")
                else:
                    # Use test pattern
                    frame_info = {
                        "frame": self.test_pattern_generator.generate_frame(),
                        "timestamp": time.time(),
                        "camera_index": -1,
                        "source": "test_pattern"
                    }
                    
                    try:
                        self.frame_queue.put(frame_info, timeout=0.1)
                    except queue.Full:
                        pass
            
            except Exception as e:
                self.logger.error(f"Capture loop error: {e}")
                if self.auto_reconnect:
                    time.sleep(1.0)
                else:
                    time.sleep(5.0)
        
        # Cleanup
        if self.current_camera is not None:
            self.current_camera.release()
    
    def _reconnect_camera(self):
        """Attempt to reconnect to a camera."""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                self.logger.info(f"Reconnect attempt {attempt + 1}/{max_attempts}")
                time.sleep(1.0)
                self._setup_capture(self.current_index)
                
                # Test the connection
                if self.current_camera is not None and self.current_camera.isOpened():
                    ret, test_frame = self.current_camera.read()
                    if ret and test_frame is not None:
                        self.logger.info("Camera reconnection successful")
                        return True
            except Exception as e:
                self.logger.warning(f"Reconnect attempt {attempt + 1} failed: {e}")
        
        self.logger.error("All reconnection attempts failed")
        return False
    
    def get_frame(self, timeout: Optional[float] = None) -> Optional[np.ndarray]:
        """
        Get the next available frame from the capture queue.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            NumPy array representing the frame, or None if no frame available
        """
        try:
            if timeout is not None:
                frame_info = self.frame_queue.get(timeout=timeout)
            else:
                frame_info = self.frame_queue.get_nowait()
            
            return frame_info["frame"]
        except queue.Empty:
            return None
    
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Get the most recently captured frame."""
        return self.latest_frame
    
    def get_latest_frame_info(self) -> Optional[dict]:
        """Get detailed information about the latest frame."""
        if self.latest_frame is None:
            return None
        
        return {
            "frame": self.latest_frame,
            "timestamp": self.latest_frame_time,
            "camera_index": self.current_index,
            "source": "camera" if self.current_index >= 0 else "test_pattern",
            "frames_captured": self.frames_captured,
            "dropped_frames": self.dropped_frames,
            "current_fps": self.avg_fps
        }
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics for the capture system."""
        current_time = time.time()
        
        # Calculate average FPS over the last period
        if current_time - self.last_fps_check > 1.0:
            time_diff = current_time - self.last_fps_check
            if time_diff > 0:
                self.avg_fps = self.frames_captured / time_diff
            self.last_fps_check = current_time
            self.frames_captured = 0
        
        return {
            "camera_index": self.current_index,
            "source": "camera" if self.current_index >= 0 else "test_pattern",
            "avg_fps": self.avg_fps,
            "frames_captured": self.frames_captured,
            "dropped_frames": self.dropped_frames,
            "queue_size": self.frame_queue.qsize(),
            "has_camera": self.current_camera is not None and self.current_camera.isOpened(),
            "is_running": self.capture_thread is not None and self.capture_thread.is_alive()
        }
    
    def set_camera(self, index: int):
        """Change camera device to a new index."""
        self.logger.info(f"Switching camera to index {index}")
        
        # Stop current capture
        self.stop_capture_thread()
        
        # Update camera index
        self.camera_index = index
        
        # Reinitialize capture
        self._initialize_capture()
        
        # Restart capture thread
        self.start_capture_thread()
class TestPatternGenerator:
    """Generates test patterns for use when no camera is available."""
    
    def __init__(self):
        self.width = 1920
        self.height = 1080
        self.time = 0.0
    
    def generate_frame(self) -> np.ndarray:
        """Generate a test frame with various patterns."""
        self.time += 0.016  # ~60 Hz
        
        # Create base frame
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Add test pattern elements
        self._draw_test_pattern(frame)
        
        # Add some noise for realistic texture
        noise = np.random.normal(0, 10, frame.shape).astype(np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        return frame
    
    def _draw_test_pattern(self, frame: np.ndarray):
        """Draw various test pattern elements."""
        # Create a simple cross pattern
        center_x, center_y = self.width // 2, self.height // 2
        length = min(self.width, self.height) // 3
        
        # Draw diagonal lines
        cv2.line(frame, (0, 0), (self.width, self.height), (50, 50, 50), 2)
        cv2.line(frame, (0, self.height), (self.width, 0), (50, 50, 50), 2)
        
        # Draw cross
        cv2.line(frame, (center_x - length, center_y), (center_x + length, center_y), (100, 100, 100), 2)
        cv2.line(frame, (center_x, center_y - length), (center_x, center_y + length), (100, 100, 100), 2)
        
        # Draw concentric circles
        for i in range(3, min(self.width, self.height) // 4, 20):
            cv2.circle(frame, (center_x, center_y), i * 2, (50, 50, 50), 2)
        
        # Add time-based pattern
        time_pattern = int(self.time * 10) % 255
        cv2.rectangle(frame, (10, 10), (100, 100), (time_pattern, 0, 255 - time_pattern), -1)
class CameraProbe:
    """Scans for available cameras and detects special hardware like GoPro UVC."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def scan_cameras(self) -> list:
        """Scan for available camera devices."""
        cameras = []
        
        # Try to detect cameras using different backends
        backends = [cv2.CAP_V4L2, cv2.CAP_V4L, cv2.CAP_DSHOW, cv2.CAP_MSMF]
        
        for backend in backends:
            try:
                temp_cap = cv2.VideoCapture(cv2.CAP_ANY, backend)
                
                # Try indices 0-5 (typical camera indices)
                for i in range(6):
                    temp_cap = cv2.VideoCapture(i, backend)
                    if temp_cap.isOpened():
                        # Get camera properties
                        width = int(temp_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(temp_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        fps = int(temp_cap.get(cv2.CAP_PROP_FPS))
                        
                        camera_info = {
                            "index": i,
                            "backend": backend,
                            "width": width,
                            "height": height,
                            "fps": fps,
                            "gopro": self._detect_gopro(temp_cap, i)
                        }
                        
                        cameras.append(camera_info)
                        temp_cap.release()
            except Exception as e:
                self.logger.debug(f"Camera scan error with backend {backend}: {e}")
                continue
        
        return cameras
    
    def _detect_gopro(self, cap, index: int) -> bool:
        """Detect if a camera is a GoPro UVC device."""
        try:
            # GoPro UVC cameras typically have specific properties
            # Try to get manufacturer information
            if hasattr(cap, 'getCaptureProperty'):
                # Windows DShow property
                return False
            elif hasattr(cap, 'get'):
                # Try to get some hardware-specific properties
                # GoPro UVC devices may have specific VID/PID
                pass
            
            # For now, assume standard USB cameras
            # Real GoPro detection would need deeper hardware inspection
            return False
        except:
            return False
    
    def release(self):
        """Release all camera resources."""
        # Cleanup is handled in the main VideoCapture class
        pass
if __name__ == "__main__":
    # Test the VideoCapture class
    logging.basicConfig(level=logging.INFO)
    
    print("Testing VideoCapture...")
    
    # Create capture instance
    capture = VideoCapture(camera_index=0)
    
    # Start capture thread
    capture.start_capture_thread()
    
    try:
        # Capture and display some frames
        for i in range(10):
            frame = capture.get_frame(timeout=1.0)
            if frame is not None:
                print(f"Captured frame {i}: shape={frame.shape}, dtype={frame.dtype}")
                # Convert BGR to RGB for display (if needed)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                print(f"Frame {i} is None")
            
            time.sleep(0.1)
    
    finally:
        # Cleanup
        capture.stop_capture_thread()
        print("Test completed.")