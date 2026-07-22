# File Integrity Monitoring (FIM) Tool

A modern, high-performance desktop application built with Python 3, Tkinter (`ttkbootstrap`), SQLite, and Pandas. It monitors folder integrity by recursively hashing files (using chunked SHA-256 computation), creating a secure metadata baseline, and highlighting any changes (Added, Modified, or Deleted files) in subsequent scans.

## Features

- **Modern UI Dashboard**: Leverages the `ttkbootstrap` Darkly theme for styling, equipped with clear metric cards, custom color coding for changes, search-as-you-type filtering, and sortable table columns.
- **Background Multithreading**: All hashing and scan checks are performed on daemon threads, preventing UI lockups or application freezes on large directories.
- **Robust Change Detection**:
  - 🟢 **Added**: Files created after the baseline snapshot.
  - 🟠 **Modified**: File content edits (detected using fast size/timestamp checks, followed by SHA-256 comparisons).
  - 🔴 **Deleted**: Files missing since baseline snapshot.
- **Professional Reporting**: Export detailed reports in **CSV** (powered by `pandas`) or **TXT** format.
- **Execution Log History**: View scan logs showing timestamps, changes detected, files processed, and scan durations in an interactive table history viewer.
- **Dashboard Summary**: Analyze file statistics like database disk size, total monitored files, aggregated size, and file type extension breakdown.
- **Self-Healing DB**: Automatic SQLite corruption detection and database reconstruction.
- **Theme Customization**: Toggle between light and dark modes with a single click.

---

## Folder Structure

```text
file-monitoring-tool/
│
├── main.py                # Main application entry point (logs & initialization)
├── gui.py                 # Multi-tab modern GUI layout (ttkbootstrap)
├── scanner.py             # Folder crawler and change comparison core logic
├── hashing.py             # Chunk-based file reader for SHA-256 calculation
├── database.py            # SQLite baseline and scan history CRUD helper
├── report.py              # Text and pandas-based CSV report generation
├── utils.py               # Time, size formatting, and logging setup
├── config.py              # Configuration constraints, ignorelists, and paths
│
├── database/              # Stores the local SQLite database file (fim.db)
├── logs/                  # Contains application execution log files (application.log)
├── reports/               # Default output directory for CSV and TXT reports
├── assets/                # Icon files and visual resources
└── README.md              # Project documentation
```

---

## Technologies Used

- **Python 3.x**: Programming language.
- **Tkinter / ttkbootstrap**: Native desktop visual components styled with modern CSS bootstrap themes.
- **SQLite3**: Lightweight, transactional database engine.
- **Pandas**: Structured CSV data export.
- **Hashlib**: Chunked SHA-256 calculations.
- **Pathlib**: Modern, platform-independent filesystem operations.
- **Logging & Threading**: Native background process safety and application execution recording.

---

## Installation

1. **Clone the repository** (or download workspace folder).

2. Ensure you have **Python 3.10+** installed on your operating system.

3. **Install Dependencies**:
   Install the required external libraries using `pip`:
   ```bash
   pip install pandas ttkbootstrap
   ```

---

## Running Instructions

Run the application using the Python interpreter from your terminal:

```bash
python main.py
```

### Steps to Monitor a Folder:
1. **Choose Directory**: Click the **Select Folder** button and choose the target directory.
2. **Setup Baseline**: Click **Create Baseline**. The progress bar will count up as it generates hashes for all contents and stores them in the baseline database.
3. **Run Integrity Scans**: When file changes are made, click **Scan Folder** to execute comparisons. Detected modifications appear in the table tagged by category (Added in green, Modified in orange, Deleted in red).
4. **Reports**: Click **Export CSV** or **Export TXT** to save reports to disk.
5. **Logs & Metrics**: Check the **Scan History** tab to view your past scans, or open the **Dashboard** to see file extension counts.

---

## Future Enhancements & Bonus Features

- **Automatic Daemon Monitoring**: Schedule scans to run periodically every hour/day.
- **SMTP Email alerts**: Send automated alerts to admins when critical alterations are detected.
- **Multi-threaded hashing**: Implement a concurrent thread-pool for ultra-fast processing of massive data structures.
- **PDF Exporting**: Implement reportlab PDF formatted reporting sheets.
