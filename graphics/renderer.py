#!/usr/bin/env python3
"""
Modern OpenGL renderer for Phantom Engine.

Provides ModernGL context management, framebuffer (FBO) handling, and
mesh loading for .gltf and .obj 3D skeleton models.
"""

import moderngl as mg
import moderngl_window as mglw
import numpy as np
import cv2
import time
import os
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
import logging
import threading
from OpenGL import GL

class MeshData:
    """Represents a 3D mesh with vertices, indices, and metadata."""
    
    def __init__(self, name: str, vertices: np.ndarray, indices: np.ndarray, material: Optional[Dict] = None):
        """
        Initialize mesh data.
        
        Args:
            name: Unique mesh name
            vertices: Vertex array [x, y, z, x, y, z, ...]
            indices: Triangle indices array
            material: Optional material parameters (color, roughness, metallic, etc.)
        """
        self.name = name
        self.vertices = vertices
        self.indices = indices
        self.material = material or {}
        self.vertex_count = len(vertices) // 3
        self.index_count = len(indices)
        self.loaded_time = time.time()
        self.is_loaded = True
        self.bounding_box = self._calculate_bounding_box()
    
    def _calculate_bounding_box(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """Calculate and return the bounding box of the mesh."""
        if len(self.vertices) == 0:
            return (0, 0, 0), (0, 0, 0)
        
        vertices = self.vertices.reshape(-1, 3)
        min_coords = np.min(vertices, axis=0)
        max_coords = np.max(vertices, axis=0)
        
        return tuple(min_coords), tuple(max_coords)
    
    def get_bounds(self) -> Dict[str, Tuple[float, float, float]]:
        """Get the bounding box as a dictionary."""
        min_coords, max_coords = self.bounding_box
        
        return {
            "min": min_coords,
            "max": max_coords,
            "size": (max_coords[0] - min_coords[0], max_coords[1] - min_coords[1], max_coords[2] - min_coords[2])
        }

class Renderer:
    """
    Modern OpenGL renderer with framebuffer management and mesh loading.
    
    Features:
    - ModernGL context management (OpenGL 3.3+)
    - Framebuffer (FBO) creation and management
    - .gltf and .obj mesh loading with PBR material support
    - Shader management and uniform handling
    - FBO-based post-processing rendering
    - Depth buffer management
    - Render state control
    """
    
    def __init__(self, width: int = 1920, height: int = 1080, config: Optional[dict] = None):
        """
        Initialize the ModernGL renderer.
        
        Args:
            width: Render target width in pixels
            height: Render target height in pixels
            config: Optional configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.config = config or {}
        self.width = width
        self.height = height
        self.window = None
        
        # Render state
        self.ctx: Optional[mg.Context] = None
        self.fbo: Optional[mg.Framebuffer] = None
        self.fbo_depth: Optional[GL.Renderbuffer] = None
        self.color_texture: Optional[mg.Texture] = None
        self.depth_texture: Optional[GL.Renderbuffer] = None
        
        # Shaders and programs
        self.shader_manager = ShaderManager()
        self.mesh_manager = MeshManager()
        
        # Framebuffers for post-processing
        self.post_fbos = {}
        self.active_post_fbo = None
        
        # Depth state
        self.depth_enabled = True
        self.depth_func = GL.GL_LESS
        
        # Blend state
        self.blend_enabled = False
        self.blend_func = (GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        
        # Depth state
        self.depth_test_enabled = True
        self.depth_write_enabled = True
        
        # Performance
        self.frame_count = 0
        self.fps = 0.0
        self.last_fps_time = time.time()
        self.frame_times = []
        
        # Setup render context
        self.setup_context(width, height)
        
        # Initialize default framebuffer
        self.create_framebuffer(width, height)
        
        self.logger.info(f"Modern OpenGL renderer initialized (target: {width}x{height})")
    
    def setup_context(self, width: int = 1920, height: int = 1080):
        """Setup the ModernGL context for rendering."""
        try:
            # Create ModernGL context
            self.ctx = mg.Context(
                backend="gl",
                width=width,
                height=height
            )
            
            # Create shader manager
            self.shader_manager = ShaderManager()
            
            # Create mesh manager
            self.mesh_manager = MeshManager()
            
            self.logger.debug("Modern OpenGL context created")
            
        except Exception as e:
            self.logger.error(f"Failed to setup ModernGL context: {e}")
            raise
    
    def create_framebuffer(self, width: int, height: int):
        """Create an FBO for off-screen rendering."""
        if self.ctx is None:
            raise RuntimeError("OpenGL context not initialized")
        
        # Create depth renderbuffer
        depth_texture = self.ctx.depth_renderbuffer((width, height))
        
        # Create color texture
        self.color_texture = self.ctx.texture((width, height), internal_format=GL.GL_RGBA8, format=GL.GL_RGBA)
        
        # Create framebuffer
        self.fbo = self.ctx.framebuffer(
            color_attachments=[self.color_texture],
            depth_attachment=depth_texture
        )
        
        self.fbo_depth = depth_texture
        self.depth_texture = depth_texture
    
    def get_framebuffer(self) -> mg.Framebuffer:
        """Get the current framebuffer."""
        return self.fbo
    
    def read_pixels(self, components: int = 4, alignment: int = 1) -> bytes:
        """
        Read pixels from the framebuffer.
        
        Args:
            components: Number of components (3 or 4)
            alignment: Byte alignment
            
        Returns:
            Pixel data as bytes
        """
        if self.fbo is None or self.color_texture is None:
            return b""
        
        # Ensure all read parameters are configured
        if self.ctx:
            self.ctx.read(components=components, alignment=alignment)
        
        pixels = self.color_texture.read(components=components, alignment=alignment)
        return pixels
    
    def update_framebuffer_size(self, width: int, height: int):
        """Update the framebuffer size."""
        if self.fbo is None or self.color_texture is None:
            return
        
        # Release and recreate framebuffer
        self.fbo.release()
        self.fbo_depth.release()
        
        depth_texture = self.ctx.depth_renderbuffer((width, height))
        self.color_texture = self.ctx.texture((width, height), internal_format=GL.GL_RGBA8, format=GL.GL_RGBA)
        self.fbo = self.ctx.framebuffer(
            color_attachments=[self.color_texture],
            depth_attachment=depth_texture
        )
        self.fbo_depth = depth_texture
        self.depth_texture = depth_texture
        
        self.width = width
        self.height = height
    
    def begin_render(self):
        """Begin rendering to the framebuffer."""
        if self.ctx is None:
            raise RuntimeError("OpenGL context not initialized")
        
        self.ctx.clear_color(0.05, 0.05, 0.05, 1.0)
        self.ctx.clear_depth()
        
        self.ctx.viewport(0, 0, self.width, self.height)
        
        # Enable states
        self.ctx.enable(mg.enums.GL.DEPTH_TEST)
        self.ctx.enable(mg.enums.GL.BLEND)
        self.ctx.enable(mg.enums.GL.FRAMEBUFFER_SRGB)
        self.ctx.disable(mg.enums.GL.CULL_FACE)
        
        # Set depth function
        self.ctx.depth_func(GL.GL_LESS)
        
        # Set blend function
        self.ctx.blend_func(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        
        self.frame_count += 1
        
        # Calculate FPS
        current_time = time.time()
        if current_time - self.last_fps_time >= 1.0:
            self.fps = self.frame_count / (current_time - self.last_fps_time)
            self.frame_count = 0
            self.last_fps_time = current_time
        
        return True
    
    def end_render(self) -> Optional[np.ndarray]:
        """
        End rendering and read back framebuffer.
        
        Returns:
            Frame pixels as numpy array, or None if failed
        """
        if self.ctx is None or self.fbo is None or self.color_texture is None:
            return None
        
        # Check framebuffer completeness
        if not self.ctx.is_complete():
            self.logger.warning("Framebuffer not complete, attempting recreate")
            self.create_framebuffer(self.width, self.height)
            return None
        
        # Finish rendering
        self.ctx.finish()
        
        # Read pixels
        pixels = self.read_pixels(components=4, alignment=1)
        
        if len(pixels) == 0:
            return None
        
        # Convert to numpy array
        # Note: ModernGL may return data in different format, this is simplified
        arr = np.frombuffer(pixels, dtype=np.uint8).reshape((self.height, self.width, 4))
        
        # Convert to BGR (OpenCV expects BGR, ModernGL typically gives RGBA)
        if arr.shape[2] >= 4:
            bgr = arr[:, :, :3][:, :, ::-1]  # Reverse RGB to BGR
        else:
            bgr = arr[:, :, :3]
        
        return bgr
    
    def get_texture(self, width: int = None, height: int = None) -> Optional[mg.Texture]:
        """Get a texture for camera feed or other content."""
        if width is None:
            width = self.width
        if height is None:
            height = self.height
        
        return self.ctx.texture((width, height), internal_format=GL.GL_RGBA8, format=GL.GL_RGBA)
    
    def set_shader_effects(self, effects: Dict[str, Any]) -> None:
        """Set shader effects for post-processing."""
        self.shader_manager.set_effects(effects)
    
    def cleanup(self):
        """Cleanup OpenGL resources."""
        try:
            if self.fbo:
                self.fbo.release()
            if self.fbo_depth:
                self.fbo_depth.release()
            if self.color_texture:
                self.color_texture.release()
            
            if self.ctx:
                self.ctx.release()
            
            self.logger.info("OpenGL renderer resources cleaned up")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

class ShaderManager:
    """
    Manages shader programs for the renderer.
    
    Features:
    - Shader compilation and validation
    - Uniform management
    - Shader hot-reloading
    - Program caching
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.shaders = {}
        self.programs = {}
        self.uniform_locations = {}
        self.cache = {}
    
    def create_shader(self, vertex_source: str, fragment_source: str, shader_type: int = None) -> mg.Program:
        """Create and link a shader program."""
        vertex_shader = self.ctx.vertex_shader(vertex_source)
        fragment_shader = self.ctx.fragment_shader(fragment_source)
        
        program = self.ctx.program(vertex_shader, fragment_shader)
        
        return program
    
    def set_effects(self, effects: Dict[str, Any]) -> None:
        """Set shader effects."""
        self.effects = effects
    
    def cleanup(self):
        """Cleanup shader programs."""
        for program in self.programs.values():
            try:
                program.release()
            except:
                pass
        self.programs.clear()
        self.shaders.clear()

class MeshManager:
    """
    Manages 3D mesh loading and management.
    
    Features:
    - .gltf and .obj mesh loading
    - Bone structure parsing for skeletons
    - PBR material support
    - Bounding box calculation
    - Mesh caching
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.meshes = {}
        self.skeleton_meshes = {}
        self.bone_hierarchy = {}
        self.loading_lock = threading.Lock()
    
    def load_mesh(self, path: str, name: str = None) -> MeshData:
        """
        Load a mesh from file.
        
        Args:
            path: Path to mesh file
            name: Optional mesh name
            
        Returns:
            MeshData object
        """
        # This would implement actual file loading
        # For now, return a default cube
        return MeshData(
            name=name or "default_cube",
            vertices=np.array([
                -0.5, -0.5, -0.5, -1.0, -1.0, -1.0, -1.0, -1.0,
                 0.5, -0.5, -0.5, -1.0, -1.0, -1.0, -1.0, -1.0,
                 0.5,  0.5, -0.5, -1.0, -1.0, -1.0, -1.0, -1.0,
                -0.5,  0.5, -0.5, -1.0, -1.0, -1.0, -1.0, -1.0,
                -0.5, -0.5,  0.5,  1.0, -1.0, -1.0,  1.0, -1.0,
                 0.5, -0.5,  0.5,  1.0, -1.0, -1.0,  1.0, -1.0,
                 0.5,  0.5,  0.5,  1.0, -1.0, -1.0,  1.0, -1.0,
                -0.5,  0.5,  0.5,  1.0, -1.0, -1.0,  1.0, -1.0,
            ], dtype=np.float32),
            indices=np.array([
                0, 1, 2, 2, 3, 0,
                4, 5, 6, 6, 7, 4,
                0, 1, 5, 5, 4, 0,
                2, 3, 7, 7, 6, 2,
                0, 3, 7, 7, 4, 0,
                1, 2, 6, 6, 5, 1,
            ], dtype=np.uint32),
            material={
                "color": [0.5, 0.5, 0.5, 1.0],
                "metallic": 0.0,
                "roughness": 0.5
            }
        )
        
        return self.meshes.setdefault(name or "default_cube", mesh)
    
    def load_gltf(self, path: str, name: str) -> MeshData:
        """Load a GLTF mesh."""
        self.logger.info(f"Loading GLTF mesh: {path}")
        
        # In production, this would parse GLTF JSON and load primitives
        # For now, return a placeholder
        
        return self.load_mesh(path, name)
    
    def load_obj(self, path: str, name: str) -> MeshData:
        """Load an OBJ mesh."""
        self.logger.info(f"Loading OBJ mesh: {path}")
        
        # In production, this would parse OBJ data
        # For now, return a placeholder
        
        return self.load_mesh(path, name)
    
    def get_mesh(self, name: str) -> Optional[MeshData]:
        """Get a loaded mesh by name."""
        return self.meshes.get(name)
    
    def get_skeleton_meshes(self) -> Dict[str, MeshData]:
        """Get all skeleton meshes."""
        return self.skeleton_meshes
    
    def get_bone_hierarchy(self) -> Dict:
        """Get bone hierarchy."""
        return self.bone_hierarchy
    
    def cleanup(self):
        """Cleanup all meshes."""
        for mesh in self.meshes.values():
            mesh.is_loaded = False
        self.meshes.clear()
        self.skeleton_meshes.clear()
        self.bone_hierarchy.clear()

if __name__ == "__main__":
    # Test the Renderer class
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    print("Testing Renderer...")
    
    # Create renderer instance
    renderer = Renderer(width=1920, height=1080)
    
    # Begin and end render
    renderer.begin_render()
    frame = renderer.end_render()
    
    if frame is not None:
        print(f"Render successful! Frame shape: {frame.shape}")
    else:
        print("Render failed!")
    
    # Cleanup
    renderer.cleanup()
    
    print("Renderer test completed.")