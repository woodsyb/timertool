"""Main application window."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict
import db
import timer_engine
from ui.client_list import ClientListPanel
from ui.timer_display import TimerDisplayPanel
from ui.time_summary import TimeSummaryPanel
from ui.dialogs import ManualEntryDialog, BuildInvoiceDialog, RecoveryDialog, SettingsDialog, BusinessSetupDialog, InvoiceListDialog, TimeEntriesDialog, TaxYearSummaryDialog
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
        # Dark theme (sv_ttk compatible)
        self.BG = '#1c1c1c'

        # Container that holds either client list OR timer view
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Client list view (shown first)
        self.client_view = tk.Frame(self, bg=self.BG)
        self.client_view.grid(row=0, column=0, sticky='nsew')
        self.client_view.columnconfigure(0, weight=1)
        self.client_view.rowconfigure(0, weight=1)

        self.client_panel = ClientListPanel(self.client_view, self._on_client_selected)
        self.client_panel.pack(fill='both', expand=True, padx=4, pady=4)

        # Timer view (shown when client selected)
        self.timer_view = tk.Frame(self, bg=self.BG)
        self.timer_view.columnconfigure(0, weight=1)
        self.timer_view.rowconfigure(1, weight=1)

        # Back button header
        header = tk.Frame(self.timer_view, bg=self.BG)
        header.grid(row=0, column=0, sticky='ew', padx=8, pady=(8, 0))

        self.back_btn = tk.Label(
            header,
            text="< Back",
            font=('Segoe UI', 10),
            bg=self.BG,
            fg='#4fc3f7',
            cursor='hand2'
        )
        self.back_btn.pack(side='left')
        self.back_btn.bind('<Button-1>', lambda e: self._show_client_list())
        self.back_btn.bind('<Enter>', lambda e: self.back_btn.config(fg='#81c784'))
        self.back_btn.bind('<Leave>', lambda e: self.back_btn.config(fg='#4fc3f7'))

        # Minimize to tray
        if self.on_minimize_to_tray:
            tray_btn = tk.Label(
                header,
                text="[_]",
                font=('Consolas', 9),
                bg=self.BG,
                fg='#666666',
                cursor='hand2'
            )
            tray_btn.pack(side='right')
            tray_btn.bind('<Button-1>', lambda e: self.on_minimize_to_tray())
            tray_btn.bind('<Enter>', lambda e: tray_btn.config(fg='#4fc3f7'))
            tray_btn.bind('<Leave>', lambda e: tray_btn.config(fg='#666666'))

        # Timer content
        timer_content = tk.Frame(self.timer_view, bg=self.BG)
        timer_content.grid(row=1, column=0, sticky='nsew', padx=4, pady=4)
        timer_content.columnconfigure(0, weight=1)
        timer_content.rowconfigure(0, weight=1)

        self.timer_panel = TimerDisplayPanel(timer_content, self.engine)
        self.timer_panel.pack(fill='both', expand=True)

        # Time summary
        self.summary_panel = TimeSummaryPanel(timer_content)
        self.summary_panel.pack(fill='x')

        # Bind events
        self.timer_panel.bind('<<TimerStopped>>', lambda e: self._refresh_summary())
        self.timer_panel.bind('<<ManualEntry>>', lambda e: self._show_manual_entry())

    def _create_menu(self, parent):
        """Create the menu bar (hidden by default, show with Alt)."""
        self.menubar = tk.Menu(parent)
        self.menu_parent = parent
        self.menu_visible = False

        # File menu
        file_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Invoices Folder", command=self._open_invoices_folder)
        if self.on_minimize_to_tray:
            file_menu.add_command(label="Minimize to Tray", command=self.on_minimize_to_tray)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._do_exit)

        # Edit menu
        edit_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Business Setup...", command=self._show_business_setup)
        edit_menu.add_command(label="Settings...", command=self._show_settings)

        # View menu
        view_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Time Entries...", command=self._show_time_entries)
        view_menu.add_command(label="Invoices...", command=self._show_invoices)
        view_menu.add_command(label="Tax Year Summary...", command=self._show_tax_summary)
        view_menu.add_separator()
        view_menu.add_command(label="Refresh", command=self._refresh_all)

        # Actions menu
        actions_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Actions", menu=actions_menu)
        actions_menu.add_command(label="Build Invoice...", command=self._show_build_invoice)

        # Bind Alt to toggle menu
        parent.bind('<Alt_L>', self._toggle_menu)
        parent.bind('<Alt_R>', self._toggle_menu)
        parent.bind('<FocusOut>', lambda e: self._hide_menu())

    def _toggle_menu(self, event=None):
        """Toggle menu bar visibility."""
        if self.menu_visible:
            self._hide_menu()
        else:
            self._show_menu()

    def _show_menu(self):
        """Show the menu bar."""
        self.menu_parent.config(menu=self.menubar)
        self.menu_visible = True

    def _hide_menu(self):
        """Hide the menu bar."""
        self.menu_parent.config(menu='')
        self.menu_visible = False

    def _on_client_selected(self, client: Optional[Dict]):
        """Handle client selection - switch to timer view."""
        self.current_client = client
        self.timer_panel.set_client(client)
        self.summary_panel.set_client(client)
        if client:
            self._show_timer_view()

    def _show_timer_view(self):
        """Show the timer view, hide client list."""
        self.client_view.grid_remove()
        self.timer_view.grid(row=0, column=0, sticky='nsew')

    def _show_client_list(self):
        """Show the client list, hide timer view."""
        # Don't allow going back if timer is running
        if self.engine.state == 'running':
            from tkinter import messagebox
            messagebox.showwarning("Timer Running", "Stop the timer before going back.", parent=self)
            return
        self.timer_view.grid_remove()
        self.client_view.grid(row=0, column=0, sticky='nsew')
        self.current_client = None
        self.timer_panel.set_client(None)
        self.summary_panel.set_client(None)

    def _on_timer_state_change(self, state: str):
        """Handle timer state changes."""
        self._refresh_summary()

    def _on_idle_detected(self, idle_seconds: int):
        """Handle idle detection - just stop the timer."""
        # Stop the timer immediately - don't give option to resume
        # (resuming can mess up which day the time gets recorded to)
        elapsed = self.engine.get_elapsed_seconds()
        self.engine.stop()
        self.timer_panel.update_state_from_engine()
        self._refresh_summary()

        # Bring window to front and notify user
        root = self.winfo_toplevel()
        root.deiconify()
        root.lift()
        root.attributes('-topmost', True)
        root.focus_force()

        idle_min = idle_seconds // 60
        time_str = timer_engine.format_seconds(elapsed)
        messagebox.showinfo(
            "Timer Stopped",
            f"Timer stopped due to {idle_min} minutes of inactivity.\n\nTime recorded: {time_str}",
            parent=root
        )

        # Remove topmost after dialog dismissed
        root.attributes('-topmost', False)

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

    def _show_tax_summary(self):
        """Show the tax year summary dialog."""
        dialog = TaxYearSummaryDialog(self.winfo_toplevel())
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
