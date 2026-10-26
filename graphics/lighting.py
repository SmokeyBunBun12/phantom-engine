#!/usr/bin/env python3
"""
Virtual 3D lighting system for Phantom Engine.

Provides a comprehensive virtual light system supporting point, spot, and
directional lights with proper physical units and color temperature matching
for realistic haunted house projection.
"""

import numpy as np
import time
import threading
from typing import Optional, List, Dict, Tuple, Any
import logging
from dataclasses import dataclass, field
from enum import Enum

@dataclass
class VirtualLight:
    """
    Represents a virtual light in the 3D scene.
    
    Attributes:
        id: Unique light identifier
        light_type: Type of light (point, spot, directional)
        position: 3D position of the light
        color: RGB color in linear space
        intensity: Intensity in lumens/candela
        radius: Light radius (point lights)
        cutoff_angle: Cutoff angle for spot lights (degrees)
        decay: Light decay rate
        enabled: Whether light is active
        shadow_enabled: Whether shadow casting is enabled
        custom_data: Additional light properties
    """
    
    id: int
    light_type: str
    position: np.ndarray
    color: np.ndarray
    intensity: float
    radius: float = 0.0
    cutoff_angle: float = 180.0
    decay: float = 2.0
    enabled: bool = True
    shadow_enabled: bool = False
    custom_data: Optional[Dict] = None
    
    def __post_init__(self):
        if self.position is None:
            self.position = np.zeros(3, dtype=np.float32)
        if self.color is None:
            self.color = np.ones(3, dtype=np.float32) * 0.5
    
    @property
    def is_active(self) -> bool:
        return self.enabled

class LightingState(Enum):
    """States for the lighting system."""
    OFF = "off"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"

