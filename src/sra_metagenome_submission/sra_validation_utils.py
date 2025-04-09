#!/usr/bin/env python3
"""
SRA Validation Utilities

This module provides validation functions for SRA metadata to ensure
compliance with NCBI's SRA submission requirements.
"""

import os
import sys
import json
import pandas as pd
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Define the valid options for constrained fields
VALID_OPTIONS = {
    'library_strategy': [
        'WGA', 'WGS', 'WXS', 'RNA-Seq', 'miRNA-Seq', 'WCS', 'CLONE', 'POOLCLONE', 
        'AMPLICON', 'CLONEEND', 'FINISHING', 'ChIP-Seq', 'MNase-Seq', 
        'DNase-Hypersensitivity', 'Bisulfite-Seq', 'Tn-Seq', 'EST', 'FL-cDNA', 
        'CTS', 'MRE-Seq', 'MeDIP-Seq', 'MBD-Seq', 'Synthetic-Long-Read', 
        'ATAC-seq', 'ChIA-PET', 'FAIRE-seq', 'Hi-C', 'ncRNA-Seq', 'RAD-Seq', 
        'RIP-Seq', 'SELEX', 'ssRNA-seq', 'Targeted-Capture', 
        'Tethered Chromatin Conformation Capture', 'DIP-Seq', 'GBS', 
        'Inverse rRNA', 'NOMe-Seq', 'Ribo-seq', 'VALIDATION', 'OTHER'
    ],
    'library_source': [
        'GENOMIC', 'TRANSCRIPTOMIC', 'METAGENOMIC', 'METATRANSCRIPTOMIC', 
        'SYNTHETIC', 'VIRAL RNA', 'GENOMIC SINGLE CELL', 'TRANSCRIPTOMIC SINGLE CELL', 'OTHER'
    ],
    'library_selection': [
        'RANDOM', 'PCR', 'RANDOM PCR', 'RT-PCR', 'HMPR', 'MF', 'CF-S', 'CF-M', 
        'CF-H', 'CF-T', 'MDA', 'MSLL', 'cDNA', 'ChIP', 'MNase', 'DNAse', 
        'Hybrid Selection', 'Reduced Representation', 'Restriction Digest', 
        '5-methylcytidine antibody', 'MBD2 protein methyl-CpG binding domain', 
        'CAGE', 'RACE', 'size fractionation', 'Padlock probes capture method', 
        'other', 'unspecified', 'cDNA_oligo_dT', 'cDNA_randomPriming', 
        'Inverse rRNA', 'Oligo-dT', 'PolyA', 'repeat fractionation'
    ],
    'library_layout': ['paired', 'single'],
    'platform': [
        'ABI_SOLID', 'BGISEQ', 'CAPILLARY', 'COMPLETE_GENOMICS', 'DNBSEQ', 
        'ELEMENT', 'GENAPSYS', 'GENEMIND', 'HELICOS', 'ILLUMINA', 'ION_TORRENT', 
        'OXFORD_NANOPORE', 'PACBIO_SMRT', 'TAPESTRI', 'ULTIMA', 'VELA_DIAGNOSTICS'
    ],
    'filetype': [
        'fastq', 'bam', 'srf', 'sff', 'PacBio_HDF5', 'CompleteGenomics_native', 
        'OxfordNanopore_native'
    ]
}

# Add common instrument models (this would be replaced with a complete list from xlsx)
VALID_OPTIONS['instrument_model'] = [
    # Illumina
    'Illumina NovaSeq X', 'Illumina NovaSeq 6000', 'Illumina HiSeq X', 'Illumina HiSeq 2500',
    'Illumina HiSeq 2000', 'Illumina HiSeq 1500', 'Illumina HiSeq 1000', 'Illumina MiSeq',
    'Illumina MiniSeq', 'Illumina NextSeq 500', 'Illumina NextSeq 550', 'Illumina NextSeq 1000',
    'Illumina NextSeq 2000', 'Illumina iSeq 100',
    # Oxford Nanopore
    'MinION', 'GridION', 'PromethION',
    # PacBio
    'PacBio RS', 'PacBio RS II', 'PacBio Sequel', 'PacBio Sequel II', 'PacBio Revio',
    # Ion Torrent
    'Ion Torrent PGM', 'Ion Torrent S5', 'Ion Torrent S5 XL', 'Ion Torrent Genexus',
    # Others
    'unspecified'
]

