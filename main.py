import sys
import traceback
import ttkbootstrap as ttk
import config
from utils import ensure_directories, setup_logging, get_logger
from gui import FIMApplication

def main():
    # 1. Prepare required workspace directories (logs, reports, database)
    ensure_directories()
    
    # 2. Setup Logging
    logger = setup_logging()
    logger.info("=========================================")
    logger.info(f"Starting {config.APP_TITLE} (v{config.APP_VERSION})")
    
    # 3. Intercept and log any uncaught Python exceptions
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Uncaught Exception detected:", exc_info=(exc_type, exc_value, exc_traceback))
        # Log to stderr as fallback
        traceback.print_exception(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception

    try:
        # 4. Start the ttkbootstrap GUI Window
        # Note: ttk.Window initializes a tk.Tk sub-class under the hood
        root = ttk.Window(
            title=config.APP_TITLE,
            themename=config.DEFAULT_THEME,
            resizable=(True, True)
        )
        
        # 5. Initialize application layout
        app = FIMApplication(root)
        
        # 6. Execute Tkinter main event loop
        logger.info("Application interface loaded. Starting event loop.")
        root.mainloop()
        
        logger.info("Application closed successfully.")
        
    except Exception as e:
        logger.critical(f"Failed to start FIM tool: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
