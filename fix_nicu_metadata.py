#!/usr/bin/env python3
import sys

bioproject_file = "validated_metadata/validated-NICU-bioproject-metadata-cleaned.txt"
output_file = "validated_metadata/validated-NICU-bioproject-metadata-cleaned-fixed.txt"

# Standard values for missing fields
ORGANISM = "metagenome"
HOST = "Homo sapiens"
ISOLATION_SOURCE = "stool"
COLLECTION_DATE = "not collected"
GEO_LOC_NAME = "USA: Ohio, Cincinnati"
LAT_LON = "39.10 N 84.51 W"

fixed_count = 0
total_count = 0

with open(bioproject_file, 'r') as f_in, open(output_file, 'w') as f_out:
    # Read and write header
    header = f_in.readline()
    f_out.write(header)

    header_fields = header.strip().split('\t')
    organism_idx = header_fields.index('organism')
    host_idx = header_fields.index('host')
    isolation_source_idx = header_fields.index('isolation_source')
    collection_date_idx = header_fields.index('collection_date')
    geo_loc_name_idx = header_fields.index('geo_loc_name')
    lat_lon_idx = header_fields.index('lat_lon')

    for line in f_in:
        total_count += 1
        fields = line.strip().split('\t')

        # Pad fields if needed
        while len(fields) < len(header_fields):
            fields.append('')

        needs_fix = False

        # Fix organism
        if fields[organism_idx] == '':
            fields[organism_idx] = ORGANISM
            needs_fix = True

        # Fix host
        if fields[host_idx] == '':
            fields[host_idx] = HOST
            needs_fix = True

        # Fix isolation_source
        if fields[isolation_source_idx] == '':
            fields[isolation_source_idx] = ISOLATION_SOURCE
            needs_fix = True

        # Fix collection_date
        if fields[collection_date_idx] == '':
            fields[collection_date_idx] = COLLECTION_DATE
            needs_fix = True

        # Fix geo_loc_name
        if fields[geo_loc_name_idx] == '':
            fields[geo_loc_name_idx] = GEO_LOC_NAME
            needs_fix = True

        # Fix lat_lon
        if fields[lat_lon_idx] == '':
            fields[lat_lon_idx] = LAT_LON
            needs_fix = True

        if needs_fix:
            fixed_count += 1

        f_out.write('\t'.join(fields) + '\n')

print(f"Processed {total_count} samples")
print(f"Fixed {fixed_count} samples with missing fields")
print(f"Output: {output_file}")
