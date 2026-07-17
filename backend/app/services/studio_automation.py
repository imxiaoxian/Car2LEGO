"""BrickLink Studio automation via Windows UI Automation.

Leverages pywinauto to programmatically control Studio 2.0:
  - Open .io files
  - Trigger photorealistic renders (POV-Ray)
  - Export building instructions (PDF)
  - Export BrickLink parts list (XML)
  - Take viewport screenshots
  - Apply custom decals via PartDesigner

Studio is Unity-based — the automation sends keyboard shortcuts
and menu commands to the Studio window.

Hotkeys discovered:
  Ctrl+O       — Open file
  Ctrl+Shift+R — Render (photorealistic)
  Ctrl+R       — Quick render
  Ctrl+Shift+E — Export parts list
  Ctrl+I       — Generate instructions
  F7           — Toggle steps mode
  F8           — Hide/show parts
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Optional

import os
STUDIO_PATH = os.getenv("STUDIO_PATH", r"D:\lego\Studio 2.0\Studio.exe")
PARTDESIGNER_PATH = os.getenv("PARTDESIGNER_PATH", r"D:\lego\Studio 2.0\patcher2\Patcher.exe")


class StudioAutomation:
    """Programmatic control of BrickLink Studio."""

    def __init__(self, studio_path: str = STUDIO_PATH):
        self.studio_path = studio_path
        self.process: subprocess.Popen | None = None
        self.app = None
        self.main_window = None

    # ── Launch / Connect ──────────────────────────

    def launch(self, io_file: str | None = None) -> bool:
        """Launch Studio, optionally opening a .io file.

        Returns True if Studio launched successfully.
        """
        args = [self.studio_path]
        if io_file and os.path.exists(io_file):
            args.append(os.path.abspath(io_file))

        try:
            self.process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            # Wait for Studio window to appear
            time.sleep(3)

            from pywinauto import Application
            self.app = Application(backend="uia").connect(
                path=self.studio_path, timeout=10
            )
            self.main_window = self.app.top_window()
            return True
        except Exception as e:
            print(f"[StudioAuto] Launch failed: {e}")
            return False

    def connect(self) -> bool:
        """Connect to an already-running Studio instance."""
        try:
            from pywinauto import Application
            self.app = Application(backend="uia").connect(
                path=self.studio_path, timeout=5
            )
            self.main_window = self.app.top_window()
            return True
        except Exception as e:
            print(f"[StudioAuto] Connect failed: {e}")
            return False

    def is_running(self) -> bool:
        """Check if Studio is currently running."""
        try:
            self.connect()
            return self.main_window is not None
        except Exception:
            return False

    # ── File Operations ───────────────────────────

    def open_file(self, io_file: str) -> bool:
        """Open a .io file in Studio."""
        if not os.path.exists(io_file):
            print(f"[StudioAuto] File not found: {io_file}")
            return False

        try:
            abs_path = os.path.abspath(io_file)
            # Send Ctrl+O
            self.main_window.type_keys("^o")
            time.sleep(0.5)
            # Type the file path into the open dialog
            self.main_window.type_keys(abs_path)
            time.sleep(0.3)
            self.main_window.type_keys("{ENTER}")
            time.sleep(2)
            return True
        except Exception as e:
            print(f"[StudioAuto] Open failed: {e}")
            # Fallback: launch new instance with the file
            return self.launch(io_file)

    # ── Render ────────────────────────────────────

    def render(self, wait: bool = True, timeout: int = 300) -> Optional[str]:
        """Trigger photorealistic render (Ctrl+Shift+R).

        If wait=True, blocks until render completes.
        Returns the path to the rendered image, if found.
        """
        try:
            self._ensure_window()
            self.main_window.set_focus()
            time.sleep(0.3)
            self.main_window.type_keys("^+r")  # Ctrl+Shift+R
            print("[StudioAuto] Render started...")

            if wait:
                return self._wait_for_render(timeout)
            return None
        except Exception as e:
            print(f"[StudioAuto] Render failed: {e}")
            return None

    def _wait_for_render(self, timeout: int = 300) -> Optional[str]:
        """Wait for render to complete by watching for the render window to close."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                # Check if render progress dialog exists
                dialogs = self.app.windows()
                for dlg in dialogs:
                    if "render" in dlg.window_text().lower():
                        time.sleep(2)
                        continue
                # If no render dialog, render might be done
                break
            except Exception:
                break
            time.sleep(3)
        print("[StudioAuto] Render completed")
        # Find the most recent render output
        return self._find_render_output()

    def _find_render_output(self) -> Optional[str]:
        """Find the most recently rendered image."""
        render_dirs = [
            os.path.expanduser("~/Documents/Studio/Renders"),
            os.path.expanduser("~/Pictures/Studio"),
            os.path.join(os.path.dirname(self.studio_path), "Renders"),
        ]
        for d in render_dirs:
            if os.path.isdir(d):
                files = sorted(
                    Path(d).glob("*.png"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if files:
                    return str(files[0])
        return None

    # ── Export ────────────────────────────────────

    def export_parts_list(self, output_path: str) -> bool:
        """Export BrickLink-compatible parts list XML.

        Studio → File → Export as → Parts List → BrickLink XML
        """
        try:
            self._ensure_window()
            self.main_window.set_focus()
            time.sleep(0.3)
            self.main_window.type_keys("^+e")  # Ctrl+Shift+E
            time.sleep(1)

            # Navigate the export dialog
            # Type output path
            self.main_window.type_keys(os.path.abspath(output_path))
            time.sleep(0.3)
            self.main_window.type_keys("{ENTER}")
            time.sleep(2)
            return os.path.exists(output_path)
        except Exception as e:
            print(f"[StudioAuto] Export failed: {e}")
            return False

    def export_instructions(self, output_path: str) -> bool:
        """Export PDF building instructions.

        Studio → Instruction → Generate → Export PDF
        """
        try:
            self._ensure_window()
            self.main_window.set_focus()
            time.sleep(0.3)
            # Ctrl+I opens instruction designer
            self.main_window.type_keys("^i")
            time.sleep(3)
            # After instruction designer opens, export
            self.main_window.type_keys("^+e")
            time.sleep(1)
            self.main_window.type_keys(os.path.abspath(output_path))
            time.sleep(0.3)
            self.main_window.type_keys("{ENTER}")
            time.sleep(5)
            return os.path.exists(output_path)
        except Exception as e:
            print(f"[StudioAuto] Instructions export failed: {e}")
            return False

    # ── Screenshot ────────────────────────────────

    def screenshot(self, output_path: str) -> bool:
        """Take a screenshot of the Studio 3D viewport."""
        try:
            self._ensure_window()
            self.main_window.set_focus()
            time.sleep(0.5)

            from PIL import ImageGrab
            # Get window rect
            rect = self.main_window.rectangle()
            bbox = (rect.left, rect.top, rect.right, rect.bottom)
            img = ImageGrab.grab(bbox)
            img.save(output_path, "PNG")
            print(f"[StudioAuto] Screenshot saved: {output_path}")
            return True
        except Exception as e:
            print(f"[StudioAuto] Screenshot failed: {e}")
            # Fallback: use pyautogui if available
            try:
                import pyautogui
                pyautogui.screenshot(output_path)
                return True
            except Exception:
                return False

    # ── Decal / PartDesigner ──────────────────────

    def open_partdesigner(self) -> bool:
        """Launch PartDesigner for custom decals."""
        try:
            subprocess.Popen([PARTDESIGNER_PATH])
            time.sleep(3)
            return True
        except Exception as e:
            print(f"[StudioAuto] PartDesigner launch failed: {e}")
            return False

    # ── Close ─────────────────────────────────────

    def close(self):
        """Close Studio."""
        try:
            if self.main_window:
                self.main_window.type_keys("%{F4}")  # Alt+F4
                time.sleep(1)
                # Confirm save dialog if appears
                try:
                    self.main_window.type_keys("n")  # Don't save
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            if self.process:
                try:
                    self.process.terminate()
                except Exception:
                    pass
            self.process = None
            self.app = None
            self.main_window = None

    # ── Helpers ───────────────────────────────────

    def _ensure_window(self):
        """Ensure we have a valid window handle."""
        if not self.main_window:
            if not self.connect():
                raise RuntimeError("Studio is not running")


# ── High-level operations ────────────────────────

def open_design_in_studio(io_file: str) -> dict:
    """Open a .io design file in BrickLink Studio.

    This is the primary entry point — call this after generating a .io file.
    Studio handles everything: 3D view, rendering, instructions, export.
    """
    result = {
        "success": False,
        "studio_opened": False,
        "file_opened": False,
        "io_path": os.path.abspath(io_file),
    }

    if not os.path.exists(io_file):
        result["error"] = f"File not found: {io_file}"
        return result

    auto = StudioAutomation()

    # Try connecting to existing Studio first
    if auto.connect():
        result["studio_opened"] = True
        result["file_opened"] = auto.open_file(io_file)
    else:
        # Launch new Studio with the file
        result["studio_opened"] = auto.launch(io_file)
        result["file_opened"] = result["studio_opened"]

    result["success"] = result["file_opened"]
    return result


def render_design(io_file: str, output_dir: str | None = None) -> dict:
    """Open a design in Studio and trigger photorealistic rendering.

    Studio uses POV-Ray for photorealistic rendering.
    Returns path to rendered image.
    """
    if not output_dir:
        output_dir = str(Path(io_file).parent)

    result = open_design_in_studio(io_file)
    if not result["success"]:
        return result

    auto = StudioAutomation()
    auto.connect()
    render_path = auto.render(wait=True, timeout=300)
    result["render_path"] = render_path
    return result
