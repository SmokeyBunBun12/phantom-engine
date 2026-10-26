#!/usr/bin/env python3
"""
UI Manager module for Phantom Engine.

Provides comprehensive UI management with docking layout, control panels,
menus, and toolbars for the Phantom Studio interface.
"""

import dearpygui.dearpygui as dpg
import time
import threading
import json
from typing import Optional, Dict, List, Callable, Any
import logging
from pathlib import Path

from graphics.renderer import Renderer
class UIManager:
    """
    Comprehensive UI management system for Phantom Engine.
    
    Manages the complete user interface including:
    - Dockable workspace layout
    - Control panels and toolbars
    - Menus and keyboard shortcuts
    - Real-time status monitoring
    - Theme and appearance customization
    """
    
    def __init__(self, app=None):
        """
        Initialize the UI manager.
        
        Args:
            app: Reference to the main PhantomEngine application instance
        """
        self.logger = logging.getLogger(__name__)
        self.app = app
        
        # UI state
        self.window_width = 1920
        self.window_height = 1080
        self.dockspace_only = True
        self.show_demo_window = False
        self.current_theme = "dark"
        
        # Panel visibility state
        self.panel_visibility = {
            "camera_feed": True,
            "tracker_overlay": True,
            "lighting_panel": True,
            "effect_panel": True,
            "scene_panel": True,
            "log_panel": True
        }
        
        # Current dock layout
        self.dock_layout = "standard"
        
        # Menu bar state
        self.show_file_menu = True
        self.show_edit_menu = True
        self.show_view_menu = True
        self.show_calibration_menu = True
        self.show_help_menu = True
        
        # Window state
        self.main_window_size = [self.window_width, self.window_height]
        self.main_window_pos = [0, 0]
        
        # Theme configuration
        self.theme_colors = self._get_theme_colors()
        
        # Font registry
        self.fonts = {}
        
        # Callback registry
        self.callbacks = {}
        
        # Performance monitoring
        self.frame_times = []
        self.ui_frame_count = 0
        
        # Initialize UI
        self._initialize_ui()
    
    def _initialize_ui(self):
        """Initialize the Dear PyGui UI system."""
        try:
            # Setup Dear PyGui context
            dpg.create_context()
            
            # Configure viewport
            dpg.setup_viewport(self.window_width, self.window_height)
            dpg.set_viewport_title("Phantom Engine - Spectral Projection Suite")
            
            # Set window flags
            dpg.set_item_config("primary_window", dpg.mvWindowFlags_NoResize | dpg.mvWindowFlags_NoMove)
            
