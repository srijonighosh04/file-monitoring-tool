import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Tuple
import config
from utils import get_logger

class DatabaseError(Exception):
    """Custom exception for database errors."""
    pass

class DatabaseManager:
    def __init__(self, db_path: Path = config.DATABASE_PATH):
        self.db_path = db_path
        self.logger = get_logger()
        self.initialize_db()

    def get_connection(self) -> sqlite3.Connection:
        """Establishes and returns a database connection."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Access columns by name
            return conn
        except sqlite3.Error as e:
            self.logger.error(f"Failed to connect to database: {e}")
            raise DatabaseError(f"Database connection error: {e}")

    def initialize_db(self):
        """Initializes tables in the SQLite database. Rebuilds if corrupted."""
        try:
            self._create_tables()
        except sqlite3.DatabaseError as e:
            self.logger.warning(f"Database corrupted or inaccessible. Recreating: {e}")
            self.recreate_db()

    def _create_tables(self):
        """Internal helper to create baseline and history tables."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Baseline table: stores baseline metadata for monitored files
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS baseline (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filepath TEXT UNIQUE,
                    filename TEXT,
                    sha256 TEXT,
                    filesize INTEGER,
                    modified_time REAL
                )
            """)
            
            # History table: stores summaries of previous scans
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scan_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    folder_path TEXT,
                    added INTEGER,
                    modified INTEGER,
                    deleted INTEGER,
                    total_files INTEGER,
                    duration REAL
                )
            """)
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            self.logger.error(f"Error creating tables: {e}")
            raise DatabaseError(e)
        finally:
            conn.close()

    def recreate_db(self):
        """Deletes the existing database file and recreates tables from scratch."""
        self.logger.warning("Recreating database due to corruption or reset request.")
        try:
            if self.db_path.exists():
                self.db_path.unlink()
            self._create_tables()
            self.logger.info("Database recreated successfully.")
        except Exception as e:
            self.logger.critical(f"Critical error: Failed to recreate database: {e}")
            raise DatabaseError(f"Database reconstruction failed: {e}")

    def clear_baseline(self):
        """Clears all records in the baseline table."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM baseline")
            conn.commit()
            self.logger.info("Database baseline table cleared.")
        except sqlite3.Error as e:
            conn.rollback()
            self.logger.error(f"Error clearing baseline table: {e}")
            raise DatabaseError(e)
        finally:
            conn.close()

    def save_baseline(self, entries: List[Dict[str, Any]]):
        """
        Saves a list of baseline file records to the database.
        
        Args:
            entries: List of dicts, each with filepath, filename, sha256, filesize, modified_time.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Insert entries using REPLACE to handle updates cleanly
            cursor.executemany("""
                INSERT OR REPLACE INTO baseline (filepath, filename, sha256, filesize, modified_time)
                VALUES (:filepath, :filename, :sha256, :filesize, :modified_time)
            """, entries)
            conn.commit()
            self.logger.info(f"Saved {len(entries)} records to the baseline table.")
        except sqlite3.Error as e:
            conn.rollback()
            self.logger.error(f"Error saving baseline entries: {e}")
            raise DatabaseError(e)
        finally:
            conn.close()

    def get_baseline(self) -> Dict[str, Dict[str, Any]]:
        """
        Retrieves baseline records from the database.
        
        Returns:
            Dict mapping filepath to baseline dictionary details.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        baseline = {}
        try:
            cursor.execute("SELECT filepath, filename, sha256, filesize, modified_time FROM baseline")
            rows = cursor.fetchall()
            for row in rows:
                baseline[row['filepath']] = {
                    'filepath': row['filepath'],
                    'filename': row['filename'],
                    'sha256': row['sha256'],
                    'filesize': row['filesize'],
                    'modified_time': row['modified_time']
                }
            return baseline
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving baseline records: {e}")
            raise DatabaseError(e)
        finally:
            conn.close()

    def add_scan_history(self, folder_path: str, added: int, modified: int, deleted: int, total_files: int, duration: float):
        """Adds a summary entry to the scan history."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Use python's current time for timestamp formatting
        from datetime import datetime
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            cursor.execute("""
                INSERT INTO scan_history (timestamp, folder_path, added, modified, deleted, total_files, duration)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (now_str, folder_path, added, modified, deleted, total_files, duration))
            conn.commit()
            self.logger.info("Scan history updated.")
        except sqlite3.Error as e:
            conn.rollback()
            self.logger.error(f"Error adding scan history: {e}")
            raise DatabaseError(e)
        finally:
            conn.close()

    def get_scan_history(self) -> List[Tuple[int, str, str, int, int, int, int, float]]:
        """Retrieves scan history rows."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, timestamp, folder_path, added, modified, deleted, total_files, duration 
                FROM scan_history 
                ORDER BY id DESC
            """)
            rows = cursor.fetchall()
            return [tuple(row) for row in rows]
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving scan history: {e}")
            raise DatabaseError(e)
        finally:
            conn.close()

    def clear_scan_history(self):
        """Clears all scan history entries."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM scan_history")
            conn.commit()
            self.logger.info("Scan history table cleared.")
        except sqlite3.Error as e:
            conn.rollback()
            self.logger.error(f"Error clearing scan history: {e}")
            raise DatabaseError(e)
        finally:
            conn.close()
