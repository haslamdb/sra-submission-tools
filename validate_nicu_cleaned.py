#!/usr/bin/env python3
import os
import sys

sequence_dir = "/bulkpool/sequence_data/mss_data"
sample_metadata = "validated_metadata/validated-NICU-sample-metadata-cleaned.txt"
bioproject_metadata = "validated_metadata/validated-NICU-bioproject-metadata-cleaned.txt"

errors = []
warnings = []

print("Validating NICU cleaned metadata files...\n")

# Validate sample metadata
print(f"1. Checking {sample_metadata}")
with open(sample_metadata, 'r') as f:
    lines = f.readlines()
    header = lines[0].strip().split('\t')

    # Check required columns
    required_cols = ['sample_name', 'library_ID', 'filename', 'filename2']
    for col in required_cols:
        if col not in header:
            errors.append(f"Missing required column: {col}")

    print(f"   - Header columns: {len(header)}")
    print(f"   - Data rows: {len(lines)-1}")

    # Check all files exist
    missing_files = []
    for i, line in enumerate(lines[1:], start=2):
        fields = line.strip().split('\t')
        if len(fields) < len(header):
            warnings.append(f"Line {i}: Insufficient fields")
            continue

        sample_name = fields[0]
        filename1_idx = header.index('filename')
        filename2_idx = header.index('filename2')

        filename1 = fields[filename1_idx] if filename1_idx < len(fields) else ''
        filename2 = fields[filename2_idx] if filename2_idx < len(fields) else ''

        if filename1:
            path1 = os.path.join(sequence_dir, filename1)
            if not os.path.exists(path1):
                missing_files.append(filename1)

        if filename2:
            path2 = os.path.join(sequence_dir, filename2)
            if not os.path.exists(path2):
                missing_files.append(filename2)

    if missing_files:
        errors.append(f"Missing {len(missing_files)} sequence files")
        print(f"   - Missing files: {len(missing_files)}")
        for f in missing_files[:5]:
            print(f"     * {f}")
        if len(missing_files) > 5:
            print(f"     ... and {len(missing_files)-5} more")
    else:
        print(f"   - All sequence files found!")

# Validate bioproject metadata
print(f"\n2. Checking {bioproject_metadata}")
with open(bioproject_metadata, 'r') as f:
    lines = f.readlines()
    header = lines[0].strip().split('\t')

    print(f"   - Header columns: {len(header)}")
    print(f"   - Data rows: {len(lines)-1}")

    # Check sample counts match
    with open(sample_metadata, 'r') as sf:
        sample_lines = len(sf.readlines()) - 1

    bioproject_lines = len(lines) - 1

    if sample_lines != bioproject_lines:
        errors.append(f"Sample count mismatch: sample_metadata has {sample_lines}, bioproject has {bioproject_lines}")
    else:
        print(f"   - Sample counts match: {sample_lines} samples")

# Summary
print("\n" + "="*60)
if errors:
    print(f"VALIDATION FAILED - {len(errors)} error(s):")
    for err in errors:
        print(f"  ERROR: {err}")
    sys.exit(1)
elif warnings:
    print(f"VALIDATION PASSED WITH WARNINGS - {len(warnings)} warning(s):")
    for warn in warnings:
        print(f"  WARNING: {warn}")
    sys.exit(0)
else:
    print("VALIDATION PASSED - No errors or warnings")
    print("\nMetadata files are ready for submission!")
    print(f"  - {sample_metadata}")
    print(f"  - {bioproject_metadata}")
    sys.exit(0)
