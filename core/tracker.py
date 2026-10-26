#!/usr/bin/env python3
"""
Threaded pose tracking module for Phantom Engine.

Provides real-time 3D pose detection using MediaPipe with smoothing,
scaling, and threaded processing for optimal performance.
"""

import cv2
import numpy as np
import threading
import time
import queue
from typing import Optional, List, Dict, Tuple, Any
import logging
import mediapipe as mp
from mediapipe.python.solutions.pose import Pose, PoseLandmark, PoseLandmarkEnum
from dataclasses import dataclass, field
from enum import Enum

from core.camera_probe import get_camera_probe
class TrackingState(Enum):
    """States for the pose tracking system."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    TRACKING = "tracking"
    PAUSED = "paused"
    ERROR = "error"
@dataclass
class PoseKeypoint:
    """
    Represents a single 3D pose keypoint from MediaPipe.
    
    Attributes:
        id: Unique identifier for the landmark
        x: Normalized x coordinate (0-1)
        y: Normalized y coordinate (0-1)  
        z: Normalized z coordinate (depth) (-1 to 1)
        visibility: Confidence score (0-1)
        presence: Whether the landmark is visible
        timestamp: Time when keypoint was detected
        smoothed: Whether this is a smoothed version
        world_coords: 3D world coordinates (if available)
    """
    id: int
    x: float
    y: float
    z: float
    visibility: float
    presence: bool
    timestamp: float
    smoothed: bool = False
    world_coords: Optional[Tuple[float, float, float]] = None
    
    @classmethod
    def from_mediapipe_landmark(cls, landmark: Any, landmark_id: int, smoothed: bool = False, timestamp: Optional[float] = None) -> 'PoseKeypoint':
        """Create a PoseKeypoint from a MediaPipe landmark."""
        if timestamp is None:
            timestamp = time.time()
        
        # Extract landmark data
        x = landmark.x
        y = landmark.y
        z = landmark.z
        visibility = landmark.visibility if hasattr(landmark, 'visibility') else 1.0
        
        # Convert normalized coordinates to absolute (0-1 range)
        presence = visibility > 0.5
        
        # Convert to world coordinates if available
        world_coords = None
        if hasattr(landmark, 'x_translation') and hasattr(landmark, 'y_translation') and hasattr(landmark, 'z_translation'):
            # MediaPipe 3D world coordinates
            world_coords = (landmark.x_translation, landmark.y_translation, landmark.z_translation)
        
        return cls(
            id=landmark_id,
            x=x,
            y=y,
            z=z,
            visibility=visibility,
            presence=presence,
            timestamp=timestamp,
            smoothed=smoothed,
            world_coords=world_coords
        )
@dataclass
class SkeletonStructure:
    """Defines the skeletal structure for bone mapping."""
    
    # MediaPipe landmark IDs
    NOSE = 0
    LEFT_EYE_INNER = 1
    LEFT_EYE = 2
    LEFT_EYE_OUTER = 3
    RIGHT_EYE_INNER = 4
    RIGHT_EYE = 5
    RIGHT_EYE_OUTER = 6
    LEFT_EAR = 7
    RIGHT_EAR = 8
    MOUTH_LEFT = 9
    MOUTH_RIGHT = 10
    
    # Torso
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 13
    RIGHT_HIP = 14
    
    # Arms
    LEFT_ELBOW = 15
    RIGHT_ELBOW = 16
    LEFT_WRIST = 17
    RIGHT_WRIST = 18
    
    # Legs
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    
    # Additional joints for full skeleton
    LEFT_PINKY = 19
    LEFT_INDEX = 20
    LEFT_THUMB = 21
    RIGHT_PINKY = 22
    RIGHT_INDEX = 23
    RIGHT_THUMB = 24

class PoseTracker:
    """
    Real-time 3D pose tracking system with MediaPipe and EMA smoothing.
    
    Features:
    - Threaded processing for smooth performance
    - Exponential Moving Average (EMA) filtering for noise reduction
    - Depth scaling and coordinate transformation
    - Multi-camera support with automatic selection
    - Performance monitoring and metrics collection
    """
    
    def __init__(self, config: Optional[dict] = None):
        """
        Initialize pose tracker with configuration.
        
        Args:
            config: Optional configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.config = config or {}
        self.model_complexity = self.config.get("model_complexity", 1)
        self.smooth_landmarks = self.config.get("smooth_landmarks", True)
        self.tracking_concurrency = self.config.get("tracking_concurrency", 1)
        self.max_num_hands = self.config.get("max_num_hands", 2)
        self.min_detection_confidence = self.config.get("min_detection_confidence", 0.5)
        self.min_tracking_confidence = self.config.get("min_tracking_confidence", 0.5)
        
        # Feature flags
        self.enable_hand_tracking = self.config.get("enable_hand_tracking", False)
        self.enable_face_tracking = self.config.get("enable_face_tracking", False)
        self.use_world_landmarks = self.config.get("use_world_landmarks", True)
        self.output_scale = self.config.get("output_scale", 1.0)
        self.filtering_enabled = self.config.get("filtering_enabled", True)
        self.ema_alpha = self.config.get("ema_alpha", 0.3)
        
        # Depth scaling
        depth_scaling = self.config.get("depth_scaling", {"base_distance": 100.0, "scale_factor": 1.0})
        self.base_distance = depth_scaling.get("base_distance", 100.0)
        self.scale_factor = depth_scaling.get("scale_factor", 1.0)
        
        # Tracking state
        self.state = TrackingState.INITIALIZING
        self.latest_keypoints: Optional[List[PoseKeypoint]] = None
        self.latest_keypoints_time = 0
        self.latest_keypoints_world: Optional[List[PoseKeypoint]] = None
        
        # Threading
        self.keypoint_queue = queue.Queue(maxsize=10)
        self.processing_thread = None
        self.stopped = False
        
        # Smoothing and filtering
        self.raw_keypoints = []
        self.smoothed_keypoints = []
        self.ema_history = {}
        
        # Performance monitoring
        self.frames_processed = 0
        self.detections_count = 0
        self.avg_processing_time = 0.0
        self.last_perf_check = time.time()
        
        # Camera and device info
        self.camera_probe = get_camera_probe()
        self.available_cameras = self.camera_probe.scan_cameras()
        
        # Initialize MediaPipe pose solution
        self._initialize_mediapipe()
        
        # Start processing thread
        self.start_processing()
    
    def _initialize_mediapipe(self):
        """Initialize MediaPipe pose solution with optimal settings."""
        try:
            # Configure pose solution options
            pose_options = mp.solutions.pose.PoseOptions(
                model_complexity=self.model_complexity,
                smooth_landmarks=self.smooth_landmarks,
                enable_segmentation=False,
                refine_face_landmarks=self.enable_face_tracking,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence
            )
            
            # Create pose solution
            self.pose = Pose(
                static_image_mode=False,
                max_num_hands=self.max_num_hands if self.enable_hand_tracking else 0,
                model_complexity=self.model_complexity,
                smooth_landmarks=self.smooth_landmarks,
                enable_segmentation=False,
                refine_face_landmarks=self.enable_face_tracking,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence
            )
            
            self.logger.info("MediaPipe Pose solution initialized successfully")
            self.state = TrackingState.IDLE
            
        except Exception as e:
            self.logger.error(f"Failed to initialize MediaPipe Pose: {e}")
            self.state = TrackingState.ERROR
            raise
    
    def start_processing(self):
        """Start the background processing thread."""
        if self.processing_thread is None or not self.processing_thread.is_alive():
            self.stopped = False
            self.processing_thread = threading.Thread(
                target=self._processing_loop,
                daemon=True,
                name="PoseTracker"
            )
            self.processing_thread.start()
            self.logger.info("Pose tracker processing thread started")
    
    def stop_processing(self):
        """Stop the processing thread gracefully."""
        self.stopped = True
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)
            self.logger.info("Pose tracker processing thread stopped")
        
        # Cleanup
        if hasattr(self, 'pose'):
            self.pose.close()
    
    def process_frame(self, frame: np.ndarray) -> Optional[List[PoseKeypoint]]:
        """
        Process a single video frame for pose detection.
        
        Args:
            frame: Input BGR image frame
            
        Returns:
            List of PoseKeypoint objects, or None if no pose detected
        """
        if self.state == TrackingState.ERROR:
            return None
        
        if self.state == TrackingState.INITIALIZING:
            # Brief delay while initializing
            time.sleep(0.1)
            return None
        
        try:
            # Convert frame to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process frame with MediaPipe
            results = self.pose.process(rgb_frame)
            
            if results.pose_landmarks:
                # Convert landmarks to PoseKeypoint objects
                current_time = time.time()
                
                # Process landmarks in world coordinates if enabled
                if self.use_world_landmarks and hasattr(results, 'pose_world_landmarks'):
                    keypoints = self._convert_landmarks_to_keypoints(
                        results.pose_landmarks,
                        results.pose_world_landmarks,
                        current_time,
                        smoothed=True
                    )
                else:
                    keypoints = self._convert_landmarks_to_keypoints(
                        results.pose_landmarks,
                        None,
                        current_time,
                        smoothed=self.smooth_landmarks
                    )
                
                # Add to queue for processing
                try:
                    self.keypoint_queue.put({
                        "keypoints": keypoints,
                        "timestamp": current_time,
                        "frame_shape": frame.shape
                    }, timeout=0.1)
                except queue.Full:
                    # Remove oldest item
                    try:
                        self.keypoint_queue.get_nowait()
                        self.keypoint_queue.put({
                            "keypoints": keypoints,
                            "timestamp": current_time,
                            "frame_shape": frame.shape
                        }, timeout=0.1)
                    except:
                        pass
                
                self.detections_count += 1
                return keypoints
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error processing frame: {e}")
            self.state = TrackingState.ERROR
            return None
    
    def _convert_landmarks_to_keypoints(self, landmarks, world_landmarks, timestamp: float, smoothed: bool) -> List[PoseKeypoint]:
        """Convert MediaPipe landmarks to PoseKeypoint objects."""
        keypoints = []
        
        # Define the key landmarks we care about for skeleton tracking
        key_landmarks = [
            PoseLandmark.NOSE,
            PoseLandmark.LEFT_SHOULDER,
            PoseLandmark.RIGHT_SHOULDER,
            PoseLandmark.LEFT_ELBOW,
            PoseLandmark.RIGHT_ELBOW,
            PoseLandmark.LEFT_WRIST,
            PoseLandmark.RIGHT_WRIST,
            PoseLandmark.LEFT_HIP,
            PoseLandmark.RIGHT_HIP,
            PoseLandmark.LEFT_KNEE,
            PoseLandmark.RIGHT_KNEE,
            PoseLandmark.LEFT_ANKLE,
            PoseLandmark.RIGHT_ANKLE,
        ]
        
        for landmark_id in key_landmarks:
            landmark = landmarks.landmark[landmark_id]
            
            # Create PoseKeypoint
            keypoint = PoseKeypoint.from_mediapipe_landmark(
                landmark, landmark_id, smoothed, timestamp
            )
            
            # Apply depth scaling if enabled
            if self.filtering_enabled and not smoothed:
                keypoint = self._apply_depth_scaling(keypoint)
            
            keypoints.append(keypoint)
        
        return keypoints
    
    def _apply_depth_scaling(self, keypoint: PoseKeypoint) -> 'PoseKeypoint':
        """Apply depth scaling to a keypoint based on camera distance."""
        # Simple depth scaling based on Z coordinate
        original_z = keypoint.z
        
        # Apply scaling factor
        scaled_z = original_z * self.scale_factor
        
        # Apply base distance adjustment
        scaled_z = scaled_z + (self.base_distance * (1 - self.scale_factor))
        
        # Create new keypoint with scaled Z coordinate
        return PoseKeypoint(
            id=keypoint.id,
            x=keypoint.x,
            y=keypoint.y,
            z=scaled_z,
            visibility=keypoint.visibility,
            presence=keypoint.presence,
            timestamp=keypoint.timestamp,
            smoothed=keypoint.smoothed,
            world_coords=keypoint.world_coords
        )
    
    def _processing_loop(self):
        """Background processing loop for smoothing and filtering."""
        self.start_processing()
        
        while not self.stopped:
            try:
                # Get latest keypoint batch
                try:
                    batch = self.keypoint_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                keypoints = batch["keypoints"]
                timestamp = batch["timestamp"]
                frame_shape = batch["frame_shape"]
                
                # Apply smoothing if enabled
                if self.filtering_enabled and self.smoothed_keypoints:
                    smoothed = self._apply_ema_filtering(keypoints)
                else:
                    smoothed = keypoints
                
                # Update latest keypoints
                self.latest_keypoints = smoothed
                self.latest_keypoints_time = timestamp
                
                # Apply additional filtering
                if self.filtering_enabled:
                    self.latest_keypoints = self._apply_spatial_filtering(self.latest_keypoints)
                
                # Performance monitoring
                self.frames_processed += 1
                
                # Update performance metrics
                current_time = time.time()
                if current_time - self.last_perf_check > 1.0:
                    self.avg_processing_time = 1.0 / max(1, self.frames_processed - self.last_perf_check)
                    self.last_perf_check = current_time
                    self.frames_processed = 0
                
            except Exception as e:
                self.logger.error(f"Processing loop error: {e}")
                time.sleep(0.1)
        
        self.logger.info("Pose tracker processing loop stopped")
    
    def _apply_ema_filtering(self, keypoints: List[PoseKeypoint]) -> List[PoseKeypoint]:
        """Apply Exponential Moving Average filtering to keypoints."""
        smoothed = []
        
        for keypoint in keypoints:
            key = keypoint.id
            
            # Initialize EMA for this keypoint
            if key not in self.ema_history:
                self.ema_history[key] = {
                    "value": (keypoint.x, keypoint.y, keypoint.z),
                    "alpha": self.ema_alpha
                }
            
            # Apply EMA filter
            ema_data = self.ema_history[key]
            alpha = ema_data["alpha"]
            
            # Update EMA
            old_value = ema_data["value"]
            new_value = (
                alpha * keypoint.x + (1 - alpha) * old_value[0],
                alpha * keypoint.y + (1 - alpha) * old_value[1],
                alpha * keypoint.z + (1 - alpha) * old_value[2]
            )
            
            ema_data["value"] = new_value
            
            # Create smoothed keypoint
            smoothed_keypoint = PoseKeypoint(
                id=keypoint.id,
                x=new_value[0],
                y=new_value[1],
                z=new_value[2],
                visibility=keypoint.visibility,
                presence=keypoint.presence,
                timestamp=keypoint.timestamp,
                smoothed=True,
                world_coords=keypoint.world_coords
            )
            
            smoothed.append(smoothed_keypoint)
        
        return smoothed
    
    def _apply_spatial_filtering(self, keypoints: List[PoseKeypoint]) -> List[PoseKeypoint]:
        """Apply spatial filtering based on joint relationships."""
        filtered = []
        
        for keypoint in keypoints:
            # Skip if keypoint has low confidence
            if keypoint.visibility < 0.3:
                filtered.append(keypoint)
                continue
            
            # Apply spatial constraints based on joint relationships
            filtered_keypoint = self._apply_joint_constraints(keypoint, keypoints)
            filtered.append(filtered_keypoint)
        
        return filtered
    
    def _apply_joint_constraints(self, keypoint: PoseKeypoint, all_keypoints: List[PoseKeypoint]) -> PoseKeypoint:
        """Apply spatial constraints based on joint relationships."""
        # Find related joints (parent/child relationships)
        related_joints = self._get_related_joints(keypoint.id)
        
        if not related_joints:
            return keypoint
        
        # Get positions of related joints
        related_positions = []
        for rel_id in related_joints:
            for kp in all_keypoints:
                if kp.id == rel_id:
                    related_positions.append((kp.x, kp.y, kp.z))
                    break
        
        if len(related_positions) < 2:
            return keypoint
        
        # Calculate expected position based on joint relationships
        # This is a simplified constraint - real implementations would use
        # more sophisticated IK (Inverse Kinematics) algorithms
        
        return keypoint
    
    def _get_related_joints(self, landmark_id: int) -> List[int]:
        """Get joints related to a given landmark based on skeletal structure."""
        # Define bone/joint relationships
        relationships = {
            PoseLandmark.LEFT_SHOULDER: [PoseLandmark.LEFT_ELBOW, PoseLandmark.LEFT_HIP, PoseLandmark.NOSE],
            PoseLandmark.RIGHT_SHOULDER: [PoseLandmark.RIGHT_ELBOW, PoseLandmark.RIGHT_HIP, PoseLandmark.NOSE],
            PoseLandmark.LEFT_ELBOW: [PoseLandmark.LEFT_SHOULDER, PoseLandmark.LEFT_WRIST],
            PoseLandmark.RIGHT_ELBOW: [PoseLandmark.RIGHT_SHOULDER, PoseLandmark.RIGHT_WRIST],
            PoseLandmark.LEFT_WRIST: [PoseLandmark.LEFT_ELBOW],
            PoseLandmark.RIGHT_WRIST: [PoseLandmark.RIGHT_ELBOW],
            PoseLandmark.LEFT_HIP: [PoseLandmark.LEFT_SHOULDER, PoseLandmark.LEFT_KNEE, PoseLandmark.RIGHT_HIP],
            PoseLandmark.RIGHT_HIP: [PoseLandmark.RIGHT_SHOULDER, PoseLandmark.RIGHT_KNEE, PoseLandmark.LEFT_HIP],
            PoseLandmark.LEFT_KNEE: [PoseLandmark.LEFT_HIP, PoseLandmark.LEFT_ANKLE],
            PoseLandmark.RIGHT_KNEE: [PoseLandmark.RIGHT_HIP, PoseLandmark.RIGHT_ANKLE],
            PoseLandmark.LEFT_ANKLE: [PoseLandmark.LEFT_KNEE],
            PoseLandmark.RIGHT_ANKLE: [PoseLandmark.RIGHT_KNEE],
        }
        
        return relationships.get(landmark_id, [])
    
    def get_latest_keypoints(self) -> Optional[List[PoseKeypoint]]:
        """Get the latest processed keypoints."""
        return self.latest_keypoints
    
    def get_latest_keypoints_world(self) -> Optional[List[PoseKeypoint]]:
        """Get the latest keypoints in world coordinates."""
        return self.latest_keypoints_world
    
    def get_latest_keypoints_time(self) -> float:
        """Get timestamp of latest keypoints."""
        return self.latest_keypoints_time
    
    def set_latest_keypoints(self, keypoints: List[PoseKeypoint]):
        """Set latest keypoints directly (for rigging integration)."""
        self.latest_keypoints = keypoints
        self.latest_keypoints_time = time.time()
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics for the tracker."""
        return {
            "state": self.state.value,
            "frames_processed": self.frames_processed,
            "detections_count": self.detections_count,
            "avg_processing_time_ms": self.avg_processing_time * 1000,
            "queue_size": self.keypoint_queue.qsize(),
            "available_cameras": len(self.available_cameras),
            "has_pose": hasattr(self, 'pose') and self.pose is not None
        }
    
    def reset(self):
        """Reset the tracker state."""
        self.latest_keypoints = None
        self.latest_keypoints_time = 0
        self.raw_keypoints = []
        self.smoothed_keypoints = []
        self.ema_history = {}
        
        if hasattr(self, 'pose'):
            self.pose.close()
            self._initialize_mediapipe()
        
        self.state = TrackingState.IDLE
        self.logger.info("Pose tracker reset")
    
    def set_tracking_enabled(self, enabled: bool):
        """Enable or disable tracking."""
        if enabled:
            self.state = TrackingState.TRACKING
        else:
            self.state = TrackingState.PAUSED
        
        self.logger.info(f"Pose tracking {'enabled' if enabled else 'disabled'}")

class SkeletonRigging:
    """
    Skeleton rigging and inverse kinematics system.
    
    Translates MediaPipe 3D pose landmarks into bone matrices and applies
    inverse kinematics for realistic skeleton animations.
    """
    
    def __init__(self, config: Optional[dict] = None):
        """
        Initialize skeleton rigging system.
        
        Args:
            config: Optional configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.config = config or {}
        self.ik_solver = self.config.get("ik_solver", "faberique")
        self.bone_weight = self.config.get("bone_weight", 0.5)
        self.shoulder_offset = np.array(self.config.get("shoulder_offset", [0.0, 0.0, 0.0]), dtype=np.float32)
        self.hip_offset = np.array(self.config.get("hip_offset", [0.0, 0.0, 0.0]), dtype=np.float32)
        self.knee_bend_limit = self.config.get("knee_bend_limit", 0.8)
        self.elbow_twist_compensation = self.config.get("elbow_twist_compensation", True)
        self.auto_calibration = self.config.get("auto_calibration", True)
        
        # Joint offset mapping
        self.joint_offset_mapping = self.config.get("joint_offset_mapping", {})
        
        # Bone matrix storage
        self.bone_matrices = {}
        self.joint_transforms = {}
        
        # Calibration data
        self.calibration_samples = []
        self.calibration_baseline = {}
        
        # Performance
        self.ik_iterations = 0
        self.total_bones = 0
    
    def apply_rigging(self, keypoints: List[PoseKeypoint]) -> Dict[str, np.ndarray]:
        """
        Apply rigging transformations to keypoints.
        
        Args:
            keypoints: List of PoseKeypoint objects from MediaPipe
            
        Returns:
            Dictionary of bone matrices keyed by bone name
        """
        if not keypoints:
            return {}
        
        try:
            # Convert keypoints to joint format
            joints = self._keypoints_to_joints(keypoints)
            
            # Apply rigging transformations
            bone_matrices = self._calculate_bone_matrices(joints)
            
            # Apply inverse kinematics
            ik_matrices = self._apply_inverse_kinematics(joints)
            
            # Combine results
            self.bone_matrices = {**bone_matrices, **ik_matrices}
            self.joint_transforms = self._calculate_joint_transforms(joints)
            
            return self.bone_matrices
            
        except Exception as e:
            self.logger.error(f"Error in rigging: {e}")
            return {}
    
    def _keypoints_to_joints(self, keypoints: List[PoseKeypoint]) -> Dict[int, Dict[str, float]]:
        """Convert PoseKeypoint objects to joint dictionary format."""
        joints = {}
        
        for keypoint in keypoints:
            # Apply joint offset mapping if configured
            offset = self.joint_offset_mapping.get(keypoint.id, {})
            
            joint = {
                "position": (keypoint.x, keypoint.y, keypoint.z),
                "visibility": keypoint.visibility,
                "smoothed": keypoint.smoothed
            }
            
            # Apply offsets
            if offset:
                joint["position"] = (
                    keypoint.x + offset.get("x", 0.0),
                    keypoint.y + offset.get("y", 0.0),
                    keypoint.z + offset.get("z", 0.0)
                )
            
            # Apply bone-specific offsets
            if keypoint.id == PoseLandmark.LEFT_SHOULDER or keypoint.id == PoseLandmark.RIGHT_SHOULDER:
                joint["position"] = (
                    keypoint.x + self.shoulder_offset[0],
                    keypoint.y + self.shoulder_offset[1],
                    keypoint.z + self.shoulder_offset[2]
                )
            
            elif keypoint.id == PoseLandmark.LEFT_HIP or keypoint.id == PoseLandmark.RIGHT_HIP:
                joint["position"] = (
                    keypoint.x + self.hip_offset[0],
                    keypoint.y + self.hip_offset[1],
                    keypoint.z + self.hip_offset[2]
                )
            
            joints[keypoint.id] = joint
        
        return joints
    
    def _calculate_bone_matrices(self, joints: Dict[int, Dict[str, float]]) -> Dict[str, np.ndarray]:
        """Calculate bone transformation matrices from joint positions."""
        bone_matrices = {}
        
        # Define bone connections (parent-child relationships)
        bones = [
            ("left_shoulder_to_left_elbow", PoseLandmark.LEFT_SHOULDER, PoseLandmark.LEFT_ELBOW),
            ("right_shoulder_to_right_elbow", PoseLandmark.RIGHT_SHOULDER, PoseLandmark.RIGHT_ELBOW),
            ("left_elbow_to_left_wrist", PoseLandmark.LEFT_ELBOW, PoseLandmark.LEFT_WRIST),
            ("right_elbow_to_right_wrist", PoseLandmark.RIGHT_ELBOW, PoseLandmark.RIGHT_WRIST),
            ("left_hip_to_left_knee", PoseLandmark.LEFT_HIP, PoseLandmark.LEFT_KNEE),
            ("right_hip_to_right_knee", PoseLandmark.RIGHT_HIP, PoseLandmark.RIGHT_KNEE),
            ("left_knee_to_left_ankle", PoseLandmark.LEFT_KNEE, PoseLandmark.LEFT_ANKLE),
            ("right_knee_to_right_ankle", PoseLandmark.RIGHT_KNEE, PoseLandmark.RIGHT_ANKLE),
            ("pelvis_to_left_hip", PoseLandmark.NOSE, PoseLandmark.LEFT_HIP),  # Simplified torso
            ("pelvis_to_right_hip", PoseLandmark.NOSE, PoseLandmark.RIGHT_HIP),
        ]
        
        for bone_name, parent_id, child_id in bones:
            if parent_id in joints and child_id in joints:
                parent = joints[parent_id]
                child = joints[child_id]
                
                # Calculate bone matrix
                bone_matrix = self._calculate_single_bone_matrix(parent, child, bone_name)
                bone_matrices[bone_name] = bone_matrix
        
        return bone_matrices
    
    def _calculate_single_bone_matrix(self, parent: Dict, child: Dict, bone_name: str) -> np.ndarray:
        """Calculate transformation matrix for a single bone."""
        # Calculate bone vector
        parent_pos = np.array(parent["position"], dtype=np.float32)
        child_pos = np.array(child["position"], dtype=np.float32)
        bone_vector = child_pos - parent_pos
        
        # Calculate bone length
        bone_length = np.linalg.norm(bone_vector)
        if bone_length < 0.001:
            bone_length = 0.001
        
        # Calculate bone direction (normalized)
        bone_direction = bone_vector / bone_length
        
        # Calculate rotation (simplified - in real implementation would use
        # more sophisticated IK algorithms)
        # For now, create identity rotation with appropriate scaling
        bone_matrix = np.eye(4, dtype=np.float32)
        
        # Apply translation
        bone_matrix[:3, 3] = parent_pos
        
        # Apply scaling (bone length)
        scale_factor = bone_length / 0.1  # Normalize to reference length
        bone_matrix[0, 0] = scale_factor
        bone_matrix[1, 1] = scale_factor
        bone_matrix[2, 2] = scale_factor
        
        # Apply rotation to align with bone direction
        # This is a simplified approach - real implementation would
        # use proper joint orientation and rotation matrices
        bone_matrix[:3, 2] = bone_direction  # Align Z-axis with bone direction
        
        return bone_matrix
    
    def _apply_inverse_kinematics(self, joints: Dict[int, Dict[str, float]]) -> Dict[str, np.ndarray]:
        """Apply inverse kinematics to refine bone positions."""
        ik_matrices = {}
        
        # Simplified IK implementation
        # In a production system, this would use proper IK solvers
        
        # Shoulder/elbow constraints
        for side in ["left", "right"]:
            shoulder_id = PoseLandmark.LEFT_SHOULDER if side == "left" else PoseLandmark.RIGHT_SHOULDER
            elbow_id = PoseLandmark.LEFT_ELBOW if side == "left" else PoseLandmark.RIGHT_ELBOW
            wrist_id = PoseLandmark.LEFT_WRIST if side == "left" else PoseLandmark.RIGHT_WRIST
            
            if all(joint_id in joints for joint_id in [shoulder_id, elbow_id, wrist_id]):
                # Simple elbow bending constraint
                shoulder_pos = np.array(joints[shoulder_id]["position"], dtype=np.float32)
                elbow_pos = np.array(joints[elbow_id]["position"], dtype=np.float32)
                wrist_pos = np.array(joints[wrist_id]["position"], dtype=np.float32)
                
                # Calculate elbow position with IK
                shoulder_to_elbow = elbow_pos - shoulder_pos
                elbow_to_wrist = wrist_pos - elbow_pos
                
                # Simple IK adjustment - keep elbow at reasonable distance
                elbow_distance = np.linalg.norm(elbow_to_wrist)
                if elbow_distance > 0.5:  # Maximum elbow extension
                    # Bend elbow towards shoulder
                    elbow_pos = shoulder_pos + shoulder_to_elbow * 0.7
                
                # Create adjusted bone matrix
                bone_matrix = self._calculate_single_bone_matrix(
                    joints[shoulder_id], 
                    {"position": elbow_pos.tolist()}, 
                    f"{side}_elbow_ik"
                )
                
                ik_matrices[f"{side}_elbow_ik"] = bone_matrix
        
        # Leg constraints
        for side in ["left", "right"]:
            hip_id = PoseLandmark.LEFT_HIP if side == "left" else PoseLandmark.RIGHT_HIP
            knee_id = PoseLandmark.LEFT_KNEE if side == "left" else PoseLandmark.RIGHT_KNEE
            ankle_id = PoseLandmark.LEFT_ANKLE if side == "left" else PoseLandmark.RIGHT_ANKLE
            
            if all(joint_id in joints for joint_id in [hip_id, knee_id, ankle_id]):
                # Knee bending constraint
                hip_pos = np.array(joints[hip_id]["position"], dtype=np.float32)
                knee_pos = np.array(joints[knee_id]["position"], dtype=np.float32)
                ankle_pos = np.array(joints[ankle_id]["position"], dtype=np.float32)
                
                # Calculate knee position with IK
                hip_to_knee = knee_pos - hip_pos
                knee_to_ankle = ankle_pos - knee_pos
                
                # Apply knee bend limit
                knee_angle = self._calculate_joint_angle(hip_to_knee, knee_to_ankle)
                if knee_angle > self.knee_bend_limit:
                    # Adjust knee position
                    knee_pos = hip_pos + hip_to_knee * (self.knee_bend_limit / knee_angle)
                
                # Create adjusted bone matrix
                bone_matrix = self._calculate_single_bone_matrix(
                    joints[hip_id],
                    {"position": knee_pos.tolist()},
                    f"{side}_knee_ik"
                )
                
                ik_matrices[f"{side}_knee_ik"] = bone_matrix
        
        self.ik_iterations += 1
        return ik_matrices
    
    def _calculate_joint_angle(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate angle between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm_product = np.linalg.norm(vec1) * np.linalg.norm(vec2)
        
        if norm_product < 0.001:
            return 0.0
        
        # Clamp to valid range for arccos
        cos_angle = max(-1.0, min(1.0, dot_product / norm_product))
        
        return np.arccos(cos_angle)
    
    def _calculate_joint_transforms(self, joints: Dict[int, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
        """Calculate individual joint transformation matrices."""
        joint_transforms = {}
        
        for joint_id, joint_data in joints.items():
            # Convert joint position to transformation matrix
            position = joint_data["position"]
            
            # Simple translation matrix
            transform = {
                "translation": position,
                "rotation": [0.0, 0.0, 0.0, 1.0],  # Identity quaternion
                "scale": [1.0, 1.0, 1.0],
                "joint_id": joint_id
            }
            
            joint_transforms[f"joint_{joint_id}"] = transform
        
        return joint_transforms
    
    def get_bone_matrices(self) -> Dict[str, np.ndarray]:
        """Get current bone matrices."""
        return self.bone_matrices.copy()
    
    def get_joint_transforms(self) -> Dict[str, Dict[str, float]]:
        """Get current joint transforms."""
        return self.joint_transforms.copy()
    
    def add_calibration_sample(self, keypoints: List[PoseKeypoint]):
        """Add a calibration sample for baseline calculation."""
        if self.auto_calibration:
            self.calibration_samples.append(keypoints)
            
            # Keep only recent samples for memory efficiency
            if len(self.calibration_samples) > self.config.get("calibration_samples", 30):
                self.calibration_samples.pop(0)
    
    def calculate_calibration_baseline(self):
        """Calculate baseline from calibration samples."""
        if not self.calibration_samples:
            return
        
        # Calculate average position for each joint
        joint_sums = {}
        joint_counts = {}
        
        for sample in self.calibration_samples:
            for keypoint in sample:
                joint_id = keypoint.id
                if joint_id not in joint_sums:
                    joint_sums[joint_id] = [0.0, 0.0, 0.0]
                    joint_counts[joint_id] = 0
                
                joint_sums[joint_id][0] += keypoint.x
                joint_sums[joint_id][1] += keypoint.y
                joint_sums[joint_id][2] += keypoint.z
                joint_counts[joint_id] += 1
        
        # Calculate averages
        self.calibration_baseline = {}
        for joint_id in joint_sums:
            count = joint_counts[joint_id]
            self.calibration_baseline[joint_id] = (
                joint_sums[joint_id][0] / count,
                joint_sums[joint_id][1] / count,
                joint_sums[joint_id][2] / count
            )
        
        self.logger.info(f"Calculated calibration baseline with {len(self.calibration_samples)} samples")
    
    def apply_calibration_offset(self, keypoints: List[PoseKeypoint]) -> List[PoseKeypoint]:
        """Apply calibration offsets to keypoints."""
        if not self.calibration_baseline:
            return keypoints
        
        adjusted_keypoints = []
        
        for keypoint in keypoints:
            joint_id = keypoint.id
            
            if joint_id in self.calibration_baseline:
                baseline = self.calibration_baseline[joint_id]
                
                # Apply offset from baseline
                offset_x = keypoint.x - baseline[0]
                offset_y = keypoint.y - baseline[1]
                offset_z = keypoint.z - baseline[2]
                
                # Apply offset (can be tuned for sensitivity)
                adjusted_keypoint = PoseKeypoint(
                    id=keypoint.id,
                    x=keypoint.x + offset_x * 0.1,  # Reduced sensitivity
                    y=keypoint.y + offset_y * 0.1,
                    z=keypoint.z + offset_z * 0.1,
                    visibility=keypoint.visibility,
                    presence=keypoint.presence,
                    timestamp=keypoint.timestamp,
                    smoothed=keypoint.smoothed,
                    world_coords=keypoint.world_coords
                )
            else:
                adjusted_keypoint = keypoint
            
            adjusted_keypoints.append(adjusted_keypoint)
        
        return adjusted_keypoints
    
    def get_calibration_baseline(self) -> Dict[int, Tuple[float, float, float]]:
        """Get the current calibration baseline."""
        return self.calibration_baseline.copy()

if __name__ == "__main__":
    # Test the PoseTracker and SkeletonRigging classes
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    print("Testing PoseTracker and SkeletonRigging...")
    
    # Create mock frame for testing
    test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # Initialize tracker
    tracker = PoseTracker()
    rigging = SkeletonRigging()
    
    # Test processing (would normally need actual camera)
    print("Components initialized successfully")
    print("Note: Actual testing requires camera input")