import time
from pathlib import Path
from typing import Callable, List, Dict, Any, Tuple
import config
from hashing import calculate_sha256
from database import DatabaseManager
from utils import get_logger

class FolderScanner:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = get_logger()

    def should_ignore(self, file_path: Path, root_dir: Path) -> bool:
        """
        Determine if a file or its parent directories match the ignore configuration.
        """
        # Check filename
        if file_path.name in config.IGNORE_FILENAMES:
            return True
            
        # Check if any parent directory under the root is in IGNORE_DIRNAMES
        try:
            relative_parts = file_path.relative_to(root_dir).parts[:-1]
            if any(part in config.IGNORE_DIRNAMES for part in relative_parts):
                return True
        except ValueError:
            # File is not under root_dir
            pass
            
        return False

    def list_files(self, root_path: Path) -> List[Path]:
        """
        Recursively find all non-ignored files within the root path.
        """
        files = []
        try:
            # Check directory existence & permissions
            if not root_path.exists():
                raise FileNotFoundError(f"Selected folder does not exist: {root_path}")
            if not root_path.is_dir():
                raise NotADirectoryError(f"Selected path is not a folder: {root_path}")
                
            # Recursive scan
            for item in root_path.rglob('*'):
                if item.is_file():
                    if not self.should_ignore(item, root_path):
                        files.append(item)
        except PermissionError as e:
            self.logger.error(f"Permission denied during directory list: {e}")
            raise PermissionError(f"Permission denied accessing folder content: {e}")
        except Exception as e:
            self.logger.error(f"Error listing files in {root_path}: {e}")
            raise
            
        return files

    def create_baseline(self, folder_path: Path, progress_callback: Callable[[int, int, str], None] = None) -> Tuple[int, float]:
        """
        Scans folder, hashes all files, and stores metadata in SQLite.
        
        Args:
            folder_path: Path of folder to baseline.
            progress_callback: Optional function(current_count, total_count, current_filepath).
            
        Returns:
            Tuple of (total_files_scanned, duration_seconds)
        """
        folder_path = folder_path.resolve()
        self.logger.info(f"Starting baseline creation for: {folder_path}")
        start_time = time.time()
        
        # 1. Gather all files
        files_to_hash = self.list_files(folder_path)
        total_files = len(files_to_hash)
        
        if total_files == 0:
            # Handle empty folder scenario
            self.db_manager.clear_baseline()

            duration = time.time() - start_time
            self.logger.info("Baseline created successfully (empty directory).")
            return 0, duration
            
        # 2. Clear previous baseline entries
        self.db_manager.clear_baseline()
        
        # 3. Hash files and collect entries
        baseline_entries = []
        for i, file_path in enumerate(files_to_hash, start=1):
            if progress_callback:
                progress_callback(i, total_files, str(file_path))
                
            try:
                file_hash = calculate_sha256(file_path, config.HASH_CHUNK_SIZE)
                if file_hash is None:
                    # Logging handled in hashing.py
                    continue
                    
                stat = file_path.stat()
                baseline_entries.append({
                    "filepath": str(file_path.resolve()),
                    "filename": file_path.name,
                    "sha256": file_hash,
                    "filesize": stat.st_size,
                    "modified_time": stat.st_mtime
                })
            except Exception as e:
                self.logger.error(f"Error gathering metadata for {file_path}: {e}")
                
        # 4. Save to Database
        if baseline_entries:
            self.db_manager.save_baseline(baseline_entries)
            
        duration = time.time() - start_time
        self.logger.info(f"Baseline creation finished. Scanned: {total_files}, Saved: {len(baseline_entries)}, Duration: {duration:.2f}s")
        return len(baseline_entries), duration

    def scan_folder(self, folder_path: Path, progress_callback: Callable[[int, int, str], None] = None) -> Tuple[List[Dict[str, Any]], Dict[str, int], float]:
        """
        Compare current folder status with stored baseline, detecting Added, Modified, and Deleted files.
        
        Args:
            folder_path: Folder path to scan.
            progress_callback: Optional progress callback.
            
        Returns:
            Tuple of (scan_results_list, status_counts_dict, duration_seconds)
            where scan_results_list contains dicts with keys: status, filename, filepath, sha256, filesize.
        """
        import os
        is_windows = (os.name == 'nt')
        
        folder_path = folder_path.resolve()
        self.logger.info(f"Starting scan comparison for folder: {folder_path}")
        start_time = time.time()
        
        # 1. Fetch current baseline from Database
        baseline = self.db_manager.get_baseline()
        
        # Map baseline keys case-insensitively on Windows
        baseline_lookup = {k.lower() if is_windows else k: v for k, v in baseline.items()}
        
        # 2. Gather current files in folder
        current_files = self.list_files(folder_path)
        total_files = len(current_files)
        
        results = []
        counts = {"Added": 0, "Modified": 0, "Deleted": 0, "Total": 0}
        
        # Keep track of paths found in this scan
        scanned_paths = set()
        
        # 3. Process current files (find Added and Modified)
        for i, file_path in enumerate(current_files, start=1):
            if progress_callback:
                progress_callback(i, total_files, str(file_path))
                
            abs_path_str = str(file_path.resolve())
            abs_path_key = abs_path_str.lower() if is_windows else abs_path_str
            scanned_paths.add(abs_path_key)
            
            try:
                # Get current stats & hash
                stat = file_path.stat()
                file_size = stat.st_size
                modified_time = stat.st_mtime
                
                # Check if it exists in baseline
                if abs_path_key not in baseline_lookup:
                    # Added File
                    # Hash file
                    file_hash = calculate_sha256(file_path, config.HASH_CHUNK_SIZE) or "UNKNOWN"
                    results.append({
                        "status": "Added",
                        "filename": file_path.name,
                        "filepath": abs_path_str,
                        "sha256": file_hash,
                        "filesize": file_size,
                        "modified_time": modified_time
                    })
                    counts["Added"] += 1
                else:
                    # Check for Modification (fast check by size or modified time, then hash check)
                    baseline_entry = baseline_lookup[abs_path_key]
                    
                    # Quick size/time comparison to avoid unnecessary hashing
                    is_modified_fast = (
                        baseline_entry["filesize"] != file_size or
                        abs(baseline_entry["modified_time"] - modified_time) > 0.01
                    )
                    
                    if is_modified_fast:
                        # Perform SHA-256 hash comparison
                        file_hash = calculate_sha256(file_path, config.HASH_CHUNK_SIZE)
                        
                        if file_hash and file_hash != baseline_entry["sha256"]:
                            results.append({
                                "status": "Modified",
                                "filename": file_path.name,
                                "filepath": abs_path_str,
                                "sha256": file_hash,
                                "filesize": file_size,
                                "modified_time": modified_time
                            })
                            counts["Modified"] += 1
            except Exception as e:
                self.logger.error(f"Error scanning file {file_path}: {e}")
                
        # 4. Check for Deleted files (exist in baseline but not in scanned paths)
        for path_str, baseline_entry in baseline.items():
            # If path_str is not in scanned_paths and is under the currently scanned folder path
            try:
                # Only check baseline entries that belong to the folder path we are scanning
                is_subpath = Path(path_str).is_relative_to(folder_path)
            except ValueError:
                is_subpath = False
                
            path_key = path_str.lower() if is_windows else path_str
            if is_subpath and path_key not in scanned_paths:
                results.append({
                    "status": "Deleted",
                    "filename": baseline_entry["filename"],
                    "filepath": path_str,
                    "sha256": baseline_entry["sha256"],
                    "filesize": baseline_entry["filesize"],
                    "modified_time": baseline_entry["modified_time"]
                })
                counts["Deleted"] += 1
                
        counts["Total"] = counts["Added"] + counts["Modified"] + counts["Deleted"]
        duration = time.time() - start_time
        
        # 5. Save to history
        self.db_manager.add_scan_history(
            folder_path=str(folder_path.resolve()),
            added=counts["Added"],
            modified=counts["Modified"],
            deleted=counts["Deleted"],
            total_files=total_files,
            duration=duration
        )
        
        self.logger.info(f"Scan finished. Added: {counts['Added']}, Modified: {counts['Modified']}, Deleted: {counts['Deleted']}, Duration: {duration:.2f}s")
        return results, counts, duration
