# Phantom Engine

## Real-time Haunted House Projection Mapping System

A production-ready, multi-threaded desktop application for real-time computer
vision, 3D skeleton tracking, AI-powered skeleton swapping, custom 3D lighting,
and advanced shader effects for haunted house projection mapping.

---

## Overview

Phantom Engine is an elite real-time graphics software suite designed for
professional haunted house environments. It combines:

- **Multi-threaded real-time computer vision** (OpenCV capture + MediaPipe 3D pose tracking)
- **AI-driven skeleton swapping** (MediaPipe 3D keypoints → bone matrix transformation)
- **Interactive 3D lighting system** (Point, Spot, Directional virtual lights)
- **Advanced shader effects** (Glitch, Flash, Chromatic Aberration, Vignette, Film Grain, Lens Distortion)
- **4-corner projection mapping warp** (keystone correction)

---

## Quick Start

### Prerequisites

- **Python:** 3.8 or higher
- **Hardware:**
  - **GPU:** OpenGL 3.3+ compatible (NVIDIA, AMD, Intel)
  - **CPU:** Multi-core recommended (4+ cores)
  - **RAM:** 8 GB minimum, 16 GB recommended
  - **Camera:** GoPro UVC or USB webcam

### Installation

```bash
# Clone or download the project
cd phantom_engine

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import cv2, mediapipe, moderngl, numpy; print('OK')"
```

### Launch

```bash
# Standard launch
python main.py

# Launch with development tools
python main.py --dev

# Headless mode (for testing)
python main.py --headless
```

### First Run

1. Launch `python main.py`.
2. Select your camera source in the **Camera Feed** panel.
3. Position your actor in frame.
4. Adjust tracking calibration (press `R` to reset baseline).
5. Open the **Calibration** menu and run the 4-corner warp tool.
6. Load a skeleton model via the **Scene Manager** panel.
7. Place virtual lights and configure effects.
8. Trigger jump-scare with `[SPACE]`.

---

## Architecture

```
phantom_engine/
├── main.py                     # Entry point & application lifecycle
├── config.py                   # JSON-based persistent configuration
├── core/
│   ├── capture.py              # Threaded OpenCV video capture
│   ├── camera_probe.py        # Hardware camera detection
│   ├── tracker.py              # MediaPipe 3D pose + EMA smoothing
│   └── rigging.py              # Inverse Kinematics & bone mapping
├── editor/
│   ├── ui_manager.py           # Phantom Studio control panels
│   ├── viewport_3d.py          # Interactive 3D viewport
│   └── projector_warp.py      # 4-corner warp calibration
├── graphics/
│   ├── renderer.py             # ModernGL context & FBO
│   ├── lighting.py             # Virtual 3D light system
│   └── postprocess.py         # Post-processing pipeline
├── shaders/
│   ├── skeleton.vert           # Skeletal vertex shader
│   ├── skeleton.frag           # PBR skeleton material shader
│   ├── post_base.vert          # Screen-space quad
│   ├── post_glitch.frag        # Digital glitch effect
│   ├── post_flash.frag         # Jump-scare flash
│   ├── post_chromatic.frag     # Chromatic aberration
│   ├── post_vignette.frag      # Vignette & color grading
│   ├── post_film_grain.frag    # Film grain
│   └── warp.frag               # Projection warp
├── assets/
│   ├── models/                 # Skeleton models
│   └── presets/                # Scene presets
└── requirements.txt
```

---

## Performance Targets

- **Latency:** Sub-15ms frame loop (60 FPS target with interactive latency <15ms)
- **Threading:** Dedicated threads for capture, tracking, rendering, UI
- **GPU:** OpenGL 3.3+ with FBO off-screen rendering
- **Memory:** Efficient frame buffer management and texture caching

### Hardware Adaptive Profiles

| Profile | Description | GPU Target |
|---------|-------------|------------|
| `low` | Integrated graphics | Integrated GPU |
| `balanced` | Default | Mid-range GPU |
| `high` | High-end | Discrete GPU |
| `ultra` | Maximum quality | High-end discrete GPU |

---

## Features

### 1. Camera Capture

- Threaded OpenCV capture (GoPro UVC / webcam fallback)
- Auto-reconnect on device loss
- Test pattern fallback when no camera available

### 2. AI Skeleton Tracking

- MediaPipe 3D Pose Landmarker (33 keypoints)
- EMA smoothing
- Depth scaling
- World landmarks support

### 3. Skeleton Rigging & IK

- Joint mapping from MediaPipe keypoints to bone hierarchy
- Inverse Kinematics (Faber-Quadrature based)
- Bone matrix alignment
- Auto-calibration with offset mapping

### 4. Custom 3D Lighting

- Virtual Point lights (inverse square falloff)
- Spot lights (cone falloff)
- Directional lights (infinite range)
- Ambient light
- Color temperature control

### 5. Shader Effects Suite

- **Jump-Scare Flash:** Instant skeleton swap with adjustable frequency/decay
- **Digital Glitch:** RGB split, scanlines, noise, block displacement
- **Skeleton Material:** Bone glow, X-ray transparency, wireframe mode, ghostly trails
- **Post-Processing:** Color grading, film grain, lens distortion, vignette

### 6. Projection Mapping

- 4-corner interactive warp
- Mesh warping for complex surfaces
- Automatic calibration convergence

---

## Controls & Keybindings

| Key | Action |
|-----|--------|
| `F11` | Toggle projector fullscreen output |
| `C` | Toggle projector calibration mode |
| `SPACE` | Trigger jump-scare skeleton swap |
| `R` | Reset tracking calibration baseline |
| `ESC` | Open settings / exit |

---

## Configuration

Persistent JSON configuration is stored in:

```
~/.phantom_engine/phantom_config.json
```

---

## Asset Guide

See [ASSET_GUIDE.md](ASSET_GUIDE.md) for detailed instructions on importing
custom 3D skeleton assets from Mixamo, Blender, or Sketchfab.

---

## License

Phantom Engine - Production use for haunted house entertainment systems.
