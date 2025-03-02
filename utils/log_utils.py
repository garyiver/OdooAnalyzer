"""Logging utilities for Odoo analyzer"""
import logging
import sys

def setup_logging(level_name='INFO'):
    """Setup logging configuration"""
    level = getattr(logging, level_name)
    
    # Configure logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    
    # Create a file handler
    file_handler = logging.FileHandler('odoo_analyzer.log')
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    # Add the file handler to the root logger
    logging.getLogger().addHandler(file_handler)
    
    return logging.getLogger()
