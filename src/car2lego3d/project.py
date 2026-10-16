"""Deployment identity for the independently versioned LLM + Blender project."""

PROJECT_NAME = "Car2LGEO_3D_LLM"
DEFAULT_BACKEND = "gpt-blender"
FRONTEND_PORT = 8778
API_PORT = 8777
LEGACY_WEB_PORT = 8775


def desktop_backend(requested=None):
    if requested and requested != DEFAULT_BACKEND:
        raise ValueError("This project uses LLM + Blender; use Car2LEGO_3D for Hunyuan3D reconstruction")
    return DEFAULT_BACKEND
