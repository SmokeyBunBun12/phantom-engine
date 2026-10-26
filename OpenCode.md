# OpenCode Context: Phantom Engine

## Project Overview
Phantom Engine is a real-time Python desktop application for haunted house projection mapping, AI skeleton swapping (MediaPipe 3D), custom OpenGL lighting, and advanced fragment shader effects.

## Core Tech Stack
- **Language:** Python 3.10+
- **Capture:** OpenCV (`cv2`) for UVC / GoPro feeds
- **Tracking:** MediaPipe 3D Pose Landmarker (threaded)
- **Rendering:** `moderngl` and `moderngl-window`
- **UI & Viewport:** Dear ImGui / PyQt integration for the 3D Studio editor layout, lighting controls, and 4-corner projection mapping warp.

## Architecture Rules
- Keep modules modular (`core/`, `editor/`, `graphics/`, `shaders/`).
- Ensure native cross-platform execution (Linux and Windows).
- Target sub-15ms loop performance.
