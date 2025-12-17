"""Client list panel."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Callable, List, Dict
import os
import subprocess
import sys
import db


class ClientListPanel(ttk.Frame):
    """Panel showing list of clients with add/edit functionality."""

    def __init__(self, parent, on_select: Callable[[Optional[Dict]], None]):
        super().__init__(parent)
        self.on_select = on_select
        self.clients: List[Dict] = []
        self.selected_id: Optional[int] = None

        self._create_widgets()
        self.refresh()

    def _create_widgets(self):
        # Header
        header = ttk.Label(self, text="CLIENTS", font=('Segoe UI', 10, 'bold'))
        header.pack(fill='x', padx=5, pady=(5, 5))

        # Treeview
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill='both', expand=True, padx=5)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=('rate',),
            show='tree',
            selectmode='browse'
        )

        # Configure columns
        self.tree.column('#0', width=180, minwidth=120)
        self.tree.column('rate', width=70, minwidth=60, anchor='e')

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        self.tree.bind('<Double-1>', self._on_double_click)
        self.tree.bind('<Button-3>', self._on_right_click)  # Right click

        # Context menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Edit", command=self._edit_selected)
        self.context_menu.add_command(label="Toggle Favorite", command=self._toggle_favorite)
        self.context_menu.add_command(label="Open Invoices Folder", command=self._open_client_invoices)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Delete", command=self._delete_selected)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', padx=5, pady=5)

        self.add_btn = ttk.Button(btn_frame, text="+ Add Client", command=self._add_client)
        self.add_btn.pack(fill='x')

    def refresh(self):
        """Refresh the client list from database."""
        self.clients = db.get_clients()

        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Add clients
        for client in self.clients:
            # Star prefix for favorites
            prefix = "*  " if client.get('favorite') else "   "
            name = prefix + client['name']
            rate_str = f"${client['hourly_rate']:.0f}/hr" if client['hourly_rate'] else "No rate"
            self.tree.insert('', 'end', iid=str(client['id']),
                           text=name,
                           values=(rate_str,))

        # Restore selection if possible
        if self.selected_id:
            try:
                self.tree.selection_set(str(self.selected_id))
            except tk.TclError:
                pass

    def _on_select(self, event):
        """Handle selection."""
        selection = self.tree.selection()
        if selection:
            client_id = int(selection[0])
            self.selected_id = client_id
            client = next((c for c in self.clients if c['id'] == client_id), None)
            self.on_select(client)
        else:
            self.selected_id = None
            self.on_select(None)

    def _on_double_click(self, event):
        """Handle double click to edit client."""
        selection = self.tree.selection()
        if selection:
            client_id = int(selection[0])
            client = next((c for c in self.clients if c['id'] == client_id), None)
            if client:
                self._edit_client(client)

    def _on_right_click(self, event):
        """Show context menu on right click."""
        # Select item under cursor
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.selected_id = int(item)
            self.context_menu.post(event.x_root, event.y_root)

    def _edit_selected(self):
        """Edit the selected client."""
        if self.selected_id:
            client = next((c for c in self.clients if c['id'] == self.selected_id), None)
            if client:
                self._edit_client(client)

    def _toggle_favorite(self):
        """Toggle favorite status of selected client."""
        if self.selected_id:
            db.toggle_client_favorite(self.selected_id)
            self.refresh()

    def _open_client_invoices(self):
        """Open the selected client's invoices folder."""
        if not self.selected_id:
            return

        client = next((c for c in self.clients if c['id'] == self.selected_id), None)
        if not client:
            return

        # Get client folder path
        client_folder = db.get_pdfs_dir() / client['name'].replace(' ', '_')
        client_folder.mkdir(exist_ok=True)

        # Open in file manager
        if sys.platform == 'win32':
            os.startfile(str(client_folder))
        elif sys.platform == 'darwin':
            subprocess.run(['open', str(client_folder)])
        else:
            subprocess.run(['xdg-open', str(client_folder)])

    def _delete_selected(self):
        """Delete the selected client."""
        if not self.selected_id:
            return

        client = next((c for c in self.clients if c['id'] == self.selected_id), None)
        if not client:
            return

        # Confirm deletion
        result = messagebox.askyesnocancel(
            "Delete Client",
            f"Delete '{client['name']}'?\n\n"
            "Yes = Delete permanently (only if no time entries)\n"
            "No = Archive (hide but keep data)",
            parent=self
        )

        if result is None:  # Cancel
            return
        elif result:  # Yes - delete
            try:
                db.delete_client(self.selected_id)
                self.selected_id = None
                self.refresh()
                self.on_select(None)
            except ValueError as e:
                messagebox.showerror("Cannot Delete", str(e), parent=self)
        else:  # No - archive
            db.archive_client(self.selected_id)
            self.selected_id = None
            self.refresh()
            self.on_select(None)

    def _add_client(self):
        """Show dialog to add new client."""
        dialog = ClientDialog(self, title="Add Client")
        self.wait_window(dialog)

        if dialog.result:
            name, rate, track = dialog.result
            db.save_client(name, rate, track)
            self.refresh()

    def _edit_client(self, client: Dict):
        """Show dialog to edit existing client."""
        dialog = ClientDialog(self, title="Edit Client", client=client)
        self.wait_window(dialog)

        if dialog.result:
            name, rate, track = dialog.result
            db.update_client(client['id'], name, rate, track)
            self.refresh()
            # Re-trigger selection callback with updated data
            updated = db.get_client(client['id'])
            if updated:
                self.on_select(updated)

    def get_selected_client(self) -> Optional[Dict]:
        """Get currently selected client."""
        if self.selected_id:
            return db.get_client(self.selected_id)
        return None


