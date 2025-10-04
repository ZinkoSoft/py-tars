#!/usr/bin/env python3
"""
Quick test script to verify OpenGL is working correctly in the Docker container.
Run this inside the container to check OpenGL setup.
"""

import sys

def test_opengl_imports():
    """Test that OpenGL libraries can be imported."""
    print("=" * 60)
    print("Testing OpenGL Imports")
    print("=" * 60)
    
    try:
        from OpenGL.GL import glGetString, GL_VERSION, GL_VENDOR, GL_RENDERER
        print("✓ OpenGL.GL imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import OpenGL.GL: {e}")
        return False
    
    try:
        import pygame
        from pygame.locals import DOUBLEBUF, OPENGL
        print("✓ Pygame with OpenGL support imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import pygame OpenGL: {e}")
        return False
    
    return True

def test_opengl_context():
    """Test creating an OpenGL context with pygame."""
    print("\n" + "=" * 60)
    print("Testing OpenGL Context Creation")
    print("=" * 60)
    
    try:
        import pygame
        from pygame.locals import DOUBLEBUF, OPENGL
        from OpenGL.GL import (
            glGetString, glClearColor, glClear,
            GL_VERSION, GL_VENDOR, GL_RENDERER, GL_COLOR_BUFFER_BIT
        )
        
        pygame.init()
        screen = pygame.display.set_mode((640, 480), DOUBLEBUF | OPENGL)
        print("✓ OpenGL context created successfully")
        
        # Get OpenGL info
        vendor = glGetString(GL_VENDOR)
        renderer = glGetString(GL_RENDERER)
        version = glGetString(GL_VERSION)
        
        if vendor:
            print(f"  Vendor: {vendor.decode('utf-8')}")
        if renderer:
            print(f"  Renderer: {renderer.decode('utf-8')}")
        if version:
            print(f"  Version: {version.decode('utf-8')}")
        
        # Test basic rendering
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)
        pygame.display.flip()
        print("✓ Basic OpenGL rendering successful")
        
        pygame.quit()
        return True
        
    except Exception as e:
        print(f"✗ Failed to create OpenGL context: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_environment():
    """Check relevant environment variables."""
    print("\n" + "=" * 60)
    print("Environment Variables")
    print("=" * 60)
    
    import os
    
    env_vars = [
        'DISPLAY',
        'SDL_VIDEODRIVER',
        'LIBGL_ALWAYS_INDIRECT',
        'LIBGL_ALWAYS_SOFTWARE',
        'MESA_GL_VERSION_OVERRIDE',
        'MESA_GLSL_VERSION_OVERRIDE',
    ]
    
    for var in env_vars:
        value = os.environ.get(var, '(not set)')
        print(f"  {var}: {value}")

def check_dri_devices():
    """Check if DRI devices are accessible."""
    print("\n" + "=" * 60)
    print("DRI Devices")
    print("=" * 60)
    
    import os
    import stat
    
    dri_path = "/dev/dri"
    
    if not os.path.exists(dri_path):
        print(f"✗ {dri_path} does not exist")
        return False
    
    try:
        devices = os.listdir(dri_path)
        if not devices:
            print(f"✗ {dri_path} is empty")
            return False
        
        print(f"✓ Found {len(devices)} DRI device(s):")
        for device in sorted(devices):
            device_path = os.path.join(dri_path, device)
            try:
                st = os.stat(device_path)
                mode = stat.filemode(st.st_mode)
                print(f"  {device}: {mode}")
            except Exception as e:
                print(f"  {device}: Error accessing - {e}")
        
        return True
    except Exception as e:
        print(f"✗ Failed to list {dri_path}: {e}")
        return False

def main():
    """Run all OpenGL tests."""
    print("\n" + "=" * 60)
    print("TARS OpenGL Docker Test")
    print("=" * 60 + "\n")
    
    results = []
    
    # Check environment
    check_environment()
    
    # Check DRI devices
    dri_ok = check_dri_devices()
    results.append(("DRI Devices", dri_ok))
    
    # Test imports
    imports_ok = test_opengl_imports()
    results.append(("OpenGL Imports", imports_ok))
    
    # Test context creation (only if imports worked)
    if imports_ok:
        context_ok = test_opengl_context()
        results.append(("OpenGL Context", context_ok))
    else:
        results.append(("OpenGL Context", False))
        print("\n✗ Skipping context test due to import failures")
    
    # Print summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed! OpenGL is working correctly.")
        print("=" * 60)
        return 0
    else:
        print("✗ Some tests failed. Check the output above for details.")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
