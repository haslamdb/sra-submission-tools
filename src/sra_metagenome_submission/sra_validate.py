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
    
    Returns:
        str: Validated date in ISO 8601 format
    """
    if not date_str or pd.isna(date_str) or str(date_str).strip() == "":
        return ""
    
    date_str = str(date_str).strip()
    
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
    if '/' in date_str:
        dates = date_str.split('/')
        if len(dates) == 2:
            start_date = validate_date_format(dates[0])
            end_date = validate_date_format(dates[1])
            if start_date and end_date:
                return f"{start_date}/{end_date}"
    
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
    
    # MM/DD/YYYY or DD/MM/YYYY format
    mdy_or_dmy = re.match(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$', date_str)
    if mdy_or_dmy:
        d1, d2, year = mdy_or_dmy.groups()
        
        # Assume MM/DD/YYYY for US format
        # But try to be smart about it (if d1 > 12, it's probably DD/MM/YYYY)
        if int(d1) > 12:
            day, month = d1, d2
        else:
            month, day = d1, d2
        
        # Ensure two digits
        month = month.zfill(2)
        day = day.zfill(2)
        
        return f"{year}-{month}-{day}"
    
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
    
    # Fill missing required fields with defaults
    required_fields = [
        'library_strategy', 'library_source', 'library_selection',
        'platform', 'instrument_model'
    ]
    
    for field in required_fields:
        if field in default_values and field in validated_df.columns:
            validated_df[field] = validated_df[field].fillna(default_values[field])
    
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
    
    # Fill missing required fields with defaults
    required_fields = [
        'library_strategy', 'library_source', 'library_selection',
        'platform', 'instrument_model'
    ]
    
    for field in required_fields:
        if field in default_values and field in validated_df.columns:
            validated_df[field] = validated_df[field].fillna(default_values[field])
    
    # Ensure required columns exist
    essential_columns = [
        'bioproject_id', 'project_title', 'project_description', 'sample_source',
        'collection_date', 'geo_loc_name', 'lat_lon', 'library_strategy',
        'library_source', 'library_selection', 'platform', 'instrument_model',
        'env_biome', 'env_feature', 'env_material'
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
    
    # Validate date formats
    if 'collection_date' in validated_df.columns:
        validated_df['collection_date'] = validated_df['collection_date'].apply(validate_date_format)
        
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
            if row['sample_source'] == 'host-associated':
                if 'host' in validated_df.columns and (pd.isna(row['host']) or row['host'] == ''):
                    logger.warning(f"Sample source is host-associated but 'host' field is empty")
    
    # Add file_number column if not present
    if 'file_number' not in validated_df.columns:
        validated_df['file_number'] = range(1, len(validated_df) + 1)
    
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
    # Initialize issues list
    issues = []
    
    # Load config if provided
    config = None
    if config_file:
        config = load_config(config_file)
    
    # Load metadata files
    try:
        bioproject_df = load_metadata_file(bioproject_file)
        logger.info(f"Loaded bioproject metadata from {bioproject_file}")
    except Exception as e:
        issues.append(f"Failed to load bioproject metadata file: {str(e)}")
        bioproject_df = pd.DataFrame()
    
    try:
        sample_df = load_metadata_file(sample_file)
        logger.info(f"Loaded sample metadata from {sample_file}")
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
    
    # Validate and fix metadata
    if not bioproject_df.empty:
        bioproject_df = validate_bioproject_metadata(bioproject_df, config)
        issues.append("Validated bioproject metadata")
    
    if not sample_df.empty:
        sample_df = validate_sample_metadata(sample_df, config)
        issues.append("Validated sample metadata")
    
    # Cross-validate samples between files
    if not bioproject_df.empty and not sample_df.empty:
        if 'sample_name' in bioproject_df.columns and 'sample_name' in sample_df.columns:
            bioproject_samples = set(bioproject_df['sample_name'].dropna().tolist())
            sample_metadata_samples = set(sample_df['sample_name'].dropna().tolist())
            
            # Check for samples in sample metadata but not in bioproject
            missing_in_bioproject = sample_metadata_samples - bioproject_samples
            if missing_in_bioproject:
                issues.append(f"Samples in sample metadata but missing in bioproject: {', '.join(missing_in_bioproject)}")
            
            # Check for samples in bioproject but not in sample metadata
            missing_in_sample_metadata = bioproject_samples - sample_metadata_samples
            if missing_in_sample_metadata:
                issues.append(f"Samples in bioproject but missing in sample metadata: {', '.join(missing_in_sample_metadata)}")
    
    # Save validated files if requested
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
        if not bioproject_df.empty:
            output_bioproject = os.path.join(output_dir, "validated_bioproject.txt")
            save_metadata_file(bioproject_df, output_bioproject)
            issues.append(f"Saved validated bioproject metadata to {output_bioproject}")
        
        if not sample_df.empty:
            output_sample = os.path.join(output_dir, "validated_sample.txt")
            save_metadata_file(sample_df, output_sample)
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
    
    args = parser.parse_args()
    
    # Re-initialize logging with validation name if provided
    if args.validation_name:
        setup_logging(args.validation_name)
        logger.info(f"Using validation name: {args.validation_name}")
    
    # Load config if provided
    config = None
    if args.config:
        config = load_config(args.config)
    
    # Check if required parameters are provided
    if not args.sample_metadata and not args.bioproject_metadata:
        parser.print_help()
        print("\nError: At least one of --sample-metadata or --bioproject-metadata must be specified.")
        sys.exit(1)
    
    # Validate sample metadata if provided
    sample_df = None
    if args.sample_metadata:
        try:
            sample_df = load_metadata_file(args.sample_metadata)
            logger.info(f"Loaded sample metadata from {args.sample_metadata}")
            print(f"Loaded sample metadata from {args.sample_metadata}")
            
            # Validate
            sample_df = validate_sample_metadata(sample_df, config)
            logger.info("Validated sample metadata")
            print("Validated sample metadata")
            
            # Save if output path is specified
            if args.output_sample_metadata:
                save_metadata_file(sample_df, args.output_sample_metadata)
                logger.info(f"Saved validated sample metadata to {args.output_sample_metadata}")
                print(f"Saved validated sample metadata to {args.output_sample_metadata}")
            elif args.output_dir:
                output_path = os.path.join(args.output_dir, "validated_sample_metadata.txt")
                save_metadata_file(sample_df, output_path)
                logger.info(f"Saved validated sample metadata to {output_path}")
                print(f"Saved validated sample metadata to {output_path}")
            
        except Exception as e:
            logger.error(f"Error validating sample metadata: {str(e)}")
            print(f"Error validating sample metadata: {str(e)}")
            sys.exit(1)
    
    # Validate bioproject metadata if provided
    bioproject_df = None
    if args.bioproject_metadata:
        try:
            bioproject_df = load_metadata_file(args.bioproject_metadata)
            logger.info(f"Loaded bioproject metadata from {args.bioproject_metadata}")
            print(f"Loaded bioproject metadata from {args.bioproject_metadata}")
            
            # Validate
            bioproject_df = validate_bioproject_metadata(bioproject_df, config)
            logger.info("Validated bioproject metadata")
            print("Validated bioproject metadata")
            
            # Save if output path is specified
            if args.output_bioproject_metadata:
                save_metadata_file(bioproject_df, args.output_bioproject_metadata)
                logger.info(f"Saved validated bioproject metadata to {args.output_bioproject_metadata}")
                print(f"Saved validated bioproject metadata to {args.output_bioproject_metadata}")
            elif args.output_dir:
                output_path = os.path.join(args.output_dir, "validated_bioproject_metadata.txt")
                save_metadata_file(bioproject_df, output_path)
                logger.info(f"Saved validated bioproject metadata to {output_path}")
                print(f"Saved validated bioproject metadata to {output_path}")
            
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
            
            if not missing_in_bioproject and not missing_in_sample_metadata:
                print("All samples are consistent between both metadata files.")
    
    print("\nValidation completed successfully.")
    
if __name__ == "__main__":
    main()