class ClientDialog(tk.Toplevel):
    """Dialog for adding/editing a client."""

    def __init__(self, parent, title: str, client: Optional[Dict] = None):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.client = client

        self.transient(parent)
        self.grab_set()

        self._create_widgets()

        # Center on parent
        self.geometry('+%d+%d' % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill='both', expand=True)

        # Name
        ttk.Label(frame, text="Client Name:").grid(row=0, column=0, sticky='w', pady=2)
        self.name_var = tk.StringVar(value=self.client['name'] if self.client else '')
        self.name_entry = ttk.Entry(frame, textvariable=self.name_var, width=30)
        self.name_entry.grid(row=0, column=1, pady=2, padx=(5, 0))

        # Rate
        ttk.Label(frame, text="Hourly Rate ($):").grid(row=1, column=0, sticky='w', pady=2)
        self.rate_var = tk.StringVar(value=str(self.client['hourly_rate']) if self.client else '')
        self.rate_entry = ttk.Entry(frame, textvariable=self.rate_var, width=30)
        self.rate_entry.grid(row=1, column=1, pady=2, padx=(5, 0))

        # Track activity checkbox
        self.track_var = tk.BooleanVar(value=self.client.get('track_activity', 1) if self.client else True)
        self.track_check = ttk.Checkbutton(frame, text="Track keyboard/mouse activity", variable=self.track_var)
        self.track_check.grid(row=2, column=0, columnspan=2, sticky='w', pady=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0))

        ttk.Button(btn_frame, text="Save", command=self._save).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side='left', padx=5)

        self.name_entry.focus_set()
        self.bind('<Return>', lambda e: self._save())
        self.bind('<Escape>', lambda e: self.destroy())

    def _save(self):
        """Validate and save."""
        name = self.name_var.get().strip()
        rate_str = self.rate_var.get().strip()

        if not name:
            messagebox.showerror("Error", "Client name is required.", parent=self)
            return

        try:
            rate = float(rate_str)
            if rate < 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid hourly rate.", parent=self)
            return

        self.result = (name, rate, self.track_var.get())
        self.destroy()
