#!/usr/bin/env python3
"""
SRA Submission Utilities

This module provides utility functions for SRA metadata preparation, file verification,
and other helper functions needed for SRA submissions.
"""

import os
import sys
import json
import pandas as pd
import logging
from pathlib import Path
import re

logger = logging.getLogger(__name__)

def prepare_metadata(input_file, output_file=None, config_file=None):
    """
    Prepare SRA-compatible metadata from different input formats.
    
    Args:
        input_file (str): Path to input metadata file (CSV or Excel)
        output_file (str, optional): Path to save the processed metadata file
        config_file (str, optional): Path to configuration file with default values
    
    Returns:
        pd.DataFrame: Processed metadata dataframe
    """
    try:
        # Load input metadata file
        if input_file.endswith('.csv'):
            df = pd.read_csv(input_file)
        elif input_file.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(input_file)
        else:
            raise ValueError(f"Unsupported file format: {input_file}")
        
        # Load configuration if provided
        default_values = {}
        contact = {}
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                default_values = config.get('default_values', {})
                contact = config.get('contact', {})
        
        # Create SRA-compatible metadata dataframe
        sra_df = pd.DataFrame()
        
        # Map required fields
        required_fields = {
            "sample_name": "sample_name",
            "title": "title",
            "library_ID": "library_ID",
            "library_strategy": "library_strategy",
            "library_source": "library_source",
            "library_selection": "library_selection",
            "library_layout": "library_layout",
            "platform": "platform",
            "instrument_model": "instrument_model"
        }
        
        # Copy existing fields and apply defaults where needed
        for target_field, source_field in required_fields.items():
            if source_field in df.columns:
                sra_df[target_field] = df[source_field]
            elif target_field in default_values:
                sra_df[target_field] = default_values[target_field]
            else:
                sra_df[target_field] = ""
        
        # Handle common file naming patterns
        if 'filename' in df.columns:
            sra_df['filename'] = df['filename']
            
            # If paired files are in separate columns
            if 'filename2' in df.columns:
                sra_df['filename2'] = df['filename2']
            
            # Try to infer paired files if not explicitly provided
            if 'filename2' not in df.columns and 'filename2' not in sra_df.columns:
                sra_df['filename2'] = ""
                # Look for common paired-end patterns (R1/R2, _1/_2)
                for i, row in sra_df.iterrows():
                    filename = row['filename']
                    if '_R1' in filename or '_1.' in filename:
                        paired_file = filename.replace('_R1', '_R2').replace('_1.', '_2.')
                        sra_df.at[i, 'filename2'] = paired_file
        
        # Add additional SRA-required fields
        # Try to infer from title if available
        if 'title' in sra_df.columns:
            # Infer sample_source and host from title
            sra_df['sample_source'] = sra_df['title'].apply(
                lambda x: 'host-associated' if isinstance(x, str) and ('Human' in x or 'Mouse' in x) else 'environmental'
            )
            
            sra_df['host'] = sra_df['title'].apply(
                lambda x: 'Homo sapiens' if isinstance(x, str) and 'Human' in x 
                     else 'Mus musculus' if isinstance(x, str) and 'Mouse' in x else ''
            )
            
            sra_df['isolation_source'] = sra_df['title'].apply(
                lambda x: 'Stool' if isinstance(x, str) and 'Stool' in x else ''
            )
        
        # Add contact information
        for key, value in contact.items():
            sra_df[f'contact_{key}'] = value
        
        # Add empty bioproject/biosample fields if not present
        if 'bioproject_id' not in sra_df.columns:
            sra_df['bioproject_id'] = ""
        if 'biosample_id' not in sra_df.columns:
            sra_df['biosample_id'] = ""
        
        # Add design description if missing
        if 'design_description' not in sra_df.columns:
            if 'design_description' in df.columns:
                sra_df['design_description'] = df['design_description']
            else:
                sra_df['design_description'] = "Metagenomic sequencing"
        
        # Save processed metadata if output file is specified
        if output_file:
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            sra_df.to_csv(output_file, index=False)
            logger.info(f"Processed metadata saved to {output_file}")
        
        return sra_df
        
    except Exception as e:
        logger.error(f"Error in metadata preparation: {str(e)}")
        raise

def verify_files(metadata_df, base_dir=None, column_names=None):
    """
    Verify the existence of sequence files referenced in metadata.
    
    Args:
        metadata_df (pd.DataFrame): Metadata dataframe
        base_dir (str, optional): Base directory where files are located
        column_names (list, optional): List of column names containing filenames
    
    Returns:
        tuple: (success_flag, list_of_missing_files, list_of_found_files)
    """
    if column_names is None:
        # Default column names for files (common patterns)
        column_names = ['filename', 'filename2', 'filepath', 'filepath2', 'file1', 'file2']
    
    # Filter to columns that actually exist in the dataframe
    file_columns = [col for col in column_names if col in metadata_df.columns]
    
    if not file_columns:
        logger.error("No file columns found in metadata")
        return False, [], []
    
    missing_files = []
    found_files = []
    
    # Check each file referenced in the metadata
    for _, row in metadata_df.iterrows():
        for col in file_columns:
            if pd.isna(row[col]) or row[col] == '':
                continue
                
            filename = row[col]
            
            # Handle both absolute and relative paths
            if os.path.isabs(filename) or base_dir is None:
                filepath = filename
            else:
                filepath = os.path.join(base_dir, filename)
            
            # Check if file exists
            if os.path.exists(filepath):
                found_files.append(filepath)
            else:
                missing_files.append(filepath)
    
    if missing_files:
        logger.warning(f"Found {len(missing_files)} missing files")
        return False, missing_files, found_files
    else:
        logger.info(f"Verified {len(found_files)} files exist")
        return True, missing_files, found_files

