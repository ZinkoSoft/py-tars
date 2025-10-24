#!/usr/bin/env python3
"""Find available camera devices and their capabilities."""

import cv2
import sys

def test_camera(index):
    """Test if a camera index is accessible and get basic info."""
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        return None
    
    # Get camera properties
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    # Try to read a frame
    ret, frame = cap.read()
    cap.release()
    
    if ret and frame is not None:
        return {
            'width': int(width),
            'height': int(height),
            'fps': int(fps),
            'frame_shape': frame.shape
        }
    return None

def main():
    print("Scanning for camera devices...\n")
    
    found_cameras = []
    
    # Test indices 0-20 (covers your range)
    for i in range(21):
        print(f"Testing /dev/video{i}...", end=" ")
        info = test_camera(i)
        
        if info:
            print(f"✓ FOUND")
            print(f"  Resolution: {info['width']}x{info['height']}")
            print(f"  FPS: {info['fps']}")
            print(f"  Frame shape: {info['frame_shape']}")
            found_cameras.append(i)
        else:
            print("✗")
    
    print("\n" + "="*50)
    if found_cameras:
        print(f"Working camera indices: {found_cameras}")
        print(f"\nRecommended: Use index {found_cameras[0]} (first working camera)")
    else:
        print("No working cameras found!")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
