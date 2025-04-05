#!/usr/bin/env python3
"""
Hellman Dataset SRA Submission Script

This script prepares and submits the Hellman metagenomic dataset to NCBI's SRA.
It uses the metadata from hellman_metadata2.csv and configuration from dbh_config.json.
"""

import os
import sys
import json
import pandas as pd
import logging
from pathlib import Path
from sra_submission import SRASubmission

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("hellman_submission.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# File paths
CONFIG_FILE = "dbh_config.json"
METADATA_FILE = "hellman_metadata2.csv"
DATA_DIR = "/media/david/BackupNAS/Data/MSSData/Human/RawHumanSequenceFiles"
OUTPUT_DIR = "hellman_sra_submission"

def prepare_metadata_file(input_csv, output_csv):
    """
    Prepare a SRA-compatible metadata file from the Hellman metadata CSV.
    
    Args:
        input_csv: Path to the original Hellman metadata CSV
        output_csv: Path to save the SRA-compatible metadata CSV
    """
    try:
        # Read the original metadata
        df = pd.read_csv(input_csv)
        
        # Load default values from config
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            default_values = config.get('default_values', {})
            contact = config.get('contact', {})
        
        # Create a new dataframe for SRA submission with required columns
        sra_df = pd.DataFrame()
        
        # Add sample information
        sra_df['sample_name'] = df['sample_name']
        sra_df['title'] = df['title']
        sra_df['library_ID'] = df['library_ID']
        
        # Add library information - use values from metadata if present, otherwise use defaults
        for field in ['library_strategy', 'library_source', 'library_selection', 'platform', 'instrument_model']:
            if field in df.columns:
                sra_df[field] = df[field]
            elif field in default_values:
                sra_df[field] = default_values[field]
        
        # Add design description
        if 'design_description' in df.columns:
            sra_df['design_description'] = df['design_description']
        else:
            sra_df['design_description'] = "Metagenomic sequencing of stool samples"
        
        # Add file information
        sra_df['filetype'] = df['filetype']
        sra_df['filename'] = df['filename']
        sra_df['filename2'] = df['filename2']
        
        # Add file paths
        sra_df['filepath'] = sra_df['filename'].apply(lambda x: os.path.join(DATA_DIR, x))
        sra_df['filepath2'] = sra_df['filename2'].apply(lambda x: os.path.join(DATA_DIR, x) if pd.notna(x) else '')
        
        # Add contact information
        for key, value in contact.items():
            sra_df[f'contact_{key}'] = value
        
        # Add additional metadata
        sra_df['bioproject_id'] = ""  # Leave blank to create new or add your bioproject ID
        sra_df['biosample_id'] = ""   # Leave blank to create new
        
        # Extract sample source from title (human or mouse)
        sra_df['sample_source'] = df['title'].apply(
            lambda x: 'host-associated' if 'Human' in x or 'Mouse' in x else 'environmental'
        )
        
        # Add host information
        sra_df['host'] = df['title'].apply(
            lambda x: 'Homo sapiens' if 'Human' in x else 'Mus musculus' if 'Mouse' in x else ''
        )
        
        # Add isolation source
        sra_df['isolation_source'] = df['title'].apply(
            lambda x: 'Stool' if 'Stool' in x else ''
        )
        
        # Save the SRA-compatible metadata
        sra_df.to_csv(output_csv, index=False)
        logger.info(f"SRA metadata file created: {output_csv}")
        return sra_df
        
    except Exception as e:
        logger.error(f"Failed to prepare metadata: {str(e)}")
        sys.exit(1)

def verify_files_exist(sra_df):
    """
    Verify that all sequence files exist at the specified paths.
    
    Args:
        sra_df: DataFrame containing file paths
    
    Returns:
        bool: True if all files exist, False otherwise
    """
    missing_files = []
    
    # Check first file for each sample
    for _, row in sra_df.iterrows():
        filepath = row['filepath']
        if not os.path.exists(filepath):
            missing_files.append(filepath)
        
        # Check second file if it exists (paired-end)
        if pd.notna(row['filepath2']) and row['filepath2'] != '':
            if not os.path.exists(row['filepath2']):
                missing_files.append(row['filepath2'])
    
    if missing_files:
        logger.error(f"Missing {len(missing_files)} sequence files:")
        for file in missing_files[:10]:  # Show first 10 missing files
            logger.error(f"  - {file}")
        if len(missing_files) > 10:
            logger.error(f"  ... and {len(missing_files) - 10} more")
        return False
    
    logger.info(f"All {len(sra_df) * 2} sequence files found")
    return True

def main():
    """Main function to prepare and submit Hellman dataset to SRA."""
    logger.info("Starting Hellman dataset SRA submission preparation")
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Prepare SRA-compatible metadata file
    sra_metadata_file = os.path.join(OUTPUT_DIR, "sra_metadata.csv")
    sra_df = prepare_metadata_file(METADATA_FILE, sra_metadata_file)
    
    # Verify files exist
    if not verify_files_exist(sra_df):
        logger.error("Some sequence files are missing. Please check the paths.")
        print("\nWould you like to continue anyway? [y/N]")
        response = input("> ").strip().lower()
        if response != 'y':
            sys.exit(1)
    
    # Initialize SRA submission
    submission = SRASubmission(CONFIG_FILE)
    
    # Collect metadata from prepared file
    submission.collect_metadata_from_file(sra_metadata_file)
    
    # Validate metadata
    if not submission.validate_metadata():
        logger.error("Metadata validation failed. Please correct the issues and try again.")
        sys.exit(1)
    
    # Get list of all files to submit
    files = []
    for _, row in sra_df.iterrows():
        files.append(row['filepath'])
        if pd.notna(row['filepath2']) and row['filepath2'] != '':
            files.append(row['filepath2'])
    
    # Set files in submission object
    submission.files = files
    
    # Prepare submission package
    submission_xml_path = submission.prepare_submission_package(OUTPUT_DIR)
    
    # Ask if user wants to submit
    print("\nSubmission package prepared. Would you like to submit to SRA now? [y/N]")
    response = input("> ").strip().lower()
    if response == 'y':
        submission.authenticate()
        if submission.upload_files():
            submission.submit(submission_xml_path)
    else:
        logger.info(f"Submission package prepared in {OUTPUT_DIR}")
        logger.info("Run the following command to submit to SRA later:")
        print(f"\npython sra_submission.py --config {CONFIG_FILE} --output {OUTPUT_DIR} --submit")

if __name__ == "__main__":
    main()
