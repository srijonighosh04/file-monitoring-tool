from pathlib import Path
from datetime import datetime
import pandas as pd
from typing import List, Dict, Any
from utils import get_logger, format_size, format_timestamp

class ReportGenerator:
    def __init__(self):
        self.logger = get_logger()

    def export_txt(self, results: List[Dict[str, Any]], counts: Dict[str, int], duration: float, export_path: Path) -> Path:
        """
        Exports the scan results into a formatted TXT report.
        """
        try:
            # Group files by status
            added_files = [r for r in results if r["status"] == "Added"]
            modified_files = [r for r in results if r["status"] == "Modified"]
            deleted_files = [r for r in results if r["status"] == "Deleted"]
            
            current_date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with export_path.open("w", encoding="utf-8") as f:
                f.write(f"Date: {current_date_str}\n")
                f.write(f"Scan Time: {duration:.2f} sec\n\n")
                
                f.write("-----------------------------------\n\n")
                f.write("Added Files\n\n")
                if added_files:
                    for item in added_files:
                        f.write(f"{item['filename']} ({item['filepath']})\n")
                else:
                    f.write("None\n")
                f.write("\n")
                
                f.write("-----------------------------------\n\n")
                f.write("Modified Files\n\n")
                if modified_files:
                    for item in modified_files:
                        f.write(f"{item['filename']} ({item['filepath']})\n")
                else:
                    f.write("None\n")
                f.write("\n")
                
                f.write("-----------------------------------\n\n")
                f.write("Deleted Files\n\n")
                if deleted_files:
                    for item in deleted_files:
                        f.write(f"{item['filename']} ({item['filepath']})\n")
                else:
                    f.write("None\n")
                f.write("\n")
                
                f.write("-----------------------------------\n\n")
                f.write("Summary\n\n")
                f.write(f"Added : {counts.get('Added', 0)}\n")
                f.write(f"Modified : {counts.get('Modified', 0)}\n")
                f.write(f"Deleted : {counts.get('Deleted', 0)}\n")
                
            self.logger.info(f"TXT report exported successfully to {export_path}")
            return export_path
        except Exception as e:
            self.logger.error(f"Failed to export TXT report: {e}")
            raise

    def export_csv(self, results: List[Dict[str, Any]], export_path: Path) -> Path:
        """
        Exports the scan results into a CSV report using pandas.
        """
        try:
            if not results:
                # Create empty dataframe with headers
                df = pd.DataFrame(columns=["Status", "Filename", "Path", "SHA256", "Size", "Timestamp"])
            else:
                # Prepare data dictionary list
                data = []
                for r in results:
                    data.append({
                        "Status": r["status"],
                        "Filename": r["filename"],
                        "Path": r["filepath"],
                        "SHA256": r["sha256"],
                        "Size": format_size(r["filesize"]),
                        "Timestamp": format_timestamp(r["modified_time"])
                    })
                df = pd.DataFrame(data)
                
            # Export dataframe to CSV
            df.to_csv(export_path, index=False, encoding="utf-8")
            self.logger.info(f"CSV report exported successfully to {export_path}")
            return export_path
        except Exception as e:
            self.logger.error(f"Failed to export CSV report: {e}")
            raise
