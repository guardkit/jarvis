"""Configuration package for Jarvis.

Re-exports :class:`JarvisConfig` for convenience so consumers can write::

    from jarvis.config import JarvisConfig
"""

from jarvis.config.settings import JarvisConfig

__all__ = ["JarvisConfig"]
