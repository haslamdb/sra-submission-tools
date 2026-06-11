#!/usr/bin/env python3
import os

metadata_file = "validated_metadata/validated-NICU-sample-metadata.txt"
sequence_dir = "/bulkpool/sequence_data/mss_data"

missing_files = []
found_count = 0

with open(metadata_file, 'r') as f:
    # Skip header
    next(f)
    for line in f:
        fields = line.strip().split('\t')
        sample_name = fields[0]
        r1 = f"{sample_name}_R1.fastq.gz"
        r2 = f"{sample_name}_R2.fastq.gz"

        r1_path = os.path.join(sequence_dir, r1)
        r2_path = os.path.join(sequence_dir, r2)

        if not os.path.exists(r1_path):
            missing_files.append(r1)
        else:
            found_count += 1

        if not os.path.exists(r2_path):
            missing_files.append(r2)
        else:
            found_count += 1

print(f"Found: {found_count} files")
print(f"Missing: {len(missing_files)} files")
if missing_files:
    print(f"\nFirst 20 missing files:")
    for f in missing_files[:20]:
        print(f"  {f}")
