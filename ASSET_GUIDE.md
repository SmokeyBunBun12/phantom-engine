# Phantom Engine - Asset Guide

## Overview

The Phantom Engine supports importing custom 3D skeleton models for AI-powered
skeleton swapping and projection mapping. This guide explains how to prepare
and import models from various sources.

## Supported Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| GLTF (JSON) | `.gltf` | Text-based, good for development |
| GLTF (Binary) | `.glb` | Binary container, efficient storage |
| Wavefront OBJ | `.obj` | Legacy format, widely supported |

## Importing from Mixamo

1. Download a character model from [Mixamo](https://www.mixamo.com/) with animations.
2. Ensure the model has:
   - Hip/pelvis bone as root
   - Spine bones (spine, chest, neck)
   - Upper arm chains (clavicle, upper arm, forearm, hand)
   - Lower arm chains (femur, tibia, fibula, foot)
   - Neck and head bones
3. Convert to GLTF using the Mixamo Blender addon or online converter.
4. Place in `assets/models/` directory.

## Importing from Blender

1. Export model as GLTF (with animations) or OBJ.
2. In Blender, ensure proper bone naming:
   - `hip`, `spine`, `chest`, `neck`, `head`
   - `clavicle_L`, `clavicle_R`, `upper_arm_L`, `upper_arm_R`, `forearm_L`, `forearm_R`, `hand_L`, `hand_R`
   - `femur_L`, `femur_R`, `tibia_L`, `tibia_R`, `foot_L`, `foot_R`
3. Export with "Export to glTF 2.0" enabled.

## Importing from Sketchfab

1. Import model into Blender or use the Sketchfab Blender uploader.
2. Ensure the skeleton is properly retargeted to a standard bone set.
3. Export as GLTF binary.

## Bone Hierarchy Requirements

The Phantom Engine expects the following bone hierarchy structure:

```
Root (pelvis/hip)
├── Spine
│   ├── Chest
│   └── Neck
│       └── Head
├── Left Upper Arm
│   ├── Clavicle
│   ├── Upper Arm
│   ├── Forearm
│   └── Hand
├── Left Lower Arm
├── Right Upper Arm
├── Right Lower Arm
├── Left Leg
│   ├── Femur
│   ├── Tibia
│   └── Foot
├── Right Leg
│   ├── Femur
│   ├── Tibia
│   └── Foot
└── ... additional bones
```

## Calibration Procedure

1. Launch Phantom Engine with `python main.py`.
2. Load your skeleton model via the Scene Manager panel.
3. Use the calibration tool in the 3D Viewport to align joints:
   - Frontal view calibration (for forward kinematics)
   - Side view calibration (for lateral alignment)
4. Adjust joint offset scaling via the UI sliders in the rigging panel.

## Joint Offset Scaling

MediaPipe produces 3D coordinates relative to the camera. The engine applies
joint offsets to map these to the skeleton bone hierarchy.

Access the offset mapping via:
```
phantom_engine -> Settings -> Advanced -> Joint Offset Mapping
```

Or programmatically via `config.py`:

```python
from config import get_config
config = get_config()
config.set("rigging.joint_offset_mapping", {11: {"x": 0.0, "y": 0.0, "z": 0.0}})
```

## Troubleshooting

- **Missing bones**: Verify all expected bones exist in the model.
- **Poor tracking**: Adjust EMA smoothing alpha and depth scaling.
- **Incorrect offsets**: Use the calibration tools and adjust offsets.
