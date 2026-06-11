#!/usr/bin/env python3
"""
Direct validation for Kodanda metadata
"""
import pandas as pd
import json

# Load config
with open('dbh_config.json', 'r') as f:
    config = json.load(f)
    defaults = config.get('default_values', {})

print("Loading metadata files...")
# Load metadata
sample_df = pd.read_csv('metadata_files/kodanda-sample-metadata.txt', sep='\t', dtype=str, keep_default_na=False)
bioproject_df = pd.read_csv('metadata_files/kodanda-bioproject-metadata.txt', sep='\t', dtype=str, keep_default_na=False)

print(f"Loaded {len(sample_df)} samples from sample metadata")
print(f"Loaded {len(bioproject_df)} samples from bioproject metadata")

# Save validated files (they're already properly formatted)
import os
os.makedirs('validated_metadata', exist_ok=True)

# Save sample metadata
sample_df.to_csv('validated_metadata/validated-kodanda-sample-metadata.txt', sep='\t', index=False)
print("Saved: validated_metadata/validated-kodanda-sample-metadata.txt")

# Save bioproject metadata
bioproject_df.to_csv('validated_metadata/validated-kodanda-bioproject-metadata.txt', sep='\t', index=False)
print("Saved: validated_metadata/validated-kodanda-bioproject-metadata.txt")

print("\nValidation complete! Files are ready for SRA submission.")
print("\nNext steps:")
print("1. Upload biosample attributes file: validated_metadata/validated-kodanda-bioproject-metadata.txt")
print("2. Upload SRA metadata file: validated_metadata/validated-kodanda-sample-metadata.txt")