ghtlight(dpg.mvThemeVar_BG, (30, 30, 30, 255))  # Dark background
            
            # Register theme variables
            self._setup_theme()
            
            # Create main window
            with dpg.window(tag="primary_window", no_close=True, no_move=False, no_resize=False):
                # Create dockspace
                with dpg.dockspace(tag="dockspace", width=0, height=0):
                    self._create_dock_layout()
            
            self.logger.info("UI system initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize UI: {e}")
            raise
    
    def _create_dock_layout(self):
        """Create the main dock layout."""
        # Main viewport dock
        dpg.add_dock(
            label="3D Viewport",
            parent="dockspace",
            width=-1,
            height=-1,
            dock_slot=dpg.mvDockSlot_Center
        )
        
        # Camera feed dock
        dpg.add_dock(
            label="Camera Feed",
            parent="dockspace",
            width=400,
            height=0,
            dock_slot=dpg.mvDockSlot_Left,
            closable=True,
            show=self.panel_visibility["camera_feed"]
        )
        
        # Tracker overlay dock
        dpg.add_dock(
            label="Tracker Overlay",
            parent="dockspace",
            width=300,
            height=0,
            dock_slot=dpg.mvDockSlot_Right,
            closable=True,
            show=self.panel_visibility["tracker_overlay"]
        )
        
        # Lighting panel dock
        dpg.add_dock(
            label="Lighting Control",
            parent="dockspace",
            width=350,
            height=0,
            dock_slot=dpg.mvDockSlot_Right,
            closable=True,
            show=self.panel_visibility["lighting_panel"]
        )
        
        # Effects panel dock
        dpg.add_dock(
            label="Effects Control",
            parent="dockspace",
            width=300,
            height=0,
            dock_slot=dpg.mvDockSlot_Bottom,
            closable=True,
            show=self.panel_visibility["effect_panel"]
        )
        
        # Scene panel dock
        dpg.add_dock(
            label="Scene Manager",
            parent="dockspace",
            width=250,
            height=0,
            dock_slot=dpg.mvDockSlot_Bottom,
            closable=True,
            show=self.panel_visibility["scene_panel"]
        )
        
        # Log panel dock
        dpg.add_dock(
            label="Logs",
            parent="dockspace",
            width=300,
            height=200,
            dock_slot=dpg.mvDockSlot_Bottom,
            closable=True,
            show=self.panel_visibility["log_panel"]
        )
    
    def _setup_theme(self):
        """Setup the UI theme."""
        # Create custom theme
        with dpg.theme() as phantom_theme:
            # Set colors for various UI elements
            dpg.add_theme_color(dpg.mvThemeCol_Button, (50, 50, 70, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (70, 70, 90, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (90, 90, 110, 255))
            
            dpg.add_theme_color(dpg.mvThemeCol_Header, (40, 40, 60, 255))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (60, 60, 80, 255))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (80, 80, 100, 255))
            
            dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, (100, 100, 150, 255))
            dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, (120, 120, 170, 255))
            
            # Apply theme to viewport
            dpg.bind_theme(phantom_theme)
    
    def _get_theme_colors(self) -> Dict[str, tuple]:
        """Get theme color palette."""
        return {
            "dark": {
                "background": (30, 30, 30, 255),
                "panel": (40, 40, 45, 255),
                "accent": (70, 130, 180, 255),  # Phantom blue
                "success": (50, 205, 50, 255),
                "warning": (255, 215, 0, 255),
                "error": (220, 20, 60, 255),
                "text": (240, 240, 240, 255),
                "text_dimmed": (150, 150, 150, 255),
                "border": (60, 60, 65, 255)
            },
            "light": {
                "background": (245, 245, 245, 255),
                "panel": (235, 235, 240, 255),
                "accent": (0, 100, 200, 255),
                "success": (34, 139, 34, 255),
                "warning": (255, 140, 0, 255),
                "error": (220, 20, 60, 255),
                "text": (33, 37, 41, 255),
                "text_dimmed": (108, 117, 125, 255),
                "border": (222, 226, 230, 255)
            }
        }
    
    def create_menus(self):
        """Create the main application menu bar."""
        with dpg.menu_bar():
            # File Menu
            with dpg.menu(label="File"):
                dpg.add_menu_item(label="Save Scene", callback=self._save_scene_callback)
                dpg.add_menu_item(label="Load Scene", callback=self._load_scene_callback)
                dpg.add_menu_item(label="Reset Defaults", callback=self._reset_defaults_callback)
                dpg.add_separator()
                dpg.add_menu_item(label="Export Warmup", callback=self._export_warmup_callback)
                dpg.add_menu_item(label="Import Preset", callback=self._import_preset_callback)
                dpg.add_separator()
                dpg.add_menu_item(label="Quit", callback=self._quit_callback)
            
            # Edit Menu
            with dpg.menu(label="Edit"):
                dpg.add_menu_item(label="Preferences", callback=self._open_preferences_callback)
                dpg.add_menu_item(label="Keybindings", callback=self._open_keybindings_callback)
            
            # View Menu
            with dpg.menu(label="View"):
                dpg.add_menu_item(label="Toggle Camera Feed", callback=lambda: self._toggle_panel("camera_feed"))
                dpg.add_menu_item(label="Toggle Tracker Overlay", callback=lambda: self._toggle_panel("tracker_overlay"))
                dpg.add_menu_item(label="Toggle Lighting Panel", callback=lambda: self._toggle_panel("lighting_panel"))
                dpg.add_menu_item(label="Toggle Effects Panel", callback=lambda: self._toggle_panel("effect_panel"))
                dpg.add_menu_item(label="Toggle Scene Panel", callback=lambda: self._toggle_panel("scene_panel"))
                dpg.add_menu_item(label="Toggle Log Panel", callback=lambda: self._toggle_panel("log_panel"))
                dpg.add_separator()
                dpg.add_menu_item(label="Full Screen", callback=self._toggle_fullscreen)
            
            # Calibration Menu
            with dpg.menu(label="Calibration"):
                dpg.add_menu_item(label="Open 4-Corner Warp Tool", callback=self._open_warp_tool_callback)
                dpg.add_menu_item(label="Recalibrate Tracking", callback=self._recalibrate_callback)
                dpg.add_menu_item(label="Reset Calibration", callback=self._reset_calibration_callback)
            
            # Help Menu
            with dpg.menu(label="Help"):
                dpg.add_menu_item(label="Asset Guide", callback=self._open_asset_guide_callback)
                dpg.add_menu_item(label="About", callback=self._show_about_callback)
                dpg.add_menu_item(label="Show Demo Window", callback=self._toggle_demo_callback)
    
    def create_control_toolbar(self):
        """Create the main control toolbar."""
        with dpg.collapsing_header(label="Controls", default_open=True):
            dpg.add_text("Quick Actions", color=self.theme_colors[self.current_theme]["accent"])
            
            # Action buttons
            dpg.add_button(label="[F11] Fullscreen Output", callback=self._toggle_fullscreen_output)
            dpg.add_button(label="[C] Calibration Mode", callback=self._toggle_calibration_mode)
            dpg.add_button(label="[SPACE] Trigger Jump-Scare", callback=self._trigger_jump_scare)
            dpg.add_button(label="[R] Reset Calibration", callback=self._reset_tracking_calibration)
            dpg.add_button(label="[ESC] Open Settings", callback=self._open_settings)
    
    def create_camera_panel(self):
        """Create the camera control panel."""
        with dpg.collapsing_header(label="Camera Controls", default_open=True):
            dpg.add_text("Video Source", color=self.theme_colors[self.current_theme]["accent"])
            
            # Camera selection
            cameras = self._get_available_cameras()
            if cameras:
                dpg.add_combo(
                    items=cameras,
                    default_value=self.app.config.get("camera_index", 0) if self.app else 0,
                    callback=self._on_camera_change,
                    label="Camera Source"
                )
            
            # Camera settings
            dpg.add_slider_int(label="Resolution Width", default_value=1920, min_value=640, max_value=3840, callback=self._on_resolution_change)
            dpg.add_slider_int(label="Resolution Height", default_value=1080, min_value=480, max_value=2160, callback=self._on_resolution_change)
            dpg.add_slider_int(label="FPS", default_value=30, min_value=15, max_value=120, callback=self._on_fps_change)
            
            # Auto-reconnect toggle
            dpg.add_checkbox(label="Auto-reconnect", default_value=True, callback=self._on_autoreconnect_toggle)
    
    def create_tracker_panel(self):
        """Create the pose tracker control panel."""
        with dpg.collapsing_header(label="Pose Tracker", default_open=True):
            dpg.add_text("Tracking Settings", color=self.theme_colors[self.current_theme]["accent"])
            
            # Tracking model
            dpg.add_slider_int(
                label="Model Complexity",
                default_value=1,
                min_value=0,
                max_value=2,
                callback=self._on_tracker_model_change
            )
            
            # Confidence thresholds
            dpg.add_slider_float(
                label="Min Detection Confidence",
                default_value=0.5,
                min_value=0.1,
                max_value=1.0,
                callback=self._on_min_confidence_change
            )
            
            dpg.add_slider_float(
                label="Min Tracking Confidence",
                default_value=0.5,
                min_value=0.1,
                max_value=1.0,
                callback=self._on_min_tracking_confidence_change
            )
            
            # Feature toggles
            dpg.add_checkbox(label="Smooth Landmarks", default_value=True, callback=self._on_smooth_landmarks_toggle)
            dpg.add_checkbox(label="World Landmarks", default_value=True, callback=self._on_world_landmarks_toggle)
            dpg.add_checkbox(label="Filter Output", default_value=True, callback=self._on_filter_toggle)
            
            # Performance display
            dpg.add_text(label="Performance Metrics")
            self.tracker_perf_text = dpg.add_text("")
    
    def create_lighting_panel(self):
        """Create the lighting control panel."""
        with dpg.collapsing_header(label="Lighting System", default_open=True):
            dpg.add_text("Light Controls", color=self.theme_colors[self.current_theme]["accent"])
            
            # Ambient light
            dpg.add_text("Ambient Light")
            dpg.add_slider_float(label="R##ambient_r", default_value=0.3, min_value=0.0, max_value=1.0, callback=self._on_ambient_r_change)
            dpg.add_slider_float(label="G##ambient_g", default_value=0.3, min_value=0.0, max_value=1.0, callback=self._on_ambient_g_change)
            dpg.add_slider_float(label="B##ambient_b", default_value=0.3, min_value=0.0, max_value=1.0, callback=self._on_ambient_b_change)
            dpg.add_slider_float(label="Intensity", default_value=0.6, min_value=0.0, max_value=2.0, callback=self._on_ambient_intensity_change)
            
            # Point lights
            dpg.add_text("Point Lights")
            self.point_lights_list = dpg.add_listbox(items=[], callback=self._on_point_light_select)
            
            # Light manipulation controls
            dpg.add_button(label="Add Point Light", callback=self._add_point_light)
            dpg.add_button(label="Remove Selected Light", callback=self._remove_point_light)
            
            # Lighting effects
            dpg.add_text("Lighting Effects")
            dpg.add_checkbox(label="Bloom", default_value=True, callback=self._on_bloom_toggle)
            dpg.add_slider_float(label="Bloom Threshold", default_value=0.8, min_value=0.0, max_value=1.0)
            dpg.add_slider_float(label="Bloom Intensity", default_value=1.0, min_value=0.0, max_value=2.0)
            
            dpg.add_checkbox(label="Glare", default_value=False, callback=self._on_glare_toggle)
            dpg.add_slider_float(label="Glare Intensity", default_value=0.3, min_value=0.0, max_value=1.0)
    
    def create_effects_panel(self):
        """Create the shader effects control panel."""
        with dpg.collapsing_header(label="Effects Control", default_open=True):
            dpg.add_text("Shader Effects", color=self.theme_colors[self.current_theme]["accent"])
            
            # Jump-scare flash
            dpg.add_text("Jump-Scare Flash")
            dpg.add_checkbox(label="Enabled", callback=self._on_flash_toggle)
            dpg.add_slider_float(label="Intensity", default_value=1.0, min_value=0.0, max_value=2.0)
            dpg.add_slider_float(label="Duration", default_value=0.5, min_value=0.1, max_value=2.0)
            dpg.add_slider_float(label="Frequency", default_value=2.0, min_value=0.1, max_value=10.0)
            
            # Digital glitch
            dpg.add_text("Digital Glitch")
            dpg.add_checkbox(label="Enabled", callback=self._on_glitch_toggle)
            dpg.add_slider_float(label="Intensity", default_value=0.5, min_value=0.0, max_value=1.0)
            dpg.add_slider_float(label="Speed", default_value=1.0, min_value=0.1, max_value=5.0)
            dpg.add_checkbox(label="Scanlines", default_value=True)
            dpg.add_slider_int(label="Scanline Frequency", default_value=60, min_value=30, max_value=120)
            
            # Chromatic aberration
            dpg.add_text("Chromatic Aberration")
            dpg.add_checkbox(label="Enabled", callback=self._on_chromatic_toggle)
            dpg.add_slider_float(label="Intensity", default_value=0.5, min_value=0.0, max_value=1.0)
            dpg.add_slider_float(label="Offset", default_value=0.5, min_value=0.0, max_value=1.0)
            
            # General post-processing
            dpg.add_text("Post-Processing")
            dpg.add_checkbox(label="Vignette", default_value=True, callback=self._on_vignette_toggle)
            dpg.add_slider_float(label="Vignette Intensity", default_value=0.6, min_value=0.0, max_value=1.0)
            dpg.add_slider_float(label="Contrast", default_value=1.0, min_value=0.5, max_value=2.0)
            dpg.add_slider_float(label="Saturation", default_value=1.0, min_value=0.5, max_value=2.0)
            dpg.add_slider_float(label="Exposure", default_value=0.0, min_value=-1.0, max_value=1.0)
            
            # Color grading
            dpg.add_text("Color Grading")
            dpg.add_slider_int(label="Temperature", default_value=5500, min_value=2000, max_value=10000)
            dpg.add_slider_float(label="Tint", default_value=0.0, min_value=-1.0, max_value=1.0)
            dpg.add_slider_float(label="Gamma", default_value=1.0, min_value=0.5, max_value=2.0)
    
    def create_scene_panel(self):
        """Create the scene management panel."""
        with dpg.collapsing_header(label="Scene Manager", default_open=True):
            dpg.add_text("Scene Control", color=self.theme_colors[self.current_theme]["accent"])
            
            # Current scene info
            dpg.add_text(label="Current Scene: Default")
            dpg.add_text(label="Model: None")
            
            # Scene actions
            dpg.add_button(label="Save Current Scene", callback=self._save_current_scene)
            dpg.add_button(label="Load Scene", callback=self._load_scene)
            dpg.add_button(label="New Scene", callback=self._new_scene)
            
            # Model loading
            dpg.add_text("Model Loading")
            dpg.add_button(label="Load Skeleton Model", callback=self._load_skeleton_model)
            dpg.add_button(label="Load Camera Path", callback=self._load_camera_path)
            
            # Scene presets
            dpg.add_text("Presets")
            presets = self._get_available_presets()
            if presets:
                dpg.add_combo(items=presets, callback=self._on_preset_select, label="Load Preset")
            dpg.add_button(label="Save Preset", callback=self._save_preset)
    
    def create_status_bar(self):
        """Create the application status bar."""
        with dpg.collapsing_header(label="Status", default_open=False):
            # Performance metrics
            self.performance_text = dpg.add_text("Performance: Ready")
            self.fps_text = dpg.add_text("FPS: 0")
            self.tracker_text = dpg.add_text("Tracker: Initializing...")
            self.capture_text = dpg.add_text("Capture: Ready")
            
            # System status
            self.status_separator = dpg.add_separator()
            
            # Application info
            dpg.add_text("Phantom Engine v2.0.0")
            dpg.add_text("Spectral Projection Suite")
            
            # Build info
            self.build_info = dpg.add_text("Build: Development")
    
    def update_status(self, frame_count: int = 0, fps: float = 0.0, tracker_state: str = "Idle", capture_status: str = "Ready"):
        """Update the status bar with current system information."""
        self.ui_frame_count = frame_count
        
        # Update FPS display
        dpg.set_value(self.fps_text, f"FPS: {fps:.1f}")
        
        # Update tracker status
        dpg.set_value(self.tracker_text, f"Tracker: {tracker_state}")
        
        # Update capture status
        dpg.set_value(self.capture_text, f"Capture: {capture_status}")
        
        # Update performance metrics
        avg_frame_time = sum(self.frame_times) / len(self.frame_times) if self.frame_times else 0
        dpg.set_value(self.performance_text, f"Frame Time: {avg_frame_time:.2f}ms | Dropped: {len(self.frame_times)}")
    
    def run(self):
        """Run the UI event loop."""
        try:
            dpg.show_viewport()
            
            # Main UI loop
            while dpg.is_viewport_open():
                # Start timing frame
                frame_start = time.time()
                
                # Render UI
                self._render_ui()
                
                # Calculate and display FPS
                frame_time = time.time() - frame_start
                self.frame_times.append(frame_time)
                if len(self.frame_times) > 100:
                    self.frame_times.pop(0)
                
                # Small delay to prevent CPU spinning
                time.sleep(0.001)
            
            self.logger.info("UI shutdown completed")
            
        except Exception as e:
            self.logger.error(f"UI runtime error: {e}")
            raise
    
    def _render_ui(self):
        """Render the main UI."""
        # Clear viewport
        dpg.clear_drawing()
        
        # Create menus
        self.create_menus()
        
        # Create control toolbar
        self.create_control_toolbar()
        
        # Create panels (conditionally based on visibility)
        if self.panel_visibility["camera_feed"]:
            self.create_camera_panel()
        
        if self.panel_visibility["tracker_overlay"]:
            self.create_tracker_panel()
        
        if self.panel_visibility["lighting_panel"]:
            self.create_lighting_panel()
        
        if self.panel_visibility["effect_panel"]:
            self.create_effects_panel()
        
        if self.panel_visibility["scene_panel"]:
            self.create_scene_panel()
        
        # Always create status bar
        self.create_status_bar()
        
        # Show demo window if enabled
        if self.show_demo_window:
            dpg.show_demo()
    
    # Callback handlers
    def _save_scene_callback(self):
        """Handle save scene action."""
        self.logger.info("Saving scene...")
        if self.app:
            self.app.current_scene = self._generate_scene_data()
            self.app.save_config({"current_scene": self.app.current_scene})
    
    def _load_scene_callback(self):
        """Handle load scene action."""
        self.logger.info("Loading scene...")
        if self.app:
            # This would open a file dialog in a real implementation
            pass
    
    def _reset_defaults_callback(self):
        """Handle reset defaults action."""
        self.logger.info("Resetting to defaults...")
        if self.app:
            self.app.reset_config()
    
    def _export_warmup_callback(self):
        """Handle export warmup action."""
        self.logger.info("Exporting warmup data...")
        # Implementation would export calibration data
    
    def _import_preset_callback(self):
        """Handle import preset action."""
        self.logger.info("Importing preset...")
        # Implementation would open file dialog
    
    def _quit_callback(self):
        """Handle quit action."""
        self.logger.info("Quitting application...")
        dpg.stop_dearpygui()
    
    def _open_preferences_callback(self):
        """Handle open preferences action."""
        self.logger.info("Opening preferences...")
        # Open preferences dialog
    
    def _open_keybindings_callback(self):
        """Handle open keybindings action."""
        self.logger.info("Opening keybindings...")
        # Open keybindings dialog
    
    def _toggle_fullscreen(self):
        """Handle toggle fullscreen action."""
        if self.app:
            self.app.fullscreen_projector = not self.app.fullscreen_projector
            self._update_window_mode()
    
    def _open_warp_tool_callback(self):
        """Handle open warp tool action."""
        self.logger.info("Opening 4-corner warp tool...")
        # Open calibration/warp tool
    
    def _recalibrate_callback(self):
        """Handle recalibrate action."""
        self.logger.info("Recalibrating tracking...")
        if self.app and self.app.tracker:
            self.app.tracker.reset()
    
    def _reset_calibration_callback(self):
        """Handle reset calibration action."""
        self.logger.info("Resetting calibration...")
        if self.app and self.app.rigging:
            self.app.rigging.calibration_samples = []
            self.app.rigging.calibration_baseline = {}
    
    def _open_asset_guide_callback(self):
        """Handle open asset guide action."""
        self.logger.info("Opening asset guide...")
        # Open asset guide documentation
    
    def _show_about_callback(self):
        """Handle show about action."""
        self.logger.info("Showing about dialog...")
        # Show about dialog
    
    def _toggle_demo_callback(self):
        """Handle toggle demo window action."""
        self.show_demo_window = not self.show_demo_window
        if self.show_demo_window:
            self.logger.info("Demo window enabled")
        else:
            self.logger.info("Demo window disabled")
    
    # Control callbacks
    def _toggle_fullscreen_output(self):
        """Handle toggle fullscreen output."""
        if self.app:
            self.app.fullscreen_projector = not self.app.fullscreen_projector
            self._update_window_mode()
    
    def _toggle_calibration_mode(self):
        """Handle toggle calibration mode."""
        if self.app:
            self.app.calibration_mode = not self.app.calibration_mode
    
    def _trigger_jump_scare(self):
        """Handle trigger jump-scare effect."""
        if self.app:
            # Trigger flash effect
            self.app.config["effects"]["flash"]["enabled"] = True
            self._update_shader_effects()
            
            # Trigger skeleton swap
            self._swap_skeleton_mode()
    
    def _reset_tracking_calibration(self):
        """Handle reset tracking calibration."""
        if self.app and self.app.tracker:
            self.app.tracker.reset()
            self.app.rigging.reset_calibration()
    
    def _open_settings(self):
        """Handle open settings."""
        # Open settings dialog
        pass
    
    # Panel visibility methods
    def _toggle_panel(self, panel_name: str):
        """Toggle visibility of a panel."""
        if panel_name in self.panel_visibility:
            self.panel_visibility[panel_name] = not self.panel_visibility[panel_name]
    
    # Utility methods
    def _get_available_cameras(self) -> List[str]:
        """Get list of available camera devices."""
        try:
            cameras = self.camera_probe.scan_cameras()
            return [f"Camera {cam['index']}" for cam in cameras]
        except:
            return ["Default Camera"]
    
    def _generate_scene_data(self) -> Dict:
        """Generate scene data for saving."""
        return {
            "timestamp": time.time(),
            "camera_index": self.app.config.get("camera_index", 0) if self.app else 0,
            "warp_coords": self.app.config.get("projector", {}).get("warp_coords", {}),
            "lighting_settings": self.app.config.get("lighting", {}),
            "effect_settings": self.app.config.get("effects", {}),
            "viewport_settings": self.app.config.get("viewport", {})
        }
    
    def _update_window_mode(self):
        """Update window mode (fullscreen/windowed)."""
        if self.app:
            if self.app.fullscreen_projector:
                dpg.maximize_viewport()
            else:
                dpg.restore_viewport()
    
    def _update_shader_effects(self):
        """Update shader effects in the renderer."""
        if self.app and self.app.renderer:
            self.app.renderer.set_shader_effects(self.app.config["effects"])
    
    def _swap_skeleton_mode(self):
        """Swap skeleton rendering mode for jump-scare effect."""
        if self.app and self.app.renderer:
            self.app.renderer.toggle_skeleton_mode()
    
    def _get_available_presets(self) -> List[str]:
        """Get list of available scene presets."""
        # Implementation would scan presets directory
        return ["Default Scene", "Haunted House", "Ghostly Hallway"]

# Global UI manager instance
_ui_manager_instance: Optional[UIManager] = None
def get_ui_manager(app=None) -> UIManager:
    """Get the global UI manager instance."""
    global _ui_manager_instance
    if _ui_manager_instance is None:
        _ui_manager_instance = UIManager(app)
    return _ui_manager_instance
def reset_ui_manager():
    """Reset the global UI manager instance."""
    global _ui_manager_instance
    _ui_manager_instance = None
if __name__ == "__main__":
    # Test the UIManager class
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    print("Testing UIManager...")
    
    # Create UI manager
    ui_manager = UIManager()
    
    print("UI Manager initialized successfully")
    print("Note: Full UI testing requires Dear PyGui display context")