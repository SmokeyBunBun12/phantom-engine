#!/usr/bin/env python3
"""
Projector warp and calibration module for Phantom Engine.

Provides 4-corner interactive keystone / mesh-warping calibration,
projection matrix calculation, and automatic calibration routines.
"""

import numpy as np
import cv2
import time
import threading
from typing import Optional, List, Tuple, Dict, Any
import logging
import json
from enum import Enum
from dataclasses import dataclass

from graphics.renderer import Renderer
class CalibrationState(Enum):
    """States for the projector calibration system."""
    IDLE = "idle"
    WARMUP = "warmup"
    CALIBRATING = "calibrating"
    CONVERGING = "converging"
    COMPLETE = "complete"
    FAILED = "failed"
@dataclass
class CornerPoint:
    """Represents a 2D corner point in image space."""
    
    x: float
    y: float
    id: int
    detected: bool = False
    confidence: float = 0.0
    timestamp: float = 0.0
    
    def to_array(self) -> np.ndarray:
        """Convert to numpy array for matrix operations."""
        return np.array([self.x, self.y], dtype=np.float32)
    
    @classmethod
    def from_array(cls, arr: np.ndarray, id: int) -> 'CornerPoint':
        """Create from numpy array."""
        return cls(x=arr[0], y=arr[1], id=id)
