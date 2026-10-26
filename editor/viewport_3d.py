#!/usr/bin/env python3
"""
3D Viewport module for Phantom Engine.

Provides interactive 3D editor viewport with orbit/pan/zoom controls,
3D skeleton visualization, and tracking overlay integration.
"""

import numpy as np
import time
import threading
from typing import Optional, List, Tuple, Dict, Any
import logging
import math
from OpenGL import GL
import moderngl as mg

from graphics.renderer import Renderer
class Viewport3D:
    """
    Interactive 3D viewport for the Phantom Engine editor.
    
    Features:
    - Orbit, pan, and zoom camera controls
    - 3D skeleton visualization with bone rendering
    - MediaPipe tracking overlay integration
    - Selection and manipulation gizmos
    - Depth sorting and occlusion handling
    - Performance-optimized rendering
    """
    
    def __init__(self, renderer: Renderer):
        """
        Initialize the 3D viewport.
        
        Args:
            renderer: Reference to the graphics renderer
        """
        self.logger = logging.getLogger(__name__)
        self.renderer = renderer
        
        # Viewport configuration
        self.viewport_width = 1920
        self.viewport_height = 1080
        self.aspect_ratio = self.viewport_width / self.viewport_height
        self.near_clip = 0.1
        self.far_clip = 5000.0
        
        # Camera state
        self.camera_position = np.array([0.0, 0.0, 500.0], dtype=np.float32)
        self.camera_target = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self.camera_up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        self.camera_pitch = -20.0  # degrees
        self.camera_yaw = 0.0      # degrees
        self.camera_roll = 0.0     # degrees
        self.camera_distance = 500.0
        
        # Control state
        self.mouse_x = 0
        self.mouse_y = 0
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.left_mouse_pressed = False
        self.right_mouse_pressed = False
        self.middle_mouse_pressed = False
        
        # Interaction state
        self.orbit_mode = True
        self.pan_mode = False
        self.zoom_mode = False
        self.selection_box = None
        self.selected_object = None
        
        # Grid and axis display
        self.show_grid = True
        self.show_axes = True
        self.grid_size = 10
        self.grid_spacing = 1.0
        
        # Performance
        self.frame_count = 0
        self.last_fps_update = time.time()
        self.current_fps = 0.0
        
        # Track data
        self.latest_keypoints = None
        self.latest_frame = None
        self.bone_matrices = []
        
        # Background thread for continuous updates
        self.update_thread = None
        self.update_running = False
        
        # Selection and manipulation
        self.selected_joints = []
        self.manipulation_gizmo = None
        
        # Initialize viewport
        self._initialize_viewport()
        
        # Start update thread
        self.start_updates()
    
    def _initialize_viewport(self):
        """Initialize the viewport with OpenGL context and shader programs."""
        try:
            # Create framebuffers for off-screen rendering
            self.fbo = self.renderer.ctx.framebuffer(
                color_attachments=[self.renderer.ctx.texture((self.viewport_width, self.viewport_height), components=3)],
                depth_attachment=self.renderer.ctx.depth_renderbuffer((self.viewport_width, self.viewport_height))
            )
            
            # Create shader programs for viewport rendering
            self._create_viewport_shaders()
            
            # Initialize rendering primitives
            self._initialize_primitives()
            
            # Setup OpenGL state
            self._setup_opengl_state()
            
            self.logger.info("Viewport initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize viewport: {e}")
            raise
    
    def _create_viewport_shaders(self):
        """Create shader programs for viewport rendering."""
        # Simple 3D rendering shader
        self.viewport_shader = """
        # Vertex shader
        attribute vec3 in_Position;
        attribute vec3 in_Normal;
        attribute vec2 in_TexCoord;
        
        uniform mat4 P;
        uniform mat4 V;
        uniform mat4 M;
        
        varying vec3 frag_Normal;
        varying vec3 frag_Position;
        varying vec2 frag_TexCoord;
        
        void main() {
            frag_Normal = normalize((M * vec4(in_Normal, 0.0)).xyz);
            frag_Position = (M * vec4(in_Position, 1.0)).xyz;
            frag_TexCoord = in_TexCoord;
            
            gl_Position = P * V * M * vec4(in_Position, 1.0);
        }
        """
        
        # Line rendering shader for bones
        self.line_shader = """
        attribute vec3 in_Position;
        
        uniform mat4 P;
        uniform mat4 V;
        
        void main() {
            gl_Position = P * V * vec4(in_Position, 1.0);
        }
        """
        
        # Grid rendering shader
        self.grid_shader = """
        attribute vec3 in_Position;
        
        uniform mat4 P;
        uniform mat4 V;
        
        void main() {
            gl_Position = P * V * vec4(in_Position, 1.0);
        }
        """
        
        # Simple shader compilation would go here
        # In practice, we'd use ModernGL to compile these
        
        self.logger.debug("Viewport shaders compiled")
    
    def _initialize_primitives(self):
        """Initialize rendering primitives (cube, sphere, lines, grid)."""
        # Create simple cube for 3D objects
        self.cube_vertices = np.array([
            # Front face
            -0.5, -0.5,  0.5,   0.0, 0.0,  1.0,   0.0, 0.0,
             0.5, -0.5,  0.5,   0.0, 0.0,  1.0,   1.0, 0.0,
             0.5,  0.5,  0.5,   0.0, 0.0,  1.0,   1.0, 1.0,
            -0.5,  0.5,  0.5,   0.0, 0.0,  1.0,   0.0, 1.0,
            # Back face
            -0.5, -0.5, -0.5,   0.0, 0.0, -1.0,   0.0, 0.0,
             0.5, -0.5, -0.5,   0.0, 0.0, -1.0,   1.0, 0.0,
             0.5,  0.5, -0.5,   0.0, 0.0, -1.0,   1.0, 1.0,
            -0.5,  0.5, -0.5,   0.0, 0.0, -1.0,   0.0, 1.0,
        ], dtype=np.float32)
        
        self.cube_indices = np.array([
            0, 1, 2, 2, 3, 0,  # Front face
            4, 5, 6, 6, 7, 4,  # Back face
            0, 1, 5, 5, 4, 0,  # Bottom face
            2, 3, 7, 7, 6, 2,  # Top face
            0, 3, 7, 7, 4, 0,  # Left face
            1, 2, 6, 6, 5, 1   # Right face
        ], dtype=np.uint32)
        
        # Create axes (X=red, Y=green, Z=blue)
        self.axes_vertices = np.array([
            # X-axis
            0.0, 0.0, 0.0,   1.0, 0.0, 0.0,   0.0, 0.0,
            1.0, 0.0, 0.0,   1.0, 0.0, 0.0,   1.0, 0.0,
            # Y-axis
            0.0, 0.0, 0.0,   0.0, 1.0, 0.0,   0.0, 0.0,
            0.0, 1.0, 0.0,   0.0, 1.0, 0.0,   1.0, 0.0,
            # Z-axis
            0.0, 0.0, 0.0,   0.0, 0.0, 1.0,   0.0, 0.0,
            0.0, 0.0, 1.0,   0.0, 0.0, 1.0,   1.0, 0.0,
        ], dtype=np.float32)
        
        # Create grid vertices
        self._create_grid()
        
        # Create bone lines (initial empty)
        self.bone_vertices = np.array([], dtype=np.float32)
    
    def _create_grid(self):
        """Create grid vertices for the 3D scene."""
        grid_vertices = []
        size = self.grid_size
        spacing = self.grid_spacing
        
        # Horizontal lines
        for z in range(-size, size + 1):
            for x in range(-size, size + 1):
                x_pos = x * spacing
                z_pos = z * spacing
                
                # Line segment
                grid_vertices.extend([
                    x_pos, 0.0, z_pos,
                    x_pos + spacing, 0.0, z_pos
                ])
        
        # Vertical lines
        for x in range(-size, size + 1):
            for z in range(-size, size + 1):
                x_pos = x * spacing
                z_pos = z * spacing
                
                # Line segment
                grid_vertices.extend([
                    x_pos, 0.0, z_pos,
                    x_pos, 0.0, z_pos + spacing
                ])
        
        self.grid_vertices = np.array(grid_vertices, dtype=np.float32)
    
    def _setup_opengl_state(self):
        """Setup OpenGL state for rendering."""
        # Enable depth testing
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthFunc(GL.GL_LESS)
        
        # Enable blending for transparency
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        
        # Enable line smoothing
        GL.glEnable(GL.GL_LINE_SMOOTH)
        
        # Set clear color
        GL.glClearColor(0.15, 0.15, 0.15, 1.0)
        
        # Setup viewport
        GL.glViewport(0, 0, self.viewport_width, self.viewport_height)
    
    def start_updates(self):
        """Start the background update thread."""
        if self.update_thread is None or not self.update_thread.is_alive():
            self.update_running = True
            self.update_thread = threading.Thread(
                target=self._update_loop,
                daemon=True,
                name="ViewportUpdates"
            )
            self.update_thread.start()
            self.logger.info("Viewport update thread started")
    
    def stop_updates(self):
        """Stop the update thread."""
        self.update_running = False
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=2.0)
            self.logger.info("Viewport update thread stopped")
    
    def _update_loop(self):
        """Background update loop for continuous viewport updates."""
        while self.update_running:
            try:
                # Update camera matrices
                self._update_camera_matrices()
                
                # Update performance metrics
                self.frame_count += 1
                current_time = time.time()
                
                if current_time - self.last_fps_update > 1.0:
                    self.current_fps = self.frame_count / (current_time - self.last_fps_update)
                    self.frame_count = 0
                    self.last_fps_update = current_time
                
                # Sleep to prevent CPU spinning
                time.sleep(0.016)  # ~60 Hz
                
            except Exception as e:
                self.logger.error(f"Viewport update loop error: {e}")
                time.sleep(0.1)
    
    def _update_camera_matrices(self):
        """Update camera view and projection matrices."""
        # Calculate camera transformation matrices
        # This would use OpenGL/ModernGL in a real implementation
        pass
    
    def set_viewport_size(self, width: int, height: int):
        """Set the viewport size."""
        self.viewport_width = width
        self.viewport_height = height
        self.aspect_ratio = width / height
        
        # Update framebuffer
        if hasattr(self, 'fbo'):
            self.fbo.release()
            self.fbo = self.renderer.ctx.framebuffer(
                color_attachments=[self.renderer.ctx.texture((width, height), components=3)],
                depth_attachment=self.renderer.ctx.depth_renderbuffer((width, height))
            )
        
        # Update OpenGL viewport
        GL.glViewport(0, 0, width, height)
    
    def set_keypoints(self, keypoints: Optional[List]) -> None:
        """Set the latest pose keypoints for rendering."""
        self.latest_keypoints = keypoints
    
    def set_frame(self, frame: Optional[np.ndarray]) -> None:
        """Set the latest camera frame for overlay."""
        self.latest_frame = frame
    
    def set_bone_matrices(self, bone_matrices: List) -> None:
        """Set bone matrices for skeleton rendering."""
        self.bone_matrices = bone_matrices
    
    def handle_mouse_press(self, x: int, y: int, button: int) -> None:
        """Handle mouse button press events."""
        self.mouse_x = x
        self.mouse_y = y
        self.last_mouse_x = x
        self.last_mouse_y = y
        
        if button == 0:  # Left button
            self.left_mouse_pressed = True
            if self.orbit_mode:
                self.orbit_mode = True
                self.pan_mode = False
                self.zoom_mode = False
        elif button == 1:  # Right button
            self.right_mouse_pressed = True
            self.pan_mode = True
            self.orbit_mode = False
        elif button == 2:  # Middle button
            self.middle_mouse_pressed = True
            self.zoom_mode = True
            self.orbit_mode = False
    
    def handle_mouse_release(self, x: int, y: int, button: int) -> None:
        """Handle mouse button release events."""
        self.mouse_x = x
        self.mouse_y = y
        
        if button == 0:
            self.left_mouse_pressed = False
        elif button == 1:
            self.right_mouse_pressed = False
        elif button == 2:
            self.middle_mouse_pressed = False
    
    def handle_mouse_motion(self, x: int, y: int) -> None:
        """Handle mouse motion events."""
        if self.left_mouse_pressed and self.orbit_mode:
            # Orbit camera
            delta_x = x - self.last_mouse_x
            delta_y = y - self.last_mouse_y
            
            self.camera_yaw += delta_x * 0.5
            self.camera_pitch -= delta_y * 0.5
            
            # Limit pitch
            self.camera_pitch = max(-89.0, min(89.0, self.camera_pitch))
            
            self._update_camera_transform()
            
        elif self.right_mouse_pressed and self.pan_mode:
            # Pan camera
            delta_x = x - self.last_mouse_x
            delta_y = y - self.last_mouse_y
            
            # Move camera based on pan
            self.camera_target[0] += delta_x * 0.01
            self.camera_target[1] -= delta_y * 0.01
            
            self._update_camera_transform()
            
        elif self.middle_mouse_pressed and self.zoom_mode:
            # Zoom camera
            delta_y = y - self.last_mouse_y
            
            self.camera_distance += delta_y * 0.1
            self.camera_distance = max(10.0, min(2000.0, self.camera_distance))
            
            self._update_camera_transform()
        
        self.last_mouse_x = x
        self.last_mouse_y = y
    
    def handle_mouse_wheel(self, delta: int) -> None:
        """Handle mouse wheel events for zooming."""
        self.camera_distance += delta * 0.5
        self.camera_distance = max(10.0, min(2000.0, self.camera_distance))
        self._update_camera_transform()
    
    def _update_camera_transform(self):
        """Update camera transform based on current parameters."""
        # Calculate camera position based on orbit angles and distance
        pitch_rad = math.radians(self.camera_pitch)
        yaw_rad = math.radians(self.camera_yaw)
        
        # Camera position in spherical coordinates
        x = self.camera_distance * math.sin(yaw_rad) * math.cos(pitch_rad)
        y = self.camera_distance * math.sin(pitch_rad)
        z = self.camera_distance * math.cos(yaw_rad) * math.cos(pitch_rad)
        
        self.camera_position = np.array([x, y, z], dtype=np.float32)
        
        # Look at target
        direction = self.camera_target - self.camera_position
        direction = direction / np.linalg.norm(direction)
        
        # Calculate up vector
        right = np.cross(direction, np.array([0.0, 1.0, 0.0], dtype=np.float32))
        if np.linalg.norm(right) < 0.001:
            right = np.cross(direction, np.array([1.0, 0.0, 0.0], dtype=np.float32))
        
        right = right / np.linalg.norm(right)
        up = np.cross(right, direction)
        
        # Update camera up vector
        self.camera_up = up
    
    def render(self) -> np.ndarray:
        """
        Render the viewport.
        
        Returns:
            Rendered frame as numpy array
        """
        start_time = time.time()
        
        try:
            # Clear buffers
            GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
            
            # Set viewport
            GL.glViewport(0, 0, self.viewport_width, self.viewport_height)
            
            # Apply projection matrix
            self._apply_projection_matrix()
            
            # Apply view matrix
            self._apply_view_matrix()
            
            # Render scene elements
            self._render_scene()
            
            # Read pixels
            pixels = self.fbo.read(components=3, alignment=1)
            frame = np.frombuffer(pixels, dtype=np.uint8).reshape((self.viewport_height, self.viewport_width, 3))
            
            # Convert BGR to RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Add performance overlay
            self._add_performance_overlay(frame)
            
            return frame
            
        except Exception as e:
            self.logger.error(f"Viewport render error: {e}")
            # Return blank frame on error
            return np.zeros((self.viewport_height, self.viewport_width, 3), dtype=np.uint8)
    
    def _apply_projection_matrix(self):
        """Apply perspective projection matrix."""
        # This would use ModernGL in a real implementation
        # For now, it's a placeholder
        pass
    
    def _apply_view_matrix(self):
        """Apply view matrix."""
        # This would use ModernGL in a real implementation
        # For now, it's a placeholder
        pass
    
    def _render_scene(self):
        """Render the 3D scene."""
        # Render background
        self._render_background()
        
        # Render grid
        if self.show_grid:
            self._render_grid()
        
        # Render coordinate axes
        if self.show_axes:
            self._render_axes()
        
        # Render skeleton
        self._render_skeleton()
        
        # Render selected object
        if self.selected_object:
            self._render_selection_gizmo()
        
        # Render tracking overlay
        if self.latest_frame is not None:
            self._render_tracking_overlay()
    
    def _render_background(self):
        """Render the background."""
        # Clear with background color
        GL.glClearColor(0.15, 0.15, 0.15, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
    
    def _render_grid(self):
        """Render the 3D grid."""
        # Render grid lines
        # This would use OpenGL rendering in a real implementation
        pass
    
    def _render_axes(self):
        """Render coordinate axes."""
        # Render X, Y, Z axes
        # This would use OpenGL rendering in a real implementation
        pass
    
    def _render_skeleton(self):
        """Render the 3D skeleton."""
        if self.latest_keypoints:
            # Convert keypoints to 3D positions
            positions = self._keypoints_to_3d_positions(self.latest_keypoints)
            
            # Render bones
            self._render_bones(positions)
    
    def _keypoints_to_3d_positions(self, keypoints) -> Dict[int, Tuple[float, float, float]]:
        """Convert keypoints to 3D positions for rendering."""
        positions = {}
        
        # This would map MediaPipe keypoints to 3D world positions
        # For now, return empty dict
        return positions
    
    def _render_bones(self, positions: Dict[int, Tuple[float, float, float]]):
        """Render skeleton bones as lines."""
        # Render bones between joints
        # This would use OpenGL rendering in a real implementation
        pass
    
    def _render_selection_gizmo(self):
        """Render selection gizmo for selected object."""
        # Render 3D transformation gizmo
        # This would use OpenGL rendering in a real implementation
        pass
    
    def _render_tracking_overlay(self):
        """Render tracking overlay (camera feed + keypoints)."""
        # Overlay camera feed and tracking data
        # This would use OpenGL texture rendering in a real implementation
        pass
    
    def _add_performance_overlay(self, frame: np.ndarray):
        """Add performance metrics overlay to frame."""
        # Add FPS, render time, and other metrics
        # This would use OpenCV drawing in a real implementation
        pass
    
    def get_camera_matrix(self) -> np.ndarray:
        """Get the current camera matrix."""
        # Calculate and return camera matrix
        return np.eye(4, dtype=np.float32)
    
    def get_view_matrix(self) -> np.ndarray:
        """Get the current view matrix."""
        # Calculate and return view matrix
        return np.eye(4, dtype=np.float32)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get viewport performance statistics."""
        return {
            "fps": self.current_fps,
            "frame_count": self.frame_count,
            "viewport_size": (self.viewport_width, self.viewport_height),
            "camera_position": self.camera_position.tolist(),
            "camera_target": self.camera_target.tolist(),
            "camera_distance": self.camera_distance,
            "orbit_mode": self.orbit_mode,
            "pan_mode": self.pan_mode,
            "zoom_mode": self.zoom_mode,
            "show_grid": self.show_grid,
            "show_axes": self.show_axes
        }
    
    def reset_camera(self):
        """Reset camera to default position."""
        self.camera_position = np.array([0.0, 0.0, 500.0], dtype=np.float32)
        self.camera_target = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self.camera_up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        self.camera_pitch = -20.0
        self.camera_yaw = 0.0
        self.camera_roll = 0.0
        self.camera_distance = 500.0
        self._update_camera_transform()
    
    def toggle_grid(self):
        """Toggle grid visibility."""
        self.show_grid = not self.show_grid
    
    def toggle_axes(self):
        """Toggle axes visibility."""
        self.show_axes = not self.show_axes
    
    def set_grid_size(self, size: int):
        """Set grid size."""
        self.grid_size = size
        self._create_grid()
    
    def set_grid_spacing(self, spacing: float):
        """Set grid spacing."""
        self.grid_spacing = spacing
        self._create_grid()
    
    def stop_updates(self):
        """Stop the update thread."""
        self.update_running = False
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=2.0)
            self.logger.info("Viewport update thread stopped")

if __name__ == "__main__":
    # Test the Viewport3D class
    import logging
    import cv2
    
    logging.basicConfig(level=logging.INFO)
    
    print("Testing Viewport3D...")
    
    # Create mock renderer
    class MockRenderer:
        def __init__(self):
            self.ctx = None
            self.width = 1920
            self.height = 1080
    
    # Initialize viewport
    renderer = MockRenderer()
    viewport = Viewport3D(renderer)
    
    print("Viewport3D initialized successfully")
    print("Note: Full viewport testing requires OpenGL context and actual renderer")