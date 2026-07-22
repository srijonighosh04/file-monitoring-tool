import hashlib
from pathlib import Path
from typing import Optional
from utils import get_logger

def calculate_sha256(file_path: Path, chunk_size: int = 4096) -> Optional[str]:
    """
    Calculate the SHA-256 hash of a file by reading it in chunks.
    
    Args:
        file_path (Path): Path to the file.
        chunk_size (int): Chunk size in bytes (default 4096).
        
    Returns:
        Optional[str]: Hexadecimal SHA-256 hash, or None if reading failed.
    """
    logger = get_logger()
    sha256_hash = hashlib.sha256()
    
    try:
        # Open in binary mode ('rb')
        with file_path.open('rb') as f:
            for byte_block in iter(lambda: f.read(chunk_size), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except PermissionError:
        logger.error(f"Permission denied: Unable to read file {file_path}")
        return None
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return None
    except Exception as e:
        logger.error(f"Error calculating hash for {file_path}: {e}")
        return None
