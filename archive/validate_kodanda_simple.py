#!/usr/bin/env python3
"""
Simple validation for Kodanda metadata without interactive prompts
"""
import sys
import os
import pandas as pd
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from sra_metagenome_submission.sra_validate import (
    validate_sample_metadata,
    validate_bioproject_metadata,
    check_files_exist,
    save_metadata_file
)

# Load config
with open('dbh_config.json', 'r') as f:
    config = json.load(f)

print("Loading metadata files...")
# Load metadata
sample_df = pd.read_csv('metadata_files/kodanda-sample-metadata.txt', sep='\t', dtype=str)
bioproject_df = pd.read_csv('metadata_files/kodanda-bioproject-metadata.txt', sep='\t', dtype=str)

print(f"Loaded {len(sample_df)} samples from sample metadata")
print(f"Loaded {len(bioproject_df)} samples from bioproject metadata")

# Check if files exist
print("\nChecking if all files exist...")
file_dir = '/bulkpool/sequence_data/16S_data/Kodanda/demultiplexed'
all_exist, missing_files, missing_by_sample = check_files_exist(sample_df, file_dir)

if not all_exist:
    print(f"WARNING: {len(missing_files)} files are missing!")
    for sample, files in list(missing_by_sample.items())[:5]:
        print(f"  {sample}: {files}")
else:
    print("All files exist!")

# Validate metadata
print("\nValidating sample metadata...")
validated_sample_df = validate_sample_metadata(sample_df, config)
print("Sample metadata validated!")

print("\nValidating bioproject metadata...")
validated_bioproject_df = validate_bioproject_metadata(bioproject_df, config)
print("Bioproject metadata validated!")

# Save validated files
print("\nSaving validated files...")
os.makedirs('validated_metadata', exist_ok=True)
save_metadata_file(validated_sample_df, 'validated_metadata/validated-kodanda-sample-metadata.txt')
save_metadata_file(validated_bioproject_df, 'validated_metadata/validated-kodanda-bioproject-metadata.txt')

print("\nValidation complete!")
print("Validated files saved to:")
print("  - validated_metadata/validated-kodanda-sample-metadata.txt")
print("  - validated_metadata/validated-kodanda-bioproject-metadata.txt")
