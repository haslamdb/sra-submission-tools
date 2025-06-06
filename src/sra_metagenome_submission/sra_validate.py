#!/usr/bin/env python3
"""
SRA Metadata Validation Script

This script validates metadata files for SRA submission, fixing common format issues
and ensuring compliance with SRA requirements.
"""

import os
import sys
import json
import argparse
import pandas as pd
import logging
import re
from pathlib import Path
from datetime import datetime

# Set up logging
def setup_logging(validation_name=None):
    """Set up logging with a timestamped filename and optional validation name."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if validation_name:
        log_filename = f"sra_validation_{validation_name}_{timestamp}.log"
    else:
        log_filename = f"sra_validation_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info(f"Logging to {log_filename}")
    return logger

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

# Add common instrument models
VALID_OPTIONS['instrument_model'] = [
    # Illumina
    'Illumina NovaSeq X', 'Illumina NovaSeq 6000', 'Illumina HiSeq X', 'Illumina HiSeq 2500',
    'Illumina HiSeq 2000', 'Illumina HiSeq 1500', 'Illumina HiSeq 1000', 'Illumina MiSeq',
    'Illumina MiniSeq', 'Illumina NextSeq 500', 'Illumina NextSeq 550', 'Illumina NextSeq 1000',
    'Illumina NextSeq 2000', 'Illumina iSeq 100', 'NextSeq 500', 'NextSeq 500',
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
    'collection_date': 'not collected',  # Default for collection_date
    
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

def validate_date_format(date_str):
    """
    Validate and convert date to ISO 8601 format.
    
    Supported formats:
    - "DD-Mmm-YYYY" (e.g., 30-Oct-1990)
    - "Mmm-YYYY" (e.g., Oct-1990)
    - "YYYY" (e.g., 1990)
    - ISO 8601: "YYYY-mm-dd" (e.g., 1990-10-30)
    - ISO 8601: "YYYY-mm" (e.g., 1990-10)
    - Range: "DD-Mmm-YYYY/DD-Mmm-YYYY" (e.g., 21-Oct-1952/15-Feb-1953)
    - With time: "YYYY-mm-ddThh:mm:ssZ" (e.g., 2015-10-11T17:53:03Z)
    - MM/DD/YYYY or DD/MM/YYYY: (e.g., 7/24/2017 or 24/7/2017)
    
    Returns:
        str: Validated date in ISO 8601 format
    """
    if not date_str or pd.isna(date_str) or str(date_str).strip() == "":
        return ""
    
    if date_str == "not collected" or date_str == "not provided" or date_str == "unknown":
        return date_str 
    
    # Special case handling for "not collected" and similar values
    if str(date_str).strip().lower() in ["not collected", "not provided", "unknown"]:
        return str(date_str).strip()
    
    # Convert to string and strip whitespace
    date_str = str(date_str).strip()
    
    # Log the input date for debugging
    logger.debug(f"Validating date format: '{date_str}'")
    
    # ISO 8601 with time (already correct format)
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$', date_str):
        return date_str
    
    # ISO 8601 date (already correct format)
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    
    # ISO 8601 year-month (already correct format)
    if re.match(r'^\d{4}-\d{2}$', date_str):
        return date_str
    
    # Year only
    if re.match(r'^\d{4}$', date_str):
        return date_str
    
    # Date range with slash
    if '/' in date_str and not re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', date_str):
        dates = date_str.split('/')
        if len(dates) == 2:
            start_date = validate_date_format(dates[0])
            end_date = validate_date_format(dates[1])
            if start_date and end_date:
                return f"{start_date}/{end_date}"
    
    # MM/DD/YYYY or DD/MM/YYYY format - common US date format
    mdy_or_dmy = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str)
    if mdy_or_dmy:
        d1, d2, year = mdy_or_dmy.groups()
        
        try:
            # Convert to integers for comparison
            d1_int = int(d1)
            d2_int = int(d2)
            
            # Assume MM/DD/YYYY for US format
            # But if d1 > 12, it's probably DD/MM/YYYY
            if d1_int > 12:
                day, month = d1, d2
            else:
                month, day = d1, d2
            
            # Ensure values are in valid ranges
            month_int = int(month)
            day_int = int(day)
            
            if month_int < 1 or month_int > 12:
                logger.warning(f"Invalid month value {month_int} in date {date_str}")
                month = "01"  # Default to January if invalid
            
            if day_int < 1 or day_int > 31:
                logger.warning(f"Invalid day value {day_int} in date {date_str}")
                day = "01"  # Default to 1st if invalid
            
            # Ensure two digits
            month = month.zfill(2)
            day = day.zfill(2)
            
            # Return in ISO format
            return f"{year}-{month}-{day}"
        except ValueError as e:
            logger.warning(f"Error converting date parts to integers: {e}")
            # Try to recover with defaults
            return f"{year}-01-01"
    
    # DD-Mmm-YYYY format
    dd_mmm_yyyy = re.match(r'^(\d{1,2})[-/\s]([A-Za-z]{3})[-/\s](\d{4})$', date_str)
    if dd_mmm_yyyy:
        day, month, year = dd_mmm_yyyy.groups()
        
        # Convert month abbreviation to month number
        month_abbr = month.capitalize()
        month_dict = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        
        if month_abbr in month_dict:
            month_num = month_dict[month_abbr]
            day = day.zfill(2)  # Ensure two-digit day
            return f"{year}-{month_num}-{day}"
    
    # Mmm-YYYY format
    mmm_yyyy = re.match(r'^([A-Za-z]{3})[-/\s](\d{4})$', date_str)
    if mmm_yyyy:
        month, year = mmm_yyyy.groups()
        
        # Convert month abbreviation to month number
        month_abbr = month.capitalize()
        month_dict = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        
        if month_abbr in month_dict:
            month_num = month_dict[month_abbr]
            return f"{year}-{month_num}"
    
    # YYYY/MM/DD format
    ymd = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$', date_str)
    if ymd:
        year, month, day = ymd.groups()
        
        # Ensure two digits
        month = month.zfill(2)
        day = day.zfill(2)
        
        return f"{year}-{month}-{day}"
    
    # If we can't recognize the format, return as is with a warning
    logger.warning(f"Unrecognized date format: {date_str}")
    return date_str

def validate_geo_loc_name(geo_loc):
    """
    Validate geographic location name.
    Format should be "Country:Region" (e.g., "USA:California").
    
    Returns:
        str: Validated geo_loc_name
    """
    if not geo_loc or pd.isna(geo_loc) or str(geo_loc).strip() == "":
        return ""
    
    geo_loc = str(geo_loc).strip()
    
    # Check if format is already Country:Region
    if re.match(r'^[A-Za-z\s]+:[A-Za-z\s]+$', geo_loc):
        return geo_loc
    
    # If only country is provided, add empty region
    if re.match(r'^[A-Za-z\s]+$', geo_loc) and ":" not in geo_loc:
        return f"{geo_loc}:"
    
    return geo_loc

def validate_lat_lon(lat_lon):
    """
    Validate latitude and longitude format.
    Formats can be:
    - "DD.DDDD N DD.DDDD W" (e.g., "36.9513 N 122.0733 W")
    - "DD.DDDD, DD.DDDD" (e.g., "36.9513, -122.0733")
    
    Returns:
        str: Validated lat_lon
    """
    if not lat_lon or pd.isna(lat_lon) or str(lat_lon).strip() == "":
        return ""
    
    lat_lon = str(lat_lon).strip()
    
    # Check if already in format "DD.DDDD N DD.DDDD W"
    if re.match(r'^\d+\.\d+ [NS] \d+\.\d+ [EW]$', lat_lon):
        return lat_lon
    
    # Check if in decimal format "DD.DDDD, DD.DDDD"
    decimal_format = re.match(r'^([-]?\d+\.\d+)[,\s]+([-]?\d+\.\d+)$', lat_lon)
    if decimal_format:
        lat, lon = decimal_format.groups()
        lat_float = float(lat)
        lon_float = float(lon)
        
        # Convert to DD.DDDD N DD.DDDD W format
        lat_dir = "N" if lat_float >= 0 else "S"
        lon_dir = "E" if lon_float >= 0 else "W"
        
        # Remove negative sign if present
        lat_abs = abs(lat_float)
        lon_abs = abs(lon_float)
        
        return f"{lat_abs} {lat_dir} {lon_abs} {lon_dir}"
    
    return lat_lon

def check_duplicate_sample_names(df, df_type="metadata"):
    """
    Check for duplicate sample names in the dataframe.
    
    Args:
        df (pd.DataFrame): DataFrame to check for duplicates
        df_type (str): Type of metadata for logging purposes
    
    Returns:
        list: List of duplicate sample names with details
    """
    if 'sample_name' not in df.columns:
        logger.warning(f"No sample_name column found in {df_type} dataframe")
        return []
    
    # Count occurrences of each sample name
    sample_counts = df['sample_name'].value_counts()
    
    # Get duplicate sample names (count > 1)
    duplicates = sample_counts[sample_counts > 1].index.tolist()
    
    if duplicates:
        duplicate_details = []
        for dup in duplicates:
            duplicate_rows = df[df['sample_name'] == dup].index.tolist()
            duplicate_details.append({
                'name': dup,
                'count': sample_counts[dup],
                'rows': duplicate_rows
            })
        
        logger.warning(f"Found {len(duplicates)} duplicate sample names in {df_type}: {', '.join(duplicates)}")
        return duplicate_details
    
    return []

def check_column_alignment(df):
    """
    Check for data alignment issues in the dataframe.
    
    Args:
        df (pd.DataFrame): DataFrame to check for alignment issues
    
    Returns:
        dict: Dictionary with alignment issues
    """
    alignment_issues = {
        'extra_data': [],
        'missing_data': []
    }
    
    if 'sample_name' not in df.columns or df.empty:
        return alignment_issues
    
    # Find rows with valid sample names
    valid_sample_rows = df['sample_name'].notna() & (df['sample_name'].astype(str) != '')
    
    if not valid_sample_rows.any():
        return alignment_issues
    
    # Get the last row index with a valid sample name
    last_sample_idx = valid_sample_rows.to_numpy().nonzero()[0][-1]
    
    # Check for data in other columns extending beyond the last sample name
    for col in df.columns:
        if col == 'sample_name':
            continue
            
        # Check for extra data beyond the last sample
        if last_sample_idx + 1 < len(df):
            tail_data = df.loc[last_sample_idx+1:, col]
            valid_tail_data = tail_data.notna() & (tail_data.astype(str) != '')
            
            if valid_tail_data.any():
                extra_rows = valid_tail_data.to_numpy().nonzero()[0] + last_sample_idx + 1
                alignment_issues['extra_data'].append({
                    'column': col,
                    'rows': extra_rows.tolist()
                })
        
        # Check for missing data before the last sample
        for i in range(last_sample_idx + 1):
            if valid_sample_rows[i] and (pd.isna(df.loc[i, col]) or df.loc[i, col] == ''):
                if 'missing_rows' not in alignment_issues:
                    alignment_issues['missing_rows'] = {}
                
                if col not in alignment_issues['missing_rows']:
                    alignment_issues['missing_rows'][col] = []
                
                alignment_issues['missing_rows'][col].append(i)
    
    return alignment_issues

def check_files_exist(df, base_dir=None):
    """
    Check if all files mentioned in the metadata exist in their expected locations.
    
    Args:
        df (pd.DataFrame): Metadata dataframe
        base_dir (str, optional): Base directory for relative file paths
    
    Returns:
        tuple: (all_exist_flag, list_of_missing_files, dict_of_missing_files_by_sample)
    """
    missing_files = []
    missing_by_sample = {}
    
    # Define possible filename columns to check
    filename_columns = ['filename', 'filename2', 'filepath', 'filepath2', 'file1', 'file2']
    
    # Filter to columns that actually exist in the dataframe
    existing_columns = [col for col in filename_columns if col in df.columns]
    
    if not existing_columns:
        logger.warning("No filename columns found in metadata")
        return True, [], {}
    
    # Check each file referenced in the metadata
    for idx, row in df.iterrows():
        try:
            sample_name = row.get('sample_name', f"Row_{idx}")
            sample_missing_files = []
            
            for col in existing_columns:
                # Skip if column value is missing or empty
                if pd.isna(row.get(col)) or str(row.get(col, "")).strip() == "":
                    continue
                    
                filename = str(row[col]).strip()
                
                # Handle both absolute and relative paths
                if os.path.isabs(filename):
                    file_path = filename
                elif base_dir:
                    file_path = os.path.join(base_dir, filename)
                else:
                    file_path = filename
                
                # Check if file exists
                if not os.path.exists(file_path):
                    missing_files.append(file_path)
                    sample_missing_files.append({"column": col, "file": file_path})
            
            if sample_missing_files:
                missing_by_sample[sample_name] = sample_missing_files
        except Exception as e:
            logger.error(f"Error checking files for row {idx}: {str(e)}")
            # Continue checking other rows
            continue
    
    all_exist = len(missing_files) == 0
    
    if not all_exist:
        logger.warning(f"Found {len(missing_files)} files mentioned in metadata that don't exist")
    else:
        logger.info("All files mentioned in metadata exist")
    
    return all_exist, missing_files, missing_by_sample

def remove_samples_with_missing_files(sample_df, bioproject_df, missing_by_sample):
    """
    Remove samples with missing files from both sample and bioproject metadata.
    
    Args:
        sample_df (pd.DataFrame): Sample metadata dataframe
        bioproject_df (pd.DataFrame): Bioproject metadata dataframe
        missing_by_sample (dict): Dictionary of missing files by sample name
    
    Returns:
        tuple: (updated_sample_df, updated_bioproject_df, list_of_removed_samples)
    """
    samples_to_remove = list(missing_by_sample.keys())
    
    if not samples_to_remove:
        return sample_df, bioproject_df, []
    
    # Create copies to avoid modifying the originals
    updated_sample_df = sample_df.copy()
    updated_bioproject_df = None if bioproject_df is None else bioproject_df.copy()
    
    try:
        # Remove samples from sample metadata
        if 'sample_name' in updated_sample_df.columns:
            before_count = len(updated_sample_df)
            updated_sample_df = updated_sample_df[~updated_sample_df['sample_name'].isin(samples_to_remove)]
            after_count = len(updated_sample_df)
            logger.info(f"Removed {before_count - after_count} rows from sample metadata")
            
            # Reset index to avoid indexing issues
            updated_sample_df = updated_sample_df.reset_index(drop=True)
            
        # Remove samples from bioproject metadata if it exists
        if updated_bioproject_df is not None and 'sample_name' in updated_bioproject_df.columns:
            before_count = len(updated_bioproject_df)
            updated_bioproject_df = updated_bioproject_df[~updated_bioproject_df['sample_name'].isin(samples_to_remove)]
            after_count = len(updated_bioproject_df)
            logger.info(f"Removed {before_count - after_count} rows from bioproject metadata")
            
            # Reset index to avoid indexing issues
            updated_bioproject_df = updated_bioproject_df.reset_index(drop=True)
        
        # Check that we have at least one sample remaining
        if len(updated_sample_df) == 0:
            logger.warning("All samples were removed due to missing files!")
            print("\nWARNING: All samples were removed due to missing files!")
            print("Please check your metadata and file paths.")
        
        logger.info(f"Removed {len(samples_to_remove)} samples with missing files from metadata")
        return updated_sample_df, updated_bioproject_df, samples_to_remove
        
    except Exception as e:
        logger.error(f"Error removing samples with missing files: {str(e)}")
        logger.error(f"Samples that should be removed: {samples_to_remove}")
        import traceback
        logger.error(traceback.format_exc())
        # Return original dataframes to avoid further errors
        return sample_df, bioproject_df, []

def compare_filenames_between_metadata(sample_df, bioproject_df):
    """
    Compare filenames between sample and bioproject metadata files.
    
    Args:
        sample_df (pd.DataFrame): Sample metadata dataframe
        bioproject_df (pd.DataFrame): Bioproject metadata dataframe
    
    Returns:
        dict: Dictionary with filename consistency issues
    """
    if sample_df is None or bioproject_df is None:
        return {}
    
    filename_issues = {
        'mismatches': [],
        'missing_columns': []
    }
    
    # Check if both dataframes have sample_name column
    if 'sample_name' not in sample_df.columns or 'sample_name' not in bioproject_df.columns:
        filename_issues['missing_columns'].append("One or both metadata files are missing 'sample_name' column")
        return filename_issues
    
    # Define possible filename columns to check
    filename_columns = ['filename', 'filename2', 'filepath', 'filepath2', 'file1', 'file2']
    
    # Identify which filename columns exist in each dataframe
    sample_file_columns = [col for col in filename_columns if col in sample_df.columns]
    bioproject_file_columns = [col for col in filename_columns if col in bioproject_df.columns]
    
    # Check if either dataframe is missing filename columns
    if not sample_file_columns:
        filename_issues['missing_columns'].append("Sample metadata is missing filename columns")
    
    if not bioproject_file_columns:
        filename_issues['missing_columns'].append("Bioproject metadata is missing filename columns")
    
    # If both have filename columns, check for consistency
    if sample_file_columns and bioproject_file_columns:
        # Get common samples between both dataframes
        common_samples = set(sample_df['sample_name']) & set(bioproject_df['sample_name'])
        
        for sample in common_samples:
            sample_row = sample_df[sample_df['sample_name'] == sample].iloc[0]
            bioproject_row = bioproject_df[bioproject_df['sample_name'] == sample].iloc[0]
            
            for sample_col in sample_file_columns:
                # Find the equivalent column in bioproject
                equivalent_cols = [col for col in bioproject_file_columns if col == sample_col]
                
                if not equivalent_cols:
                    continue
                
                bioproject_col = equivalent_cols[0]
                
                # Compare filenames
                sample_filename = str(sample_row.get(sample_col, "")).strip()
                bioproject_filename = str(bioproject_row.get(bioproject_col, "")).strip()
                
                # If both have values and they don't match
                if (sample_filename and bioproject_filename and 
                    sample_filename != bioproject_filename):
                    
                    # Check if the difference is just the path
                    sample_basename = os.path.basename(sample_filename)
                    bioproject_basename = os.path.basename(bioproject_filename)
                    
                    if sample_basename != bioproject_basename:
                        filename_issues['mismatches'].append({
                            'sample': sample,
                            'sample_column': sample_col,
                            'bioproject_column': bioproject_col,
                            'sample_filename': sample_filename,
                            'bioproject_filename': bioproject_filename
                        })
    
    return filename_issues

def validate_sample_metadata(df, config=None):
    """
    Validate sample metadata and fix common issues.
    
    Args:
        df (pd.DataFrame): Sample metadata dataframe
        config (dict, optional): Configuration with default values
    
    Returns:
        pd.DataFrame: Validated sample metadata
    """
    # Make a copy to avoid modifying the original
    validated_df = df.copy()
    
    # Load defaults from config if available
    default_values = {}
    if config and 'default_values' in config:
        default_values = config['default_values']
    else:
        default_values = DEFAULT_VALUES
    
    # Check for duplicate sample names
    duplicates = check_duplicate_sample_names(validated_df, "sample metadata")
    if duplicates:
        for dup in duplicates:
            logger.warning(f"Duplicate sample name '{dup['name']}' found {dup['count']} times at rows: {dup['rows']}")
            print(f"\nWARNING: Duplicate sample name '{dup['name']}' found {dup['count']} times at rows: {dup['rows']}")
            print("Please fix duplicate sample names to ensure proper SRA submission.")
    
    # Check for column alignment issues
    alignment_issues = check_column_alignment(validated_df)
    
    if alignment_issues['extra_data']:
        for issue in alignment_issues['extra_data']:
            logger.warning(f"Column '{issue['column']}' has data beyond the last valid sample_name at rows: {issue['rows']}")
            print(f"\nWARNING: Column '{issue['column']}' has data beyond the last valid sample_name at rows: {issue['rows']}")
            print("This extra data will be ignored during submission.")
    
    if 'missing_rows' in alignment_issues:
        for col, rows in alignment_issues['missing_rows'].items():
            if rows:
                logger.warning(f"Column '{col}' is missing data for {len(rows)} sample rows.")
                print(f"\nWARNING: Column '{col}' is missing data for {len(rows)} sample rows.")
                if col in default_values:
                    print(f"Missing values will be filled with default: '{default_values.get(col, '')}'")
    
    # Fill missing required fields with defaults
    required_fields = [
        'library_strategy', 'library_source', 'library_selection',
        'platform', 'instrument_model'
    ]
    
    for field in required_fields:
        if field in validated_df.columns:
            mask = validated_df[field].isnull() | (validated_df[field].astype(str) == '')
            if mask.any() and field in default_values:
                validated_df.loc[mask, field] = default_values[field]
                logger.info(f"Applied default value '{default_values[field]}' to {mask.sum()} empty cells in '{field}'")
    
    # Ensure required columns exist
    essential_columns = [
        'sample_name', 'library_ID', 'title', 'library_strategy',
        'library_source', 'library_selection', 'library_layout',
        'platform', 'instrument_model', 'design_description',
        'filetype', 'filename'
    ]
    
    for col in essential_columns:
        if col not in validated_df.columns:
            if col in default_values:
                validated_df[col] = default_values[col]
            else:
                validated_df[col] = ""
    
    # Validate library_layout (must be "single" or "paired")
    if 'library_layout' in validated_df.columns:
        # Convert to lowercase and fix any variations
        validated_df['library_layout'] = validated_df['library_layout'].apply(
            lambda x: 'paired' if str(x).lower().strip() in ['paired', 'pair', 'pe'] 
            else 'single' if str(x).lower().strip() in ['single', 'se'] 
            else x
        )
    
    # Validate constrained fields against valid options
    for field, valid_options in VALID_OPTIONS.items():
        if field in validated_df.columns:
            for idx, value in enumerate(validated_df[field]):
                if pd.notna(value) and value != "" and value not in valid_options:
                    logger.warning(f"Invalid {field} value: '{value}'. Will use default if available.")
                    if field in default_values:
                        validated_df.at[idx, field] = default_values[field]
    
    # Validate filenames - ensure they exist and match sample names
    if 'filename' in validated_df.columns and 'filename2' in validated_df.columns:
        # Matching library_layout with filenames
        for idx, row in validated_df.iterrows():
            if row['library_layout'] == 'paired' and (pd.isna(row['filename2']) or row['filename2'] == ''):
                logger.warning(f"Sample {row['sample_name']} is marked as paired but missing second filename")
            if row['library_layout'] == 'single' and not (pd.isna(row['filename2']) or row['filename2'] == ''):
                logger.warning(f"Sample {row['sample_name']} is marked as single but has a second filename")
    
    # Set library_ID to sample_name if empty
    if 'library_ID' in validated_df.columns and 'sample_name' in validated_df.columns:
        mask = validated_df['library_ID'].isnull() | (validated_df['library_ID'] == "")
        if mask.any():
            validated_df.loc[mask, 'library_ID'] = validated_df.loc[mask, 'sample_name']
            logger.info(f"Set library_ID to sample_name for {mask.sum()} samples")
    
    # If we have valid samples, trim the dataframe to only include rows with valid sample names
    if 'sample_name' in validated_df.columns:
        valid_samples = validated_df['sample_name'].notna() & (validated_df['sample_name'].astype(str) != '')
        if valid_samples.any():
            last_valid_idx = valid_samples.to_numpy().nonzero()[0][-1]
            if last_valid_idx + 1 < len(validated_df):
                validated_df = validated_df.iloc[:last_valid_idx + 1].copy()
                logger.info(f"Trimmed dataframe to include only rows with valid sample names (1 to {last_valid_idx + 1})")
    
    return validated_df

def validate_bioproject_metadata(df, config=None):
    """
    Validate bioproject metadata and fix common issues.
    
    Args:
        df (pd.DataFrame): Bioproject metadata dataframe
        config (dict, optional): Configuration with default values
    
    Returns:
        pd.DataFrame: Validated bioproject metadata
    """
    # Make a copy to avoid modifying the original
    validated_df = df.copy()
    
    # Load defaults from config if available
    default_values = {}
    if config and 'default_values' in config:
        default_values = config['default_values']
    else:
        default_values = DEFAULT_VALUES
    
    # Check for duplicate sample names
    duplicates = check_duplicate_sample_names(validated_df, "bioproject metadata")
    if duplicates:
        for dup in duplicates:
            logger.warning(f"Duplicate sample name '{dup['name']}' found {dup['count']} times at rows: {dup['rows']}")
            print(f"\nWARNING: Duplicate sample name '{dup['name']}' found {dup['count']} times at rows: {dup['rows']}")
            print("Please fix duplicate sample names to ensure proper SRA submission.")
    
    # Check for column alignment issues
    alignment_issues = check_column_alignment(validated_df)
    
    if alignment_issues['extra_data']:
        for issue in alignment_issues['extra_data']:
            logger.warning(f"Column '{issue['column']}' has data beyond the last valid sample_name at rows: {issue['rows']}")
            print(f"\nWARNING: Column '{issue['column']}' has data beyond the last valid sample_name at rows: {issue['rows']}")
            print("This extra data will be ignored during submission.")
    
    if 'missing_rows' in alignment_issues:
        for col, rows in alignment_issues['missing_rows'].items():
            if rows:
                logger.warning(f"Column '{col}' is missing data for {len(rows)} sample rows.")
                print(f"\nWARNING: Column '{col}' is missing data for {len(rows)} sample rows.")
                if col in default_values:
                    print(f"Missing values will be filled with default: '{default_values.get(col, '')}'")
    
    # Fill missing required fields with defaults
    required_fields = [
        'library_strategy', 'library_source', 'library_selection',
        'platform', 'instrument_model', 'collection_date' 
    ]
    
    for field in required_fields:
        if field in validated_df.columns:
            mask = validated_df[field].isnull() | (validated_df[field].astype(str) == '')
            if mask.any() and field in default_values:
                validated_df.loc[mask, field] = default_values[field]
                logger.info(f"Applied default value '{default_values[field]}' to {mask.sum()} empty cells in '{field}'")
    
    # Ensure required columns exist
    essential_columns = [
        'bioproject_id', 'project_title', 'project_description', 'sample_source',
        'collection_date', 'geo_loc_name', 'lat_lon', 'library_strategy',
        'library_source', 'library_selection', 'platform', 'instrument_model'
    ]
    
    for col in essential_columns:
        if col not in validated_df.columns:
            if col in default_values:
                validated_df[col] = default_values[col]
            else:
                validated_df[col] = ""
    
    # Validate constrained fields against valid options
    for field, valid_options in VALID_OPTIONS.items():
        if field in validated_df.columns:
            for idx, value in enumerate(validated_df[field]):
                if pd.notna(value) and value != "" and value not in valid_options:
                    logger.warning(f"Invalid {field} value: '{value}'. Will use default if available.")
                    if field in default_values:
                        validated_df.at[idx, field] = default_values[field]
    
    # Enhanced validation for collection_date - ensure it's never empty
    if 'collection_date' in validated_df.columns:
        try:
            # Find empty collection dates
            empty_dates = validated_df['collection_date'].isnull() | (validated_df['collection_date'].astype(str) == '')
            if empty_dates.any():
                empty_count = empty_dates.sum()
                logger.warning(f"Found {empty_count} empty collection_date fields. Filling with default value.")
                print(f"\nWARNING: Found {empty_count} empty collection_date fields.")
                print(f"Filling with default value: '{default_values['collection_date']}'")
                
                # Fill empty dates with default value
                validated_df.loc[empty_dates, 'collection_date'] = default_values['collection_date']
            
            # Validate the format of non-empty dates - apply the function to each row with error handling
            for idx, value in validated_df['collection_date'].items():
                try:
                    if value != default_values['collection_date'] and pd.notna(value) and str(value).strip() != '':
                        validated_df.at[idx, 'collection_date'] = validate_date_format(value)
                except Exception as e:
                    logger.warning(f"Error validating date at row {idx}: '{value}' - {str(e)}")
                    validated_df.at[idx, 'collection_date'] = default_values['collection_date']
        except Exception as e:
            logger.error(f"Error during collection_date validation: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
    # Validate geographic location format
    if 'geo_loc_name' in validated_df.columns:
        validated_df['geo_loc_name'] = validated_df['geo_loc_name'].apply(validate_geo_loc_name)
    
    # Validate latitude/longitude format
    if 'lat_lon' in validated_df.columns:
        validated_df['lat_lon'] = validated_df['lat_lon'].apply(validate_lat_lon)
    
    # Validate sample source (must be "environmental" or "host-associated")
    if 'sample_source' in validated_df.columns:
        validated_df['sample_source'] = validated_df['sample_source'].apply(
            lambda x: 'environmental' if str(x).lower().strip() in ['environmental', 'environment'] 
            else 'host-associated' if str(x).lower().strip() in ['host-associated', 'host', 'host associated'] 
            else x
        )
        
        # Check if host fields are filled for host-associated samples
        for idx, row in validated_df.iterrows():
            if row.get('sample_source') == 'host-associated':
                if 'host' in validated_df.columns and (pd.isna(row['host']) or row['host'] == ''):
                    logger.warning(f"Sample source is host-associated but 'host' field is empty for sample {row.get('sample_name', f'at row {idx}')}")
    
    # Add file_number column if not present
    if 'file_number' not in validated_df.columns:
        validated_df['file_number'] = range(1, len(validated_df) + 1)
    
    # If we have valid samples, trim the dataframe to only include rows with valid sample names
    if 'sample_name' in validated_df.columns:
        valid_samples = validated_df['sample_name'].notna() & (validated_df['sample_name'].astype(str) != '')
        if valid_samples.any():
            last_valid_idx = valid_samples.to_numpy().nonzero()[0][-1]
            if last_valid_idx + 1 < len(validated_df):
                validated_df = validated_df.iloc[:last_valid_idx + 1].copy()
                logger.info(f"Trimmed dataframe to include only rows with valid sample names (1 to {last_valid_idx + 1})")
    
    return validated_df

def load_metadata_file(file_path):
    """
    Load metadata from file (tab-delimited TXT or Excel).
    
    Args:
        file_path (str): Path to metadata file
    
    Returns:
        pd.DataFrame: Loaded metadata
    """
    try:
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.txt':
            # Try to load as tab-delimited
            df = pd.read_csv(file_path, sep='\t')
        elif file_ext in ['.xlsx', '.xls']:
            # Load Excel file
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_ext}. Only tab-delimited .txt or Excel .xlsx/.xls files are supported.")
        
        return df
    except Exception as e:
        logger.error(f"Error loading metadata file {file_path}: {str(e)}")
        raise

def save_metadata_file(df, output_path):
    """
    Save metadata to file in the same format as input.
    
    Args:
        df (pd.DataFrame): Metadata dataframe
        output_path (str): Path to save the file
    """
    try:
        # Create directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"Created output directory: {output_dir}")
        
        file_ext = os.path.splitext(output_path)[1].lower()
        
        if file_ext == '.txt':
            # Save as tab-delimited
            df.to_csv(output_path, sep='\t', index=False)
        elif file_ext in ['.xlsx', '.xls']:
            # Save as Excel
            df.to_excel(output_path, index=False)
        else:
            raise ValueError(f"Unsupported output format: {file_ext}. Use .txt for tab-delimited or .xlsx/.xls for Excel.")
        
        logger.info(f"Saved validated metadata to {output_path}")
    except Exception as e:
        logger.error(f"Error saving metadata file to {output_path}: {str(e)}")
        raise

def load_config(config_file):
    """
    Load configuration from JSON file.
    
    Args:
        config_file (str): Path to configuration file
    
    Returns:
        dict: Configuration data
    """
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        logger.info(f"Loaded configuration from {config_file}")
        return config
    except Exception as e:
        logger.error(f"Error loading configuration file: {str(e)}")
        return {}

def validate_and_fix_metadata(bioproject_file, sample_file, config_file=None, output_dir=None, file_dir=None):
    """
    Validate and fix bioproject and sample metadata files.
    
    Args:
        bioproject_file (str): Path to bioproject metadata file
        sample_file (str): Path to sample metadata file
        config_file (str): Path to configuration file with defaults
        output_dir (str): Directory to save validated files
        file_dir (str): Directory containing the sequence files
        
    Returns:
        tuple: (bioproject_df, sample_df, list_of_issues)
    """
    # Initialize issues list
    issues = []
    
    # Load config if provided
    config = None
    if config_file:
        config = load_config(config_file)
    
    # Load metadata files
    try:
        sample_df = load_metadata_file(sample_file)
        logger.info(f"Loaded sample metadata from {sample_file}")
    except Exception as e:
        issues.append(f"Failed to load sample metadata file: {str(e)}")
        sample_df = pd.DataFrame()
    
    try:
        bioproject_df = load_metadata_file(bioproject_file)
        logger.info(f"Loaded bioproject metadata from {bioproject_file}")
    except Exception as e:
        issues.append(f"Failed to load bioproject metadata file: {str(e)}")
        bioproject_df = pd.DataFrame()
    
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
    
    # MODIFIED: Check if all files mentioned in metadata exist before proceeding with other validations
    if not sample_df.empty and file_dir:
        all_exist, missing_files, missing_by_sample = check_files_exist(sample_df, file_dir)
        
        if not all_exist:
            print("\n" + "="*80)
            print(f"WARNING: Found {len(missing_files)} files referenced in metadata that don't exist")
            print(f"Missing files are associated with {len(missing_by_sample)} samples")
            print("\nMissing files by sample (showing up to 5 per sample):")
            
            for sample_name, files in missing_by_sample.items():
                print(f"\nSample: {sample_name}")
                for i, file_info in enumerate(files[:5]):
                    print(f"  - {file_info['column']}: {file_info['file']}")
                if len(files) > 5:
                    print(f"  - ... and {len(files) - 5} more files")
            
            print("\nOptions:")
            print("1. Stop validation and find the missing files")
            print("2. Remove samples with missing files from both metadata files and continue")
            
            while True:
                try:
                    choice = input("\nEnter your choice (1 or 2): ")
                    if choice == "1":
                        print("\nValidation stopped. Please find the missing files and try again.")
                        logger.info("User chose to stop validation to find missing files")
                        sys.exit(0)
                    elif choice == "2":
                        print("\nRemoving samples with missing files from metadata...")
                        sample_df, bioproject_df, removed_samples = remove_samples_with_missing_files(
                            sample_df, bioproject_df, missing_by_sample
                        )
                        
                        issues.append(f"Removed {len(removed_samples)} samples with missing files from metadata")
                        print(f"Removed {len(removed_samples)} samples from metadata")
                        logger.info(f"Removed samples: {', '.join(removed_samples)}")
                        break
                    else:
                        print("Invalid choice. Please enter 1 or 2.")
                except KeyboardInterrupt:
                    print("\nValidation cancelled by user.")
                    sys.exit(0)
            
            print("="*80 + "\n")
    
    # MODIFIED: Check for filename consistency between sample and bioproject metadata
    if not sample_df.empty and not bioproject_df.empty:
        filename_issues = compare_filenames_between_metadata(sample_df, bioproject_df)
        
        if filename_issues['missing_columns']:
            for issue in filename_issues['missing_columns']:
                issues.append(issue)
                print(f"\nWARNING: {issue}")
        
        if filename_issues['mismatches']:
            print("\n" + "="*80)
            print(f"WARNING: Found {len(filename_issues['mismatches'])} filename mismatches between sample and bioproject metadata")
            print("\nFilename mismatches by sample:")
            
            for mismatch in filename_issues['mismatches']:
                print(f"\nSample: {mismatch['sample']}")
                print(f"  Sample metadata ({mismatch['sample_column']}): {mismatch['sample_filename']}")
                print(f"  Bioproject metadata ({mismatch['bioproject_column']}): {mismatch['bioproject_filename']}")
            
            print("\nTo ensure successful submission, filenames should match exactly between both metadata files.")
            print("Options:")
            print("1. Stop validation and fix the filename mismatches")
            print("2. Continue validation (filenames will not be automatically fixed)")
            
            while True:
                try:
                    choice = input("\nEnter your choice (1 or 2): ")
                    if choice == "1":
                        print("\nValidation stopped. Please fix the filename mismatches and try again.")
                        logger.info("User chose to stop validation to fix filename mismatches")
                        sys.exit(0)
                    elif choice == "2":
                        print("\nContinuing validation without fixing filename mismatches...")
                        issues.append(f"Found {len(filename_issues['mismatches'])} filename mismatches between metadata files")
                        break
                    else:
                        print("Invalid choice. Please enter 1 or 2.")
                except KeyboardInterrupt:
                    print("\nValidation cancelled by user.")
                    sys.exit(0)
            
            print("="*80 + "\n")
    
    # Continue with other validation checks
    # Check for duplicate sample names
    if not bioproject_df.empty and 'sample_name' in bioproject_df.columns:
        duplicates = check_duplicate_sample_names(bioproject_df, "bioproject metadata")
        if duplicates:
            for dup in duplicates:
                issues.append(f"Duplicate sample name '{dup['name']}' found {dup['count']} times at rows: {dup['rows']} in bioproject metadata")
                print(f"\nWARNING: Duplicate sample name '{dup['name']}' found {dup['count']} times at rows: {dup['rows']} in bioproject metadata")
    
    if not sample_df.empty and 'sample_name' in sample_df.columns:
        duplicates = check_duplicate_sample_names(sample_df, "sample metadata")
        if duplicates:
            for dup in duplicates:
                issues.append(f"Duplicate sample name '{dup['name']}' found {dup['count']} times at rows: {dup['rows']} in sample metadata")
                print(f"\nWARNING: Duplicate sample name '{dup['name']}' found {dup['count']} times at rows: {dup['rows']} in sample metadata")
    
    # Cross-validate samples between files
    if not bioproject_df.empty and not sample_df.empty:
        if 'sample_name' in bioproject_df.columns and 'sample_name' in sample_df.columns:
            bioproject_samples = set(bioproject_df['sample_name'].dropna().tolist())
            sample_metadata_samples = set(sample_df['sample_name'].dropna().tolist())
            
            # Check for samples in sample metadata but not in bioproject
            missing_in_bioproject = sample_metadata_samples - bioproject_samples
            if missing_in_bioproject:
                issues.append(f"Samples in sample metadata but missing in bioproject: {', '.join(missing_in_bioproject)}")
                print(f"\nWARNING: Found {len(missing_in_bioproject)} samples in sample metadata but missing in bioproject metadata")
                if len(missing_in_bioproject) <= 10:
                    print(f"Missing samples: {', '.join(missing_in_bioproject)}")
                else:
                    print(f"First 10 missing samples: {', '.join(list(missing_in_bioproject)[:10])}, ...")
            
            # Check for samples in bioproject but not in sample metadata
            missing_in_sample_metadata = bioproject_samples - sample_metadata_samples
            if missing_in_sample_metadata:
                issues.append(f"Samples in bioproject but missing in sample metadata: {', '.join(missing_in_sample_metadata)}")
                print(f"\nWARNING: Found {len(missing_in_sample_metadata)} samples in bioproject metadata but missing in sample metadata")
                if len(missing_in_sample_metadata) <= 10:
                    print(f"Missing samples: {', '.join(missing_in_sample_metadata)}")
                else:
                    print(f"First 10 missing samples: {', '.join(list(missing_in_sample_metadata)[:10])}, ...")
    
    # Check for column alignment issues
    if not bioproject_df.empty:
        alignment_issues = check_column_alignment(bioproject_df)
        if alignment_issues['extra_data'] or ('missing_rows' in alignment_issues and alignment_issues['missing_rows']):
            issues.append("Column alignment issues found in bioproject metadata. See logs for details.")
    
    if not sample_df.empty:
        alignment_issues = check_column_alignment(sample_df)
        if alignment_issues['extra_data'] or ('missing_rows' in alignment_issues and alignment_issues['missing_rows']):
            issues.append("Column alignment issues found in sample metadata. See logs for details.")
    
    # Validate and fix metadata
    if not bioproject_df.empty:
        bioproject_df = validate_bioproject_metadata(bioproject_df, config)
        issues.append("Validated bioproject metadata")
    
    if not sample_df.empty:
        sample_df = validate_sample_metadata(sample_df, config)
        issues.append("Validated sample metadata")
    
    # Save validated files if requested
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Created output directory: {output_dir}")
        
        if not bioproject_df.empty:
            original_bioproject_filename = os.path.basename(bioproject_file)
            output_bioproject = os.path.join(output_dir, f"validated-{original_bioproject_filename}")
            save_metadata_file(bioproject_df, output_bioproject)
            issues.append(f"Saved validated bioproject metadata to {output_bioproject}")
        
        if not sample_df.empty:
            original_sample_filename = os.path.basename(sample_file)
            output_sample = os.path.join(output_dir, f"validated-{original_sample_filename}")
            save_metadata_file(sample_df, output_sample)
            issues.append(f"Saved validated sample metadata to {output_sample}")
    
    return bioproject_df, sample_df, issues


def main():
    """Main entry point for the SRA validation tool."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="SRA Metadata Validation Tool"
    )
    
    parser.add_argument('--config', help='Path to configuration JSON file')
    parser.add_argument('--sample-metadata', help='Path to sample metadata file (tab-delimited TXT or Excel)')
    parser.add_argument('--bioproject-metadata', help='Path to bioproject metadata file (tab-delimited TXT or Excel)')
    parser.add_argument('--output-sample-metadata', help='Path to save validated sample metadata')
    parser.add_argument('--output-bioproject-metadata', help='Path to save validated bioproject metadata')
    parser.add_argument('--output-dir', help='Directory to save validated files')
    parser.add_argument('--validation-name', help='Custom name for this validation (used in log filename)')
    parser.add_argument('--strict', action='store_true', help='Enable strict validation (exit with error on duplicates or collection_date issues)')
    parser.add_argument('--file-dir', help='Directory containing sequence files to check file existence')
    
    args = parser.parse_args()
    
    # Re-initialize logging with validation name if provided
    if args.validation_name:
        setup_logging(args.validation_name)
        logger.info(f"Using validation name: {args.validation_name}")
    
    # Load config if provided
    config = None
    if args.config:
        config = load_config(args.config)
        # Add custom instrument models to valid options
        if config and 'default_values' in config and 'instrument_model' in config['default_values']:
            custom_instrument = config['default_values']['instrument_model']
            if custom_instrument and custom_instrument not in VALID_OPTIONS['instrument_model']:
                VALID_OPTIONS['instrument_model'].append(custom_instrument)
                logger.info(f"Added custom instrument model from config: {custom_instrument}")
    
    # Set default output location if none provided
    if not args.output_sample_metadata and not args.output_bioproject_metadata and not args.output_dir:
        default_output_dir = "validated_metadata"
        os.makedirs(default_output_dir, exist_ok=True)
        args.output_dir = default_output_dir
        logger.info(f"No output location specified, using default: {default_output_dir}")
        print(f"No output location specified, using default: {default_output_dir}")
    
    # Check if required parameters are provided
    if not args.sample_metadata and not args.bioproject_metadata:
        parser.print_help()
        print("\nError: At least one of --sample-metadata or --bioproject-metadata must be specified.")
        sys.exit(1)
    
    # Track validation issues for strict mode
    validation_errors = []
    
    # Track whether files were saved
    sample_saved = False
    bioproject_saved = False
    
    # MODIFIED: First check if files exist (for both sample and bioproject metadata)
    if args.file_dir:
        print("\nChecking if sequence files exist at the specified location...")
        
        # If both metadata files are provided, check files from each
        if args.sample_metadata and args.bioproject_metadata:
            try:
                # Load both metadata files
                sample_df = load_metadata_file(args.sample_metadata)
                bioproject_df = load_metadata_file(args.bioproject_metadata)
                
                # Check files from sample metadata
                all_exist, missing_files, missing_by_sample = check_files_exist(sample_df, args.file_dir)
                
                if not all_exist:
                    print("\n" + "="*80)
                    print(f"WARNING: Found {len(missing_files)} files referenced in metadata that don't exist")
                    print(f"Missing files are associated with {len(missing_by_sample)} samples")
                    print("\nMissing files by sample (showing up to 5 per sample):")
                    
                    for sample_name, files in missing_by_sample.items():
                        print(f"\nSample: {sample_name}")
                        for i, file_info in enumerate(files[:5]):
                            print(f"  - {file_info['column']}: {file_info['file']}")
                        if len(files) > 5:
                            print(f"  - ... and {len(files) - 5} more files")
                    
                    print("\nOptions:")
                    print("1. Stop validation and find the missing files")
                    print("2. Remove samples with missing files from the metadata and continue")
                    
                    choice = input("\nEnter your choice (1 or 2): ")
                    if choice == "1":
                        print("\nValidation stopped. Please find the missing files and try again.")
                        logger.info("User chose to stop validation to find missing files")
                        sys.exit(0)
                    elif choice == "2":
                        print("\nRemoving samples with missing files from metadata...")
                        sample_df, bioproject_df, removed_samples = remove_samples_with_missing_files(
                            sample_df, bioproject_df, missing_by_sample
                        )
                        
                        if removed_samples:
                            print(f"Removed {len(removed_samples)} samples from metadata")
                            logger.info(f"Removed samples: {', '.join(removed_samples)}")
                            
                            # Save the updated metadata files for further processing
                            args.sample_df = sample_df
                            args.bioproject_df = bioproject_df
                    else:
                        print("Invalid choice. Defaulting to stopping validation.")
                        logger.info("Invalid choice entered, stopping validation")
                        sys.exit(0)
                    
                    print("="*80 + "\n")
                else:
                    print("All files referenced in metadata exist!")
                
                # Now check for filename consistency between the two metadata files
                filename_issues = compare_filenames_between_metadata(sample_df, bioproject_df)
                
                if filename_issues['mismatches']:
                    print("\n" + "="*80)
                    print(f"WARNING: Found {len(filename_issues['mismatches'])} filename mismatches between sample and bioproject metadata")
                    print("\nFilename mismatches by sample:")
                    
                    for mismatch in filename_issues['mismatches']:
                        print(f"\nSample: {mismatch['sample']}")
                        print(f"  Sample metadata ({mismatch['sample_column']}): {mismatch['sample_filename']}")
                        print(f"  Bioproject metadata ({mismatch['bioproject_column']}): {mismatch['bioproject_filename']}")
                    
                    print("\nTo ensure successful submission, filenames should match exactly between both metadata files.")
                    print("Options:")
                    print("1. Stop validation and fix the filename mismatches")
                    print("2. Continue validation (filenames will not be automatically fixed)")
                    
                    choice = input("\nEnter your choice (1 or 2): ")
                    if choice == "1":
                        print("\nValidation stopped. Please fix the filename mismatches and try again.")
                        logger.info("User chose to stop validation to fix filename mismatches")
                        sys.exit(0)
                    elif choice == "2":
                        print("\nContinuing validation without fixing filename mismatches...")
                        validation_errors.append(f"Found {len(filename_issues['mismatches'])} filename mismatches between metadata files")
                    else:
                        print("Invalid choice. Defaulting to stopping validation.")
                        logger.info("Invalid choice entered, stopping validation")
                        sys.exit(0)
                    
                    print("="*80 + "\n")
                
            except Exception as e:
                logger.error(f"Error during file existence check: {str(e)}")
                print(f"\nError during file existence check: {str(e)}")
                print("Continuing validation without file checking...")
                import traceback
                logger.error(traceback.format_exc())
        
        # If only sample metadata is provided
        elif args.sample_metadata:
            try:
                sample_df = load_metadata_file(args.sample_metadata)
                all_exist, missing_files, missing_by_sample = check_files_exist(sample_df, args.file_dir)
                
                if not all_exist:
                    # Handle missing files as above
                    print("\n" + "="*80)
                    print(f"WARNING: Found {len(missing_files)} files referenced in metadata that don't exist")
                    print(f"Missing files are associated with {len(missing_by_sample)} samples")
                    # ... (similar to above)
                    # ... handle user choice
                    print("="*80 + "\n")
            except Exception as e:
                logger.error(f"Error checking file existence for sample metadata: {str(e)}")
                print(f"\nError checking file existence for sample metadata: {str(e)}")
    
    # Continue with regular validation
    # Validate sample metadata if provided
    sample_df = None
    if args.sample_metadata:
        try:
            # If we already loaded and processed the sample_df due to file existence check, use that
            if hasattr(args, 'sample_df'):
                sample_df = args.sample_df
            else:
                sample_df = load_metadata_file(args.sample_metadata)
            
            logger.info(f"Loaded sample metadata from {args.sample_metadata}")
            print(f"Loaded sample metadata from {args.sample_metadata}")
            
            # Check for duplicates in sample metadata
            duplicates = check_duplicate_sample_names(sample_df, "sample metadata")
            if duplicates:
                dup_msg = f"\nWARNING: Found {len(duplicates)} duplicate sample names in sample metadata."
                print(dup_msg)
                for dup in duplicates[:10]:  # Show details for first 10
                    print(f"  '{dup['name']}' found {dup['count']} times at rows: {dup['rows']}")
                
                if args.strict:
                    validation_errors.append(f"Duplicate sample names found in sample metadata: {', '.join([d['name'] for d in duplicates])}")
            
            # Validate
            sample_df = validate_sample_metadata(sample_df, config)
            logger.info("Validated sample metadata")
            print("Validated sample metadata")
            
            # Save if output path is specified
            if args.output_sample_metadata:
                save_metadata_file(sample_df, args.output_sample_metadata)
                logger.info(f"Saved validated sample metadata to {args.output_sample_metadata}")
                print(f"Saved validated sample metadata to {args.output_sample_metadata}")
                sample_saved = True
            elif args.output_dir:
                # Use original filename with "validated-" prefix
                original_filename = os.path.basename(args.sample_metadata)
                output_path = os.path.join(args.output_dir, f"validated-{original_filename}")
                save_metadata_file(sample_df, output_path)
                logger.info(f"Saved validated sample metadata to {output_path}")
                print(f"Saved validated sample metadata to {output_path}")
                sample_saved = True
            
        except Exception as e:
            logger.error(f"Error validating sample metadata: {str(e)}")
            print(f"Error validating sample metadata: {str(e)}")
            sys.exit(1)
    
    # Validate bioproject metadata if provided
    bioproject_df = None
    if args.bioproject_metadata:
        try:
            # If we already loaded and processed the bioproject_df due to file existence check, use that
            if hasattr(args, 'bioproject_df'):
                bioproject_df = args.bioproject_df
            else:
                bioproject_df = load_metadata_file(args.bioproject_metadata)
            
            logger.info(f"Loaded bioproject metadata from {args.bioproject_metadata}")
            print(f"Loaded bioproject metadata from {args.bioproject_metadata}")
            
            # Check for duplicates in bioproject metadata
            duplicates = check_duplicate_sample_names(bioproject_df, "bioproject metadata")
            if duplicates:
                dup_msg = f"\nWARNING: Found {len(duplicates)} duplicate sample names in bioproject metadata."
                print(dup_msg)
                for dup in duplicates[:10]:  # Show details for first 10
                    print(f"  '{dup['name']}' found {dup['count']} times at rows: {dup['rows']}")
                
                if args.strict:
                    validation_errors.append(f"Duplicate sample names found in bioproject metadata: {', '.join([d['name'] for d in duplicates])}")
            
            # Check for empty collection_date fields
            if 'collection_date' in bioproject_df.columns:
                empty_dates = bioproject_df['collection_date'].isnull() | (bioproject_df['collection_date'].astype(str) == '')
                if empty_dates.any():
                    empty_count = empty_dates.sum()
                    print(f"\nWARNING: Found {empty_count} empty collection_date fields.")
                    print(f"These will be filled with default value: '{DEFAULT_VALUES['collection_date']}'")
                    
                    if args.strict:
                        empty_rows = empty_dates.to_numpy().nonzero()[0].tolist()
                        validation_errors.append(f"Empty collection_date fields found at rows: {empty_rows[:10]}{'...' if len(empty_rows) > 10 else ''}")
            
            # Validate
            bioproject_df = validate_bioproject_metadata(bioproject_df, config)
            logger.info("Validated bioproject metadata")
            print("Validated bioproject metadata")
            
            # Save if output path is specified
            if args.output_bioproject_metadata:
                save_metadata_file(bioproject_df, args.output_bioproject_metadata)
                logger.info(f"Saved validated bioproject metadata to {args.output_bioproject_metadata}")
                print(f"Saved validated bioproject metadata to {args.output_bioproject_metadata}")
                bioproject_saved = True
            elif args.output_dir:
                # Use original filename with "validated-" prefix
                original_filename = os.path.basename(args.bioproject_metadata)
                output_path = os.path.join(args.output_dir, f"validated-{original_filename}")
                save_metadata_file(bioproject_df, output_path)
                logger.info(f"Saved validated bioproject metadata to {output_path}")
                print(f"Saved validated bioproject metadata to {output_path}")
                bioproject_saved = True
            
        except Exception as e:
            logger.error(f"Error validating bioproject metadata: {str(e)}")
            print(f"Error validating bioproject metadata: {str(e)}")
            sys.exit(1)
    
    # Cross-validate if both metadata files are provided
    if sample_df is not None and bioproject_df is not None:
        print("\nPerforming cross-validation between sample and bioproject metadata:")
        
        if 'sample_name' in bioproject_df.columns and 'sample_name' in sample_df.columns:
            bioproject_samples = set(bioproject_df['sample_name'].dropna().tolist())
            sample_metadata_samples = set(sample_df['sample_name'].dropna().tolist())
            
            # Check for samples in sample metadata but not in bioproject
            missing_in_bioproject = sample_metadata_samples - bioproject_samples
            if missing_in_bioproject:
                message = f"Warning: {len(missing_in_bioproject)} samples in sample metadata but missing in bioproject"
                logger.warning(message)
                print(message)
                if len(missing_in_bioproject) <= 10:
                    print(f"  Missing samples: {', '.join(missing_in_bioproject)}")
                else:
                    print(f"  First 10 missing samples: {', '.join(list(missing_in_bioproject)[:10])}, ...")
                
                if args.strict:
                    validation_errors.append(f"Samples in sample metadata but missing in bioproject: {', '.join(list(missing_in_bioproject)[:10])}")
            
            # Check for samples in bioproject but not in sample metadata
            missing_in_sample_metadata = bioproject_samples - sample_metadata_samples
            if missing_in_sample_metadata:
                message = f"Warning: {len(missing_in_sample_metadata)} samples in bioproject but missing in sample metadata"
                logger.warning(message)
                print(message)
                if len(missing_in_sample_metadata) <= 10:
                    print(f"  Missing samples: {', '.join(missing_in_sample_metadata)}")
                else:
                    print(f"  First 10 missing samples: {', '.join(list(missing_in_sample_metadata)[:10])}, ...")
                
                if args.strict:
                    validation_errors.append(f"Samples in bioproject but missing in sample metadata: {', '.join(list(missing_in_sample_metadata)[:10])}")
            
            if not missing_in_bioproject and not missing_in_sample_metadata:
                print("All samples are consistent between both metadata files.")
    
    # Handle strict mode errors
    if args.strict and validation_errors:
        print("\nERROR: Validation failed in strict mode due to the following issues:")
        for i, error in enumerate(validation_errors, 1):
            print(f"{i}. {error}")
        print("\nPlease fix these issues and run validation again.")
        sys.exit(1)
    
    print("\nValidation completed successfully.")