# Define default values for required fields
DEFAULT_VALUES = {
    # Bioproject metadata defaults
    'organism': 'Homo sapiens',
    'geo_loc_name': 'United States: Ohio: Cincinnati',
    'lat_lon': '39.10 N 84.51 W',
    
    # Sample metadata defaults
    'title': 'metagenomics project',
    'library_strategy': 'WGS',
    'library_source': 'METAGENOMIC',
    'library_selection': 'RANDOM',
    'library_layout': 'paired',
    'platform': 'ILLUMINA',
    'instrument_model': 'Illumina NovaSeq X',
    'filetype': 'fastq'
}

def load_custom_defaults(config_file=None):
    """
    Load custom default values from a configuration file.
    
    Args:
        config_file (str): Path to the configuration file
        
    Returns:
        dict: Custom default values merged with system defaults
    """
    defaults = DEFAULT_VALUES.copy()
    
    if config_file and os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                if 'default_values' in config:
                    defaults.update(config['default_values'])
                    logger.info(f"Loaded custom defaults from {config_file}")
        except Exception as e:
            logger.warning(f"Failed to load custom defaults from {config_file}: {str(e)}")
    
    return defaults

def validate_lat_lon(lat_lon):
    """
    Validate latitude/longitude format.
    
    Args:
        lat_lon (str): Latitude and longitude string
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Pattern: XX.XX N|S XX.XX E|W where X is a number
    pattern = r'^(-?\d+(\.\d+)?\s+[NS])\s+(-?\d+(\.\d+)?\s+[EW])$'
    return bool(re.match(pattern, lat_lon))

def validate_geo_loc_name(geo_loc_name):
    """
    Validate geo_loc_name format (Country: secondary identifier(s)).
    
    Args:
        geo_loc_name (str): Geographic location string
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Pattern: Country: secondary identifiers
    pattern = r'^[A-Za-z\s]+:\s+[A-Za-z0-9\s:]+$'
    return bool(re.match(pattern, geo_loc_name))

