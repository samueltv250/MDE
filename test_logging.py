import os
import logging

DATA_BASE_DIR = ""
LOG_FILE = "sdr_recorder.log"
log_path = "sdr_recorder.log"

logging.basicConfig(level=logging.INFO, filename=log_path, filemode='a', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


logger.error("end_time must be timezone-aware")
