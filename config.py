#!/usr/bin/env python3
"""
Configuration management for Phantom Engine.

This module provides persistent JSON-based configuration storage,
keybinding management, and settings for the entire application.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import platform
class ConfigManager:
    """
    Centralized configuration manager for Phantom Engine.
    
    Handles loading, saving, and managing all user preferences and application settings.
    """
    
    def __init__(self, config_file: Optional[str] = None):
        self.platform = platform.system().lower()
        
        # Set default config file path
        if config_file:
            self.config_file = Path(config_file)
        else:
            # Default to user home directory
            home = Path.home()
            self.config_file = home / ".phantom_engine" / "phantom_config.json"
        
        # Ensure directory exists
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Default configuration
        self.default_config = self.get_default_config()
        
        # Current configuration
        self.config = self.load_config()
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get the default configuration dictionary."""
        return {
            # Window settings
            "window": {
                "width": 1920,
                "height": 1080,
                "fullscreen": False,
                "borderless": False,
                "vsync": True,
                "fps_limit": 120,
                "resizable": True
            },
            
            # Camera settings
            "camera": {
                "primary_index": 0,
                "fallback_index": 1,
                "resolution_width": 1920,
                "resolution_height": 1080,
                "fps": 30,
                "auto_reconnect": True,
                "reconnect_interval": 5.0,
                "use_gopro": True
            },
            
            # MediaPipe tracking settings
            "tracker": {
                "model_complexity": 1,  # 0=light, 1=full, 2=heavy
                "smooth_landmarks": True,
                "tracking_concurrency": 1,
                "max_num_hands": 2,
                "min_detection_confidence": 0.5,
                "min_tracking_confidence": 0.5,
                "enable_hand_tracking": False,
                "enable_face_tracking": False,
                "max_num_faces": 1,
                "use_world_landmarks": True,
                "output_scale": 1.0,
                "filtering_enabled": True,
                "ema_alpha": 0.3,
                "depth_scaling": {"base_distance": 100.0, "scale_factor": 1.0}
            },
            
            # Skeleton rigging settings
            "rigging": {
                "ik_solver": "faberique",
                "bone_weight": 0.5,
                "shoulder_offset": [0.0, 0.0, 0.0],
                "hip_offset": [0.0, 0.0, 0.0],
                "knee_bend_limit": 0.8,
                "elbow_twist_compensation": True,
                "auto_calibration": True,
                "calibration_samples": 30,
                "joint_offset_mapping": {}
            },
            
            # 3D Viewport settings
            "viewport": {
                "camera_distance": 500.0,
                "camera_fov": 60.0,
                "camera_pitch": -20.0,
                "camera_yaw": 0.0,
                "camera_roll": 0.0,
                "orbit_speed": 0.002,
                "pan_speed": 0.001,
                "zoom_speed": 0.01,
                "show_axes": True,
                "show_grid": True,
                "show_bbox": False,
                "background_color": [0.1, 0.1, 0.1],
                "clear_color": [0.15, 0.15, 0.15, 1.0],
                "near_clip": 0.1,
                "far_clip": 5000.0
            },
            
            # Lighting system settings
            "lighting": {
                "ambient_color": [0.3, 0.3, 0.3],
                "ambient_intensity": 0.6,
                "point_lights": [],
                "spot_lights": [],
                "directional_lights": [],
                "shadow_quality": "high",
                "shadow_resolution": 2048,
                "shadow_fade": 0.1,
                "bloom_enabled": True,
                "bloom_threshold": 0.8,
                "bloom_intensity": 1.0,
                "glare_enabled": False,
                "glare_intensity": 0.3
            },
            
            # Shader effects settings
            "effects": {
                "glitch": {
                    "enabled": False,
                    "mode": "rgb_split",
                    "intensity": 0.5,
                    "speed": 1.0,
                    "scanline_enabled": True,
                    "scanline_frequency": 60,
                    "noise_amount": 0.1,
                    "displacement_amount": 0.02
                },
                "flash": {
                    "enabled": False,
                    "intensity": 1.0,
                    "duration": 0.5,
                    "frequency": 2.0,
                    "decay_rate": 0.8,
                    "color": [1.0, 1.0, 1.0]
                },
                "chromatic": {
                    "enabled": False,
                    "intensity": 0.5,
                    "offset": 0.5
                },
                "vignette": {
                    "enabled": True,
                    "intensity": 0.6,
                    "roundness": 0.8,
                    "feather": 0.5,
                    "color": [0.0, 0.0, 0.0]
                },
                "color_grading": {
                    "enabled": True,
                    "temperature": 5500,
                    "tint": 0.0,
                    "exposure": 0.0,
                    "contrast": 1.0,
                    "saturation": 1.0,
                    "gamma": 1.0
                },
                "film_grain": {
                    "enabled": True,
                    "intensity": 0.3,
                    "resolution_scale": 0.5
                },
                "lens_distortion": {
                    "enabled": False,
                    "k1": -0.2,
                    "k2": 0.1,
                    "p1": 0.0,
                    "p2": 0.0
                }
            },
            
            # Projector calibration settings
            "projector": {
                "enabled": True,
                "fullscreen": False,
                "warp_enabled": True,
                "default_warmup_time": 2.0,
                "max_warp_iterations": 100,
                "convergence_threshold": 0.01,
                "corner_tracking_enabled": True,
                "auto_level_enabled": True,
                "output_width": 1920,
                "output_height": 1080,
                "warp_coords": {
                    "top_left": [0.0, 0.0],
                    "top_right": [1.0, 0.0],
                    "bottom_left": [0.0, 1.0],
                    "bottom_right": [1.0, 1.0]
                }
            },
            
            # Performance and profiling
            "performance": {
                "profile": "balanced",  # "low", "balanced", "high", "ultra"
                "thread_count": 4,
                "use_gpu_acceleration": True,
                "enable_multithreading": True,
                "render_thread": True,
                "tracker_thread": True,
                "capture_thread": True,
                "memory_optimization": True,
                "cpu_affinity": [],
                "auto_gpu_selection": True,
                "allow_overclock": False,
                "thermal_throttling": True
            },
            
            # Keybindings
            "keybindings": {
                # Global shortcuts
                "toggle_fullscreen": "F11",
                "toggle_projector": "F12",
                "toggle_calibration": "C",
                "trigger_jump_scare": "SPACE",
                "reset_tracking": "R",
                "open_settings": "ESC",
                "save_scene": "Ctrl+S",
                "load_scene": "Ctrl+O",
                "export_warmup": "Ctrl+E",
                "import_preset": "Ctrl+I",
                "reset_defaults": "Ctrl+R",
                "quit": "Ctrl+Q",
                
                # Viewport controls
                "orbit_mode": "MOUSE_LEFT",
                "pan_mode": "MOUSE_MIDDLE",
                "zoom_mode": "MOUSE_RIGHT",
                "select_object": "MOUSE_LEFT",
                "move_object": "G",
                "rotate_object": "R",
                "scale_object": "S",
                "duplicate_object": "D",
                "delete_object": "DELETE",
                
                # Effect controls
                "toggle_glitch": "G",
                "toggle_flash": "F",
                "toggle_chromatic": "H",
                "toggle_vignette": "V",
                "toggle_bloom": "B",
                "toggle_grain": "J",
                "toggle_distortion": "K",
                
                # Camera controls
                "switch_camera": "TAB",
                "capture_frame": "PERIOD",
                "record_video": "SLASH",
                
                # Lighting controls
                "toggle_lighting": "L",
                "add_point_light": "1",
                "add_spot_light": "2",
                "add_directional_light": "3",
                "light_editor": "M"
            },
            
            # UI and appearance
            "ui": {
                "dock_style": "standard",
                "panel_visibility": {
                    "camera_feed": True,
                    "tracker_overlay": True,
                    "lighting_panel": True,
                    "effect_panel": True,
                    "scene_panel": True,
                    "log_panel": True
                },
                "theme": "dark",
                "font_scale": 1.0,
                "icon_style": "phantom",
                "animation_enabled": True,
                "animation_speed": 1.0,
                "tooltips_enabled": True,
                "status_bar": True,
                "minimap_enabled": False
            },
            
            # Session management
            "session": {
                "autosave": True,
                "autosave_interval": 300.0,  # 5 minutes
                "max_history": 10,
                "scene_name": "default_scene",
                "last_used_model": "",
                "model_cache": True,
                "preload_models": True,
                "model_cache_size": 1024,  # MB
                "backup_enabled": True,
                "backup_interval": 3600.0  # 1 hour
            },
            
            # Debug and development
            "debug": {
                "enabled": False,
                "log_level": "INFO",
                "log_file": "phantom_engine.log",
                "perf_monitoring": True,
                "frame_time_display": True,
                "fps_display": True,
                "memory_usage": True,
                "gpu_metrics": True,
                "validation_enabled": True,
                "validation_verbose": False,
                "profile_export": False,
                "profile_file": "phantom_profile.json"
            }
        }
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                
                # Merge with defaults to ensure all keys exist
                merged_config = self.default_config.copy()
                self._deep_merge(merged_config, loaded_config)
                
                return merged_config
            except Exception as e:
                print(f"Warning: Failed to load config file ({e}), using defaults")
                return self.default_config.copy()
        else:
            # Create default config file
            self.save_config(self.default_config)
            return self.default_config.copy()
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]):
        """Deep merge override dict into base dict."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def save_config(self):
        """Save current configuration to JSON file."""
        try:
            # Create backup of current config
            backup_file = self.config_file.with_suffix('.json.backup')
            if self.config_file.exists():
                import shutil
                shutil.copy2(self.config_file, backup_file)
            
            # Save main config
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
                
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Example: config.get("camera.primary_index") -> 0
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any):
        """
        Set a configuration value using dot notation.
        
        Example: config.set("camera.primary_index", 1)
        """
        keys = key_path.split('.')
        target = self.config
        
        for i, key in enumerate(keys[:-1]):
            if key not in target:
                target[key] = {}
            target = target[key]
        
        target[keys[-1]] = value
        
        # Auto-save after setting
        self.save_config()
    
    def reset_to_defaults(self):
        """Reset all configuration values to defaults."""
        self.config = self.default_config.copy()
        self.save_config()
        return True
    
    def export_config(self, file_path: Optional[str] = None) -> str:
        """
        Export configuration to a file.
        
        Args:
            file_path: Optional path to export to. If None, uses timestamped file.
        """
        if file_path is None:
            import time
            timestamp = int(time.time())
            file_path = f"phantom_config_{timestamp}.json"
        
        try:
            with open(file_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            return file_path
        except Exception as e:
            print(f"Error exporting config: {e}")
            return ""
    
    def import_config(self, file_path: str) -> bool:
        """
        Import configuration from a file.
        
        Args:
            file_path: Path to the config file to import.
        """
        try:
            with open(file_path, 'r') as f:
                imported_config = json.load(f)
            
            # Merge imported config with defaults
            merged_config = self.default_config.copy()
            self._deep_merge(merged_config, imported_config)
            
            self.config = merged_config
            self.save_config()
            return True
        except Exception as e:
            print(f"Error importing config: {e}")
            return False
    
    def validate_config(self) -> tuple:
        """
        Validate the current configuration.
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        warnings = []
        
        # Check window settings
        window_width = self.config.get("window", {}).get("width", 0)
        window_height = self.config.get("window", {}).get("height", 0)
        if window_width <= 0 or window_height <= 0:
            errors.append("Window dimensions must be positive")
        
        # Check camera settings
        camera_index = self.config.get("camera", {}).get("primary_index", 0)
        if camera_index < 0:
            warnings.append("Camera index is negative, using fallback")
        
        # Check performance settings
        profile = self.config.get("performance", {}).get("profile", "balanced")
        if profile not in ["low", "balanced", "high", "ultra"]:
            errors.append(f"Invalid performance profile: {profile}")
        
        # Check keybindings (basic validation)
        keybindings = self.config.get("keybindings", {})
        for key, binding in keybindings.items():
            if not binding or not isinstance(binding, str):
                warnings.append(f"Keybinding '{key}' is invalid")
        
        # Check UI settings
        ui_theme = self.config.get("ui", {}).get("theme", "dark")
        if ui_theme not in ["light", "dark", "auto"]:
            warnings.append(f"Invalid UI theme: {ui_theme}")
        
        # Check shader effects
        effects = self.config.get("effects", {})
        for effect_name, effect_config in effects.items():
            if not isinstance(effect_config, dict):
                warnings.append(f"Effect '{effect_name}' configuration is not a dictionary")
        
        is_valid = len(errors) == 0
        return is_valid, errors + warnings

# Global configuration instance
_config_instance: Optional[ConfigManager] = None
def get_config() -> ConfigManager:
    """Get the global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance
def reset_config():
    """Reset the global configuration instance."""
    global _config_instance
    _config_instance = None
if __name__ == "__main__":
    # Test configuration manager
    config = ConfigManager()
    print("Default window width:", config.get("window.width"))
    print("Current camera index:", config.get("camera.primary_index"))
    print("Validation result:", config.validate_config())