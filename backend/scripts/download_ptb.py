import wfdb
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_ptb(dl_dir):
    os.makedirs(dl_dir, exist_ok=True)
    logger.info(f"Downloading PTB Diagnostic Database to {dl_dir}...")
    try:
        # wfdb.dl_database will download the database. 
        # By default, it downloads the whole database if we just pass 'ptbdb'
        wfdb.dl_database('ptbdb', dl_dir=dl_dir)
        logger.info("Download complete.")
    except Exception as e:
        logger.error(f"Error downloading dataset: {e}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_dir = os.path.join(base_dir, "app", "database", "ptbdb")
    download_ptb(target_dir)
