"""Main application window."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict
import db
import timer_engine
from ui.client_list import ClientListPanel
from ui.timer_display import TimerDisplayPanel
from ui.time_summary import TimeSummaryPanel
from ui.dialogs import ManualEntryDialog, BuildInvoiceDialog, IdleDialog, RecoveryDialog, SettingsDialog, BusinessSetupDialog, InvoiceListDialog, TimeEntriesDialog
import os
import subprocess
import sys


class MainWindow(ttk.Frame):
    """Main application window content."""

    def __init__(self, parent, engine: timer_engine.TimerEngine, on_minimize_to_tray=None, on_exit=None):
        super().__init__(parent)
        self.engine = engine
        self.on_minimize_to_tray = on_minimize_to_tray
        self.on_exit = on_exit
        self.current_client: Optional[Dict] = None

        # Set up engine callbacks
        self.engine.on_state_change = self._on_timer_state_change
        self.engine.on_idle_detected = self._on_idle_detected

        self._create_widgets()
        self._create_menu(parent)
        self._check_recovery()

    def _create_widgets(self):
        # Main container with two columns
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Left panel - client list
        left_frame = ttk.Frame(self, width=260)
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(5, 0), pady=5)
        left_frame.grid_propagate(False)

        self.client_panel = ClientListPanel(left_frame, self._on_client_selected)
        self.client_panel.pack(fill='both', expand=True)

        # Right panel - timer and summary
        right_frame = ttk.Frame(self)
        right_frame.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)
        right_frame.rowconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)

        # Timer display
        self.timer_panel = TimerDisplayPanel(right_frame, self.engine)
        self.timer_panel.grid(row=0, column=0, sticky='nsew')

        # Time summary
        self.summary_panel = TimeSummaryPanel(right_frame)
        self.summary_panel.grid(row=1, column=0, sticky='ew', pady=(10, 0))

        # Bind events
        self.timer_panel.bind('<<TimerStopped>>', lambda e: self._refresh_summary())
        self.timer_panel.bind('<<ManualEntry>>', lambda e: self._show_manual_entry())
        self.summary_panel.bind('<<BuildInvoice>>', lambda e: self._show_build_invoice())

    def _create_menu(self, parent):
        """Create the menu bar."""
        menubar = tk.Menu(parent)
        parent.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Invoices Folder", command=self._open_invoices_folder)
        if self.on_minimize_to_tray:
            file_menu.add_command(label="Minimize to Tray", command=self.on_minimize_to_tray)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._do_exit)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Business Setup...", command=self._show_business_setup)
        edit_menu.add_command(label="Settings...", command=self._show_settings)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Time Entries...", command=self._show_time_entries)
        view_menu.add_command(label="Invoices...", command=self._show_invoices)
        view_menu.add_separator()
        view_menu.add_command(label="Refresh", command=self._refresh_all)

    def _on_client_selected(self, client: Optional[Dict]):
        """Handle client selection."""
        self.current_client = client
        self.timer_panel.set_client(client)
        self.summary_panel.set_client(client)

    def _on_timer_state_change(self, state: str):
        """Handle timer state changes."""
        self._refresh_summary()

    def _on_idle_detected(self, idle_seconds: int):
        """Handle idle detection - show dialog."""
        dialog = IdleDialog(
            self.winfo_toplevel(),
            idle_seconds,
            self.engine.get_elapsed_seconds()
        )
        self.wait_window(dialog)

        if dialog.result == 'resume':
            self.engine.resume()
            self.timer_panel.update_state_from_engine()
        elif dialog.result == 'discard':
            self.engine.discard_idle_time(idle_seconds)
            self.engine.resume()
            self.timer_panel.update_state_from_engine()
        elif dialog.result == 'stop':
            self.engine.stop()
            self.timer_panel.update_state_from_engine()
            self._refresh_summary()

    def _check_recovery(self):
        """Check for crashed timer to recover."""
        recovery_data = self.engine.recover_from_crash()
        if recovery_data:
            client = db.get_client(recovery_data['client_id'])
            if client:
                dialog = RecoveryDialog(
                    self.winfo_toplevel(),
                    client['name'],
                    recovery_data['accumulated_seconds'],
                    recovery_data['last_save_time']
                )
                self.wait_window(dialog)

                self.engine.apply_recovery(dialog.result or False, recovery_data)
                if dialog.result:
                    self._refresh_summary()

    def _refresh_summary(self):
        """Refresh the time summary."""
        self.summary_panel.refresh()

    def _refresh_all(self):
        """Refresh all panels."""
        self.client_panel.refresh()
        self.summary_panel.refresh()

    def _show_manual_entry(self):
        """Show manual entry dialog."""
        if not self.current_client:
            return

        dialog = ManualEntryDialog(self.winfo_toplevel(), self.current_client)
        self.wait_window(dialog)

        if dialog.result:
            db.save_time_entry(
                client_id=self.current_client['id'],
                start_time=dialog.result['start_time'],
                end_time=dialog.result['end_time'],
                duration_seconds=dialog.result['duration_seconds'],
                description=dialog.result['description'],
                entry_type='manual'
            )
            self._refresh_summary()
            messagebox.showinfo("Success", f"Added {dialog.result['hours']:.2f} hours.", parent=self)

    def _show_build_invoice(self):
        """Show build invoice dialog."""
        if not self.current_client:
            return

        # Get uninvoiced entries
        entries = db.get_time_entries(
            client_id=self.current_client['id'],
            invoiced=False
        )

        if not entries:
            messagebox.showinfo("Info", "No uninvoiced time entries.", parent=self)
            return

        dialog = BuildInvoiceDialog(self.winfo_toplevel(), self.current_client, entries)
        self.wait_window(dialog)

        if dialog.result:
            self._create_invoice(dialog.result)

    def _create_invoice(self, invoice_data: dict):
        """Create the invoice in the invoices system."""
        try:
            import invoice_bridge
            result = invoice_bridge.create_invoice(
                self.current_client,
                invoice_data['entries'],
                invoice_data['description'],
                invoice_data['payment_terms'],
                invoice_data['payment_method']
            )

            if result['success']:
                # Mark entries as invoiced
                entry_ids = [e['id'] for e in invoice_data['entries']]
                db.mark_entries_invoiced(entry_ids, result['invoice_number'])

                self._refresh_summary()
                messagebox.showinfo(
                    "Invoice Created",
                    f"Invoice {result['invoice_number']} created.\n\nPDF: {result.get('pdf_path', 'N/A')}",
                    parent=self
                )
            else:
                messagebox.showerror("Error", f"Failed to create invoice:\n{result.get('error', 'Unknown error')}", parent=self)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create invoice:\n{str(e)}", parent=self)

    def _show_settings(self):
        """Show settings dialog."""
        dialog = SettingsDialog(self.winfo_toplevel())
        self.wait_window(dialog)

        if dialog.result:
            # Reload engine settings
            self.engine.inactivity_timeout = int(db.get_setting('inactivity_timeout_minutes', '10')) * 60
            self.engine.auto_save_interval = int(db.get_setting('auto_save_interval_seconds', '30'))

    def _show_business_setup(self):
        """Show business setup dialog."""
        dialog = BusinessSetupDialog(self.winfo_toplevel())
        self.wait_window(dialog)

    def _show_invoices(self):
        """Show the invoice list dialog."""
        client_id = self.current_client['id'] if self.current_client else None
        dialog = InvoiceListDialog(self.winfo_toplevel(), client_id=client_id)
        self.wait_window(dialog)

    def _show_time_entries(self):
        """Show the time entries dialog."""
        client_id = self.current_client['id'] if self.current_client else None
        client_name = self.current_client['name'] if self.current_client else ""
        dialog = TimeEntriesDialog(self.winfo_toplevel(), client_id=client_id, client_name=client_name)
        self.wait_window(dialog)

    def _do_exit(self):
        """Handle Exit menu - actually quit the app."""
        if self.on_exit:
            self.on_exit()
        else:
            self.winfo_toplevel().quit()

    def _open_invoices_folder(self):
        """Open the invoices/PDFs folder in file explorer."""
        folder = db.get_pdfs_dir()
        folder.mkdir(exist_ok=True)

        # Open folder in system file manager
        if sys.platform == 'win32':
            os.startfile(str(folder))
        elif sys.platform == 'darwin':
            subprocess.run(['open', str(folder)])
        else:
            subprocess.run(['xdg-open', str(folder)])
