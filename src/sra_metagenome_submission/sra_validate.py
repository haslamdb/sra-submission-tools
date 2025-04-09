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
def setup_logging():
    """Set up logging with a timestamped filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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

logger = setup_logging()

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
            validated_df[col] = ""
    
    # Validate library_layout (must be "single" or "paired")
    if 'library_layout' in validated_df.columns:
        # Convert to lowercase and fix any variations
        validated_df['library_layout'] = validated_df['library_layout'].apply(
            lambda x: 'paired' if str(x).lower().strip() in ['paired', 'pair', 'pe'] 
            else 'single' if str(x).lower().strip() in ['single', 'se'] 
            else x
        )
    
    # Validate filenames - ensure they exist and match sample names
    if 'filename' in validated_df.columns and 'filename2' in validated_df.columns:
        # Matching library_layout with filenames
        for idx, row in validated_df.iterrows():
            if row['library_layout'] == 'paired' and (pd.isna(row['filename2']) or row['filename2'] == ''):
                logger.warning(f"Sample {row['sample_name']} is marked as paired but missing second filename")
            if row['library_layout'] == 'single' and not (pd.isna(row['filename2']) or row['filename2'] == ''):
                logger.warning(f"Sample {row['sample_name']} is marked as single but has a second filename")
    
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
            validated_df[col] = ""
    
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

def main():
    """Main function for validating metadata files."""
    parser = argparse.ArgumentParser(description="SRA Metadata Validation Tool")
    
    parser.add_argument('--config', help='Path to configuration JSON file')
    parser.add_argument('--sample-metadata', required=True, help='Path to sample metadata file (tab-delimited TXT or Excel)')
    parser.add_argument('--bioproject-metadata', required=True, help='Path to bioproject metadata file (tab-delimited TXT or Excel)')
    parser.add_argument('--output-sample-metadata', help='Path to save validated sample metadata')
    parser.add_argument('--output-bioproject-metadata', help='Path to save validated bioproject metadata')
    
    args = parser.parse_args()
    
    # Load config if provided
    config = None
    if args.config:
        config = load_config(args.config)
    
    # Load metadata files
    print(f"Loading sample metadata from {args.sample_metadata}")
    sample_df = load_metadata_file(args.sample_metadata)
    
    print(f"Loading bioproject metadata from {args.bioproject_metadata}")
    bioproject_df = load_metadata_file(args.bioproject_metadata)
    
    # Validate metadata
    print("Validating sample metadata...")
    validated_sample_df = validate_sample_metadata(sample_df, config)
    
    print("Validating bioproject metadata...")
    validated_bioproject_df = validate_bioproject_metadata(bioproject_df, config)
    
    # Determine output paths
    sample_output = args.output_sample_metadata if args.output_sample_metadata else args.sample_metadata.rsplit('.', 1)[0] + '_validated.' + args.sample_metadata.rsplit('.', 1)[1]
    bioproject_output = args.output_bioproject_metadata if args.output_bioproject_metadata else args.bioproject_metadata.rsplit('.', 1)[0] + '_validated.' + args.bioproject_metadata.rsplit('.', 1)[1]
    
    # Save validated metadata
    print(f"Saving validated sample metadata to {sample_output}")
    save_metadata_file(validated_sample_df, sample_output)
    
    print(f"Saving validated bioproject metadata to {bioproject_output}")
    save_metadata_file(validated_bioproject_df, bioproject_output)
    
    print("\nValidation complete!")
    print(f"Validated sample metadata saved to: {sample_output}")
    print(f"Validated bioproject metadata saved to: {bioproject_output}")
    print("\nPlease review the log file for any warnings or issues that need attention.")
    print("Use these validated files for your SRA submission.")

if __name__ == "__main__":
    main()
