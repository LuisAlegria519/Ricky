"""
Ricky AI Assistant

A personal assistant for handling email replies, 3D printing quotes,
verbal inquiries, and other small tasks using Google APIs.

Main components:
- RickyAssistant: Core assistant class
- Web UI: Browser-based interface
- CLI: Command-line interface with voice support
- Status UI: Real-time status indicator
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .assistant import RickyAssistant

__all__ = ["RickyAssistant", "__version__"]
