"""Turn a plain-text TikTok plot into a HyperFrames video brief.

One line of plot == one scene == one picture with on-screen text.
"""

from .parser import Plot, Scene, ParseError, parse_plot, parse_plot_file
from .prompt import build_prompt
from .storyboard import build_storyboard

__version__ = "0.1.0"

__all__ = [
    "Plot",
    "Scene",
    "ParseError",
    "parse_plot",
    "parse_plot_file",
    "build_prompt",
    "build_storyboard",
]
