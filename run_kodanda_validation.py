#!/usr/bin/env python3
"""
Quick validation runner for Kodanda metadata
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from sra_metagenome_submission.sra_validate import main

if __name__ == '__main__':
    # Set up arguments
    sys.argv = [
        'run_kodanda_validation.py',
        '--config', 'dbh_config.json',
        '--sample-metadata', 'metadata_files/kodanda-sample-metadata.txt',
        '--bioproject-metadata', 'metadata_files/kodanda-bioproject-metadata.txt',
        '--file-dir', '/bulkpool/sequence_data/16S_data/Kodanda/demultiplexed',
        '--validation-name', 'kodanda',
        '--output-dir', 'validated_metadata'
    ]

    main()
