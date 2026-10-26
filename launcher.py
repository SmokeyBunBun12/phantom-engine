#!/usr/bin/env python3
"""
Launch script for Phantom Engine.

Provides convenient launch methods for different platforms and modes.
"""

import os
import sys
import subprocess
import platform
import argparse
from pathlib import Path


def launch_dev():
    """Launch Phantom Engine in development mode."""
    return [
        sys.executable, "-m", "dev.launcher",
        "--dev"
    ]


def launch(headless: bool = False, config_path: str = None):
    """Launch Phantom Engine with optional parameters."""
    command = [sys.executable, "main.py"]
    
    if headless:
        command.extend(["--headless"])
    
    if config_path:
        command.extend(["--config", config_path])
    
    return command


def main():
    """Main entry point for launching Phantom Engine."""
    parser = argparse.ArgumentParser(description="Phantom Engine - Real-time Haunted House Projection Mapping")
    parser.add_argument("--dev", action="store_true", help="Run in development mode")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--config", type=str, default=None, help="Path to custom config file")
    parser.add_argument("--port", type=int, default=8080, help="Port for debugging server")
    parser.add_argument("--gpu", type=str, default="auto", help="GPU selection (auto, cpu, cuda, metal, vulkan)")
    
    args = parser.parse_args()
    
    # Set environment variables
    os.environ["PHANTOM_ENGINE"] = "1"
    
    if args.gpu != "auto":
        os.environ["PHANTOM_GPU"] = args.gpu
    
    # Build command
    command = launch(headless=args.headless, config_path=args.config)
    
    if args.dev:
        command = launch_dev()
    
    # Run
    try:
        os.execvp(command[0], command)
    except Exception as e:
        print(f"Error launching Phantom Engine: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
