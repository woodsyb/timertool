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

    # Dark theme colors (sv_ttk compatible)
    BG = '#1c1c1c'
    BG_ITEM = '#2d2d2d'
    BG_HOVER = '#404040'
    BG_SELECTED = '#0078d4'
    FG = '#ffffff'
    FG_DIM = '#aaaaaa'
    FG_SELECTED = '#ffffff'
    ACCENT = '#0078d4'
    FAVORITE = '#ffca28'

    def __init__(self, parent, on_select: Callable[[Optional[Dict]], None]):
        super().__init__(parent)
        self.on_select = on_select
        self.clients: List[Dict] = []
        self.selected_id: Optional[int] = None
        self.client_frames: Dict[int, tk.Frame] = {}
        self.show_archived = False

        self._create_widgets()
        self.refresh()

    def _create_widgets(self):
        # Main container
        main = tk.Frame(self, bg=self.BG)
        main.pack(fill='both', expand=True)

        # Header with subtle line
        header_frame = tk.Frame(main, bg=self.BG)
        header_frame.pack(fill='x', padx=12, pady=(16, 8))

        tk.Label(header_frame, text="Clients", font=('Segoe UI', 13, 'bold'),
                bg=self.BG, fg=self.FG, anchor='w').pack(side='left')

        # Add button in header
        self.add_btn = tk.Label(
            header_frame, text="+", font=('Segoe UI', 16),
            bg=self.BG, fg=self.ACCENT, cursor='hand2'
        )
        self.add_btn.pack(side='right')
        self.add_btn.bind('<Button-1>', lambda e: self._add_client())
        self.add_btn.bind('<Enter>', lambda e: self.add_btn.config(fg='#81c784'))
        self.add_btn.bind('<Leave>', lambda e: self.add_btn.config(fg=self.ACCENT))

        # Show archived toggle
        self.archived_btn = tk.Label(
            header_frame, text="Show Archived", font=('Segoe UI', 8),
            bg=self.BG, fg=self.FG_DIM, cursor='hand2'
        )
        self.archived_btn.pack(side='right', padx=(0, 12))
        self.archived_btn.bind('<Button-1>', lambda e: self._toggle_show_archived())
        self.archived_btn.bind('<Enter>', lambda e: self.archived_btn.config(fg=self.ACCENT))
        self.archived_btn.bind('<Leave>', lambda e: self._update_archived_btn_style())

        # Subtle separator
        tk.Frame(main, bg='#333333', height=1).pack(fill='x', padx=12)

        # Scrollable client list
        list_container = tk.Frame(main, bg=self.BG)
        list_container.pack(fill='both', expand=True, padx=8, pady=8)

        # Canvas for scrolling
        self.canvas = tk.Canvas(list_container, bg=self.BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_container, orient='vertical', command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=self.BG)

        self.scrollable_frame.bind('<Configure>',
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw')
        self.canvas.configure(yscrollcommand=scrollbar.set)

        # Make scrollable frame expand to canvas width
        self.canvas.bind('<Configure>', self._on_canvas_configure)

        self.canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Mouse wheel scrolling
        self.canvas.bind('<Enter>', lambda e: self.canvas.bind_all('<MouseWheel>', self._on_mousewheel))
        self.canvas.bind('<Leave>', lambda e: self.canvas.unbind_all('<MouseWheel>'))

        # Context menu
        self.context_menu = tk.Menu(self, tearoff=0, bg=self.BG_ITEM, fg=self.FG,
                                   activebackground=self.ACCENT, activeforeground=self.FG_SELECTED,
                                   font=('Segoe UI', 9))
        self.context_menu.add_command(label="  Edit", command=self._edit_selected)
        self.context_menu.add_command(label="  Toggle Favorite", command=self._toggle_favorite)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="  Time Entries", command=self._show_time_entries)
        self.context_menu.add_command(label="  Build Invoice", command=self._show_build_invoice)
        self.context_menu.add_command(label="  Open Invoices Folder", command=self._open_client_invoices)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="  Delete", command=self._delete_selected)

    def _on_canvas_configure(self, event):
        """Update scrollable frame width when canvas resizes."""
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), 'units')

    def refresh(self):
        """Refresh the client list from database."""
        self.clients = db.get_clients(include_archived=self.show_archived)

        # Clear existing items
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.client_frames.clear()

        # Split into favorites, non-favorites, and archived
        favorites = [c for c in self.clients if c.get('favorite') and not c.get('archived')]
        non_favorites = [c for c in self.clients if not c.get('favorite') and not c.get('archived')]
        archived = [c for c in self.clients if c.get('archived')]

        # Add favorites first
        for client in favorites:
            self._create_client_item(client, is_favorite=True)

        # Add separator if both exist
        if favorites and non_favorites:
            sep = tk.Frame(self.scrollable_frame, bg='#404040', height=1)
            sep.pack(fill='x', padx=4, pady=6)

        # Add non-favorites
        for client in non_favorites:
            self._create_client_item(client, is_favorite=False)

        # Add archived section if showing
        if archived:
            # Archived header
            archived_sep = tk.Frame(self.scrollable_frame, bg='#404040', height=1)
            archived_sep.pack(fill='x', padx=4, pady=(12, 4))
            tk.Label(self.scrollable_frame, text="Archived", font=('Segoe UI', 9),
                    bg=self.BG, fg=self.FG_DIM).pack(anchor='w', padx=8)

            for client in archived:
                self._create_client_item(client, is_favorite=False, is_archived=True)

        # Update canvas scroll region
        self.scrollable_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

        # Restore selection visual
        if self.selected_id and self.selected_id in self.client_frames:
            self._update_item_style(self.selected_id, selected=True)

    def _toggle_show_archived(self):
        """Toggle showing archived clients."""
        self.show_archived = not self.show_archived
        self._update_archived_btn_style()
        self.refresh()

    def _update_archived_btn_style(self):
        """Update the archived button text/style."""
        if self.show_archived:
            self.archived_btn.config(text="Hide Archived", fg=self.ACCENT)
        else:
            self.archived_btn.config(text="Show Archived", fg=self.FG_DIM)

    def _create_client_item(self, client: Dict, is_favorite: bool, is_archived: bool = False):
        """Create a clickable client item."""
        client_id = client['id']

        # Outer frame with subtle left border for favorites
        frame = tk.Frame(self.scrollable_frame, bg=self.BG_ITEM, cursor='hand2')
        frame.pack(fill='x', pady=1)

        # Inner content
        inner = tk.Frame(frame, bg=self.BG_ITEM)
        inner.pack(fill='x', padx=14, pady=10)

        # Get names
        company = (client.get('company_name') or '').strip()
        contact = (client.get('contact_name') or '').strip()

        # Color based on status
        if is_archived:
            name_color = '#666666'  # Dimmed for archived
        elif is_favorite:
            name_color = self.FAVORITE
        else:
            name_color = self.FG

        # Primary name (company or contact)
        primary = company or contact
        name_lbl = tk.Label(inner, text=primary, font=('Segoe UI', 10),
                           bg=self.BG_ITEM, fg=name_color, anchor='w')
        name_lbl.pack(fill='x')

        # Secondary line: contact (if company exists) + rate
        secondary_text = ""
        if company and contact:
            secondary_text = contact
        if client['hourly_rate']:
            rate_part = f"${client['hourly_rate']:.0f}/hr"
            if secondary_text:
                secondary_text += f"  -  {rate_part}"
            else:
                secondary_text = rate_part

        contact_lbl = None
        if secondary_text:
            secondary_color = '#555555' if is_archived else self.FG_DIM
            contact_lbl = tk.Label(inner, text=secondary_text, font=('Segoe UI', 9),
                               bg=self.BG_ITEM, fg=secondary_color, anchor='w')
            contact_lbl.pack(fill='x')

        # No separate rate label - combined above
        rate_lbl = contact_lbl  # For compatibility with style updates

        # Store reference
        self.client_frames[client_id] = frame
        frame.inner = inner
        frame.name_lbl = name_lbl
        frame.secondary_lbl = contact_lbl
        frame.is_favorite = is_favorite
        frame.is_archived = is_archived

        # Bind events to all widgets
        widgets = [frame, inner, name_lbl]
        if contact_lbl:
            widgets.append(contact_lbl)
        for widget in widgets:
            widget.bind('<Button-1>', lambda e, cid=client_id: self._on_click(cid))
            widget.bind('<Double-1>', lambda e, cid=client_id: self._on_double_click(cid))
            widget.bind('<Button-3>', lambda e, cid=client_id: self._on_right_click(e, cid))
            widget.bind('<Enter>', lambda e, cid=client_id: self._on_hover(cid, True))
            widget.bind('<Leave>', lambda e, cid=client_id: self._on_hover(cid, False))
            widget.bind('<MouseWheel>', self._on_mousewheel)

    def _update_item_style(self, client_id: int, selected: bool = False, hover: bool = False):
        """Update the visual style of a client item."""
        if client_id not in self.client_frames:
            return
        frame = self.client_frames[client_id]
        is_fav = frame.is_favorite

        if selected:
            bg = self.BG_SELECTED
            fg = self.FG_SELECTED
            fg_secondary = '#333333'
        elif hover:
            bg = self.BG_HOVER
            fg = self.FAVORITE if is_fav else self.FG
            fg_secondary = self.FG_DIM
        else:
            bg = self.BG_ITEM
            fg = self.FAVORITE if is_fav else self.FG
            fg_secondary = self.FG_DIM

        frame.config(bg=bg)
        frame.inner.config(bg=bg)
        frame.name_lbl.config(bg=bg, fg=fg)
        if frame.secondary_lbl:
            frame.secondary_lbl.config(bg=bg, fg=fg_secondary)

    def _on_click(self, client_id: int):
        """Handle client click."""
        # Deselect previous
        if self.selected_id and self.selected_id in self.client_frames:
            self._update_item_style(self.selected_id, selected=False)

        self.selected_id = client_id
        self._update_item_style(client_id, selected=True)

        client = next((c for c in self.clients if c['id'] == client_id), None)
        self.on_select(client)

    def _on_hover(self, client_id: int, entering: bool):
        """Handle hover effect."""
        if client_id == self.selected_id:
            return
        self._update_item_style(client_id, hover=entering)

    def _on_double_click(self, client_id: int):
        """Handle double click to edit client."""
        client = next((c for c in self.clients if c['id'] == client_id), None)
        if client:
            self._edit_client(client)

    def _on_right_click(self, event, client_id: int):
        """Show context menu on right click (don't navigate)."""
        # Select visually but don't trigger navigation
        if self.selected_id and self.selected_id in self.client_frames:
            self._update_item_style(self.selected_id, selected=False)
        self.selected_id = client_id
        self._update_item_style(client_id, selected=True)

        # Check if client is archived
        client = next((c for c in self.clients if c['id'] == client_id), None)
        is_archived = client.get('archived', False) if client else False

        # Rebuild context menu based on archived status
        self.context_menu.delete(0, 'end')
        self.context_menu.add_command(label="  Edit", command=self._edit_selected)

        if is_archived:
            self.context_menu.add_command(label="  Restore", command=self._restore_selected)
            self.context_menu.add_separator()
            self.context_menu.add_command(label="  Time Entries", command=self._show_time_entries)
            self.context_menu.add_command(label="  Invoices", command=self._show_invoices)
            self.context_menu.add_command(label="  Open Invoices Folder", command=self._open_client_invoices)
            self.context_menu.add_separator()
            self.context_menu.add_command(label="  Delete Permanently", command=self._delete_permanently)
        else:
            self.context_menu.add_command(label="  Toggle Favorite", command=self._toggle_favorite)
            self.context_menu.add_command(label="  Billing Info", command=self._show_billing_info)
            self.context_menu.add_separator()
            self.context_menu.add_command(label="  Time Entries", command=self._show_time_entries)
            self.context_menu.add_command(label="  Invoices", command=self._show_invoices)
            self.context_menu.add_command(label="  Build Invoice", command=self._show_build_invoice)
            self.context_menu.add_command(label="  Open Invoices Folder", command=self._open_client_invoices)
            self.context_menu.add_command(label="  Generate Statement", command=self._generate_statement)
            self.context_menu.add_separator()
            self.context_menu.add_command(label="  Hide", command=self._archive_selected)
            self.context_menu.add_command(label="  Delete", command=self._delete_selected)

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

    def _show_billing_info(self):
        """Show billing info dialog for selected client."""
        if not self.selected_id:
            return

        client = next((c for c in self.clients if c['id'] == self.selected_id), None)
        if not client:
            return

        dialog = BillingInfoDialog(self.winfo_toplevel(), client)
        self.wait_window(dialog)

        if dialog.result:
            db.update_client_billing(
                client['id'],
                dialog.result['bill_to'],
                dialog.result['address'],
                dialog.result['address2'],
                dialog.result['city'],
                dialog.result['state'],
                dialog.result['zip'],
                dialog.result['email'],
                dialog.result['payment_preference']
            )
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

    def _generate_statement(self):
        """Generate a statement PDF for the selected client."""
        if not self.selected_id:
            return

        client = next((c for c in self.clients if c['id'] == self.selected_id), None)
        if not client:
            return

        try:
            import generate_pdf
            output_path = generate_pdf.generate_statement_pdf(self.selected_id)

            # Open the generated PDF
            if sys.platform == 'win32':
                os.startfile(str(output_path))
            elif sys.platform == 'darwin':
                subprocess.run(['open', str(output_path)])
            else:
                subprocess.run(['xdg-open', str(output_path)])

        except ValueError as e:
            messagebox.showinfo("Info", str(e), parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate statement: {e}", parent=self)

    def _show_time_entries(self):
        """Show time entries dialog for selected client."""
        if not self.selected_id:
            return

        client = next((c for c in self.clients if c['id'] == self.selected_id), None)
        if not client:
            return

        from ui.dialogs import TimeEntriesDialog
        dialog = TimeEntriesDialog(self.winfo_toplevel(), client_id=client['id'], client_name=client['name'])
        self.wait_window(dialog)

    def _show_invoices(self):
        """Show invoices dialog for selected client."""
        if not self.selected_id:
            return

        from ui.dialogs import InvoiceListDialog
        dialog = InvoiceListDialog(self.winfo_toplevel(), client_id=self.selected_id)
        self.wait_window(dialog)

    def _show_build_invoice(self):
        """Show build invoice dialog for selected client."""
        if not self.selected_id:
            return

        client = next((c for c in self.clients if c['id'] == self.selected_id), None)
        if not client:
            return

        # Get uninvoiced entries
        entries = db.get_time_entries(client_id=client['id'], invoiced=False)

        if not entries:
            messagebox.showinfo("Info", "No uninvoiced time entries.", parent=self)
            return

        from ui.dialogs import BuildInvoiceDialog
        dialog = BuildInvoiceDialog(self.winfo_toplevel(), client, entries)
        self.wait_window(dialog)

        if dialog.result:
            self._create_invoice(client, dialog.result)

    def _create_invoice(self, client: Dict, invoice_data: dict):
        """Create the invoice."""
        try:
            import invoice_bridge
            result = invoice_bridge.create_invoice(
                client,
                invoice_data['entries'],
                invoice_data['description'],
                invoice_data['payment_terms'],
                invoice_data['payment_method']
            )

            if result['success']:
                # Mark entries as invoiced
                entry_ids = [e['id'] for e in invoice_data['entries']]
                db.mark_entries_invoiced(entry_ids, result['invoice_number'])

                messagebox.showinfo(
                    "Invoice Created",
                    f"Invoice {result['invoice_number']} created.\n\nPDF: {result.get('pdf_path', 'N/A')}",
                    parent=self
                )
            else:
                messagebox.showerror("Error", f"Failed to create invoice:\n{result.get('error', 'Unknown error')}", parent=self)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create invoice:\n{str(e)}", parent=self)

    def _restore_selected(self):
        """Restore an archived client."""
        if not self.selected_id:
            return
        db.unarchive_client(self.selected_id)
        self.refresh()

    def _delete_permanently(self):
        """Permanently delete an archived client."""
        if not self.selected_id:
            return

        client = next((c for c in self.clients if c['id'] == self.selected_id), None)
        if not client:
            return

        if messagebox.askyesno(
            "Delete Permanently",
            f"Permanently delete '{client['name']}'?\n\nThis cannot be undone.",
            parent=self
        ):
            try:
                db.delete_client(self.selected_id)
                self.selected_id = None
                self.refresh()
            except ValueError as e:
                messagebox.showerror("Cannot Delete", str(e), parent=self)

    def _archive_selected(self):
        """Archive (hide) the selected client."""
        if not self.selected_id:
            return

        client = next((c for c in self.clients if c['id'] == self.selected_id), None)
        if not client:
            return

        db.archive_client(self.selected_id)
        self.selected_id = None
        self.refresh()
        self.on_select(None)

    def _delete_selected(self):
        """Delete the selected client."""
        if not self.selected_id:
            return

        client = next((c for c in self.clients if c['id'] == self.selected_id), None)
        if not client:
            return

        if not messagebox.askyesno(
            "Delete Client",
            f"Permanently delete '{client['name']}'?\n\nThis cannot be undone.",
            parent=self
        ):
            return

        try:
            db.delete_client(self.selected_id)
            self.selected_id = None
            self.refresh()
            self.on_select(None)
        except ValueError as e:
            messagebox.showerror("Cannot Delete", str(e), parent=self)

    def _add_client(self):
        """Show dialog to add new client."""
        dialog = ClientDialog(self, title="Add Client")
        self.wait_window(dialog)

        if dialog.result:
            contact, company, rate, track = dialog.result
            db.save_client(contact, company, rate, track)
            self.refresh()

    def _edit_client(self, client: Dict):
        """Show dialog to edit existing client."""
        dialog = ClientDialog(self, title="Edit Client", client=client)
        self.wait_window(dialog)

        if dialog.result:
            contact, company, rate, track = dialog.result
            db.update_client(client['id'], contact, company, rate, track)
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

    # Dark theme (sv_ttk compatible)
    BG = '#2a2a2a'
    FG = '#fafafa'
    FG_DIM = '#9e9e9e'

    def __init__(self, parent, title: str, client: Optional[Dict] = None):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=self.BG)
        self.result = None
        self.client = client

        self.transient(parent)
        self.grab_set()

        self._create_widgets()

        # Center on parent
        self.geometry('+%d+%d' % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))

    def _create_widgets(self):
        frame = tk.Frame(self, bg=self.BG, padx=15, pady=15)
        frame.pack(fill='both', expand=True)

        # Contact Name
        tk.Label(frame, text="Contact Name:", bg=self.BG, fg=self.FG,
                font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w', pady=4)
        self.contact_var = tk.StringVar(value=self.client.get('contact_name', '') if self.client else '')
        self.contact_entry = ttk.Entry(frame, textvariable=self.contact_var, width=28)
        self.contact_entry.grid(row=0, column=1, pady=4, padx=(8, 0))

        # Company Name
        tk.Label(frame, text="Company:", bg=self.BG, fg=self.FG,
                font=('Segoe UI', 9)).grid(row=1, column=0, sticky='w', pady=4)
        self.company_var = tk.StringVar(value=self.client.get('company_name', '') if self.client else '')
        self.company_entry = ttk.Entry(frame, textvariable=self.company_var, width=28)
        self.company_entry.grid(row=1, column=1, pady=4, padx=(8, 0))

        # Hint
        tk.Label(frame, text="(fill one or both)", bg=self.BG, fg=self.FG_DIM,
                font=('Segoe UI', 8)).grid(row=2, column=1, sticky='w', padx=(8, 0))

        # Rate
        tk.Label(frame, text="Hourly Rate ($):", bg=self.BG, fg=self.FG,
                font=('Segoe UI', 9)).grid(row=3, column=0, sticky='w', pady=4)
        self.rate_var = tk.StringVar(value=str(self.client['hourly_rate']) if self.client else '')
        self.rate_entry = ttk.Entry(frame, textvariable=self.rate_var, width=28)
        self.rate_entry.grid(row=3, column=1, pady=4, padx=(8, 0))

        # Track activity checkbox
        self.track_var = tk.BooleanVar(value=self.client.get('track_activity', 1) if self.client else True)
        self.track_check = ttk.Checkbutton(frame, text="Track keyboard/mouse activity", variable=self.track_var)
        self.track_check.grid(row=4, column=0, columnspan=2, sticky='w', pady=(12, 0))

        # Buttons
        btn_frame = tk.Frame(frame, bg=self.BG)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=(15, 0))

        ttk.Button(btn_frame, text="Save", command=self._save).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side='left', padx=5)

        self.contact_entry.focus_set()
        self.bind('<Return>', lambda e: self._save())
        self.bind('<Escape>', lambda e: self.destroy())

    def _save(self):
        """Validate and save."""
        contact = self.contact_var.get().strip()
        company = self.company_var.get().strip()
        rate_str = self.rate_var.get().strip()

        if not contact and not company:
            messagebox.showerror("Error", "Enter a contact name or company.", parent=self)
            return

        try:
            rate = float(rate_str) if rate_str else 0
            if rate < 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid hourly rate.", parent=self)
            return

        self.result = (contact, company, rate, self.track_var.get())
        self.destroy()