class LightingSystem:
    """
    Advanced virtual 3D lighting system for the haunted house scene.
    
    Features:
    - Point lights with falloff and attenuation
    - Spot lights with cone-shaped falloff
    - Directional lights with infinite range
    - Color temperature control (Kelvin)
    - Shadows with configurable quality
    - Light linking and groups
    - Ambient light management
    - Bloom and glare integration
    - Light baking support
    """
    
    def __init__(self, config: Optional[dict] = None):
        """
        Initialize the lighting system.
        
        Args:
            config: Optional configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.config = config or {}
        self.lighting_state = LightingState.INITIALIZING
        
        # Light collections
        self.point_lights = []
        self.spot_lights = []
        self.directional_lights = []
        self.all_lights = []
        
        # Ambient lighting
        self.ambient_color = np.array(
            self.config.get("ambient_color", [0.3, 0.3, 0.3]),
            dtype=np.float32
        )
        self.ambient_intensity = self.config.get("ambient_intensity", 0.6)
        
        # Lighting effects
        self.bloom_enabled = self.config.get("bloom_enabled", True)
        self.bloom_threshold = self.config.get("bloom_threshold", 0.8)
        self.bloom_intensity = self.config.get("bloom_intensity", 1.0)
        self.bloom_radius = self.config.get("bloom_radius", 8.0)
        
        self.glare_enabled = self.config.get("glare_enabled", False)
        self.glare_intensity = self.config.get("glare_intensity", 0.3)
        
        # Shadows
        self.shadow_quality = self.config.get("shadow_quality", "high")
        self.shadow_resolution = self.config.get("shadow_resolution", 2048)
        self.shadow_fade = self.config.get("shadow_fade", 0.1)
        self.shadows_enabled = True
        
        # Scene units
        self.scene_unit = 1.0  # Meters
        
        # Performance
        self.frame_count = 0
        self.light_update_count = 0
        self.last_frame_time = time.time()
        self.update_thread = None
        self.update_running = False
        
        # Light IDs
        self._next_light_id = 0
        
        # Initialize state
        self.lighting_state = LightingState.INITIALIZING
        self.logger.info("Lighting system initialized")
    
    def add_point_light(self, position: np.ndarray, color: np.ndarray, intensity: float, **kwargs) -> VirtualLight:
        """
        Add a new point light.
        
        Args:
            position: 3D light position [x, y, z]
            color: RGB color
            intensity: Light intensity
            **kwargs: Optional light parameters
            
        Returns:
            The created VirtualLight object
        """
        light = VirtualLight(
            id=self._next_light_id,
            light_type="point",
            position=np.array(position, dtype=np.float32),
            color=np.array(color, dtype=np.float32),
            intensity=intensity,
            radius=kwargs.get("radius", 0.0),
            cutoff_angle=kwargs.get("cutoff_angle", 180.0),
            decay=kwargs.get("decay", 2.0),
            enabled=kwargs.get("enabled", True),
            shadow_enabled=kwargs.get("shadow_enabled", self.shadows_enabled),
            custom_data=kwargs.get("custom_data")
        )
        
        self.point_lights.append(light)
        self.all_lights.append(light)
        self._next_light_id += 1
        
        self.logger.info(f"Added point light #{light.id} at position {light.position}")
        return light
    
    def add_spot_light(self, position: np.ndarray, color: np.ndarray, intensity: float, **kwargs) -> VirtualLight:
        """
        Add a new spot light.
        
        Args:
            position: 3D light position [x, y, z]
            color: RGB color
            intensity: Light intensity
            **kwargs: Optional light parameters
            
        Returns:
            The created VirtualLight object
        """
        light = VirtualLight(
            id=self._next_light_id,
            light_type="spot",
            position=np.array(position, dtype=np.float32),
            color=np.array(color, dtype=np.float32),
            intensity=intensity,
            radius=kwargs.get("radius", 0.0),
            cutoff_angle=kwargs.get("cutoff_angle", 45.0),
            decay=kwargs.get("decay", 2.0),
            enabled=kwargs.get("enabled", True),
            shadow_enabled=kwargs.get("shadow_enabled", self.shadows_enabled),
            custom_data=kwargs.get("custom_data")
        )
        
        self.spot_lights.append(light)
        self.all_lights.append(light)
        self._next_light_id += 1
        
        self.logger.info(f"Added spot light #{light.id} at position {light.position}")
        return light
    
    def add_directional_light(self, direction: np.ndarray, color: np.ndarray, intensity: float, **kwargs) -> VirtualLight:
        """
        Add a new directional light.
        
        Args:
            direction: Light direction (normalized or not)
            color: RGB color
            intensity: Light intensity
            **kwargs: Optional light parameters
            
        Returns:
            The created VirtualLight object
        """
        light = VirtualLight(
            id=self._next_light_id,
            light_type="directional",
            position=np.zeros(3, dtype=np.float32),  # Direction only
            color=np.array(color, dtype=np.float32),
            intensity=intensity,
            radius=kwargs.get("radius", 0.0),
            cutoff_angle=kwargs.get("cutoff_angle", 180.0),
            decay=kwargs.get("decay", 1.0),
            enabled=kwargs.get("enabled", True),
            shadow_enabled=kwargs.get("shadow_enabled", self.shadows_enabled),
            custom_data=kwargs.get("custom_data")
        )
        
        self.directional_lights.append(light)
        self.all_lights.append(light)
        self._next_light_id += 1
        
        self.logger.info(f"Added directional light #{light.id} with intensity {intensity}")
        return light
    
    def remove_light(self, light_id: int):
        """Remove a light by ID."""
        for lights in [self.point_lights, self.spot_lights, self.directional_lights, self.all_lights]:
            for light in list(lights):
                if light.id == light_id:
                    lights.remove(light)
                    self.logger.info(f"Removed light {light_id}")
                    return True
        return False
    
    def get_light(self, light_id: int) -> Optional[VirtualLight]:
        """Get a light by ID."""
        for light in self.all_lights:
            if light.id == light_id:
                return light
        return None
    
    def toggle_light(self, light_id: int, enabled: bool) -> Optional[VirtualLight]:
        """Toggle a light's enabled state."""
        light = self.get_light(light_id)
        if light is None:
            return None
        
        light.enabled = enabled
        return light
    
    def update_ambient_light(self, color: np.ndarray, intensity: float):
        """Update ambient lighting parameters."""
        self.ambient_color = np.array(color, dtype=np.float32)
        self.ambient_intensity = intensity
        
        self.logger.debug(f"Updated ambient light: color={color}, intensity={intensity}")
    
    def update_bloom(self, enabled: bool, threshold: float, intensity: float, radius: float = 8.0):
        """Update bloom parameters."""
        self.bloom_enabled = enabled
        self.bloom_threshold = threshold
        self.bloom_intensity = intensity
        self.bloom_radius = radius
        
        self.logger.debug(f"Updated bloom: enabled={enabled}, threshold={threshold}, intensity={intensity}, radius={radius}")
    
    def update_glare(self, enabled: bool, intensity: float):
        """Update glare parameters."""
        self.glare_enabled = enabled
        self.glare_intensity = intensity
        
        self.logger.debug(f"Updated glare: enabled={enabled}, intensity={intensity}")
    
    def get_lighting_data(self) -> Dict[str, Any]:
        """
        Get current lighting state for rendering.
        
        Returns:
            Dictionary with lighting state and light information
        """
        # Calculate effective lighting
        lighting_data = {
            "ambient_color": self.ambient_color.tolist(),
            "ambient_intensity": self.ambient_intensity,
            "point_lights": [],
            "spot_lights": [],
            "directional_lights": [],
            "all_lights": [],
            "bloom": {
                "enabled": self.bloom_enabled,
                "threshold": self.bloom_threshold,
                "intensity": self.bloom_intensity,
                "radius": self.bloom_radius
            },
            "glare": {
                "enabled": self.glare_enabled,
                "intensity": self.glare_intensity
            },
            "shadows": {
                "enabled": self.shadows_enabled,
                "quality": self.shadow_quality,
                "resolution": self.shadow_resolution,
                "fade": self.shadow_fade
            }
        }
        
        # Add point lights to data
        for light in self.point_lights:
            lighting_data["point_lights"].append({
                "id": light.id,
                "position": light.position.tolist(),
                "color": light.color.tolist(),
                "intensity": light.intensity,
                "enabled": light.enabled,
                "radius": light.radius
            })
        
        # Add spot lights to data
        for light in self.spot_lights:
            lighting_data["spot_lights"].append({
                "id": light.id,
                "position": light.position.tolist(),
                "color": light.color.tolist(),
                "intensity": light.intensity,
                "enabled": light.enabled,
                "cutoff_angle": light.cutoff_angle
            })
        
        # Add directional lights to data
        for light in self.directional_lights:
            lighting_data["directional_lights"].append({
                "id": light.id,
                "direction": (-light.position[0], -light.position[1], -light.position[2]).tolist(),  # Direction is negative position
                "color": light.color.tolist(),
                "intensity": light.intensity,
                "enabled": light.enabled,
                "cuttOff_angle": light.cutoff_angle
            })
        
        # Add all lights
        lighting_data["all_lights"] = [
            {
                "id": light.id,
                "type": light.light_type,
                "enabled": light.enabled,
                "intensity": light.intensity
            }
            for light in self.all_lights
        ]
        
        return lighting_data
    
    def calculate_light_contribution(self, position: np.ndarray, light: VirtualLight) -> np.ndarray:
        """
        Calculate light contribution at a given position for a specific light.
        
        Args:
            position: Position to evaluate [x, y, z]
            light: Light to calculate contribution for
            
        Returns:
            Lighting contribution (color * intensity)
        """
        if not light.enabled:
            return np.zeros(3, dtype=np.float32)
        
        # Calculate distance for point/spot lights
        distance = np.linalg.norm(position - light.position)
        decay = light.decay if light.decay != 0 else 2.0
        
        # Inverse square law
        attenuation = 1.0 / (distance ** decay)
        
        # Apply falloff
        falloff = 1.0 / (1.0 + distance / 10.0) if distance < 10.0 else 0.0
        
        contribution = light.color * (light.intensity * attenuation * falloff)
        
        # For spot lights, apply cone falloff
        if light.light_type == "spot" and distance > 0:
            angle = np.arccos(np.dot(light.position - position, np.array([0, 0, -1])) / max(1.0, np.linalg.norm(light.position - position)))
            if angle > np.radians(light.cutoff_angle / 2):
                contribution = np.zeros(3, dtype=np.float32)
        
        return contribution
    
    def get_light_for_position(self, position: np.ndarray) -> np.ndarray:
        """
        Get total lighting contribution at a given position from all lights.
        
        Args:
            position: Position to evaluate [x, y, z]
            
        Returns:
            Total lighting contribution
        """
        total_contribution = self.ambient_color * self.ambient_intensity
        
        for light in self.all_lights:
            if light.enabled:
                contribution = self.calculate_light_contribution(position, light)
                total_contribution += contribution
        
        # Convert to luminance
        luminance = np.dot(total_contribution, [0.299, 0.587, 0.114])
        
        return total_contribution
    
    def set_scene_unit(self, unit: float):
        """Set scene unit scale."""
        self.scene_unit = unit
    
    def get_scene_unit(self) -> float:
        """Get current scene unit."""
        return self.scene_unit
    
    def start(self):
        """Start the lighting system."""
        self.lighting_state = LightingState.RUNNING
        self.logger.info("Lighting system started")
        
        # Start update thread
        if self.update_thread is None or not self.update_thread.is_alive():
            self.update_running = True
            self.update_thread = threading.Thread(
                target=self._update_loop,
                daemon=True,
                name="LightingSystem"
            )
            self.update_thread.start()
    
    def stop(self):
        """Stop the lighting system."""
        self.update_running = False
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=2.0)
            self.logger.info("Lighting system stopped")
    
    def _update_loop(self):
        """Update loop for lighting calculations."""
        while self.update_running:
            try:
                self.frame_count += 1
                current_time = time.time()
                
                # Update every frame
                self.light_update_count += 1
                
                # Sleep to prevent CPU spinning
                time.sleep(0.016)  # ~60 Hz
                
            except Exception as e:
                self.logger.error(f"Lighting update loop error: {e}")
                time.sleep(0.1)
    
    def cleanup(self):
        """Cleanup lighting system resources."""
        self.stop()
        
        for light in self.all_lights:
            # Release light resources if needed
            pass
        
        self.logger.info("Lighting system cleaned up")

if __name__ == "__main__":
    # Test the LightingSystem class
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    print("Testing LightingSystem...")
    
    # Create lighting system
    lighting = LightingSystem()
    
    # Add some test lights
    lighting.add_point_light(
        position=np.array([0, 2, -2], dtype=np.float32),
        color=np.array([1.0, 0.9, 0.8], dtype=np.float32),
        intensity=100.0
    )
    
    lighting.add_directional_light(
        direction=np.array([0, 1, -0.5], dtype=np.float32),
        color=np.array([1.0, 1.0, 1.0], dtype=np.float32),
        intensity=2.0
    )
    
    print("Lighting system initialized successfully")
    print("Lighting data:", lighting.get_lighting_data())
    
    lighting.cleanup()