def validate_collection_date(date_str):
    """
    Validate collection date format (YYYY-MM-DD).
    
    Args:
        date_str (str): Date string
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Pattern: YYYY-MM-DD or YYYY/MM/DD or MM/DD/YYYY
    patterns = [
        r'^\d{4}-\d{2}-\d{2}$',  # YYYY-MM-DD
        r'^\d{4}/\d{2}/\d{2}$',  # YYYY/MM/DD
        r'^\d{1,2}/\d{1,2}/\d{4}$'  # MM/DD/YYYY
    ]
    
    return any(bool(re.match(pattern, date_str)) for pattern in patterns)

def validate_bioproject_metadata(df, defaults=None):
    """
    Validate the bioproject metadata file.
    
    Args:
        df (pd.DataFrame): Bioproject metadata dataframe
        defaults (dict): Default values for missing fields
        
    Returns:
        tuple: (validated_df, list_of_issues)
    """
    if defaults is None:
        defaults = DEFAULT_VALUES
    
    issues = []
    
    # Check for required columns
    required_columns = ['sample_name', 'organism', 'collection_date', 'geo_loc_name', 'lat_lon']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        issues.append(f"Missing required columns: {', '.join(missing_columns)}")
        # Add missing columns with default values
        for col in missing_columns:
            if col in defaults:
                df[col] = defaults[col]
            else:
                df[col] = ""
    
    # Add file_number column (1 to n)
    df['file_number'] = range(1, len(df) + 1)
    
    # Check for unique sample names
    if not df['sample_name'].is_unique:
        duplicate_samples = df[df.duplicated(subset=['sample_name'])]['sample_name'].tolist()
        issues.append(f"Duplicate sample names found: {', '.join(duplicate_samples)}")
    
    # Validate format of specific fields
    for idx, row in df.iterrows():
        # Check collection_date format
        if pd.notna(row.get('collection_date')) and not validate_collection_date(str(row['collection_date'])):
            issues.append(f"Invalid collection date format for sample {row['sample_name']}: {row['collection_date']}")
        
        # Check geo_loc_name format
        if pd.notna(row.get('geo_loc_name')) and not validate_geo_loc_name(str(row['geo_loc_name'])):
            issues.append(f"Invalid geo_loc_name format for sample {row['sample_name']}: {row['geo_loc_name']}")
        
        # Check lat_lon format
        if pd.notna(row.get('lat_lon')) and not validate_lat_lon(str(row['lat_lon'])):
            issues.append(f"Invalid lat_lon format for sample {row['sample_name']}: {row['lat_lon']}")
    
    # Apply defaults for any empty required cells
    for col in required_columns:
        if col in df.columns:
            mask = df[col].isnull() | (df[col] == "")
            if mask.any() and col in defaults:
                df.loc[mask, col] = defaults[col]
                issues.append(f"Applied default value '{defaults[col]}' to {mask.sum()} empty cells in column '{col}'")
    
    return df, issues

def validate_sample_metadata(df, bioproject_df=None, defaults=None):
    """
    Validate the sample metadata file.
    
    Args:
        df (pd.DataFrame): Sample metadata dataframe
        bioproject_df (pd.DataFrame): Bioproject metadata for cross-validation
        defaults (dict): Default values for missing fields
        
    Returns:
        tuple: (validated_df, list_of_issues)
    """
    if defaults is None:
        defaults = DEFAULT_VALUES
    
    issues = []
    
    # Check for required columns
    required_columns = [
        'sample_name', 'library_ID', 'title', 'library_strategy', 
        'library_source', 'library_selection', 'library_layout', 
        'platform', 'instrument_model', 'filetype', 'filename'
    ]
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        issues.append(f"Missing required columns: {', '.join(missing_columns)}")
        # Add missing columns with default values
        for col in missing_columns:
            if col in defaults:
                df[col] = defaults[col]
            else:
                df[col] = ""
    
    # Check for unique sample names
    if not df['sample_name'].is_unique:
        duplicate_samples = df[df.duplicated(subset=['sample_name'])]['sample_name'].tolist()
        issues.append(f"Duplicate sample names found: {', '.join(duplicate_samples)}")
    
    # Cross-validate with bioproject metadata if provided
    if bioproject_df is not None:
        bioproject_samples = set(bioproject_df['sample_name'].tolist())
        sample_metadata_samples = set(df['sample_name'].tolist())
        
        # Check for samples in sample metadata but not in bioproject
        missing_in_bioproject = sample_metadata_samples - bioproject_samples
        if missing_in_bioproject:
            issues.append(f"Samples in sample metadata but missing in bioproject: {', '.join(missing_in_bioproject)}")
        
        # Check for samples in bioproject but not in sample metadata
        missing_in_sample_metadata = bioproject_samples - sample_metadata_samples
        if missing_in_sample_metadata:
            issues.append(f"Samples in bioproject but missing in sample metadata: {', '.join(missing_in_sample_metadata)}")
    
    # Validate values for constrained fields
    for idx, row in df.iterrows():
        # Set library_ID to sample_name if empty
        if pd.isna(row.get('library_ID')) or row.get('library_ID') == "":
            df.at[idx, 'library_ID'] = row['sample_name']
        
        # Check constrained fields
        for field, valid_options in VALID_OPTIONS.items():
            if field in df.columns and pd.notna(row.get(field)):
                if row[field] not in valid_options:
                    issues.append(f"Invalid {field} value '{row[field]}' for sample {row['sample_name']}")
                    # Set to default value if invalid
                    if field in defaults:
                        df.at[idx, field] = defaults[field]
                        issues.append(f"Set {field} to default value '{defaults[field]}' for sample {row['sample_name']}")
        
        # Check if filename2 is required but missing
        if row.get('library_layout') == 'paired' and (
            'filename2' not in df.columns or 
            pd.isna(row.get('filename2')) or 
            row.get('filename2') == ""
        ):
            issues.append(f"Missing filename2 for paired-end sample {row['sample_name']}")
    
    # Apply defaults for any empty required cells
    for col in required_columns:
        if col in df.columns:
            mask = df[col].isnull() | (df[col] == "")
            if mask.any() and col in defaults:
                df.loc[mask, col] = defaults[col]
                issues.append(f"Applied default value '{defaults[col]}' to {mask.sum()} empty cells in column '{col}'")
    
    return df, issues

def validate_and_fix_metadata(bioproject_file, sample_file, config_file=None, output_dir=None):
    """
    Validate and fix bioproject and sample metadata files.
    
    Args:
        bioproject_file (str): Path to bioproject metadata file
        sample_file (str): Path to sample metadata file
        config_file (str): Path to configuration file with defaults
        output_dir (str): Directory to save validated files
        
    Returns:
        tuple: (bioproject_df, sample_df, list_of_issues)
    """
    # Load custom defaults
    defaults = load_custom_defaults(config_file)
    issues = []
    
    # Load bioproject metadata
    try:
        if bioproject_file.endswith('.csv'):
            bioproject_df = pd.read_csv(bioproject_file)
        elif bioproject_file.endswith(('.xls', '.xlsx')):
            bioproject_df = pd.read_excel(bioproject_file)
        else:
            raise ValueError(f"Unsupported bioproject file format: {bioproject_file}")
    except Exception as e:
        issues.append(f"Failed to load bioproject metadata file: {str(e)}")
        bioproject_df = pd.DataFrame()
    
    # Load sample metadata
    try:
        if sample_file.endswith('.csv'):
            sample_df = pd.read_csv(sample_file)
        elif sample_file.endswith(('.xls', '.xlsx')):
            sample_df = pd.read_excel(sample_file)
        else:
            raise ValueError(f"Unsupported sample file format: {sample_file}")
    except Exception as e:
        issues.append(f"Failed to load sample metadata file: {str(e)}")
        sample_df = pd.DataFrame()
    
    # Remove rows with no sample_name in either file
    if not bioproject_df.empty and 'sample_name' in bioproject_df.columns:
        empty_samples = bioproject_df['sample_name'].isnull() | (bioproject_df['sample_name'] == "")
        if empty_samples.any():
            issues.append(f"Removed {empty_samples.sum()} rows with empty sample_name from bioproject metadata")
            bioproject_df = bioproject_df[~empty_samples].reset_index(drop=True)
    
    if not sample_df.empty and 'sample_name' in sample_df.columns:
        empty_samples = sample_df['sample_name'].isnull() | (sample_df['sample_name'] == "")
        if empty_samples.any():
            issues.append(f"Removed {empty_samples.sum()} rows with empty sample_name from sample metadata")
            sample_df = sample_df[~empty_samples].reset_index(drop=True)
    
    # Validate and fix bioproject metadata
    if not bioproject_df.empty:
        bioproject_df, bioproject_issues = validate_bioproject_metadata(bioproject_df, defaults)
        issues.extend(bioproject_issues)
    
    # Validate and fix sample metadata
    if not sample_df.empty:
        sample_df, sample_issues = validate_sample_metadata(sample_df, bioproject_df, defaults)
        issues.extend(sample_issues)
    
    # Save validated files if requested
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
        if not bioproject_df.empty:
            output_bioproject = os.path.join(output_dir, "validated_bioproject.csv")
            bioproject_df.to_csv(output_bioproject, index=False)
            issues.append(f"Saved validated bioproject metadata to {output_bioproject}")
        
        if not sample_df.empty:
            output_sample = os.path.join(output_dir, "validated_sample.csv")
            sample_df.to_csv(output_sample, index=False)
            issues.append(f"Saved validated sample metadata to {output_sample}")
    
    return bioproject_df, sample_df, issues

def load_instrument_models_from_excel(excel_file):
    """
    Load instrument model options from an Excel file.
    
    Args:
        excel_file (str): Path to Excel file with instrument models
        
    Returns:
        list: List of valid instrument model options
    """
    try:
        df = pd.read_excel(excel_file)
        
        # Assuming the Excel has a column named 'instrument_model'
        if 'instrument_model' in df.columns:
            models = df['instrument_model'].dropna().tolist()
            return models
        else:
            # Try to guess the column - take the first column that has 'instrument' or 'model' in the name
            for col in df.columns:
                if 'instrument' in col.lower() or 'model' in col.lower():
                    models = df[col].dropna().tolist()
                    return models
            
            # If still not found, just take the first column
            models = df.iloc[:, 0].dropna().tolist()
            return models
    except Exception as e:
        logger.warning(f"Failed to load instrument models from Excel: {str(e)}")
        return VALID_OPTIONS['instrument_model']  # Return the default list
