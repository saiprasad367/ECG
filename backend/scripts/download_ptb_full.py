import wfdb
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_ptb_full(dl_dir):
    os.makedirs(dl_dir, exist_ok=True)
    logger.info(f"Fetching record list for PTB from PhysioNet...")
    records = wfdb.get_record_list('ptbdb')
    logger.info(f"Found {len(records)} records. Downloading to {dl_dir}...")
    
    # Download each record including .dat and .hea
    for r in records:
        try:
            # We don't need keep_subdirs=True if we just want them flat, but PhysioNet has patientXXX/ subdirs
            # Let's keep it simple
            wfdb.dl_pb_db('ptbdb', dl_dir, records=[r]) # wfdb.dl_database has quirks
            logger.info(f"Downloaded {r}")
        except Exception as e:
            try:
                # alternative using dl_database
                wfdb.dl_database('ptbdb', dl_dir, records=[r])
                logger.info(f"Downloaded {r}")
            except Exception as e2:
                logger.error(f"Failed to download {r}: {e2}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_dir = os.path.join(base_dir, "app", "database", "ptbdb")
    download_ptb_full(target_dir)
