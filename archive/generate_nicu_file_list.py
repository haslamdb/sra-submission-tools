#!/usr/bin/env python3
import os

sequence_dir = "/bulkpool/sequence_data/mss_data"
sample_metadata = "validated_metadata/validated-NICU-sample-metadata-cleaned.txt"
output_file = "nicu_file_list.txt"

files = []

with open(sample_metadata, 'r') as f:
    header = f.readline().strip().split('\t')
    filename1_idx = header.index('filename')
    filename2_idx = header.index('filename2')

    for line in f:
        fields = line.strip().split('\t')
        filename1 = fields[filename1_idx] if filename1_idx < len(fields) else ''
        filename2 = fields[filename2_idx] if filename2_idx < len(fields) else ''

        if filename1:
            files.append(os.path.join(sequence_dir, filename1))
        if filename2:
            files.append(os.path.join(sequence_dir, filename2))

with open(output_file, 'w') as f:
    for file in files:
        f.write(file + '\n')

print(f"Created {output_file} with {len(files)} files ({len(files)//2} sample pairs)")
