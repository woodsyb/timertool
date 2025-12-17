"""Main entry point for Timer Tool application."""

import tkinter as tk
from tkinter import ttk
import sys
import os
import socket
import threading

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db
import timer_engine
from ui.main_window import MainWindow

# Try to import theming libraries
try:
    import sv_ttk
    SV_TTK_AVAILABLE = True
except ImportError:
    SV_TTK_AVAILABLE = False

try:
    import pywinstyles
    PYWINSTYLES_AVAILABLE = True
except ImportError:
    PYWINSTYLES_AVAILABLE = False

# Single instance port
SINGLE_INSTANCE_PORT = 47839

# Try to import pystray for system tray support
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False


def create_tray_icon():
    """Create a simple icon for the system tray."""
    # Create a simple clock icon
    size = 64
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Draw circle
    margin = 4
    draw.ellipse([margin, margin, size - margin, size - margin], fill='#2196F3', outline='white', width=2)

    # Draw clock hands
    center = size // 2
    # Hour hand
    draw.line([center, center, center, center - 15], fill='white', width=3)
    # Minute hand
    draw.line([center, center, center + 12, center - 8], fill='white', width=2)

    return image


def check_single_instance():
    """Check if another instance is running. Returns True if we should continue, False if another instance exists."""
    try:
        # Try to connect to existing instance
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', SINGLE_INSTANCE_PORT))
        sock.send(b'SHOW')
        sock.close()
        return False  # Another instance exists, we sent it SHOW command
    except ConnectionRefusedError:
        return True  # No other instance, we can start
    except Exception:
        return True  # Error, try to start anyway


class TimerApp:
    """Main application class."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Timer Tool")
        self.root.geometry("360x600")
        self.root.minsize(340, 560)

        # Start single instance listener
        self._start_instance_listener()

        # Set icon if available
        try:
            if TRAY_AVAILABLE:
                icon = create_tray_icon()
                from PIL import ImageTk
                self._icon_photo = ImageTk.PhotoImage(icon)
                self.root.iconphoto(True, self._icon_photo)
        except Exception:
            pass

        # Initialize engine
        self.engine = timer_engine.TimerEngine()

        # System tray
        self.tray_icon = None
        if TRAY_AVAILABLE:
            self._setup_tray()

        # Create main window
        self.main_window = MainWindow(
            self.root,
            self.engine,
            on_minimize_to_tray=self._minimize_to_tray if TRAY_AVAILABLE else None,
            on_exit=self._do_quit
        )
        self.main_window.pack(fill='both', expand=True)

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Style
        self._setup_style()

    def _start_instance_listener(self):
        """Start listening for other instances trying to launch."""
        self._listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._listener_socket.bind(('127.0.0.1', SINGLE_INSTANCE_PORT))
            self._listener_socket.listen(1)
            self._listener_thread = threading.Thread(target=self._listen_for_instances, daemon=True)
            self._listener_thread.start()
        except Exception:
            pass  # Could not bind, continue anyway

    def _listen_for_instances(self):
        """Listen for other instances and bring window to front."""
        while True:
            try:
                conn, addr = self._listener_socket.accept()
                data = conn.recv(1024)
                conn.close()
                if data == b'SHOW':
                    self.root.after(0, self._restore_window)
            except Exception:
                break

    def _setup_style(self):
        """Set up ttk style with dark mode using sv_ttk."""
        # Use sv_ttk for modern dark theme
        if SV_TTK_AVAILABLE:
            sv_ttk.set_theme("dark")

        # Apply dark title bar on Windows
        if PYWINSTYLES_AVAILABLE and sys.platform == 'win32':
            try:
                version = sys.getwindowsversion()
                if version.major == 10 and version.build >= 22000:
                    # Windows 11 - can set custom header color
                    pywinstyles.change_header_color(self.root, "#1c1c1c")
                elif version.major == 10:
                    # Windows 10 - use dark style
                    pywinstyles.apply_style(self.root, "dark")
                    self.root.wm_attributes("-alpha", 0.99)
                    self.root.wm_attributes("-alpha", 1)
            except Exception:
                pass  # Ignore if it fails

        # Set dark background for tk widgets
        self.root.configure(bg='#1c1c1c')

        # Configure Accent button style (sv_ttk has Accent.TButton)
        style = ttk.Style()
        style.configure('Accent.TButton', font=('Segoe UI', 10, 'bold'))

    def _setup_tray(self):
        """Set up system tray icon."""
        icon_image = create_tray_icon()

        menu = pystray.Menu(
            pystray.MenuItem("Show", self._show_from_tray, default=True),
            pystray.MenuItem("Exit", self._quit_from_tray)
        )

        self.tray_icon = pystray.Icon("timer_tool", icon_image, "Timer Tool", menu)

    def _minimize_to_tray(self):
        """Minimize window to system tray."""
        if self.tray_icon:
            self.root.withdraw()
            if not self.tray_icon.visible:
                import threading
                tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
                tray_thread.start()

    def _show_from_tray(self, icon=None, item=None):
        """Show window from system tray."""
        self.root.after(0, self._restore_window)

    def _restore_window(self):
        """Restore the window."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _quit_from_tray(self, icon=None, item=None):
        """Quit from system tray."""
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self._do_quit)

    def _on_close(self):
        """Handle window close - confirm if timer running."""
        if self.engine.state in ('running', 'paused'):
            from tkinter import messagebox
            result = messagebox.askyesnocancel(
                "Timer Running",
                "Timer is still running. Stop timer and exit?",
                parent=self.root
            )
            if result is None:  # Cancel
                return
            elif result:  # Yes - stop and exit
                self.engine.stop()
            else:  # No - just exit without saving
                pass
        self._do_quit()

    def _do_quit(self):
        """Actually quit the application."""
        # Stop any running timer (saves to recovery)
        if self.engine.state == 'running':
            self.engine.pause()
        self.root.quit()
        self.root.destroy()

    def run(self):
        """Run the application."""
        self.root.mainloop()


def main():
    """Main entry point."""
    # Check for existing instance
    if not check_single_instance():
        # Another instance is running, we sent it a SHOW command
        sys.exit(0)

    # Initialize database
    db.init_db()

    # Backup database on startup (keeps last 10)
    backup_path = db.backup_database()

    # Upload to S3 if configured
    if backup_path:
        db.upload_to_s3(backup_path)

    # Create and run app
    app = TimerApp()
    app.run()


if __name__ == '__main__':
    main()
