import logging
import time
from pathlib import Path
import threading
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledFrame

import config
from utils import get_logger, format_size, format_timestamp
from database import DatabaseManager, DatabaseError
from scanner import FolderScanner
from report import ReportGenerator

class FIMApplication:
    def __init__(self, root: ttk.Window):
        self.root = root
        self.logger = get_logger()
        
        # Initialize backend managers
        try:
            self.db_manager = DatabaseManager()
            self.scanner = FolderScanner(self.db_manager)
            self.report_gen = ReportGenerator()
        except DatabaseError as e:
            messagebox.showerror("Database Error", f"Failed to initialize database: {e}")
            self.logger.error(f"Critical DB Init Error: {e}")
            raise e

        # App state variables
        self.selected_folder = tk.StringVar(value="")
        self.status_text = tk.StringVar(value="Ready")
        
        # Results storage (cached for filtering, searching, and exports)
        self.scan_results = []
        self.scan_counts = {"Added": 0, "Modified": 0, "Deleted": 0, "Total": 0}
        self.scan_duration = 0.0
        
        # Hashing progress variables (thread-safe)
        self.progress_percent = tk.DoubleVar(value=0.0)
        self.progress_label_text = tk.StringVar(value="No active task")
        
        # UI controls state lock
        self.is_busy = False
        
        # Set up ttkbootstrap styles and main window settings
        self.root.title(f"{config.APP_TITLE} (v{config.APP_VERSION})")
        self.root.geometry("1100x750")
        self.root.minsize(950, 650)
        
        # Styling configuration
        self.style = ttk.Style(theme=config.DEFAULT_THEME)
        
        # Initialize UI layout
        self.create_widgets()
        self.refresh_baseline_stats()
        self.refresh_history_table()
        self.update_buttons_state()

    def create_widgets(self):
        # 1. Main Header
        header_frame = ttk.Frame(self.root, bootstyle=SECONDARY)
        header_frame.pack(fill=X, side=TOP)
        
        title_label = ttk.Label(
            header_frame, 
            text="🔒 File Integrity Monitoring (FIM) Tool", 
            font=("Helvetica", 16, "bold"), 
            bootstyle=INVERSE
        )
        title_label.pack(side=LEFT, padx=20, pady=12)
        
        # Dark mode switch in header
        self.theme_btn = ttk.Button(
            header_frame, 
            text="🌓 Toggle Light/Dark Mode", 
            command=self.toggle_theme, 
            bootstyle=INFO, 
            style="Outline.TButton"
        )
        self.theme_btn.pack(side=RIGHT, padx=20, pady=12)
        
        # 2. Main Tabs Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        # Initialize tabs
        self.tab_monitor = ttk.Frame(self.notebook)
        self.tab_history = ttk.Frame(self.notebook)
        self.tab_dashboard = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_monitor, text="🔍 Folder Monitor")
        self.notebook.add(self.tab_history, text="📜 Scan History")
        self.notebook.add(self.tab_dashboard, text="📊 Dashboard & Stats")
        
        # Populate tabs
        self.build_monitor_tab()
        self.build_history_tab()
        self.build_dashboard_tab()
        
        # 3. Footer Bar
        self.footer_frame = ttk.Frame(self.root, bootstyle=LIGHT)
        self.footer_frame.pack(fill=X, side=BOTTOM)
        
        self.footer_label = ttk.Label(
            self.footer_frame, 
            textvariable=self.status_text, 
            font=("Helvetica", 10), 
            bootstyle=DARK
        )
        self.footer_label.pack(side=LEFT, padx=15, pady=6)
        
        self.db_status_label = ttk.Label(
            self.footer_frame, 
            text=f"DB: Connected ({config.DATABASE_PATH.name})", 
            font=("Helvetica", 9), 
            bootstyle=SECONDARY
        )
        self.db_status_label.pack(side=RIGHT, padx=15, pady=6)

    # ------------------ MONITOR TAB BUILDER ------------------
    def build_monitor_tab(self):
        # Two-column layout: Left (Controls), Right (Results Table)
        paned = ttk.Panedwindow(self.tab_monitor, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True, padx=5, pady=5)
        
        # Left Panel (Controls)
        left_panel = ttk.Frame(paned, width=320, padding=10)
        paned.add(left_panel)
        
        # Section A: Target Folder
        folder_lbl_lf = ttk.Labelframe(left_panel, text="📁 Monitored Folder", padding=10)
        folder_lbl_lf.pack(fill=X, pady=(0, 10))
        
        select_btn = ttk.Button(
            folder_lbl_lf, 
            text="Select Folder", 
            command=self.select_folder_dialog, 
            bootstyle=PRIMARY,
            width=18
        )
        select_btn.pack(pady=(0, 5))
        
        self.folder_path_label = ttk.Label(
            folder_lbl_lf, 
            textvariable=self.selected_folder, 
            wraplength=280, 
            font=("Helvetica", 9, "italic"),
            bootstyle=INFO
        )
        self.folder_path_label.pack(fill=X)
        
        # Section B: Execution Operations
        ops_lf = ttk.Labelframe(left_panel, text="⚙️ Operations", padding=10)
        ops_lf.pack(fill=X, pady=10)
        
        self.btn_baseline = ttk.Button(
            ops_lf, 
            text="Create Baseline", 
            command=self.trigger_create_baseline, 
            bootstyle=SUCCESS,
            width=22
        )
        self.btn_baseline.pack(pady=5)
        
        self.btn_refresh_baseline = ttk.Button(
            ops_lf, 
            text="Refresh Baseline", 
            command=self.trigger_refresh_baseline, 
            bootstyle=SUCCESS,
            style="Outline.TButton",
            width=22
        )
        self.btn_refresh_baseline.pack(pady=5)
        
        self.btn_scan = ttk.Button(
            ops_lf, 
            text="Scan Folder", 
            command=self.trigger_scan_folder, 
            bootstyle=WARNING,
            width=22
        )
        self.btn_scan.pack(pady=5)
        
        self.btn_clear = ttk.Button(
            ops_lf, 
            text="Clear Results", 
            command=self.clear_results_table, 
            bootstyle=SECONDARY,
            width=22
        )
        self.btn_clear.pack(pady=5)
        
        # Section C: Export Reports
        export_lf = ttk.Labelframe(left_panel, text="💾 Export Reports", padding=10)
        export_lf.pack(fill=X, pady=10)
        
        self.btn_export_csv = ttk.Button(
            export_lf, 
            text="Export CSV", 
            command=self.export_csv_action, 
            bootstyle=INFO,
            width=22
        )
        self.btn_export_csv.pack(pady=5)
        
        self.btn_export_txt = ttk.Button(
            export_lf, 
            text="Export TXT", 
            command=self.export_txt_action, 
            bootstyle=INFO,
            style="Outline.TButton",
            width=22
        )
        self.btn_export_txt.pack(pady=5)
        
        # Right Panel (Results & Dashboard Counter)
        right_panel = ttk.Frame(paned, padding=10)
        paned.add(right_panel)
        
        # Top Mini-dashboard metrics
        metrics_frame = ttk.Frame(right_panel)
        metrics_frame.pack(fill=X, pady=(0, 10))
        
        self.card_added = self.create_metric_card(metrics_frame, "ADDED", "0", SUCCESS, 0)
        self.card_modified = self.create_metric_card(metrics_frame, "MODIFIED", "0", WARNING, 1)
        self.card_deleted = self.create_metric_card(metrics_frame, "DELETED", "0", DANGER, 2)
        self.card_total = self.create_metric_card(metrics_frame, "TOTAL DETECTED", "0", INFO, 3)
        
        # Filter & Search Box Panel
        filter_search_frame = ttk.Frame(right_panel)
        filter_search_frame.pack(fill=X, pady=(0, 10))
        
        # Search Box
        ttk.Label(filter_search_frame, text="🔍 Search: ").pack(side=LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.apply_filter_search)
        search_entry = ttk.Entry(filter_search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=LEFT, padx=(0, 20))
        
        # Filter Dropdown
        ttk.Label(filter_search_frame, text="Filter: ").pack(side=LEFT, padx=(0, 5))
        self.filter_var = tk.StringVar(value="All")
        filter_combo = ttk.Combobox(
            filter_search_frame, 
            textvariable=self.filter_var, 
            values=["All", "Added", "Modified", "Deleted"], 
            state="readonly",
            width=12
        )
        filter_combo.pack(side=LEFT)
        filter_combo.bind("<<ComboboxSelected>>", self.apply_filter_search)
        
        # Progress indicator area
        self.progress_frame = ttk.Frame(right_panel)
        self.progress_frame.pack(fill=X, pady=(0, 10))
        
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, 
            variable=self.progress_percent, 
            mode='determinate', 
            bootstyle=SUCCESS
        )
        self.progress_bar.pack(fill=X, side=TOP, pady=(0, 2))
        
        self.progress_label = ttk.Label(
            self.progress_frame, 
            textvariable=self.progress_label_text, 
            font=("Helvetica", 9), 
            bootstyle=SECONDARY
        )
        self.progress_label.pack(side=LEFT)
        
        self.progress_percent_label = ttk.Label(
            self.progress_frame, 
            text="0%", 
            font=("Helvetica", 9, "bold"), 
            bootstyle=SUCCESS
        )
        self.progress_percent_label.pack(side=RIGHT)
        
        # Treeview Table
        table_frame = ttk.Frame(right_panel)
        table_frame.pack(fill=BOTH, expand=True)
        
        columns = ("status", "filename", "filepath", "sha256", "filesize")
        self.tree = ttk.Treeview(
            table_frame, 
            columns=columns, 
            show="headings", 
            bootstyle=PRIMARY
        )
        
        self.tree.heading("status", text="Status", command=lambda: self.sort_column("status", False))
        self.tree.heading("filename", text="Filename", command=lambda: self.sort_column("filename", False))
        self.tree.heading("filepath", text="Path", command=lambda: self.sort_column("filepath", False))
        self.tree.heading("sha256", text="SHA-256 Hash", command=lambda: self.sort_column("sha256", False))
        self.tree.heading("filesize", text="Size", command=lambda: self.sort_column("filesize", False))
        
        self.tree.column("status", width=90, minwidth=70, anchor=CENTER)
        self.tree.column("filename", width=150, minwidth=100)
        self.tree.column("filepath", width=250, minwidth=150)
        self.tree.column("sha256", width=220, minwidth=150)
        self.tree.column("filesize", width=90, minwidth=70, anchor=E)
        
        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(column=0, row=0, sticky='nsew')
        vsb.grid(column=1, row=0, sticky='ns')
        hsb.grid(column=0, row=1, sticky='ew')
        
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        
        # Setup tags for colored rows
        # ttkbootstrap dark/light neutral colors config
        self.tree.tag_configure("Added", foreground="#2ecc71", font=("Helvetica", 9, "bold"))
        self.tree.tag_configure("Modified", foreground="#e67e22", font=("Helvetica", 9, "bold"))
        self.tree.tag_configure("Deleted", foreground="#e74c3c", font=("Helvetica", 9, "bold"))

    def create_metric_card(self, parent, label_text, initial_value, bootstyle_theme, col_idx):
        card = ttk.Frame(parent, bootstyle=bootstyle_theme, padding=10)
        card.pack(side=LEFT, fill=BOTH, expand=True, padx=4)
        
        lbl = ttk.Label(card, text=label_text, font=("Helvetica", 8, "bold"), bootstyle=INVERSE)
        lbl.pack(anchor=W)
        
        val_lbl = ttk.Label(card, text=initial_value, font=("Helvetica", 18, "bold"), bootstyle=INVERSE)
        val_lbl.pack(anchor=E, pady=(5, 0))
        
        # Configure columns stretch
        parent.columnconfigure(col_idx, weight=1)
        return val_lbl

    # ------------------ HISTORY TAB BUILDER ------------------
    def build_history_tab(self):
        container = ttk.Frame(self.tab_history, padding=15)
        container.pack(fill=BOTH, expand=True)
        
        header_lf = ttk.Frame(container)
        header_lf.pack(fill=X, pady=(0, 10))
        
        ttk.Label(
            header_lf, 
            text="📋 Baseline and Scan Executions Logs", 
            font=("Helvetica", 12, "bold")
        ).pack(side=LEFT)
        
        btn_clear_hist = ttk.Button(
            header_lf, 
            text="Clear History Log", 
            command=self.clear_history_log, 
            bootstyle=DANGER,
            style="Outline.TButton"
        )
        btn_clear_hist.pack(side=RIGHT, padx=5)
        
        btn_refresh_hist = ttk.Button(
            header_lf, 
            text="Refresh Log", 
            command=self.refresh_history_table, 
            bootstyle=SECONDARY
        )
        btn_refresh_hist.pack(side=RIGHT, padx=5)
        
        # History Table Frame
        hist_table_frame = ttk.Frame(container)
        hist_table_frame.pack(fill=BOTH, expand=True)
        
        columns = ("id", "timestamp", "folder_path", "added", "modified", "deleted", "total_files", "duration")
        self.hist_tree = ttk.Treeview(
            hist_table_frame, 
            columns=columns, 
            show="headings", 
            bootstyle=SECONDARY
        )
        
        self.hist_tree.heading("id", text="ID")
        self.hist_tree.heading("timestamp", text="Date/Time")
        self.hist_tree.heading("folder_path", text="Monitored Folder Path")
        self.hist_tree.heading("added", text="Added")
        self.hist_tree.heading("modified", text="Modified")
        self.hist_tree.heading("deleted", text="Deleted")
        self.hist_tree.heading("total_files", text="Total Files")
        self.hist_tree.heading("duration", text="Duration")
        
        self.hist_tree.column("id", width=50, minwidth=40, anchor=CENTER)
        self.hist_tree.column("timestamp", width=150, minwidth=130, anchor=CENTER)
        self.hist_tree.column("folder_path", width=300, minwidth=200)
        self.hist_tree.column("added", width=80, minwidth=60, anchor=CENTER)
        self.hist_tree.column("modified", width=80, minwidth=60, anchor=CENTER)
        self.hist_tree.column("deleted", width=80, minwidth=60, anchor=CENTER)
        self.hist_tree.column("total_files", width=90, minwidth=70, anchor=CENTER)
        self.hist_tree.column("duration", width=90, minwidth=70, anchor=CENTER)
        
        vsb_h = ttk.Scrollbar(hist_table_frame, orient="vertical", command=self.hist_tree.yview)
        hsb_h = ttk.Scrollbar(hist_table_frame, orient="horizontal", command=self.hist_tree.xview)
        self.hist_tree.configure(yscrollcommand=vsb_h.set, xscrollcommand=hsb_h.set)
        
        self.hist_tree.grid(column=0, row=0, sticky='nsew')
        vsb_h.grid(column=1, row=0, sticky='ns')
        hsb_h.grid(column=0, row=1, sticky='ew')
        
        hist_table_frame.columnconfigure(0, weight=1)
        hist_table_frame.rowconfigure(0, weight=1)

    # ------------------ DASHBOARD TAB BUILDER ------------------
    def build_dashboard_tab(self):
        self.dashboard_scroll = ScrolledFrame(self.tab_dashboard, padding=20)
        self.dashboard_scroll.pack(fill=BOTH, expand=True)
        
        # Two panels: Left (Database status & general baseline stats), Right (File type analysis dashboard)
        grid_frame = ttk.Frame(self.dashboard_scroll)
        grid_frame.pack(fill=BOTH, expand=True)
        
        # Left Side
        left_stats = ttk.Labelframe(grid_frame, text="📊 Baseline Summary Statistics", padding=15)
        left_stats.pack(side=LEFT, fill=BOTH, expand=True, padx=10, pady=10)
        
        self.stat_db_path = self.add_stat_row(left_stats, "Database Location:", "N/A")
        self.stat_db_size = self.add_stat_row(left_stats, "Database File Size:", "N/A")
        self.stat_baseline_files = self.add_stat_row(left_stats, "Baseline Files Count:", "0 files")
        self.stat_baseline_size = self.add_stat_row(left_stats, "Total Baseline Size:", "0.00 B")
        self.stat_last_baseline = self.add_stat_row(left_stats, "Last Baseline Creation:", "N/A")
        
        # Right Side
        right_stats = ttk.Labelframe(grid_frame, text="📂 File Type Extension Breakdown", padding=15)
        right_stats.pack(side=RIGHT, fill=BOTH, expand=True, padx=10, pady=10)
        
        self.extension_listbox = ttk.Treeview(
            right_stats, 
            columns=("ext", "count", "size"), 
            show="headings", 
            bootstyle=INFO, 
            height=8
        )
        self.extension_listbox.heading("ext", text="Extension")
        self.extension_listbox.heading("count", text="File Count")
        self.extension_listbox.heading("size", text="Total Size")
        
        self.extension_listbox.column("ext", width=100, anchor=CENTER)
        self.extension_listbox.column("count", width=100, anchor=CENTER)
        self.extension_listbox.column("size", width=120, anchor=E)
        self.extension_listbox.pack(fill=BOTH, expand=True)

    def add_stat_row(self, parent, label_text, default_val):
        row = ttk.Frame(parent)
        row.pack(fill=X, pady=8)
        
        lbl = ttk.Label(row, text=label_text, font=("Helvetica", 10, "bold"), width=22)
        lbl.pack(side=LEFT)
        
        val_lbl = ttk.Label(row, text=default_val, font=("Helvetica", 10), bootstyle=PRIMARY)
        val_lbl.pack(side=LEFT, fill=X, expand=True)
        return val_lbl

    # ------------------ EVENT HANDLERS & ACTIONS ------------------
    def toggle_theme(self):
        """Toggles between Darkly and Cosmo bootstrap themes."""
        current_theme = self.style.theme.name
        new_theme = "cosmo" if current_theme == "darkly" else "darkly"
        self.style.theme_use(new_theme)
        self.logger.info(f"UI theme toggled to: {new_theme}")

    def select_folder_dialog(self):
        """Opens directory dialog to select folder to monitor."""
        folder = filedialog.askdirectory(title="Select Folder to Monitor")
        if folder:
            # Set target
            self.selected_folder.set(folder)
            self.status_text.set(f"Selected Folder: {folder}")
            self.logger.info(f"Target folder selected: {folder}")
            self.update_buttons_state()

    def update_buttons_state(self):
        """Enables/Disables buttons based on application state."""
        has_folder = bool(self.selected_folder.get())
        has_results = len(self.scan_results) > 0
        
        if self.is_busy:
            # Disable everything while busy in a background thread
            self.btn_baseline.configure(state=DISABLED)
            self.btn_refresh_baseline.configure(state=DISABLED)
            self.btn_scan.configure(state=DISABLED)
            self.btn_clear.configure(state=DISABLED)
            self.btn_export_csv.configure(state=DISABLED)
            self.btn_export_txt.configure(state=DISABLED)
            self.theme_btn.configure(state=DISABLED)
        else:
            # Normal states
            self.btn_baseline.configure(state=NORMAL if has_folder else DISABLED)
            self.btn_refresh_baseline.configure(state=NORMAL if has_folder else DISABLED)
            self.btn_scan.configure(state=NORMAL if has_folder else DISABLED)
            self.btn_clear.configure(state=NORMAL if has_results else DISABLED)
            
            # Export buttons
            self.btn_export_csv.configure(state=NORMAL if has_results else DISABLED)
            self.btn_export_txt.configure(state=NORMAL if has_results else DISABLED)
            self.theme_btn.configure(state=NORMAL)

    def set_busy_state(self, is_busy: bool, status_msg: str = ""):
        """Lock buttons and update status during execution runs."""
        self.is_busy = is_busy
        if status_msg:
            self.status_text.set(status_msg)
        self.update_buttons_state()

    # ------------------ BACKGROUND THREAD WORKERS ------------------
    def thread_safe_callback(self, current_count: int, total_count: int, file_path: str):
        """Callback triggered by scanner module in thread, safely pushes to GUI main thread."""
        def tk_update():
            percent = (current_count / total_count) * 100 if total_count > 0 else 0
            self.progress_percent.set(percent)
            self.progress_percent_label.configure(text=f"{percent:.1f}%")
            
            # Shorten filepath for progress display
            short_path = file_path
            if len(short_path) > 60:
                short_path = "..." + short_path[-57:]
            self.progress_label_text.set(f"Processing ({current_count}/{total_count}): {short_path}")
            
        self.root.after(0, tk_update)

    def trigger_create_baseline(self):
        """Starts baseline creation in a background thread."""
        folder_str = self.selected_folder.get()
        if not folder_str:
            messagebox.showwarning("Warning", "Please select a folder first.")
            return
            
        folder_path = Path(folder_str)
        if not folder_path.exists():
            messagebox.showerror("Error", f"Folder does not exist:\n{folder_str}")
            return

        self.set_busy_state(True, "Initializing baseline creation...")
        self.progress_percent.set(0.0)
        self.progress_percent_label.configure(text="0.0%")
        
        # Start worker thread
        threading.Thread(
            target=self.bg_create_baseline_worker, 
            args=(folder_path,), 
            daemon=True
        ).start()

    def bg_create_baseline_worker(self, folder_path: Path):
        self.logger.info("Baseline thread started.")
        try:
            total_scanned, duration = self.scanner.create_baseline(
                folder_path=folder_path,
                progress_callback=self.thread_safe_callback
            )
            
            # Update GUI on completion
            def on_complete():
                self.progress_percent.set(100.0)
                self.progress_percent_label.configure(text="100%")
                self.progress_label_text.set("Baseline completed successfully.")
                self.status_text.set(f"Baseline created successfully. Files scanned: {total_scanned} | Time taken: {duration:.2f} sec")
                
                messagebox.showinfo(
                    "Success", 
                    f"Baseline created successfully!\n\nFiles scanned: {total_scanned}\nTime taken: {duration:.2f} sec"
                )
                self.set_busy_state(False)
                self.refresh_baseline_stats()
                self.refresh_history_table()
                
            self.root.after(0, on_complete)
            
        except PermissionError as e:
            self.root.after(0, lambda: self.handle_thread_error("Permission Denied", f"Unable to access files in directories:\n{e}"))
        except DatabaseError as e:
            self.root.after(0, lambda: self.handle_thread_error("Database Error", f"Failed saving records to database:\n{e}"))
        except Exception as e:
            self.root.after(0, lambda: self.handle_thread_error("Scan Error", f"An unexpected error occurred during baseline setup:\n{e}"))

    def trigger_refresh_baseline(self):
        """Clears baseline and recreates it. Effectively same as create baseline, logged as refresh."""
        self.logger.info("User triggered Baseline Refresh.")
        self.trigger_create_baseline()

    def trigger_scan_folder(self):
        """Starts scanning folder in a background thread."""
        folder_str = self.selected_folder.get()
        if not folder_str:
            messagebox.showwarning("Warning", "Please select a folder first.")
            return
            
        folder_path = Path(folder_str)
        if not folder_path.exists():
            messagebox.showerror("Error", f"Folder does not exist:\n{folder_str}")
            return
            
        # Ensure we have some baseline inside the DB first (or prompt warning)
        try:
            baseline = self.db_manager.get_baseline()
            if not baseline:
                messagebox.showwarning("Baseline Missing", "No baseline exists in the database. Please create a baseline first before scanning.")
                return
        except DatabaseError as e:
            messagebox.showerror("Database Error", f"Failed to verify baseline existence: {e}")
            return

        self.set_busy_state(True, "Scanning folder contents...")
        self.progress_percent.set(0.0)
        self.progress_percent_label.configure(text="0.0%")
        
        # Clear previous UI table
        self.clear_results_table(prompt=False)
        
        # Start worker thread
        threading.Thread(
            target=self.bg_scan_folder_worker, 
            args=(folder_path,), 
            daemon=True
        ).start()

    def bg_scan_folder_worker(self, folder_path: Path):
        self.logger.info("Scan thread started.")
        try:
            results, counts, duration = self.scanner.scan_folder(
                folder_path=folder_path,
                progress_callback=self.thread_safe_callback
            )
            
            # Update GUI on completion
            def on_complete():
                self.progress_percent.set(100.0)
                self.progress_percent_label.configure(text="100%")
                self.progress_label_text.set("Scan finished.")
                self.status_text.set(
                    f"Scan complete. Added: {counts['Added']} | Modified: {counts['Modified']} | "
                    f"Deleted: {counts['Deleted']} | Total: {counts['Total']} | Time taken: {duration:.2f} sec"
                )
                
                self.scan_results = results
                self.scan_counts = counts
                self.scan_duration = duration
                
                # Update Counters and Treeview table
                self.update_counter_widgets()
                self.apply_filter_search()
                
                self.set_busy_state(False)
                self.refresh_history_table()
                
                # Notify results
                if counts["Total"] > 0:
                    messagebox.showwarning(
                        "Integrity Alert",
                        f"Scan complete. Changes detected!\n\n"
                        f"Added Files: {counts['Added']}\n"
                        f"Modified Files: {counts['Modified']}\n"
                        f"Deleted Files: {counts['Deleted']}\n\n"
                        f"Please review the results table."
                    )
                else:
                    messagebox.showinfo("Scan Clean", "Scan complete. No changes detected since baseline creation!")
                    
            self.root.after(0, on_complete)
            
        except PermissionError as e:
            self.root.after(0, lambda: self.handle_thread_error("Permission Denied", f"Unable to scan directories due to access restriction:\n{e}"))
        except DatabaseError as e:
            self.root.after(0, lambda: self.handle_thread_error("Database Error", f"Failed accessing baseline data:\n{e}"))
        except Exception as e:
            self.root.after(0, lambda: self.handle_thread_error("Scan Error", f"An unexpected error occurred during scan:\n{e}"))

    def handle_thread_error(self, title: str, message: str):
        self.progress_label_text.set("Operation failed.")
        self.progress_percent.set(0.0)
        self.progress_percent_label.configure(text="0%")
        self.status_text.set(f"Error: {title}")
        messagebox.showerror(title, message)
        self.set_busy_state(False)

    # ------------------ RESULTS VISUALIZATION & FILTERS ------------------
    def update_counter_widgets(self):
        """Updates numerical metric cards at the top of the Results panel."""
        self.card_added.configure(text=str(self.scan_counts.get("Added", 0)))
        self.card_modified.configure(text=str(self.scan_counts.get("Modified", 0)))
        self.card_deleted.configure(text=str(self.scan_counts.get("Deleted", 0)))
        self.card_total.configure(text=str(self.scan_counts.get("Total", 0)))

    def apply_filter_search(self, *args):
        """Filters treeview content dynamically by search query and combobox selection."""
        search_query = self.search_var.get().lower().strip()
        filter_status = self.filter_var.get()
        
        # Clear current tree rows
        for row in self.tree.get_children():
            self.tree.delete(row)
            
        for r in self.scan_results:
            status = r["status"]
            filename = r["filename"]
            filepath = r["filepath"]
            sha256 = r["sha256"]
            filesize = r["filesize"]
            
            # Apply Filter status
            if filter_status != "All" and status != filter_status:
                continue
                
            # Apply Search Query
            if search_query:
                in_filename = search_query in filename.lower()
                in_filepath = search_query in filepath.lower()
                in_hash = search_query in sha256.lower()
                in_status = search_query in status.lower()
                if not (in_filename or in_filepath or in_hash or in_status):
                    continue
            
            # Insert item to table
            self.tree.insert(
                "", 
                tk.END, 
                values=(
                    status, 
                    filename, 
                    filepath, 
                    sha256, 
                    format_size(filesize)
                ),
                tags=(status,)
            )

    def sort_column(self, col: str, reverse: bool):
        """Sorts Treeview contents when user clicks column headers."""
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        
        # Custom sorting logic based on column type
        if col == "filesize":
            # Sort numerically by actual size inside standard display
            def extract_size_bytes(val_str: str) -> float:
                try:
                    num_val = float(val_str.split()[0])
                    unit = val_str.split()[1]
                    multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
                    return num_val * multipliers.get(unit, 1)
                except Exception:
                    return 0
            items.sort(key=lambda t: extract_size_bytes(t[0]), reverse=reverse)
        else:
            # Alphanumeric sort
            items.sort(key=lambda t: t[0].lower(), reverse=reverse)
            
        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)
            
        # Toggle reverse flag for next click
        self.tree.heading(col, command=lambda: self.sort_column(col, not reverse))

    def clear_results_table(self, prompt: bool = True):
        """Clears results, counters, and resets search/filters."""
        if prompt and self.scan_results:
            confirm = messagebox.askyesno("Clear Results", "Are you sure you want to clear current scan results?")
            if not confirm:
                return
                
        # Clear state
        self.scan_results = []
        self.scan_counts = {"Added": 0, "Modified": 0, "Deleted": 0, "Total": 0}
        self.scan_duration = 0.0
        
        # Clear UI
        self.search_var.set("")
        self.filter_var.set("All")
        self.update_counter_widgets()
        for row in self.tree.get_children():
            self.tree.delete(row)
            
        self.status_text.set("Ready")
        self.update_buttons_state()

    # ------------------ EXPORT REPORTS CONTROLS ------------------
    def export_csv_action(self):
        """Exports scanned changes to CSV using Pandas."""
        if not self.scan_results:
            messagebox.showwarning("No Data", "There are no results to export.")
            return
            
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"fim_report_{timestamp_str}.csv"
        
        # Save Dialog
        file_path = filedialog.asksaveasfilename(
            initialdir=config.REPORTS_DIR,
            initialfile=default_name,
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        
        if file_path:
            try:
                self.report_gen.export_csv(self.scan_results, Path(file_path))
                messagebox.showinfo("Export Successful", f"CSV report exported to:\n{file_path}")
                self.logger.info(f"CSV report exported manually to: {file_path}")
            except Exception as e:
                messagebox.showerror("Export Failure", f"Failed to export CSV report: {e}")

    def export_txt_action(self):
        """Exports scanned changes to professional TXT report."""
        if not self.scan_results:
            messagebox.showwarning("No Data", "There are no results to export.")
            return
            
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"fim_report_{timestamp_str}.txt"
        
        # Save Dialog
        file_path = filedialog.asksaveasfilename(
            initialdir=config.REPORTS_DIR,
            initialfile=default_name,
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        
        if file_path:
            try:
                self.report_gen.export_txt(
                    results=self.scan_results, 
                    counts=self.scan_counts, 
                    duration=self.scan_duration, 
                    export_path=Path(file_path)
                )
                messagebox.showinfo("Export Successful", f"TXT report exported to:\n{file_path}")
                self.logger.info(f"TXT report exported manually to: {file_path}")
            except Exception as e:
                messagebox.showerror("Export Failure", f"Failed to export TXT report: {e}")

    # ------------------ HISTORY LOG OPERATIONS ------------------
    def refresh_history_table(self):
        """Reloads execution logs list in Tab 2."""
        # Clear rows
        for row in self.hist_tree.get_children():
            self.hist_tree.delete(row)
            
        try:
            history = self.db_manager.get_scan_history()
            for h in history:
                # h: (id, timestamp, folder_path, added, modified, deleted, total_files, duration)
                h_id, ts, fp, add_c, mod_c, del_c, tot_f, dur = h
                
                # Truncate folder path if extremely long
                short_fp = fp
                if len(short_fp) > 45:
                    short_fp = "..." + short_fp[-42:]
                    
                self.hist_tree.insert(
                    "", 
                    tk.END, 
                    values=(
                        h_id, 
                        ts, 
                        short_fp, 
                        add_c, 
                        mod_c, 
                        del_c, 
                        tot_f, 
                        f"{dur:.2f}s"
                    )
                )
        except DatabaseError as e:
            self.logger.error(f"Failed to fetch scan history: {e}")

    def clear_history_log(self):
        """Clears SQLite scan history records."""
        confirm = messagebox.askyesno("Clear History", "Are you sure you want to delete all historical logs? This cannot be undone.")
        if not confirm:
            return
            
        try:
            self.db_manager.clear_scan_history()
            self.refresh_history_table()
            messagebox.showinfo("Success", "Scan execution history logs cleared.")
        except DatabaseError as e:
            messagebox.showerror("Error", f"Failed to clear history log: {e}")

    # ------------------ DASHBOARD STATS CALCULATORS ------------------
    def refresh_baseline_stats(self):
        """Loads and recalculates statistics for Tab 3 dashboard."""
        try:
            # 1. DB path and size
            db_exists = config.DATABASE_PATH.exists()
            db_size_str = format_size(config.DATABASE_PATH.stat().st_size) if db_exists else "N/A"
            self.stat_db_path.configure(text=str(config.DATABASE_PATH.resolve()))
            self.stat_db_size.configure(text=db_size_str)
            
            # 2. Get baseline details
            baseline = self.db_manager.get_baseline()
            
            total_files = len(baseline)
            self.stat_baseline_files.configure(text=f"{total_files} files")
            
            total_bytes = sum(item["filesize"] for item in baseline.values())
            self.stat_baseline_size.configure(text=format_size(total_bytes))
            
            # 3. Last modification timestamp
            if total_files > 0:
                times = [item["modified_time"] for item in baseline.values()]
                self.stat_last_baseline.configure(text=format_timestamp(max(times)))
            else:
                self.stat_last_baseline.configure(text="No active baseline")
                
            # 4. File extension counts
            ext_counts = {}
            for item in baseline.values():
                filename = item["filename"]
                suffix = Path(filename).suffix.lower()
                if not suffix:
                    suffix = "No Extension"
                
                size = item["filesize"]
                if suffix not in ext_counts:
                    ext_counts[suffix] = {"count": 0, "size": 0}
                ext_counts[suffix]["count"] += 1
                ext_counts[suffix]["size"] += size
                
            # Populate Extension Table
            for row in self.extension_listbox.get_children():
                self.extension_listbox.delete(row)
                
            # Sort by count desc
            sorted_exts = sorted(ext_counts.items(), key=lambda x: x[1]["count"], reverse=True)
            for ext, stats in sorted_exts:
                self.extension_listbox.insert(
                    "",
                    tk.END,
                    values=(
                        ext,
                        stats["count"],
                        format_size(stats["size"])
                    )
                )
        except Exception as e:
            self.logger.error(f"Failed to calculate dashboard statistics: {e}")
