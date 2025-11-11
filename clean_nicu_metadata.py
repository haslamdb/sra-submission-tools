#!/usr/bin/env python3
import os

sequence_dir = "/bulkpool/sequence_data/mss_data"
sample_metadata_file = "validated_metadata/validated-NICU-sample-metadata.txt"
bioproject_metadata_file = "validated_metadata/validated-NICU-bioproject-metadata.txt"

output_sample = "validated_metadata/validated-NICU-sample-metadata-cleaned.txt"
output_bioproject = "validated_metadata/validated-NICU-bioproject-metadata-cleaned.txt"

# First, identify samples with both R1 and R2 files present
valid_samples = []

with open(sample_metadata_file, 'r') as f:
    header = f.readline()
    for line in f:
        fields = line.strip().split('\t')
        sample_name = fields[0]
        r1 = f"{sample_name}_R1.fastq.gz"
        r2 = f"{sample_name}_R2.fastq.gz"

        r1_path = os.path.join(sequence_dir, r1)
        r2_path = os.path.join(sequence_dir, r2)

        if os.path.exists(r1_path) and os.path.exists(r2_path):
            valid_samples.append(sample_name)

print(f"Valid samples with complete file pairs: {len(valid_samples)}")

# Write cleaned sample metadata
with open(sample_metadata_file, 'r') as f_in, open(output_sample, 'w') as f_out:
    header = f_in.readline()
    f_out.write(header)

    for line in f_in:
        fields = line.strip().split('\t')
        sample_name = fields[0]
        if sample_name in valid_samples:
            f_out.write(line)

print(f"Created: {output_sample}")

# Write cleaned bioproject metadata
with open(bioproject_metadata_file, 'r') as f_in, open(output_bioproject, 'w') as f_out:
    header = f_in.readline()
    f_out.write(header)

    for line in f_in:
        fields = line.strip().split('\t')
        sample_name = fields[0]
        if sample_name in valid_samples:
            f_out.write(line)

print(f"Created: {output_bioproject}")
print(f"\nRemoved {386 - len(valid_samples)} samples with missing files")
