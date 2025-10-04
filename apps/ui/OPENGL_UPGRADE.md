# OpenGL Upgrade for TARS UI

## Overview
Updated the TARS UI (`apps/ui/main.py`) to utilize OpenGL rendering with pygame, following the pattern from `module_ui.py`. This provides better performance and enables hardware-accelerated graphics.

## Key Changes

### 1. Added OpenGL Imports
```python
from pygame.locals import DOUBLEBUF, OPENGL
from OpenGL.GL import (
    glClear, glClearColor, glEnable, glDisable, glBlendFunc,
    glViewport, glMatrixMode, glLoadIdentity, glOrtho,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, GL_BLEND,
    GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_PROJECTION, GL_MODELVIEW,
    GL_TEXTURE_2D
)
```

### 2. Updated Display Mode
Changed from regular pygame display to OpenGL double-buffered mode:
```python
flags = DOUBLEBUF | OPENGL
if FULLSCREEN:
    flags |= pygame.FULLSCREEN
self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
```

### 3. Added OpenGL Initialization
New `_init_opengl()` method that:
- Sets clear color to dark background (0.02, 0.02, 0.03)
- Enables alpha blending for transparency
- Sets up 2D orthographic projection matching screen dimensions
- Configures proper viewport

### 4. Hybrid Rendering Approach
Uses an **offscreen pygame surface** for 2D rendering, then converts to OpenGL texture:

- **Offscreen Surface**: All pygame 2D operations (text, components) render to `self.offscreen_surface`
- **OpenGL Conversion**: `_pygame_surface_to_opengl()` converts the surface to an OpenGL texture
- **Display**: OpenGL renders the texture as a full-screen quad

### 5. Benefits

1. **Hardware Acceleration**: OpenGL uses GPU for rendering
2. **Better Performance**: Especially for complex scenes and effects
3. **Future Extensibility**: Can easily add:
   - 3D elements
   - Particle effects
   - Advanced shaders
   - Post-processing effects
4. **Maintains Compatibility**: All existing pygame components work unchanged

### 6. Architecture

```
┌─────────────────────────────────────┐
│  Pygame Components (2D)             │
│  - Text rendering                   │
│  - Spectrum bars                    │
│  - TARS idle animation              │
└────────────┬────────────────────────┘
             │ Render to
             ▼
┌─────────────────────────────────────┐
│  Offscreen Pygame Surface           │
│  (WIDTH x HEIGHT, RGBA)             │
└────────────┬────────────────────────┘
             │ Convert to texture
             ▼
┌─────────────────────────────────────┐
│  OpenGL Texture                     │
│  - glTexImage2D()                   │
└────────────┬────────────────────────┘
             │ Render as quad
             ▼
┌─────────────────────────────────────┐
│  OpenGL Framebuffer (Screen)        │
│  - Hardware accelerated             │
└─────────────────────────────────────┘
```

## Migration Notes

### No Breaking Changes
- All existing components work without modification
- Components still receive a pygame surface for rendering
- Configuration files remain unchanged

### Performance Considerations
1. **Texture Upload**: The `_pygame_surface_to_opengl()` method uploads texture data each frame
2. **Optimization Opportunity**: For static elements, could cache textures
3. **Memory**: Offscreen surface requires additional VRAM (~WIDTH × HEIGHT × 4 bytes)

### Future Enhancements
With OpenGL foundation in place, we can now add:
- **Shaders**: Custom GLSL shaders for visual effects
- **3D Elements**: Rotating logos, 3D visualizations
- **Particles**: Particle systems for visual feedback
- **Post-Processing**: Bloom, motion blur, color grading
- **Multiple Render Targets**: Render to texture for complex effects

## Testing
1. Start the UI: `cd apps/ui && python main.py`
2. Verify:
   - Display initializes with OpenGL context
   - All text renders correctly with fade effects
   - Spectrum bars animate smoothly
   - STT/LLM/TTS messages display properly
   - No performance regression

## Dependencies
Ensure PyOpenGL is installed:
```bash
pip install PyOpenGL PyOpenGL-accelerate
```

## References
- Inspired by: `.tars-ai-community-modules/module_ui.py`
- OpenGL Pygame integration: https://www.pygame.org/wiki/OpenGLTutorial
- PyOpenGL docs: http://pyopengl.sourceforge.net/documentation/index.html