class BillingInfoDialog(tk.Toplevel):
    """Dialog for editing client billing/invoice info."""

    BG = '#2a2a2a'
    FG = '#fafafa'
    FG_DIM = '#9e9e9e'

    PAYMENT_OPTIONS = ['ACH', 'Domestic Wire', 'International Wire', 'Check', 'Credit Card', 'PayPal', 'Other']

    def __init__(self, parent, client: Dict):
        super().__init__(parent)
        self.title("Billing Info")
        self.configure(bg=self.BG)
        self.result = None
        self.client = client

        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self.geometry('+%d+%d' % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))

    def _create_widgets(self):
        frame = tk.Frame(self, bg=self.BG, padx=15, pady=15)
        frame.pack(fill='both', expand=True)

        row = 0

        # Client name header
        name = self.client.get('company_name') or self.client.get('contact_name') or ''
        tk.Label(frame, text=name, font=('Segoe UI', 11, 'bold'),
                bg=self.BG, fg=self.FG).grid(row=row, column=0, columnspan=2, sticky='w', pady=(0, 10))
        row += 1

        # Bill To / Attn (AP contact)
        tk.Label(frame, text="Bill To / Attn:", bg=self.BG, fg=self.FG,
                font=('Segoe UI', 9)).grid(row=row, column=0, sticky='w', pady=4)
        self.bill_to_var = tk.StringVar(value=self.client.get('bill_to', '') or '')
        ttk.Entry(frame, textvariable=self.bill_to_var, width=32).grid(row=row, column=1, pady=4, padx=(8, 0))
        row += 1

        # Address line 1
        tk.Label(frame, text="Address:", bg=self.BG, fg=self.FG,
                font=('Segoe UI', 9)).grid(row=row, column=0, sticky='w', pady=4)
        self.address_var = tk.StringVar(value=self.client.get('address', '') or '')
        ttk.Entry(frame, textvariable=self.address_var, width=32).grid(row=row, column=1, pady=4, padx=(8, 0))
        row += 1

        # Address line 2
        tk.Label(frame, text="Address 2:", bg=self.BG, fg=self.FG_DIM,
                font=('Segoe UI', 9)).grid(row=row, column=0, sticky='w', pady=4)
        self.address2_var = tk.StringVar(value=self.client.get('address2', '') or '')
        ttk.Entry(frame, textvariable=self.address2_var, width=32).grid(row=row, column=1, pady=4, padx=(8, 0))
        row += 1

        # City
        tk.Label(frame, text="City:", bg=self.BG, fg=self.FG,
                font=('Segoe UI', 9)).grid(row=row, column=0, sticky='w', pady=4)
        self.city_var = tk.StringVar(value=self.client.get('city', '') or '')
        ttk.Entry(frame, textvariable=self.city_var, width=32).grid(row=row, column=1, pady=4, padx=(8, 0))
        row += 1

        # State / ZIP on same row
        state_zip_frame = tk.Frame(frame, bg=self.BG)
        state_zip_frame.grid(row=row, column=0, columnspan=2, sticky='w', pady=4)

        tk.Label(state_zip_frame, text="State:", bg=self.BG, fg=self.FG,
                font=('Segoe UI', 9)).pack(side='left')
        self.state_var = tk.StringVar(value=self.client.get('state', '') or '')
        ttk.Entry(state_zip_frame, textvariable=self.state_var, width=8).pack(side='left', padx=(8, 16))

        tk.Label(state_zip_frame, text="ZIP:", bg=self.BG, fg=self.FG,
                font=('Segoe UI', 9)).pack(side='left')
        self.zip_var = tk.StringVar(value=self.client.get('zip', '') or '')
        ttk.Entry(state_zip_frame, textvariable=self.zip_var, width=10).pack(side='left', padx=(8, 0))
        row += 1

        # Email
        tk.Label(frame, text="Email:", bg=self.BG, fg=self.FG,
                font=('Segoe UI', 9)).grid(row=row, column=0, sticky='w', pady=4)
        self.email_var = tk.StringVar(value=self.client.get('email', '') or '')
        ttk.Entry(frame, textvariable=self.email_var, width=32).grid(row=row, column=1, pady=4, padx=(8, 0))
        row += 1

        # Payment Preference
        tk.Label(frame, text="Payment Method:", bg=self.BG, fg=self.FG,
                font=('Segoe UI', 9)).grid(row=row, column=0, sticky='w', pady=4)
        self.payment_var = tk.StringVar(value=self.client.get('payment_preference', '') or '')
        payment_combo = ttk.Combobox(frame, textvariable=self.payment_var, values=self.PAYMENT_OPTIONS, width=29)
        payment_combo.grid(row=row, column=1, pady=4, padx=(8, 0))
        row += 1

        # Buttons
        btn_frame = tk.Frame(frame, bg=self.BG)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(15, 0))

        ttk.Button(btn_frame, text="Save", command=self._save).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side='left', padx=5)

        self.bind('<Return>', lambda e: self._save())
        self.bind('<Escape>', lambda e: self.destroy())

    def _save(self):
        self.result = {
            'bill_to': self.bill_to_var.get().strip(),
            'address': self.address_var.get().strip(),
            'address2': self.address2_var.get().strip(),
            'city': self.city_var.get().strip(),
            'state': self.state_var.get().strip(),
            'zip': self.zip_var.get().strip(),
            'email': self.email_var.get().strip(),
            'payment_preference': self.payment_var.get().strip()
        }
        self.destroy()
