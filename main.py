#!/usr/bin/env python3
"""
Phantom Engine - Real-time Haunted House Projection Mapping System

A production-ready, multi-threaded desktop application for real-time computer
vision, 3D skeleton tracking, AI-powered skeleton swapping, custom 3D lighting,
and advanced shader effects for haunted house projection mapping.
"""

import json
import sys
import threading
import time
import os
from typing import Optional
from pathlib import Path

# Import core modules
from core.capture import VideoCapture
from core.tracker import PoseTracker, SkeletonRigging
from editor.ui_manager import UIManager
from editor.viewport_3d import Viewport3D
from editor.projector_warp import ProjectorWarp
from graphics.renderer import Renderer
from graphics.lighting import LightingSystem
from graphics.postprocess import PostProcessor
from config import ConfigManager

class PhantomEngine:
    """
    Main application class for Phantom Engine.
    
    Manages the application lifecycle, threads, and coordinates between all components.
    """
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config
        
        # Config helpers
        self.camera_index = self.config.get("camera.primary_index", 0)
        self.warp_coords = self.config.get("projector.warp_coords", {})
        self.shader_effects = self.config.get("effects", {})
        self.lighting_settings = self.config.get("lighting", {})
        self.viewport_settings = self.config.get("viewport", {})
        
        self.running = False
        
        # Core components
        self.capture = None
        self.tracker = None
        self.rigging = None
        self.renderer = None
        self.lighting = None
        self.postprocessor = None
        self.ui_manager = None
        self.viewport3d = None
        self.projector_warp = None
        
        # Thread management
        self.capture_thread = None
        self.tracker_thread = None
        self.render_thread = None
        self.ui_thread = None
        
        # Performance monitoring
        self.frame_times = []
        self.last_time = time.time()
        
        # Application state
        self.current_scene = None
        self.selected_model = None
        self.calibration_mode = False
        self.fullscreen_projector = False
        
        # Application settings
        self.performance_profile = self.config.get("performance.profile", "balanced")
        self.log_level = self.config.get("debug.log_level", "INFO")
    
    def load_config(self) -> dict:
        """Load persistent configuration from JSON file."""
        self.config_manager.load_config()
        self.config = self.config_manager.config
        return self.config
    
    def save_config(self, config: Optional[dict] = None):
        """Save configuration to JSON file."""
        if config is None:
            config = self.config
        
        # Update manager and save
        self.config_manager.config = config
        self.config_manager.save_config()
        
        # Also update cached values
        self.config = config
        self.camera_index = config.get("camera.primary_index", 0)
        self.warp_coords = config.get("projector.warp_coords", {})
        self.shader_effects = config.get("effects", {})
        self.lighting_settings = config.get("lighting", {})
        self.viewport_settings = config.get("viewport", {})
    
    def initialize_components(self):
        """Initialize all system components."""
        print("Initializing Phantom Engine components...")
        
        # Initialize camera capture
        try:
            self.capture = VideoCapture(self.camera_index, self.config.get("camera", {}))
            print("✓ Video capture initialized")
        except Exception as e:
            print(f"✗ Failed to initialize video capture: {e}")
            sys.exit(1)
        
        # Initialize pose tracker
        try:
            self.tracker = PoseTracker(self.config.get("tracker", {}))
            print("✓ Pose tracker initialized")
        except Exception as e:
            print(f"✗ Failed to initialize pose tracker: {e}")
            sys.exit(1)
        
        # Initialize rigging system
        try:
            self.rigging = SkeletonRigging(self.config.get("rigging", {}))
            print("✓ Skeleton rigging system initialized")
        except Exception as e:
            print(f"✗ Failed to initialize rigging system: {e}")
            sys.exit(1)
        
        # Initialize renderer
        try:
            self.renderer = Renderer(self.config.get("window", {}).get("width", 1920), self.config.get("window", {}).get("height", 1080))
            print("✓ Renderer initialized")
        except Exception as e:
            print(f"✗ Failed to initialize renderer: {e}")
            sys.exit(1)
        
        # Initialize lighting system
        try:
            self.lighting = LightingSystem(self.config.get("lighting", {}))
            print("✓ Lighting system initialized")
        except Exception as e:
            print(f"✗ Failed to initialize lighting system: {e}")
            sys.exit(1)
        
        # Initialize post-processor
        try:
            self.postprocessor = PostProcessor()
            print("✓ Post-processor initialized")
        except Exception as e:
            print(f"✗ Failed to initialize post-processor: {e}")
            sys.exit(1)
        
        # Initialize viewport and UI
        try:
            self.viewport3d = Viewport3D(self.renderer)
            print("✓ 3D Viewport initialized")
        except Exception as e:
            print(f"✗ Failed to initialize 3D viewport: {e}")
            sys.exit(1)
        
        try:
            self.ui_manager = UIManager(self)
            print("✓ UI Manager initialized")
        except Exception as e:
            print(f"✗ Failed to initialize UI manager: {e}")
            sys.exit(1)
        
        try:
            self.projector_warp = ProjectorWarp(self.renderer)
            print("✓ Projector warp module initialized")
        except Exception as e:
            print(f"✗ Failed to initialize projector warp: {e}")
            sys.exit(1)
        
        print("All components initialized successfully!")
    
    def start_threads(self):
        """Start all background threads."""
        self.running = True
        
        # Start capture thread
        self.capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name="VideoCapture"
        )
        self.capture_thread.start()
        
        # Start tracker thread
        self.tracker_thread = threading.Thread(
            target=self._tracker_loop,
            daemon=True,
            name="PoseTracker"
        )
        self.tracker_thread.start()
        
        # Start render thread
        self.render_thread = threading.Thread(
            target=self._render_loop,
            daemon=True,
            name="Renderer"
        )
        self.render_thread.start()
        
        print("All threads started successfully!")
    
    def _capture_loop(self):
        """Capture loop running in background thread."""
        if self.capture is None:
            return
        
        while self.running:
            try:
                frame = self.capture.get_frame(timeout=0.033)  # ~30 FPS
                if frame is not None:
                    self.capture.set_latest_frame(frame)
                
                time.sleep(0.001)  # Minimal sleep
            
            except Exception as e:
                print(f"Capture thread error: {e}")
                time.sleep(1.0)
    
    def _tracker_loop(self):
        """Tracking loop running in background thread."""
        if self.tracker is None:
            return
        
        while self.running:
            try:
                latest_frame = self.capture.get_latest_frame() if self.capture else None
                if latest_frame is not None:
                    keypoints = self.tracker.process_frame(latest_frame)
                    if keypoints:
                        # Apply rigging transformations
                        rigged_data = self.rigging.apply_rigging(keypoints)
                        self.tracker.set_latest_keypoints(rigged_data)
                
                time.sleep(0.001)  # ~60 FPS for tracking
            
            except Exception as e:
                print(f"Tracker thread error: {e}")
                time.sleep(1.0)
    
    def _render_loop(self):
        """Render loop running in background thread."""
        if self.renderer is None:
            return
        
        while self.running:
            try:
                start_time = time.time()
                
                # Get tracking data
                latest_keypoints = self.tracker.get_latest_keypoints() if self.tracker else None
                latest_frame = self.capture.get_latest_frame() if self.capture else None
                
                # Render 3D scene
                self.renderer.begin_render()
                
                # Draw skeleton if tracking data is available
                if latest_keypoints:
                    self.renderer.draw_skeleton(latest_keypoints, self.rigging.get_bone_matrices())
                
                # Draw environment and lighting
                self.renderer.draw_environment(self.lighting.get_light_data())
                
                # Draw 3D viewport overlay
                if self.viewport3d:
                    self.viewport3d.render_overlay(latest_keypoints, latest_frame)
                
                # Apply post-processing effects
                if self.postprocessor:
                    self.postprocessor.apply_effects(self.shader_effects)
                
                # End rendering
                frame = self.renderer.end_render()
                
                # Render to screen
                if frame is not None and self.ui_manager:
                    self.ui_manager.update_camera_frame(frame)
                
                # Monitor performance
                frame_time = time.time() - start_time
                self.frame_times.append(frame_time)
                if len(self.frame_times) > 100:
                    self.frame_times.pop(0)
                
                # Target ~120 FPS for interactive experience
                sleep_time = max(0, (1/120) - frame_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                print(f"Render thread error: {e}")
                time.sleep(1.0)
    
    def run(self):
        """Main application loop."""
        print("Starting Phantom Engine...")
        print(f"Performance Profile: {self.performance_profile}")
        print(f"Display Mode: {'Fullscreen' if self.fullscreen_projector else 'Windowed'}")
        
        # Initialize all components
        self.initialize_components()
        
        # Start background threads
        self.start_threads()
        
        # Main UI thread
        try:
            self.ui_manager.run()
        except KeyboardInterrupt:
            print("\nInterrupt received, shutting down...")
        except Exception as e:
            print(f"UI Error: {e}")
        finally:
            # Clean shutdown
            print("\nShutting down Phantom Engine...")
            self.running = False
            
            # Wait for threads to finish
            if self.capture_thread:
                self.capture_thread.join(timeout=2)
            if self.tracker_thread:
                self.tracker_thread.join(timeout=2)
            if self.render_thread:
                self.render_thread.join(timeout=2)
            
            # Save configuration
            self.save_config(self.config)
            
            # Cleanup resources
            if self.renderer:
                self.renderer.cleanup()
            
            print("Phantom Engine shutdown complete.")

def main():
    """Application entry point."""
    # Check Python version
    if sys.version_info < (3, 8):
        print("Error: Phantom Engine requires Python 3.8 or higher.")
        sys.exit(1)
    
    # Create application instance
    app = PhantomEngine()
    
    # Run the application
    app.run()

if __name__ == "__main__":
    main()
