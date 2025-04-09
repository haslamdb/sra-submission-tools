#!/usr/bin/env python3
"""
Test script for SRA metadata validation functions.

This script tests the validation functions with sample metadata.
"""

import os
import sys
import pandas as pd
import tempfile
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import validation utilities
try:
    from sra_metagenome_submission.sra_validation_utils import (
        validate_bioproject_metadata,
        validate_sample_metadata,
        validate_and_fix_metadata,
        DEFAULT_VALUES,
        VALID_OPTIONS
    )
except ImportError:
    # Try local import
    sys.path.append(".")
    try:
        from sra_validation_utils import (
            validate_bioproject_metadata,
            validate_sample_metadata,
            validate_and_fix_metadata,
            DEFAULT_VALUES,
            VALID_OPTIONS
        )
    except ImportError:
        print("Error: sra_validation_utils module not found.")
        sys.exit(1)

def create_test_bioproject_metadata():
    """Create a test bioproject metadata DataFrame."""
    data = {
        'sample_name': ['sample1', 'sample2', 'sample3', 'sample4', ''],
        'organism': ['Homo sapiens', '', 'Escherichia coli', '', ''],
        'collection_date': ['2023-05-15', '2023/06/20', '05/25/2023', '', ''],
        'geo_loc_name': ['United States: Ohio: Cincinnati', '', 'Canada: Alberta', 'Invalid Location', ''],
        'lat_lon': ['39.10 N 84.51 W', '', '51.05 N 114.07 W', 'Invalid coordinates', '']
    }
    return pd.DataFrame(data)

def create_test_sample_metadata():
    """Create a test sample metadata DataFrame."""
    data = {
        'sample_name': ['sample1', 'sample2', 'sample3', 'sample5', ''],
        'library_ID': ['lib1', '', 'lib3', '', ''],
        'title': ['Sample 1 metagenome', '', '', '', ''],
        'library_strategy': ['WGS', 'RNA-Seq', 'INVALID_STRATEGY', '', ''],
        'library_source': ['METAGENOMIC', '', 'INVALID_SOURCE', '', ''],
        'library_selection': ['RANDOM', '', 'INVALID_SELECTION', '', ''],
        'library_layout': ['paired', 'single', 'invalid', '', ''],
        'platform': ['ILLUMINA', '', 'INVALID_PLATFORM', '', ''],
        'instrument_model': ['Illumina NovaSeq X', '', 'INVALID_MODEL', '', ''],
        'filetype': ['fastq', '', 'INVALID_TYPE', '', ''],
        'filename': ['sample1_R1.fastq.gz', 'sample2.fastq.gz', 'sample3_R1.fastq.gz', '', ''],
        'filename2': ['sample1_R2.fastq.gz', '', '', '', '']
    }
    return pd.DataFrame(data)

def test_bioproject_validation():
    """Test bioproject metadata validation."""
    print("\n=== Testing Bioproject Metadata Validation ===")
    
    df = create_test_bioproject_metadata()
    print("Original bioproject metadata:")
    print(df)
    
    validated_df, issues = validate_bioproject_metadata(df, DEFAULT_VALUES)
    print("\nValidated bioproject metadata:")
    print(validated_df)
    
    print("\nValidation issues:")
    for i, issue in enumerate(issues, 1):
        print(f"{i}. {issue}")
    
    print("\nChanges made:")
    # Check for file_number column
    if 'file_number' in validated_df.columns:
        print(f"- Added file_number column: {validated_df['file_number'].tolist()}")
    
    # Check for defaults applied
    for col in ['organism', 'geo_loc_name', 'lat_lon']:
        if col in validated_df.columns:
            changed = (df[col] != validated_df[col]).sum()
            if changed > 0:
                print(f"- Applied default value to {changed} empty cells in '{col}' column")

def test_sample_validation():
    """Test sample metadata validation."""
    print("\n=== Testing Sample Metadata Validation ===")
    
    df = create_test_sample_metadata()
    print("Original sample metadata:")
    print(df)
    
    validated_df, issues = validate_sample_metadata(df, None, DEFAULT_VALUES)
    print("\nValidated sample metadata:")
    print(validated_df)
    
    print("\nValidation issues:")
    for i, issue in enumerate(issues, 1):
        print(f"{i}. {issue}")
    
    print("\nChanges made:")
    # Check for library_ID defaults
    if 'library_ID' in validated_df.columns and 'sample_name' in validated_df.columns:
        changed = sum((df['library_ID'] != validated_df['library_ID']) & 
                     (df['library_ID'].isnull() | (df['library_ID'] == "")))
        if changed > 0:
            print(f"- Set library_ID to sample_name for {changed} rows")
    
    # Check for defaults applied to constrained fields
    for col in ['library_strategy', 'library_source', 'library_selection', 'platform', 'instrument_model', 'filetype']:
        if col in validated_df.columns:
            changed = (df[col] != validated_df[col]).sum()
            if changed > 0:
                print(f"- Applied default or corrected invalid values in '{col}' column for {changed} rows")

def test_cross_validation():
    """Test cross-validation between bioproject and sample metadata."""
    print("\n=== Testing Cross-Validation ===")
    
    bioproject_df = create_test_bioproject_metadata()
    sample_df = create_test_sample_metadata()
    
    print("Bioproject samples:", bioproject_df['sample_name'].dropna().tolist())
    print("Sample metadata samples:", sample_df['sample_name'].dropna().tolist())
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as bp_file, \
         tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as sample_file, \
         tempfile.TemporaryDirectory() as temp_dir:
        
        bioproject_df.to_csv(bp_file.name, index=False)
        sample_df.to_csv(sample_file.name, index=False)
        
        # Validate both files together
        validated_bp_df, validated_sample_df, issues = validate_and_fix_metadata(
            bp_file.name, sample_file.name, None, temp_dir
        )
        
        print("\nValidation issues:")
        for i, issue in enumerate(issues, 1):
            print(f"{i}. {issue}")
        
        print("\nCross-validation results:")
        bp_samples = set(validated_bp_df['sample_name'].dropna().tolist())
        sample_samples = set(validated_sample_df['sample_name'].dropna().tolist())
        
        matching = bp_samples.intersection(sample_samples)
        only_in_bp = bp_samples - sample_samples
        only_in_sample = sample_samples - bp_samples
        
        print(f"- Samples in both files: {sorted(list(matching))}")
        print(f"- Samples only in bioproject: {sorted(list(only_in_bp))}")
        print(f"- Samples only in sample metadata: {sorted(list(only_in_sample))}")
        
        # Clean up
        os.remove(bp_file.name)
        os.remove(sample_file.name)

if __name__ == "__main__":
    print("Running validation tests...\n")
    
    test_bioproject_validation()
    test_sample_validation()
    test_cross_validation()
    
    print("\nAll tests completed.")
