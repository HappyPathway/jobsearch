#!/usr/bin/env python3
from gcs_utils import gcs
import argparse

def main():
    parser = argparse.ArgumentParser(description='Force unlock the GCS database lock')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()
    
    if not args.force:
        confirm = input("WARNING: This will forcefully remove the GCS database lock. This should only be used if you're sure no other process is actively using the database. Continue? [y/N] ")
        if confirm.lower() != 'y':
            print("Aborted.")
            return
    
    if gcs.force_unlock():
        print("Successfully removed GCS database lock")
    else:
        print("Failed to remove GCS database lock")

if __name__ == "__main__":
    main()