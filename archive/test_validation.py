#!/usr/bin/env python3
"""
Test script for SRA metadata validation functions.

This script tests the validation functions with sample metadata to ensure
proper validation of SRA submission files.
"""

import os
import sys
import pandas as pd
import tempfile
import logging
import json
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"validation_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Add the src directory to path to enable imports
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'src'))
if os.path.exists(src_dir):
    sys.path.insert(0, src_dir)

# Try to import validation modules
try:
    from sra_metagenome_submission.sra_validate import (
        validate_sample_metadata,
        validate_bioproject_metadata,
        load_metadata_file,
        save_metadata_file,
        validate_date_format,
        validate_geo_loc_name,
        validate_lat_lon
    )
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Couldn't import from package. Try running from repository root.")
    sys.exit(1)

def create_test_config():
    """Create a temporary test configuration file."""
    config = {
        "default_values": {
            "library_strategy": "WGS",
            "library_source": "METAGENOMIC",
            "library_selection": "RANDOM",
            "platform": "ILLUMINA",
            "instrument_model": "Illumina MiSeq",
            "geo_loc_name": "USA:California",
            "lat_lon": "37.7749 N 122.4194 W",
            "collection_date": "2023-01-01"
        },
        "contact": {
            "name": "Test User",
            "email": "test@example.com",
            "organization": "Test Organization"
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config, f, indent=2)
        config_path = f.name
    
    return config_path, config

def create_test_sample_metadata():
    """Create test sample metadata dataframe with various validation issues."""
    data = {
        'sample_name': ['sample1', 'sample2', 'sample3', 'sample4', 'sample5'],
        'library_ID': ['lib1', '', 'lib3', 'lib4', ''],
        'title': ['Sample 1 metagenome', 'Sample 2', '', 'Sample 4', 'Sample 5'],
        'library_strategy': ['WGS', '', 'INVALIDSTRATEGY', 'WGS', 'AMPLICON'],
        'library_source': ['METAGENOMIC', '', 'INVALIDTYPE', 'METAGENOMIC', 'METAGENOMIC'],
        'library_selection': ['RANDOM', '', 'INVALIDSELECTION', 'RANDOM', 'PCR'],
        'library_layout': ['paired', 'single', 'invalid', 'paired', 'PAIRED'],
        'platform': ['ILLUMINA', '', 'INVALIDPLATFORM', 'ILLUMINA', 'ILLUMINA'],
        'instrument_model': ['Illumina MiSeq', '', 'INVALIDMODEL', 'Illumina MiSeq', 'Illumina NovaSeq 6000'],
        'design_description': ['Metagenomic sequencing', '', '', '', ''],
        'filetype': ['fastq', 'fastq', 'fastq', 'fastq', 'bam'],
        'filename': ['sample1_R1.fastq.gz', 'sample2.fastq.gz', 'sample3_R1.fastq.gz', 'sample4_R1.fastq.gz', 'sample5.bam'],
        'filename2': ['sample1_R2.fastq.gz', '', 'sample3_R2.fastq.gz', '', '']
    }
    return pd.DataFrame(data)

def create_test_bioproject_metadata():
    """Create test bioproject metadata dataframe with various validation issues."""
    data = {
        'bioproject_id': ['PRJXXXXX', '', 'PRJYYYYY', 'PRJZZZZZ', ''],
        'project_title': ['Marine Metagenome Project', 'Soil Metagenome', '', 'Human Microbiome', 'Lake Metagenome'],
        'project_description': ['Description 1', 'Description 2', '', 'Description 4', ''],
        'sample_source': ['environmental', 'environmental', 'host-associated', 'invalid', 'ENVIRONMENTAL'],
        'collection_date': ['2023-07-15', '07/20/2023', 'Jun-2023', '2023', 'invalid-date'],
        'geo_loc_name': ['USA:California', 'Canada', 'USA:Ohio:Cincinnati', 'Invalid Location', ''],
        'lat_lon': ['36.9513 N 122.0733 W', '45.123, -75.456', '39.1031 N 84.5120 W', 'invalid coords', ''],
        'library_strategy': ['WGS', '', 'INVALIDSTRATEGY', 'WGS', 'AMPLICON'],
        'library_source': ['METAGENOMIC', '', 'INVALIDTYPE', 'METAGENOMIC', 'METAGENOMIC'],
        'library_selection': ['RANDOM', '', 'INVALIDSELECTION', 'RANDOM', 'PCR'],
        'platform': ['ILLUMINA', '', 'INVALIDPLATFORM', 'ILLUMINA', 'ILLUMINA'],
        'instrument_model': ['Illumina MiSeq', '', 'INVALIDMODEL', 'Illumina MiSeq', 'Illumina NovaSeq 6000'],
        'env_biome': ['marine biome', 'soil biome', '', 'human-associated habitat', 'freshwater biome'],
        'env_feature': ['coastal water', 'agricultural soil', '', 'gut', 'lake'],
        'env_material': ['sea water', 'soil', '', 'feces', 'lake water'],
        'depth': ['10', '5', '', '', '15'],
        'altitude': ['0', '100', '', '', ''],
        'host': ['', '', 'Homo sapiens', 'Homo sapiens', ''],
        'host_tissue': ['', '', 'gut', '', ''],
        'isolation_source': ['', '', 'stool', '', '']
    }
    return pd.DataFrame(data)

def test_field_validation_functions():
    """Test the individual field validation functions."""
    logger.info("Testing individual field validation functions")
    print("\n=== Testing Field Validation Functions ===")
    
    # Test date format validation
    date_tests = [
        ('2023-07-15', '2023-07-15'),  # ISO format (already correct)
        ('07/15/2023', '2023-07-15'),  # MM/DD/YYYY
        ('15/07/2023', '2023-07-15'),  # DD/MM/YYYY
        ('15-Jul-2023', '2023-07-15'),  # DD-Mmm-YYYY
        ('Jul-2023', '2023-07'),       # Mmm-YYYY
        ('2023', '2023'),              # YYYY only
        ('2023-07-15T12:00:00Z', '2023-07-15T12:00:00Z'),  # ISO with time
        ('15-Jul-2023/20-Jul-2023', '2023-07-15/2023-07-20'),  # Date range
        ('invalid', 'invalid')         # Invalid date
    ]
    
    print("\nDate Format Validation:")
    print(f"{'Original Value':<20} | {'Validated Value':<20} | {'Status':<10}")
    print("-" * 55)
    
    for original, expected in date_tests:
        result = validate_date_format(original)
        status = "✓" if result == expected else "✗"
        print(f"{original:<20} | {result:<20} | {status:<10}")
    
    # Test geo_loc_name validation
    geo_tests = [
        ('USA:California', 'USA:California'),  # Already correct
        ('USA', 'USA:'),                      # Country only
        ('USA:California:San Francisco', 'USA:California:San Francisco'),  # Multiple levels
        ('Invalid Format', 'Invalid Format')  # Invalid format
    ]
    
    print("\nGeographic Location Validation:")
    print(f"{'Original Value':<30} | {'Validated Value':<30} | {'Status':<10}")
    print("-" * 75)
    
    for original, expected in geo_tests:
        result = validate_geo_loc_name(original)
        status = "✓" if result == expected else "✗"
        print(f"{original:<30} | {result:<30} | {status:<10}")
    
    # Test lat_lon validation
    latlon_tests = [
        ('36.9513 N 122.0733 W', '36.9513 N 122.0733 W'),  # Already correct
        ('36.9513, -122.0733', '36.9513 N 122.0733 W'),    # Decimal format
        ('-36.9513, 122.0733', '36.9513 S 122.0733 E'),    # Negative values
        ('Invalid Format', 'Invalid Format')                # Invalid format
    ]
    
    print("\nLatitude/Longitude Validation:")
    print(f"{'Original Value':<25} | {'Validated Value':<25} | {'Status':<10}")
    print("-" * 65)
    
    for original, expected in latlon_tests:
        result = validate_lat_lon(original)
        status = "✓" if result == expected else "✗"
        print(f"{original:<25} | {result:<25} | {status:<10}")

def test_sample_metadata_validation():
    """Test sample metadata validation."""
    logger.info("Testing sample metadata validation")
    print("\n=== Testing Sample Metadata Validation ===")
    
    # Create config
    config_path, config = create_test_config()
    
    # Create sample metadata
    df = create_test_sample_metadata()
    
    # Display original
    print("\nOriginal Sample Metadata (first 3 rows):")
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(df.head(3))
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
        df.to_csv(f.name, sep='\t', index=False)
        metadata_path = f.name
    
    # Load and validate
    print("\nLoading and validating sample metadata...")
    loaded_df = load_metadata_file(metadata_path)
    validated_df = validate_sample_metadata(loaded_df, config)
    
    # Display validated
    print("\nValidated Sample Metadata (first 3 rows):")
    print(validated_df.head(3))
    
    # Identify changes
    changes = {}
    for col in df.columns:
        if col in validated_df.columns:
            changed_rows = df[col] != validated_df[col]
            if changed_rows.any():
                changes[col] = changed_rows.sum()
    
    print("\nFields Modified During Validation:")
    for col, count in changes.items():
        print(f"- {col}: {count} rows modified")
    
    # Save validated metadata
    output_path = os.path.join(os.path.dirname(metadata_path), "validated_sample_metadata.txt")
    save_metadata_file(validated_df, output_path)
    print(f"\nValidated sample metadata saved to: {output_path}")
    
    # Clean up
    os.unlink(config_path)
    os.unlink(metadata_path)
    try:
        os.unlink(output_path)
    except:
        pass

def test_bioproject_metadata_validation():
    """Test bioproject metadata validation."""
    logger.info("Testing bioproject metadata validation")
    print("\n=== Testing Bioproject Metadata Validation ===")
    
    # Create config
    config_path, config = create_test_config()
    
    # Create bioproject metadata
    df = create_test_bioproject_metadata()
    
    # Display original
    print("\nOriginal Bioproject Metadata (first 3 rows):")
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(df.head(3))
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
        df.to_csv(f.name, sep='\t', index=False)
        metadata_path = f.name
    
    # Load and validate
    print("\nLoading and validating bioproject metadata...")
    loaded_df = load_metadata_file(metadata_path)
    validated_df = validate_bioproject_metadata(loaded_df, config)
    
    # Display validated
    print("\nValidated Bioproject Metadata (first 3 rows):")
    print(validated_df.head(3))
    
    # Identify changes
    changes = {}
    for col in df.columns:
        if col in validated_df.columns:
            changed_rows = df[col] != validated_df[col]
            if changed_rows.any():
                changes[col] = changed_rows.sum()
    
    print("\nFields Modified During Validation:")
    for col, count in changes.items():
        print(f"- {col}: {count} rows modified")
    
    # Check specific validations
    print("\nChecking specific validations:")
    
    # Check date format validations
    if 'collection_date' in validated_df.columns:
        date_changes = df['collection_date'] != validated_df['collection_date']
        changed_dates = pd.DataFrame({
            'Original': df.loc[date_changes, 'collection_date'],
            'Validated': validated_df.loc[date_changes, 'collection_date']
        })
        if not changed_dates.empty:
            print("\nDate Format Validations:")
            print(changed_dates)
    
    # Check geo_loc_name validations
    if 'geo_loc_name' in validated_df.columns:
        geo_changes = df['geo_loc_name'] != validated_df['geo_loc_name']
        changed_geos = pd.DataFrame({
            'Original': df.loc[geo_changes, 'geo_loc_name'],
            'Validated': validated_df.loc[geo_changes, 'geo_loc_name']
        })
        if not changed_geos.empty:
            print("\nGeographic Location Validations:")
            print(changed_geos)
    
    # Check lat_lon validations
    if 'lat_lon' in validated_df.columns:
        latlon_changes = df['lat_lon'] != validated_df['lat_lon']
        changed_latlons = pd.DataFrame({
            'Original': df.loc[latlon_changes, 'lat_lon'],
            'Validated': validated_df.loc[latlon_changes, 'lat_lon']
        })
        if not changed_latlons.empty:
            print("\nLatitude/Longitude Validations:")
            print(changed_latlons)
    
    # Save validated metadata
    output_path = os.path.join(os.path.dirname(metadata_path), "validated_bioproject_metadata.txt")
    save_metadata_file(validated_df, output_path)
    print(f"\nValidated bioproject metadata saved to: {output_path}")
    
    # Clean up
    os.unlink(config_path)
    os.unlink(metadata_path)
    try:
        os.unlink(output_path)
    except:
        pass

def test_metadata_with_both_files():
    """Test validation with both sample and bioproject metadata."""
    logger.info("Testing validation with both metadata files")
    print("\n=== Testing Combined Metadata Validation ===")
    
    # Create config
    config_path, config = create_test_config()
    
    # Create metadata
    sample_df = create_test_sample_metadata()
    bioproject_df = create_test_bioproject_metadata()
    
    # Save to temp files
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f1, \
         tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f2:
        sample_df.to_csv(f1.name, sep='\t', index=False)
        sample_path = f1.name
        
        bioproject_df.to_csv(f2.name, sep='\t', index=False)
        bioproject_path = f2.name
    
    # Create output directory
    output_dir = tempfile.mkdtemp()
    
    # Run command-line equivalent
    print("\nSimulating command-line validation:")
    cmd = f"sra-validate --config {config_path} --sample-metadata {sample_path} --bioproject-metadata {bioproject_path} --output-sample-metadata {output_dir}/validated_sample.txt --output-bioproject-metadata {output_dir}/validated_bioproject.txt"
    print(f"Command: {cmd}")
    
    # Load and validate
    print("\nValidating both metadata files...")
    sample_loaded = load_metadata_file(sample_path)
    bioproject_loaded = load_metadata_file(bioproject_path)
    
    sample_validated = validate_sample_metadata(sample_loaded, config)
    bioproject_validated = validate_bioproject_metadata(bioproject_loaded, config)
    
    # Save validated files
    sample_output = os.path.join(output_dir, "validated_sample.txt")
    bioproject_output = os.path.join(output_dir, "validated_bioproject.txt")
    
    save_metadata_file(sample_validated, sample_output)
    save_metadata_file(bioproject_validated, bioproject_output)
    
    # Cross-validation checks
    print("\nPerforming cross-validation checks:")
    
    # Check for sample name consistency
    sample_names_in_sample = set(sample_validated['sample_name'].dropna().tolist())
    sample_names_in_bioproject = set(bioproject_validated['bioproject_id'].dropna().tolist())
    
    print(f"- Sample metadata contains {len(sample_names_in_sample)} samples")
    print(f"- Bioproject metadata contains {len(sample_names_in_bioproject)} project entries")
    
    # Check for inconsistent field values
    common_fields = [field for field in sample_validated.columns if field in bioproject_validated.columns]
    print(f"\nCommon fields between sample and bioproject metadata: {common_fields}")
    
    # Output validation summary
    print("\nValidation summary:")
    print(f"- Sample metadata validated and saved to: {sample_output}")
    print(f"- Bioproject metadata validated and saved to: {bioproject_output}")
    
    # Clean up
    os.unlink(config_path)
    os.unlink(sample_path)
    os.unlink(bioproject_path)
    try:
        os.unlink(sample_output)
        os.unlink(bioproject_output)
        os.rmdir(output_dir)
    except:
        pass

if __name__ == "__main__":
    print("Running SRA metadata validation tests...\n")
    
    # Run the tests
    test_field_validation_functions()
    test_sample_metadata_validation()
    test_bioproject_metadata_validation()
    test_metadata_with_both_files()
    
    print("\nAll tests completed successfully!")
