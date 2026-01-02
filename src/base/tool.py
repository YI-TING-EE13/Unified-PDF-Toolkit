from abc import ABC, abstractmethod
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Optional

class BaseTool(ABC):
    """
    Abstract Base Class for all PDF Tools.
    
    This class defines the contract that all specific PDF tools (Compressor, Merger, etc.)
    must follow. It enforces a standard interface for UI rendering and execution.

    Attributes:
        name (str): The display name of the tool (e.g., "Compress").
        icon (str): Short emoji/symbol for the navigation menu (e.g., "📉").
    """
    name: str = "Unnamed"
    icon: str = "⚙"
    
    @abstractmethod
    def render(self, parent: ttk.Frame) -> None:
        """
        Renders the tool's specific UI into the provided parent frame.
        
        Subclasses should implement this method to build their GUI components.
        
        Args:
            parent (ttk.Frame): The Tkinter container provided by the main application
                              where the tool should draw its interface.
        """
        pass
        
    @abstractmethod
    def execute(self, params: Optional[Dict[str, Any]] = None) -> None:
        """
        Executes the tool's core logic.
        
        This method is typically triggered by a 'Start' button in the UI.
        Subclasses should typically run heavy operations in a background thread
        to keep the UI responsive.

        Args:
            params (Optional[Dict[str, Any]]): Optional parameters dictionary.
                                             Defaults to None.
        """
        pass