class ProjectorWarp:
    """
    Projector calibration and warp system for 4-corner keystone correction.
    
    Features:
    - 4-corner interactive calibration with visual guides
    - Mesh warping for complex projection distortions
    - Automatic calibration routines with convergence testing
    - Real-time warp matrix calculation and application
    - Multi-pass calibration for high accuracy
    """
    
    def __init__(self, renderer: Renderer):
        """
        Initialize projector warp system.
        
        Args:
            renderer: Reference to the graphics renderer
        """
        self.logger = logging.getLogger(__name__)
        self.renderer = renderer
        
        # Calibration state
        self.state = CalibrationState.IDLE
        self.calibration_samples = []
        self.current_sample = []
        self.max_samples = 50
        self.convergence_threshold = 0.01
        
        # Corner points
        self.corners = {
            "top_left": CornerPoint(0.0, 0.0, 0),
            "top_right": CornerPoint(1.0, 0.0, 1),
            "bottom_left": CornerPoint(0.0, 1.0, 2),
            "bottom_right": CornerPoint(1.0, 1.0, 3)
        }
        
        # Warp matrices
        self.warp_matrix = np.eye(3, dtype=np.float32)
        self.homography_matrix = np.eye(3, dtype=np.float32)
        self.calibration_matrix = np.eye(3, dtype=np.float32)
        
        # Mesh warping
        self.mesh_enabled = False
        self.mesh_density = 10
        self.mesh_vertices = []
        self.mesh_faces = []
        
        # Performance
        self.frame_count = 0
        self.update_thread = None
        self.update_running = False
        
        # Audio/visual feedback
        self.sound_enabled = False
        self.visual_feedback_enabled = True
        
        # Configuration
        self.config = {
            "warmup_time": 2.0,
            "auto_level": True,
            "corner_tracking_enabled": True,
            "max_warp_iterations": 100,
            "calibration_mode": "interactive",
            "quality_checks": True,
            "save_calibration": True,
            "calibration_file": "phantom_calibration.json"
        }
        
        # Initialize warp system
        self._initialize_warp_system()
        
        # Start update thread
        self.start_updates()
    
    def _initialize_warp_system(self):
        """Initialize the warp system with default values."""
        try:
            # Create mesh for warping
            self._create_warp_mesh()
            
            # Initialize calibration
            self._reset_calibration()
            
            # Load saved calibration if available
            self._load_calibration()
            
            self.logger.info("Projector warp system initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize warp system: {e}")
            raise
    
    def _reset_calibration(self):
        """Reset calibration to default values."""
        # Reset corners to ideal positions
        self.corners["top_left"] = CornerPoint(0.0, 0.0, 0)
        self.corners["top_right"] = CornerPoint(1.0, 0.0, 1)
        self.corners["bottom_left"] = CornerPoint(0.0, 1.0, 2)
        self.corners["bottom_right"] = CornerPoint(1.0, 1.0, 3)
        
        # Reset matrices
        self.warp_matrix = np.eye(3, dtype=np.float32)
        self.homography_matrix = np.eye(3, dtype=np.float32)
        self.calibration_matrix = np.eye(3, dtype=np.float32)
        
        # Reset calibration state
        self.state = CalibrationState.IDLE
        self.calibration_samples = []
        self.current_sample = []
        
        self.logger.debug("Calibration reset completed")
    
    def _create_warp_mesh(self):
        """Create the mesh used for warping calculations."""
        if not self.mesh_enabled:
            return
        
        # Create a grid of vertices for mesh warping
        rows = self.mesh_density
        cols = self.mesh_density
        
        vertices = []
        faces = []
        
        # Create grid vertices
        for i in range(rows):
            for j in range(cols):
                x = i / (rows - 1)
                y = j / (cols - 1)
                
                vertex = {
                    "position": np.array([x, y, 0.0], dtype=np.float32),
                    "original_position": np.array([x, y, 0.0], dtype=np.float32),
                    "displacement": np.array([0.0, 0.0, 0.0], dtype=np.float32),
                    "id": i * cols + j
                }
                vertices.append(vertex)
        
        # Create grid faces
        for i in range(rows - 1):
            for j in range(cols - 1):
                top_left = i * cols + j
                top_right = i * cols + (j + 1)
                bottom_left = (i + 1) * cols + j
                bottom_right = (i + 1) * cols + (j + 1)
                
                # Two triangles per quad
                faces.append([top_left, top_right, bottom_left])
                faces.append([top_right, bottom_right, bottom_left])
        
        self.mesh_vertices = vertices
        self.mesh_faces = faces
    
    def start_updates(self):
        """Start the background update thread."""
        if self.update_thread is None or not self.update_thread.is_alive():
            self.update_running = True
            self.update_thread = threading.Thread(
                target=self._update_loop,
                daemon=True,
                name="ProjectorWarp"
            )
            self.update_thread.start()
            self.logger.info("Projector warp update thread started")
    
    def stop_updates(self):
        """Stop the update thread."""
        self.update_running = False
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=2.0)
            self.logger.info("Projector warp update thread stopped")
    
    def _update_loop(self):
        """Background update loop for continuous warp calculations."""
        while self.update_running:
            try:
                # Update warp calculations if in calibration mode
                if self.state == CalibrationState.CALIBRATING or self.state == CalibrationState.CONVERGING:
                    self._update_warp_calculations()
                
                # Update mesh deformations
                if self.mesh_enabled:
                    self._update_mesh_deformations()
                
                # Sleep to prevent CPU spinning
                time.sleep(0.016)  # ~60 Hz
                
            except Exception as e:
                self.logger.error(f"Warp update loop error: {e}")
                time.sleep(0.1)
    
    def _update_warp_calculations(self):
        """Update warp calculations during calibration."""
        if len(self.current_sample) >= 4:
            # Calculate warp matrix from current sample
            self._calculate_warp_matrix()
            
            # Check for convergence
            if self._check_convergence():
                self.state = CalibrationState.CONVERGING
    
    def _update_mesh_deformations(self):
        """Update mesh deformations based on warp matrix."""
        if not self.mesh_vertices:
            return
        
        # Apply warp matrix to mesh vertices
        for vertex in self.mesh_vertices:
            original = vertex["original_position"]
            
            # Apply homography transformation
            point = np.array([original[0], original[1], 1.0])
            transformed = self.homography_matrix @ point
            
            transformed /= transformed[2]
            vertex["position"] = np.array([transformed[0], transformed[1], 0.0])
            
            # Add displacement for visual feedback
            vertex["displacement"] = vertex["position"] - original
    
    def start_calibration(self, warmup: bool = True):
        """
        Start the calibration process.
        
        Args:
            warmup: Whether to include a warmup period
        """
        if warmup:
            self.state = CalibrationState.WARMUP
            self.logger.info("Starting calibration warmup period...")
        else:
            self.state = CalibrationState.CALIBRATING
            self.logger.info("Starting calibration...")
        
        self._reset_calibration()
    
    def process_calibration_sample(self, frame: np.ndarray, corner_points: List[Tuple[float, float]]):
        """
        Process a single calibration sample.
        
        Args:
            frame: Current video frame
            corner_points: Detected corner points (x, y) in normalized coordinates [0,1]
        """
        if self.state not in [CalibrationState.CALIBRATING, CalibrationState.CONVERGING]:
            return
        
        try:
            # Update current sample
            self.current_sample = corner_points
            
            # Detect corners in frame (for manual calibration)
            if self.config["corner_tracking_enabled"]:
                detected_corners = self._detect_corners(frame)
                if detected_corners:
                    self.current_sample = detected_corners
            
            # Add to calibration samples
            self.calibration_samples.append(self.current_sample)
            
            # Keep only recent samples
            if len(self.calibration_samples) > self.max_samples:
                self.calibration_samples.pop(0)
            
            # Calculate warp matrix
            self._calculate_warp_matrix()
            
            # Check for convergence
            if self._check_convergence():
                if self.state == CalibrationState.CALIBRATING:
                    self.state = CalibrationState.CONVERGING
                
                # If converged, finalize calibration
                if len(self.calibration_samples) >= 10:  # Need enough samples
                    self._finalize_calibration()
                    
        except Exception as e:
            self.logger.error(f"Error processing calibration sample: {e}")
            self.state = CalibrationState.FAILED
    
    def _detect_corners(self, frame: np.ndarray) -> Optional[List[Tuple[float, float]]]:
        """Detect corners in the frame for manual calibration."""
        if frame is None:
            return None
        
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Use corner detection algorithm (Shi-Tomasi)
            corners = cv2.goodFeaturesToTrack(
                gray, maxCorners=4, qualityLevel=0.01, minDistance=10
            )
            
            if corners is not None and len(corners) >= 4:
                # Sort corners to match expected positions
                corners = sorted(corners, key=lambda x: x[0, 0] + x[0, 1])
                
                # Map to expected positions (top-left, top-right, bottom-left, bottom-right)
                # This is a simplified approach - real implementation would use
                # more sophisticated corner matching
                return [
                    (corners[0][0, 0], corners[0][0, 1]),
                    (corners[1][0, 0], corners[1][0, 1]),
                    (corners[2][0, 0], corners[2][0, 1]),
                    (corners[3][0, 0], corners[3][0, 1])
                ]
            
            return None
            
        except Exception as e:
            self.logger.error(f"Corner detection error: {e}")
            return None
    
    def _calculate_warp_matrix(self):
        """Calculate warp matrix from calibration samples."""
        if not self.current_sample or len(self.current_sample) < 4:
            return
        
        # Use the most recent sample for real-time warping
        source_points = np.array(self.current_sample, dtype=np.float32)
        
        # Define destination points (ideal positions)
        dest_points = np.array([
            [0.0, 0.0],      # top-left
            [1.0, 0.0],      # top-right
            [0.0, 1.0],      # bottom-left
            [1.0, 1.0]       # bottom-right
        ], dtype=np.float32)
        
        # Calculate homography matrix
        try:
            self.homography_matrix, mask = cv2.findHomography(source_points, dest_points, cv2.LMEDS)
            
            if self.homography_matrix is not None:
                # Normalize matrix
                self.homography_matrix = self.homography_matrix / self.homography_matrix[2, 2]
                
                # Update warp matrix
                self.warp_matrix = self.homography_matrix
                
                # Apply calibration matrix for convergence
                self._apply_calibration_matrix()
                
        except Exception as e:
            self.logger.error(f"Error calculating warp matrix: {e}")
    
    def _apply_calibration_matrix(self):
        """Apply calibration matrix for convergence."""
        # Create a smoothed version of the warp matrix
        smoothed_matrix = 0.8 * self.homography_matrix + 0.2 * self.calibration_matrix
        
        # Update calibration matrix
        self.calibration_matrix = smoothed_matrix
        
        # Update warp matrix with smoothed version
        self.warp_matrix = smoothed_matrix
    
    def _check_convergence(self) -> bool:
        """Check if calibration has converged."""
        if len(self.calibration_samples) < 2:
            return False
        
        # Compare last two samples
        last_sample = np.array(self.calibration_samples[-1])
        prev_sample = np.array(self.calibration_samples[-2])
        
        # Calculate difference
        diff = np.abs(last_sample - prev_sample)
        max_diff = np.max(diff)
        
        # Check if difference is below threshold
        if max_diff < self.convergence_threshold:
            self.logger.debug(f"Calibration converged (max diff: {max_diff:.6f})")
            return True
        
        return False
    
    def _finalize_calibration(self):
        """Finalize calibration and save results."""
        try:
            self.state = CalibrationState.COMPLETE
            self.logger.info("Calibration completed successfully")
            
            # Apply final calibration
            self._apply_calibration_matrix()
            
            # Save calibration if enabled
            if self.config["save_calibration"]:
                self._save_calibration()
            
            # Trigger completion callback
            self._on_calibration_complete()
            
        except Exception as e:
            self.logger.error(f"Error finalizing calibration: {e}")
            self.state = CalibrationState.FAILED
    
    def _apply_calibration_matrix(self):
        """Apply final calibration matrix."""
        # Apply the calibration matrix to the renderer
        if self.renderer:
            # This would set the warp matrix in the renderer
            pass
    
    def _save_calibration(self):
        """Save calibration to file."""
        calibration_data = {
            "corners": {
                "top_left": [self.corners["top_left"].x, self.corners["top_left"].y],
                "top_right": [self.corners["top_right"].x, self.corners["top_right"].y],
                "bottom_left": [self.corners["bottom_left"].x, self.corners["bottom_left"].y],
                "bottom_right": [self.corners["bottom_right"].x, self.corners["bottom_right"].y]
            },
            "homography_matrix": self.homography_matrix.tolist(),
            "warp_matrix": self.warp_matrix.tolist(),
            "calibration_matrix": self.calibration_matrix.tolist(),
            "timestamp": time.time(),
            "version": "2.0.0"
        }
        
        try:
            with open(self.config["calibration_file"], 'w') as f:
                json.dump(calibration_data, f, indent=2)
            
            self.logger.info(f"Calibration saved to {self.config['calibration_file']}")
            
        except Exception as e:
            self.logger.error(f"Error saving calibration: {e}")
    
    def _load_calibration(self):
        """Load calibration from file."""
        try:
            with open(self.config["calibration_file"], 'r') as f:
                calibration_data = json.load(f)
            
            # Apply loaded calibration
            corners = calibration_data.get("corners", {})
            
            if "top_left" in corners:
                self.corners["top_left"] = CornerPoint(
                    x=corners["top_left"][0],
                    y=corners["top_left"][1],
                    id=0
                )
            
            if "top_right" in corners:
                self.corners["top_right"] = CornerPoint(
                    x=corners["top_right"][0],
                    y=corners["top_right"][1],
                    id=1
                )
            
            if "bottom_left" in corners:
                self.corners["bottom_left"] = CornerPoint(
                    x=corners["bottom_left"][0],
                    y=corners["bottom_left"][1],
                    id=2
                )
            
            if "bottom_right" in corners:
                self.corners["bottom_right"] = CornerPoint(
                    x=corners["bottom_right"][0],
                    y=corners["bottom_right"][1],
                    id=3
                )
            
            # Load matrices
            if "homography_matrix" in calibration_data:
                self.homography_matrix = np.array(
                    calibration_data["homography_matrix"],
                    dtype=np.float32
                )
            
            if "warp_matrix" in calibration_data:
                self.warp_matrix = np.array(
                    calibration_data["warp_matrix"],
                    dtype=np.float32
                )
            
            if "calibration_matrix" in calibration_data:
                self.calibration_matrix = np.array(
                    calibration_data["calibration_matrix"],
                    dtype=np.float32
                )
            
            self.state = CalibrationState.COMPLETE
            self.logger.info(f"Calibration loaded from {self.config['calibration_file']}")
            
        except FileNotFoundError:
            self.logger.debug(f"No saved calibration found ({self.config['calibration_file']})")
        except Exception as e:
            self.logger.error(f"Error loading calibration: {e}")
    
    def _on_calibration_complete(self):
        """Callback for calibration completion."""
        # This would trigger UI updates and other systems
        self.logger.info("Calibration completion callback triggered")
    
    def get_warp_matrix(self) -> np.ndarray:
        """Get the current warp matrix."""
        return self.warp_matrix.copy()
    
    def get_homography_matrix(self) -> np.ndarray:
        """Get the current homography matrix."""
        return self.homography_matrix.copy()
    
    def get_calibration_state(self) -> Dict[str, Any]:
        """Get the current calibration state."""
        return {
            "state": self.state.value,
            "num_samples": len(self.calibration_samples),
            "max_samples": self.max_samples,
            "convergence_threshold": self.convergence_threshold,
            "corners": {
                name: {
                    "x": corner.x,
                    "y": corner.y,
                    "detected": corner.detected,
                    "confidence": corner.confidence
                }
                for name, corner in self.corners.items()
            }
        }
    
    def is_calibrated(self) -> bool:
        """Check if calibration is complete."""
        return self.state == CalibrationState.COMPLETE
    
    def set_mesh_enabled(self, enabled: bool):
        """Enable or disable mesh warping."""
        self.mesh_enabled = enabled
        if enabled:
            self._create_warp_mesh()
    
    def set_mesh_density(self, density: int):
        """Set mesh density."""
        self.mesh_density = max(2, min(20, density))  # Clamp between 2 and 20
        if self.mesh_enabled:
            self._create_warp_mesh()
    
    def get_mesh_vertices(self) -> List[Dict]:
        """Get current mesh vertices."""
        return self.mesh_vertices.copy()
    
    def get_mesh_faces(self) -> List[List[int]]:
        """Get current mesh faces."""
        return self.mesh_faces.copy()
    
    def apply_warp_to_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply warp transformation to a frame.
        
        Args:
            frame: Input frame
            
        Returns:
            Warped frame
        """
        if not self.is_calibrated():
            return frame
        
        try:
            # Apply homography warp
            warped = cv2.warpPerspective(
                frame,
                self.homography_matrix,
                (frame.shape[1], frame.shape[0])
            )
            
            return warped
            
        except Exception as e:
            self.logger.error(f"Error applying warp: {e}")
            return frame
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            "state": self.state.value,
            "num_samples": len(self.calibration_samples),
            "max_samples": self.max_samples,
            "convergence_threshold": self.convergence_threshold,
            "mesh_enabled": self.mesh_enabled,
            "mesh_density": self.mesh_density,
            "num_vertices": len(self.mesh_vertices),
            "num_faces": len(self.mesh_faces),
            "warp_matrix_applied": self.is_calibrated()
        }
    
    def stop_updates(self):
        """Stop the update thread."""
        self.update_running = False
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=2.0)
            self.logger.info("Projector warp update thread stopped")

if __name__ == "__main__":
    # Test the ProjectorWarp class
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    print("Testing ProjectorWarp...")
    
    # Create mock renderer
    class MockRenderer:
        def __init__(self):
            self.ctx = None
            self.width = 1920
            self.height = 1080
    
    # Initialize warp system
    renderer = MockRenderer()
    warp = ProjectorWarp(renderer)
    
    print("ProjectorWarp initialized successfully")
    print("Note: Full warp testing requires actual camera input")