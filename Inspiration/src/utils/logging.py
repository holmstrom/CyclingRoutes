"""
Logging utility funktioner.
"""

import logging
from pathlib import Path
from datetime import datetime


def ensure_dirs(*dirs: str) -> None:
    """
    Opretter mapper hvis de ikke eksisterer.
    
    Args:
        *dirs: Mapper at oprette
    """
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)


def get_logger(
    name: str = "AarhusBestCyclingRoutes",
    log_dir: str = "logs",
    log_level: str = "INFO"
) -> logging.Logger:
    """
    Opretter en logger med fil og console handlers.
    
    Args:
        name: Logger navn
        log_dir: Mappe til log filer
        log_level: Log niveau (DEBUG, INFO, WARNING, ERROR)
        
    Returns:
        Logger instance
    """
    ensure_dirs(log_dir)
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.propagate = False
    
    # Fjern eksisterende handlers for at undgå duplikater
    logger.handlers.clear()
    
    # Formatter
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    
    # Fil handler med timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = Path(log_dir) / f"{name}_{timestamp}.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    fh.setLevel(logging.DEBUG)  # Fil logger alt
    logger.addHandler(fh)
    
    # Console handler
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(getattr(logging, log_level.upper(), logging.INFO))  # Console logger kun INFO+
    logger.addHandler(sh)
    
    return logger