def detect_file_pairs(file_list):
    """
    Detect paired-end sequence files from a list of files.
    
    Args:
        file_list (list): List of file paths or filenames
    
    Returns:
        list: List of (file1, file2) tuples for paired files
    """
    # Common patterns for paired-end files
    patterns = [
        (r'_R1[._]', r'_R2[._]'),  # _R1. and _R2.
        (r'_1\.', r'_2\.'),        # _1. and _2.
        (r'_forward', r'_reverse'), # _forward and _reverse
        (r'_f\.', r'_r\.'),        # _f. and _r.
    ]
    
    paired_files = {}
    unpaired_files = []
    
    # First pass: identify file1 candidates and their expected file2 names
    for file_path in file_list:
        file_name = os.path.basename(file_path)
        
        # Check each pattern for file1
        is_file1 = False
        for pattern1, pattern2 in patterns:
            if re.search(pattern1, file_name):
                is_file1 = True
                expected_file2 = re.sub(pattern1, lambda m: m.group(0).replace('1', '2').replace('R1', 'R2').replace('forward', 'reverse').replace('f.', 'r.'), file_name)
                
                # Store the expected file2 name for this file1
                paired_files[file_name] = {
                    'file1_path': file_path,
                    'expected_file2': expected_file2,
                    'file2_path': None
                }
                break
        
        if not is_file1:
            # This could be file2 or an unpaired file
            unpaired_files.append(file_path)
    
    # Second pass: match file2 candidates with their file1
    for file_path in unpaired_files[:]:
        file_name = os.path.basename(file_path)
        
        # Check if this is an expected file2
        matched = False
        for file1, pair_info in paired_files.items():
            if file_name == pair_info['expected_file2']:
                pair_info['file2_path'] = file_path
                matched = True
                unpaired_files.remove(file_path)
                break
        
        if not matched:
            # This might be a standalone file, leave it in unpaired_files
            pass
    
    # Create the final list of paired files and add any remaining single files
    result_pairs = []
    for pair_info in paired_files.values():
        if pair_info['file2_path']:
            result_pairs.append((pair_info['file1_path'], pair_info['file2_path']))
        else:
            # Found a file1 without a matching file2
            unpaired_files.append(pair_info['file1_path'])
    
    # Also identify any single files (non-paired)
    single_files = [(file_path, None) for file_path in unpaired_files]
    
    return result_pairs + single_files

def collect_fastq_files(directory, recursive=True):
    """
    Collect all FASTQ files from a directory.
    
    Args:
        directory (str): Directory to search for FASTQ files
        recursive (bool): Whether to search recursively
    
    Returns:
        list: List of FASTQ file paths
    """
    fastq_extensions = ['.fastq', '.fq', '.fastq.gz', '.fq.gz']
    fastq_files = []
    
    if recursive:
        for root, _, files in os.walk(directory):
            for file in files:
                if any(file.endswith(ext) for ext in fastq_extensions):
                    fastq_files.append(os.path.join(root, file))
    else:
        path = Path(directory)
        for ext in fastq_extensions:
            fastq_files.extend([str(f) for f in path.glob(f'*{ext}')])
    
    return fastq_files

def build_sample_metadata(file_pairs, config_file=None):
    """
    Build sample metadata from file pairs.
    
    Args:
        file_pairs (list): List of (file1, file2) tuples
        config_file (str, optional): Path to configuration file with default values
    
    Returns:
        pd.DataFrame: Sample metadata dataframe
    """
    # Load default values from config
    default_values = {}
    contact = {}
    if config_file and os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
            default_values = config.get('default_values', {})
            contact = config.get('contact', {})
    
    # Create sample metadata dataframe
    samples = []
    
    for file1, file2 in file_pairs:
        # Extract sample name from file1 name
        file1_name = os.path.basename(file1)
        sample_name = re.sub(r'_R?[12]\..*$', '', file1_name)
        
        # Create sample entry
        sample = {
            'sample_name': sample_name,
            'title': f"Metagenome from {sample_name}",
            'filename': file1_name,
            'filename2': os.path.basename(file2) if file2 else "",
            'filepath': file1,
            'filepath2': file2 if file2 else "",
            'library_layout': 'paired' if file2 else 'single',
        }
        
        # Add default values
        for key, value in default_values.items():
            if key not in sample:
                sample[key] = value
        
        # Add contact information
        for key, value in contact.items():
            sample[f'contact_{key}'] = value
        
        samples.append(sample)
    
    # Create dataframe
    sra_df = pd.DataFrame(samples)
    
    # Add empty bioproject/biosample fields if not present
    if 'bioproject_id' not in sra_df.columns:
        sra_df['bioproject_id'] = ""
    if 'biosample_id' not in sra_df.columns:
        sra_df['biosample_id'] = ""
    
    return sra_df
