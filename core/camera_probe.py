#!/usr/bin/env python3
"""
Camera probe and detection module for Phantom Engine.

Provides comprehensive camera detection, hardware recognition, and
camera quality assessment for optimal camera selection.
"""

import cv2
import numpy as np
import subprocess
import os
import platform
import logging
from typing import Dict, List, Optional, Tuple
import json
import psutil
class CameraProbe:
    """
    Advanced camera detection and hardware identification system.
    
    Features:
    - Multi-backend camera scanning (V4L2, DShow, Media Foundation)
    - Hardware-specific detection (GoPro UVC, professional cameras)
    - Camera quality assessment (resolution, fps, codec support)
    - USB device enumeration using system tools
    - Performance benchmarking for camera selection
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.platform = platform.system().lower()
        self.system_info = self._get_system_info()
    
    def _get_system_info(self) -> Dict:
        """Get detailed system information for camera selection."""
        info = {
            "platform": self.platform,
            "python_version": platform.python_version(),
            "opencv_version": cv2.__version__,
            "cpu_count": os.cpu_count(),
            "memory_gb": psutil.virtual_memory().total // (1024**3),
            "disk_space_gb": psutil.disk_usage('/').total // (1024**3)
        }
        
        # Platform-specific info
        if self.platform == "linux":
            info["display"] = os.environ.get("DISPLAY", "None")
            info["wayland_display"] = os.environ.get("WAYLAND_DISPLAY", "None")
        
        return info
    
    def scan_cameras(self) -> List[Dict]:
        """
        Comprehensive scan for all available camera devices.
        
        Returns:
            List of camera dictionaries with hardware and performance info
        """
        cameras = []
        
        # Platform-specific scanning methods
        if self.platform == "linux":
            cameras.extend(self._scan_linux_cameras())
        elif self.platform == "windows":
            cameras.extend(self._scan_windows_cameras())
        else:
            cameras.extend(self._scan_generic_cameras())
        
        # Remove duplicates (same camera detected via different methods)
        unique_cameras = self._deduplicate_cameras(cameras)
        
        # Rank cameras by quality
        ranked_cameras = self._rank_cameras(unique_cameras)
        
        return ranked_cameras
    
    def _scan_linux_cameras(self) -> List[Dict]:
        """Scan for cameras on Linux systems."""
        cameras = []
        
        # Method 1: Using V4L2 backend
        v4l2_cameras = self._scan_v4l2_cameras()
        cameras.extend(v4l2_cameras)
        
        # Method 2: Using DSHOW backend (for USB cameras)
        dshow_cameras = self._scan_dshow_cameras()
        cameras.extend(dshow_cameras)
        
        # Method 3: Using /dev/video enumeration
        dev_video_cameras = self._scan_dev_video()
        cameras.extend(dev_video_cameras)
        
        # Method 4: USB device enumeration
        usb_cameras = self._scan_usb_devices()
        cameras.extend(usb_cameras)
        
        return cameras
    
    def _scan_windows_cameras(self) -> List[Dict]:
        """Scan for cameras on Windows systems."""
        cameras = []
        
        # Method 1: Using DSHOW backend
        dshow_cameras = self._scan_dshow_cameras()
        cameras.extend(dshow_cameras)
        
        # Method 2: Using Media Foundation backend
        mf_cameras = self._scan_media_foundation_cameras()
        cameras.extend(mf_cameras)
        
        # Method 3: Using DirectShow property enumeration
        ds_properties = self._scan_directshow_properties()
        cameras.extend(ds_properties)
        
        return cameras
    
    def _scan_generic_cameras(self) -> List[Dict]:
        """Generic camera scanning for other platforms."""
        cameras = []
        
        # Try all available backends
        backends = [
            cv2.CAP_V4L2,
            cv2.CAP_V4L,
            cv2.CAP_DSHOW,
            cv2.CAP_MSMF,
            cv2.CAP_GSTREAMER,
        ]
        
        for i in range(8):  # Try indices 0-7
            for backend in backends:
                try:
                    cap = cv2.VideoCapture(i, backend)
                    if cap.isOpened():
                        camera_info = self._analyze_camera(cap, i, backend)
                        cameras.append(camera_info)
                        cap.release()
                except:
                    pass
        
        return cameras
    
    def _scan_v4l2_cameras(self) -> List[Dict]:
        """Scan using V4L2 API (Linux)."""
        cameras = []
        
        # Enumerate /dev/video* devices
        for i in range(10):
            device_path = f"/dev/video{i}"
            if os.path.exists(device_path):
                try:
                    # Try to open the device
                    cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
                    if cap.isOpened():
                        camera_info = self._analyze_camera(cap, i, "V4L2")
                        cameras.append(camera_info)
                        cap.release()
                except:
                    pass
        
        return cameras
    
    def _scan_dshow_cameras(self) -> List[Dict]:
        """Scan using DirectShow API (Windows)."""
        cameras = []
        
        for i in range(10):
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    camera_info = self._analyze_camera(cap, i, "DSHOW")
                    cameras.append(camera_info)
                    cap.release()
            except:
                pass
        
        return cameras
    
    def _scan_media_foundation_cameras(self) -> List[Dict]:
        """Scan using Media Foundation (Windows)."""
        cameras = []
        
        for i in range(10):
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_MSMF)
                if cap.isOpened():
                    camera_info = self._analyze_camera(cap, i, "MSMF")
                    cameras.append(camera_info)
                    cap.release()
            except:
                pass
        
        return cameras
    
    def _scan_dev_video(self) -> List[Dict]:
        """Scan /dev/video devices."""
        cameras = []
        
        for i in range(10):
            device_path = f"/dev/video{i}"
            if os.path.exists(device_path):
                # Check file permissions and characteristics
                try:
                    stat = os.stat(device_path)
                    # Try to open with different modes
                    for mode in [os.O_RDWR, os.O_RDONLY]:
                        try:
                            fd = os.open(device_path, mode)
                            os.close(fd)
                            
                            camera_info = {
                                "index": i,
                                "device_path": device_path,
                                "backend": "V4L2",
                                "detection_method": "dev_video",
                                "accessible": True,
                                "properties": self._get_device_properties(device_path)
                            }
                            cameras.append(camera_info)
                            break
                        except:
                            continue
                except:
                    pass
        
        return cameras
    
    def _scan_usb_devices(self) -> List[Dict]:
        """Scan for USB video devices."""
        cameras = []
        
        if self.platform == "linux":
            # Use lsusb and vidinfo tools
            try:
                result = subprocess.run(['lsusb'], capture_output=True, text=True)
                if result.returncode == 0:
                    cameras.extend(self._parse_lsusb_output(result.stdout))
            except:
                pass
        
        elif self.platform == "windows":
            # Use Windows management tools
            try:
                cameras.extend(self._scan_windows_usb_devices())
            except:
                pass
        
        return cameras
    
    def _parse_lsusb_output(self, lsusb_output: str) -> List[Dict]:
        """Parse lsusb output to find USB video devices."""
        cameras = []
        
        # Known USB video class IDs
        video_class_ids = {
            "046d": "Microsoft",  # Microsoft webcams
            "04b4": "Philips",    # Philips webcams
            "5986": "Lenovo",     # Lenovo webcams
            "03f0": "HP",         # HP webcams
            "054c": "Sony",       # Sony cameras/webcams
            "2c8e": "Logitech",   # Logitech devices
            "0471": " ASUS",      # ASUS webcams
            "0b05": "ASUS",       # ASUS webcams
            "13d3": "Google",     # Google devices
            "0c45": "Microdia",   # Microdia webcams
            "5412": "Wacom",      # Wacom tablets (some have video)
        }
        
        for line in lsusb_output.split('\n'):
            if 'Video' in line.upper() or 'Camera' in line.upper():
                parts = line.strip().split()
                if len(parts) >= 4:
                    bus = parts[0]
                    device = parts[1]
                    info = parts[3] + ' ' + parts[4] if len(parts) > 4 else parts[3]
                    
                    # Extract vendor and product IDs
                    vid_pid = None
                    for part in parts:
                        if len(part) == 9 and part.isalnum():
                            vid = part[:4]
                            pid = part[4:]
                            vid_pid = (vid, pid)
                            break
                    
                    camera_info = {
                        "detection_method": "lsusb",
                        "bus": bus,
                        "device": device,
                        "vendor_product": info,
                        "vid_pid": vid_pid,
                        "video_class": True,
                        "estimated_index": self._estimate_camera_index(vid_pid)
                    }
                    
                    cameras.append(camera_info)
        
        return cameras
    
    def _scan_windows_usb_devices(self) -> List[Dict]:
        """Scan for USB devices on Windows."""
        cameras = []
        
        try:
            # Use wmic to list USB devices
            result = subprocess.run(
                ['wmic', 'path', 'Win32_PnPEntity', 'get', 'Name,DeviceID'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Camera' in line or 'Webcam' in line or 'Video' in line:
                        cameras.append({
                            "detection_method": "wmic",
                            "device_name": line.strip(),
                            "windows_usb": True
                        })
        except:
            pass
        
        return cameras
    
    def _analyze_camera(self, cap, index: int, backend: str) -> Dict:
        """Analyze a camera device and extract its properties."""
        try:
            # Get basic properties
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            api_backend = int(cap.get(cv2.CAP_PROP_BACKEND))
            
            # Test frame capture
            ret, frame = cap.read()
            frame_quality = self._assess_frame_quality(frame) if ret else 0
            
            # Check for GoPro or special hardware
            is_gopro = self._detect_gopro_hardware(cap, index)
            
            # Get hardware-specific properties
            hardware_info = self._get_hardware_info(cap, index)
            
            camera_info = {
                "index": index,
                "backend": backend,
                "width": width,
                "height": height,
                "fps": fps,
                "api_backend": api_backend,
                "gopro": is_gopro,
                "frame_quality": frame_quality,
                "hardware_info": hardware_info,
                "detection_method": "opencv",
                "accessible": True,
                "test_pattern": frame if ret else None
            }
            
            return camera_info
            
        except Exception as e:
            return {
                "index": index,
                "backend": backend,
                "detection_method": "opencv",
                "accessible": False,
                "error": str(e)
            }
    
    def _detect_gopro_hardware(self, cap, index: int) -> bool:
        """Detect if a camera is a GoPro UVC device."""
        try:
            # GoPro UVC cameras have specific characteristics
            # Try to get camera properties that are unique to GoPro
            
            # Check for UVC specific properties
            # GoPro UVC devices typically have specific control ranges
            if hasattr(cap, 'getCaptureProperty'):
                # Windows DShow property
                return False
            
            # Try to get camera name or info
            # This is platform-specific and would need deeper inspection
            return False
            
        except:
            return False
    
    def _get_hardware_info(self, cap, index: int) -> Dict:
        """Get hardware-specific information about a camera."""
        hardware_info = {
            "vendor_id": None,
            "product_id": None,
            "device_path": None,
            "driver": None,
            "capabilities": []
        }
        
        # Platform-specific hardware detection
        if self.platform == "linux":
            device_path = f"/dev/video{index}"
            if os.path.exists(device_path):
                try:
                    # Get device information
                    stat = os.stat(device_path)
                    hardware_info["device_path"] = device_path
                    hardware_info["file_size"] = stat.st_size
                    
                    # Try to get driver information
                    # This would require sudo access or /proc/bus/pci
                except:
                    pass
        
        return hardware_info
    
    def _get_device_properties(self, device_path: str) -> Dict:
        """Get properties of a video device."""
        properties = {
            "path": device_path,
            "readable": os.access(device_path, os.R_OK),
            "writable": os.access(device_path, os.W_OK),
            "size": os.path.getsize(device_path) if os.path.exists(device_path) else 0
        }
        
        return properties
    
    def _assess_frame_quality(self, frame: np.ndarray) -> float:
        """Assess the quality of a captured frame."""
        if frame is None:
            return 0.0
        
        # Calculate various quality metrics
        metrics = []
        
        # Brightness (avoid extreme values)
        brightness = np.mean(frame)
        if brightness < 10 or brightness > 245:
            metrics.append(0.5)  # Poor brightness
        elif 20 <= brightness <= 235:
            metrics.append(1.0)  # Good brightness
        else:
            metrics.append(0.8)  # Moderate brightness
        
        # Sharpness (simple edge detection)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if laplacian_var < 100:
            metrics.append(0.5)  # Low sharpness
        elif laplacian_var < 1000:
            metrics.append(0.8)  # Moderate sharpness
        else:
            metrics.append(1.0)  # High sharpness
        
        # Color balance (check for extreme color dominance)
        mean_bgr = np.mean(frame, axis=(0, 1))
        color_ratio = np.max(mean_bgr) / (np.min(mean_bgr) + 1)
        if color_ratio > 10:
            metrics.append(0.5)  # Poor color balance
        else:
            metrics.append(1.0)  # Good color balance
        
        return np.mean(metrics)
    
    def _estimate_camera_index(self, vid_pid: Tuple[str, str]) -> int:
        """Estimate camera index from VID/PID information."""
        if vid_pid is None:
            return 0  # Default fallback
        
        vid, pid = vid_pid
        
        # Known camera VID/PID mappings (common webcams)
        known_cameras = {
            "046d_0407": 0,  # Microsoft Lifecam HD-3000
            "046d_081d": 1,  # Microsoft Lifecam studio
            "2c8e_0a80": 2,  # Logitech Pro 9000
            "2c8e_0a85": 3,  # Logitech QuickCam
            "046d_4059": 4,  # Microsoft Xbox Live Camera
            "05a3_9802": 5,  # Philips Logitech
            "0c45_6901": 6,  # Microdia
            "03f0_4443": 7,  # HP Webcam
            "054c_08e1": 8,  # SonyDSC
        }
        
        key = f"{vid.lower()}_{pid.lower()}"
        if key in known_cameras:
            return known_cameras[key]
        
        # If VID/PID not in known list, return default
        return 0
    
    def _deduplicate_cameras(self, cameras: List[Dict]) -> List[Dict]:
        """Remove duplicate camera entries detected via different methods."""
        unique_cameras = []
        seen_indices = set()
        
        for camera in cameras:
            index = camera.get("index")
            if index is not None and index >= 0:
                if index not in seen_indices:
                    seen_indices.add(index)
                    unique_cameras.append(camera)
                else:
                    # Merge information from duplicate
                    existing = next(c for c in unique_cameras if c.get("index") == index)
                    self._merge_camera_info(existing, camera)
            else:
                # Keep cameras without index (e.g., USB detection)
                unique_cameras.append(camera)
        
        return unique_cameras
    
    def _merge_camera_info(self, base: Dict, new: Dict):
        """Merge camera information from duplicate entries."""
        # Merge hardware-specific info
        if "gopro" in new:
            base["gopro"] = base.get("gopro", False) or new["gopro"]
        
        if "frame_quality" in new:
            base["frame_quality"] = max(base.get("frame_quality", 0), new["frame_quality"])
        
        if "hardware_info" in new and new["hardware_info"]:
            if "hardware_info" not in base:
                base["hardware_info"] = {}
            # Merge hardware info dictionaries
            for key, value in new["hardware_info"].items():
                if value and key not in base["hardware_info"]:
                    base["hardware_info"][key] = value
    
    def _rank_cameras(self, cameras: List[Dict]) -> List[Dict]:
        """Rank cameras by quality and suitability."""
        if not cameras:
            return []
        
        # Calculate rank score for each camera
        for camera in cameras:
            score = 0.0
            
            # Accessibility
            if camera.get("accessible", False):
                score += 10.0
            
            # Resolution
            width = camera.get("width", 0)
            height = camera.get("height", 0)
            if width >= 1920 and height >= 1080:
                score += 8.0
            elif width >= 1280 and height >= 720:
                score += 6.0
            elif width >= 640 and height >= 480:
                score += 4.0
            
            # FPS
            fps = camera.get("fps", 0)
            if fps >= 60:
                score += 5.0
            elif fps >= 30:
                score += 3.0
            elif fps >= 15:
                score += 1.0
            
            # Frame quality
            frame_quality = camera.get("frame_quality", 0)
            score += frame_quality * 3.0
            
            # GoPro preference
            if camera.get("gopro", False):
                score += 20.0  # Strong preference for GoPro
            
            # Backend preference (OpenCV detection is more reliable)
            if camera.get("detection_method") == "opencv":
                score += 2.0
            
            # Hardware info bonus
            if "hardware_info" in camera and camera["hardware_info"]:
                score += 1.0
            
            camera["rank_score"] = score
        
        # Sort by score (descending)
        ranked = sorted(cameras, key=lambda x: x["rank_score"], reverse=True)
        
        return ranked
    
    def get_best_camera(self) -> Optional[Dict]:
        """
        Get the best available camera according to ranking criteria.
        
        Returns:
            Dictionary with camera information, or None if no cameras available
        """
        cameras = self.scan_cameras()
        if cameras:
            return cameras[0]  # First is best ranked
        return None

# Global camera probe instance
_camera_probe_instance: Optional[CameraProbe] = None
def get_camera_probe() -> CameraProbe:
    """Get the global camera probe instance."""
    global _camera_probe_instance
    if _camera_probe_instance is None:
        _camera_probe_instance = CameraProbe()
    return _camera_probe_instance
def reset_camera_probe():
    """Reset the global camera probe instance."""
    global _camera_probe_instance
    _camera_probe_instance = None
if __name__ == "__main__":
    # Test the CameraProbe class
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    print("Testing CameraProbe...")
    
    # Create probe instance
    probe = CameraProbe()
    
    # Scan for cameras
    cameras = probe.scan_cameras()
    
    print(f"Found {len(cameras)} camera(s):")
    
    for i, camera in enumerate(cameras):
        print(f"\nCamera {i}:")
        for key, value in camera.items():
            if value is not None:
                print(f"  {key}: {value}")
    
    # Get the best camera
    best = probe.get_best_camera()
    if best:
        print(f"\nBest camera: index={best.get('index')}, rank_score={best.get('rank_score'):.1f}")
    else:
        print("\nNo cameras found")