#!/usr/bin/env python3
"""
SRA Metagenomic Data Submission Script

This script automates the process of preparing and submitting metagenomic data
to NCBI's Sequence Read Archive (SRA). It helps generate required metadata
files and uploads data using Aspera.

Optimized for handling large numbers of files with batch processing, checkpoints,
and improved memory management.
"""

import os
import sys
import json
import argparse
import pandas as pd
import logging
import re
import tempfile
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Import utility functions from the same package
try:
    from sra_metagenome_submission.sra_utils import (
        prepare_metadata,
        detect_file_pairs,
        collect_fastq_files,
        build_sample_metadata
    )
    from sra_metagenome_submission.sra_validate import (
        validate_sample_metadata,
        validate_bioproject_metadata,
        load_metadata_file,
        save_metadata_file
    )
except ImportError:
    # If not installed, try local import
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(current_dir)
    try:
        from sra_utils import (
            prepare_metadata,
            detect_file_pairs,
            collect_fastq_files,
            build_sample_metadata
        )
        from sra_validate import (
            validate_sample_metadata,
            validate_bioproject_metadata,
            load_metadata_file,
            save_metadata_file
        )
    except ImportError:
        print("Error: required modules not found. Please ensure sra_utils.py and sra_validate.py are in the same directory.")
        sys.exit(1)

# Set up logging with dynamic log file name
def setup_logging(submission_name=None):
    """Set up logging with a timestamped filename and optional submission name."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if submission_name:
        log_filename = f"sra_submission_{submission_name}_{timestamp}.log"
    else:
        log_filename = f"sra_submission_{timestamp}.log"
    
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
    return log_filename

# Initialize logging with default timestamp
log_filename = setup_logging()
logger = logging.getLogger(__name__)

class SRASubmission:
    """Class to handle SRA submission process for metagenomic data with optimizations."""
    
    def __init__(self, config_file=None):
        """Initialize the submission class with configuration settings."""
        self.config = {}
        self.sample_metadata_df = None
        self.bioproject_metadata_df = None
        self.files = []
        self.performance_config = {
            'batch_size': 10,
            'chunk_size': 1000,
            'max_workers': 10,
            'enable_checkpoints': True,
            'aspera_timeout': 3600
        }
        
        if config_file:
            self.load_config(config_file)
    
    def load_config(self, config_file):
        """Load configuration from JSON file."""
        try:
            with open(config_file, 'r') as f:
                self.config = json.load(f)
                # Load performance settings if available
                if 'performance' in self.config:
                    self.performance_config.update(self.config['performance'])
                logger.info(f"Loaded configuration from {config_file}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            sys.exit(1)

    def load_sample_metadata(self, metadata_file):
        """Load sample metadata from a tab-delimited TXT or Excel file with chunking for large files."""
        try:
            # Check file size
            file_size = os.path.getsize(metadata_file) / (1024 * 1024)  # Size in MB
            
            if file_size > 10:  # If file is larger than 10MB, use chunking
                logger.info(f"Large file detected ({file_size:.1f} MB), using chunk processing")
                self.sample_metadata_df = self._load_large_metadata_file(metadata_file, 'sample')
            else:
                self.sample_metadata_df = load_metadata_file(metadata_file)
                self.sample_metadata_df = validate_sample_metadata(self.sample_metadata_df, self.config)
            
            if len(self.sample_metadata_df) > 0:
                logger.info(f"Loaded sample metadata from {metadata_file} with {len(self.sample_metadata_df)} samples")
            else:
                logger.error("Sample metadata file is empty")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to load sample metadata: {str(e)}")
            sys.exit(1)
            
        return len(self.sample_metadata_df)
    
    def _load_large_metadata_file(self, file_path, metadata_type='sample'):
        """Load and validate large metadata files by processing in chunks."""
        file_ext = os.path.splitext(file_path)[1].lower()
        chunk_size = self.performance_config['chunk_size']
        
        validated_chunks = []
        
        if file_ext == '.txt':
            # Process tab-delimited file in chunks
            chunks = pd.read_csv(file_path, sep='\t', chunksize=chunk_size)
            for i, chunk in enumerate(chunks):
                logger.info(f"Processing chunk {i+1} ({len(chunk)} rows)")
                if metadata_type == 'sample':
                    validated_chunk = validate_sample_metadata(chunk, self.config)
                else:
                    validated_chunk = validate_bioproject_metadata(chunk, self.config)
                validated_chunks.append(validated_chunk)
        else:
            # For Excel files, we need to load the whole file but can process in chunks
            df = pd.read_excel(file_path)
            for i in range(0, len(df), chunk_size):
                chunk = df.iloc[i:i+chunk_size]
                logger.info(f"Processing chunk {i//chunk_size + 1} ({len(chunk)} rows)")
                if metadata_type == 'sample':
                    validated_chunk = validate_sample_metadata(chunk, self.config)
                else:
                    validated_chunk = validate_bioproject_metadata(chunk, self.config)
                validated_chunks.append(validated_chunk)
        
        # Combine all chunks
        return pd.concat(validated_chunks, ignore_index=True)
    
    def load_bioproject_metadata(self, metadata_file):
        """Load bioproject metadata from a tab-delimited TXT or Excel file."""
        try:
            # Check file size
            file_size = os.path.getsize(metadata_file) / (1024 * 1024)  # Size in MB
            
            if file_size > 10:  # If file is larger than 10MB, use chunking
                logger.info(f"Large file detected ({file_size:.1f} MB), using chunk processing")
                self.bioproject_metadata_df = self._load_large_metadata_file(metadata_file, 'bioproject')
            else:
                self.bioproject_metadata_df = load_metadata_file(metadata_file)
                self.bioproject_metadata_df = validate_bioproject_metadata(self.bioproject_metadata_df, self.config)
            
            if len(self.bioproject_metadata_df) > 0:
                logger.info(f"Loaded bioproject metadata from {metadata_file}")
            else:
                logger.error("Bioproject metadata file is empty")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to load bioproject metadata: {str(e)}")
            sys.exit(1)
    
    def check_files_exist_parallel(self, file_paths, base_dir=None):
        """Check file existence in parallel for better performance."""
        existing_files = []
        missing_files = []
        lock = threading.Lock()
        max_workers = self.performance_config['max_workers']
        
        def check_file(file_info):
            file_path, sample_name, column = file_info
            
            # Handle both absolute and relative paths
            if os.path.isabs(file_path):
                full_path = file_path
            elif base_dir:
                full_path = os.path.join(base_dir, file_path)
            else:
                full_path = file_path
            
            exists = os.path.exists(full_path)
            
            with lock:
                if exists:
                    existing_files.append(full_path)
                else:
                    missing_files.append({
                        'sample': sample_name,
                        'column': column,
                        'file': full_path
                    })
            
            return full_path, exists
        
        # Prepare file information for parallel checking
        file_info_list = []
        for idx, row in self.sample_metadata_df.iterrows():
            sample_name = row.get('sample_name', f"Row_{idx}")
            for col in ['filename', 'filename2', 'filepath', 'filepath2', 'file1', 'file2']:
                if col in row and pd.notna(row[col]) and str(row[col]).strip():
                    file_info_list.append((str(row[col]).strip(), sample_name, col))
        
        total_files = len(file_info_list)
        checked_files = 0
        
        print(f"\nChecking existence of {total_files} files using {max_workers} workers...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(check_file, info): info for info in file_info_list}
            
            for future in as_completed(futures):
                try:
                    _, exists = future.result()
                    checked_files += 1
                    
                    # Progress indicator
                    if checked_files % 10 == 0 or checked_files == total_files:
                        print(f"  Checked {checked_files}/{total_files} files...", end='\r')
                        
                except Exception as e:
                    logger.error(f"Error checking file: {e}")
        
        print(f"\n  Found {len(existing_files)} existing files, {len(missing_files)} missing files")
        
        # Group missing files by sample
        missing_by_sample = {}
        for miss in missing_files:
            sample = miss['sample']
            if sample not in missing_by_sample:
                missing_by_sample[sample] = []
            missing_by_sample[sample].append({
                'column': miss['column'],
                'file': miss['file']
            })
        
        return len(missing_files) == 0, missing_files, missing_by_sample
    
    def collect_sequence_files(self, file_dir=None):
        """Collect sequence files for submission with parallel file checking."""
        if self.sample_metadata_df is None or len(self.sample_metadata_df) == 0:
            logger.error("No sample metadata available for file filtering")
            return 0
        
        # Use parallel file checking
        all_exist, missing_files, missing_by_sample = self.check_files_exist_parallel([], file_dir)
        
        # Collect existing files
        self.files = []
        file_count = 0
        
        # Define filename columns to check
        filename_keys = ['filename', 'filename2', 'filepath', 'filepath2', 'file1', 'file2']
        available_keys = [key for key in filename_keys if key in self.sample_metadata_df.columns]
        
        if not available_keys:
            logger.warning("No filename columns found in sample metadata")
            return 0
        
        # Process each row in the metadata DataFrame
        for idx, row in self.sample_metadata_df.iterrows():
            for key in available_keys:
                filename = row.get(key)
                if filename is None or pd.isna(filename) or str(filename).strip() == "":
                    continue
                
                # Handle both absolute and relative paths
                if os.path.isabs(str(filename)):
                    file_path = str(filename)
                elif file_dir:
                    file_path = os.path.join(file_dir, str(filename))
                else:
                    file_path = str(filename)
                
                # Check if file exists before adding
                if os.path.exists(file_path):
                    self.files.append(file_path)
                    file_count += 1
        
        # Remove duplicates while preserving order
        self.files = list(dict.fromkeys(self.files))
        file_count = len(self.files)
        
        # Handle missing files reporting
        if missing_files:
            logger.warning(f"Could not find {len(missing_files)} files mentioned in sample metadata")
            print(f"\nWarning: {len(missing_files)} files mentioned in metadata are missing.")
            print("You may need to check file paths in your metadata file.")
            
        if file_count > 0:
            logger.info(f"Found {file_count} unique sequence files from metadata")
            print(f"\nFound {file_count} unique sequence files to upload")
        else:
            logger.warning("No files found from metadata information")
            
        return file_count
    
    def generate_template_metadata(self, file_dir, output_dir):
        """
        Generate template metadata files from a directory of sequence files.
        
        Args:
            file_dir (str): Directory containing sequence files
            output_dir (str): Directory to save template files
        
        Returns:
            tuple: (sample_metadata_path, bioproject_metadata_path)
        """
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Collect FASTQ files
            fastq_files = collect_fastq_files(file_dir, recursive=True)
            if not fastq_files:
                logger.error(f"No FASTQ files found in {file_dir}")
                return None, None
            
            logger.info(f"Found {len(fastq_files)} FASTQ files")
            
            # Detect paired files
            file_pairs = detect_file_pairs(fastq_files)
            logger.info(f"Detected {len(file_pairs)} file pairs/singles")
            
            # Build sample metadata
            sample_df = build_sample_metadata(file_pairs, self.config)
            
            # Create bioproject template with one row
            bioproject_columns = [
                'bioproject_id', 'project_title', 'project_description', 
                'sample_source', 'collection_date', 'geo_loc_name', 
                'lat_lon', 'library_strategy', 'library_source', 
                'library_selection', 'platform', 'instrument_model',
                'env_biome', 'env_feature', 'env_material',
                'depth', 'altitude', 'host', 'host_tissue', 'isolation_source'
            ]
            
            # Fill in defaults from config where available
            bioproject_data = {col: [''] for col in bioproject_columns}
            if self.config and 'default_values' in self.config:
                for col in bioproject_columns:
                    if col in self.config['default_values']:
                        bioproject_data[col] = [self.config['default_values'][col]]
            
            bioproject_df = pd.DataFrame(bioproject_data)
            
            # Save template files
            sample_output_path = os.path.join(output_dir, 'sample-metadata-template.txt')
            bioproject_output_path = os.path.join(output_dir, 'bioproject-metadata-template.txt')
            
            save_metadata_file(sample_df, sample_output_path)
            save_metadata_file(bioproject_df, bioproject_output_path)
            
            logger.info(f"Generated template files in {output_dir}")
            print(f"\nGenerated template metadata files:")
            print(f"  - Sample metadata: {sample_output_path}")
            print(f"  - Bioproject metadata: {bioproject_output_path}")
            print("\nPlease fill in the required fields before submission.")
            
            return sample_output_path, bioproject_output_path
            
        except Exception as e:
            logger.error(f"Error generating template metadata: {str(e)}")
            print(f"\nError generating template metadata: {str(e)}")
            return None, None
    
    def create_upload_checkpoint(self, checkpoint_file, uploaded_files, failed_files=None):
        """Save upload progress to a checkpoint file."""
        checkpoint_data = {
            'uploaded_files': list(uploaded_files),
            'failed_files': list(failed_files) if failed_files else [],
            'timestamp': datetime.now().isoformat()
        }
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
        logger.debug(f"Saved checkpoint with {len(uploaded_files)} uploaded files")
    
    def load_upload_checkpoint(self, checkpoint_file):
        """Load upload progress from checkpoint file."""
        if os.path.exists(checkpoint_file):
            try:
                with open(checkpoint_file, 'r') as f:
                    data = json.load(f)
                    uploaded = set(data.get('uploaded_files', []))
                    failed = set(data.get('failed_files', []))
                    timestamp = data.get('timestamp', 'Unknown')
                    logger.info(f"Loaded checkpoint from {timestamp} with {len(uploaded)} uploaded files")
                    return uploaded, failed
            except Exception as e:
                logger.warning(f"Could not load checkpoint file: {e}")
        return set(), set()
    
    def run_aspera_command(self, cmd, timeout=None):
        """Run Aspera command with better error handling using subprocess."""
        if timeout is None:
            timeout = self.performance_config['aspera_timeout']
        
        try:
            logger.debug(f"Running command: {cmd}")
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=timeout
            )
            
            if result.returncode != 0:
                logger.error(f"Aspera command failed with return code {result.returncode}")
                logger.error(f"stderr: {result.stderr}")
                return False
            
            logger.debug("Aspera command completed successfully")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(f"Aspera command timed out after {timeout} seconds")
            return False
        except Exception as e:
            logger.error(f"Error running Aspera command: {str(e)}")
            return False
    
    def upload_files_with_aspera(self, key_path=None, upload_destination=None, aspera_path=None):
        """
        Upload files using Aspera command line with batch processing and checkpoint support.
        
        Args:
            key_path: Path to Aspera key file (required)
            upload_destination: NCBI upload destination (required)
            aspera_path: Full path to the Aspera Connect (ascp) executable
        
        Returns:
            bool: True if upload successful, False otherwise
        """
        # Validate required parameters
        if not key_path:
            logger.error("Aspera key file path is required")
            return False
        
        if not upload_destination:
            logger.error("NCBI upload destination is required")
            return False
        
        # If no files are specified, exit early
        if not self.files:
            logger.error("No files specified for upload")
            print("\nError: No files specified for upload. Please check your metadata file.")
            return False
        
        batch_size = self.performance_config['batch_size']
        enable_checkpoints = self.performance_config['enable_checkpoints']
        
        try:
            # Find Aspera path if not provided
            if not aspera_path:
                aspera_path = self._find_aspera_path()
                
            logger.info(f"Using Aspera client at: {aspera_path}")
            
            # Create a temporary directory for the submission
            temp_dir = tempfile.mkdtemp(prefix="sra_submission_")
            logger.info(f"Created temporary directory for submission: {temp_dir}")
            
            # Update log filename to include the submission folder name
            temp_dir_name = os.path.basename(os.path.normpath(temp_dir))
            global log_filename
            
            # Set up checkpoint file
            checkpoint_file = None
            uploaded_files = set()
            failed_files = set()
            
            if enable_checkpoints:
                checkpoint_file = f"upload_checkpoint_{temp_dir_name}.json"
                uploaded_files, failed_files = self.load_upload_checkpoint(checkpoint_file)
                
                if uploaded_files:
                    print(f"\nResuming upload: {len(uploaded_files)} files already uploaded")
                    # Filter out already uploaded files
                    self.files = [f for f in self.files if f not in uploaded_files]
                    print(f"Remaining files to upload: {len(self.files)}")
            
            # Process files in batches
            total_files = len(self.files)
            total_batches = (total_files + batch_size - 1) // batch_size
            
            print(f"\nPreparing to upload {total_files} files in {total_batches} batches of up to {batch_size} files each...")
            
            upload_success = True
            
            for batch_num, batch_start in enumerate(range(0, total_files, batch_size), 1):
                batch_end = min(batch_start + batch_size, total_files)
                batch_files = self.files[batch_start:batch_end]
                
                print(f"\n{'='*60}")
                print(f"Processing batch {batch_num}/{total_batches} ({len(batch_files)} files)")
                print(f"{'='*60}")
                
                # Create a batch subdirectory
                batch_dir = os.path.join(temp_dir, f"batch_{batch_num:03d}")
                os.makedirs(batch_dir, exist_ok=True)
                
                # Process files in this batch
                batch_prepared_files = []
                for i, file_path in enumerate(batch_files):
                    file_name = os.path.basename(file_path)
                    target_path = os.path.join(batch_dir, file_name)
                    
                    try:
                        # Try to create a symbolic link first
                        os.symlink(os.path.abspath(file_path), target_path)
                        logger.debug(f"Created symlink for {file_name}")
                        batch_prepared_files.append(file_path)
                    except (OSError, AttributeError):
                        # If symlink fails, copy the file
                        try:
                            shutil.copy2(file_path, target_path)
                            logger.debug(f"Copied {file_name} to temporary directory")
                            batch_prepared_files.append(file_path)
                        except Exception as e:
                            logger.error(f"Failed to prepare file {file_name}: {e}")
                            failed_files.add(file_path)
                            continue
                    
                    # Show progress within batch
                    if (i+1) % 5 == 0 or i == len(batch_files) - 1:
                        print(f"  Prepared {i+1}/{len(batch_files)} files in current batch...")
                
                # Upload this batch
                if batch_prepared_files:
                    batch_upload_dest = f"{upload_destination}/{temp_dir_name}"
                    cmd = f'"{aspera_path}" -i "{key_path}" -QT -l100m -k1 -d "{batch_dir}" {batch_upload_dest}'
                    
                    print(f"\nUploading batch {batch_num}...")
                    upload_result = self.run_aspera_command(cmd)
                    
                    if upload_result:
                        logger.info(f"Successfully uploaded batch {batch_num}")
                        print(f"✓ Batch {batch_num} uploaded successfully")
                        
                        # Update uploaded files
                        uploaded_files.update(batch_prepared_files)
                        
                        # Save checkpoint after each successful batch
                        if enable_checkpoints and checkpoint_file:
                            self.create_upload_checkpoint(checkpoint_file, uploaded_files, failed_files)
                    else:
                        logger.error(f"Failed to upload batch {batch_num}")
                        print(f"✗ Failed to upload batch {batch_num}")
                        failed_files.update(batch_prepared_files)
                        upload_success = False
                        
                        # Ask user if they want to continue
                        response = input("\nDo you want to continue with the next batch? (y/n): ")
                        if response.lower() != 'y':
                            print("Upload cancelled by user")
                            return False
                
                # Clean up this batch directory after successful upload
                try:
                    shutil.rmtree(batch_dir)
                    logger.debug(f"Cleaned up batch directory: {batch_dir}")
                except Exception as e:
                    logger.warning(f"Could not clean up batch directory: {e}")
            
            # Upload submit.ready file if all batches were successful
            if upload_success and len(failed_files) == 0:
                print("\nAll batches uploaded successfully. Finalizing submission...")
                ready_file = os.path.join(temp_dir, "submit.ready")
                with open(ready_file, "w") as f:
                    f.write("    ")
                
                temp_dir_name = os.path.basename(os.path.normpath(temp_dir))
                upload_destination_with_dir = f"{upload_destination}/{temp_dir_name}"
                submit_cmd = f'"{aspera_path}" -i "{key_path}" -QT "{ready_file}" {upload_destination_with_dir}'
                
                submit_result = self.run_aspera_command(submit_cmd)
                
                if submit_result:
                    logger.info("Submit.ready file uploaded successfully")
                    print("\n✓ Submission completed successfully!")
                    print(f"\nSuccessfully uploaded {len(uploaded_files)} files")
                    
                    # Clean up checkpoint file
                    if enable_checkpoints and checkpoint_file and os.path.exists(checkpoint_file):
                        os.remove(checkpoint_file)
                        logger.debug("Removed checkpoint file")
                    
                    print("\nTo complete your submission:")
                    print("1. Log into NCBI Submission Portal: https://submit.ncbi.nlm.nih.gov/")
                    print("2. Select 'New Submission' and choose 'Sequence Read Archive (SRA)'")
                    print("3. Follow the steps as outlined in the README.md document")
                    return True
                else:
                    logger.error("Failed to upload submit.ready file")
                    print("\n✗ Warning: Files were uploaded but the submission marker failed.")
                    print("Please contact NCBI SRA support for assistance.")
                    return False
            else:
                print(f"\n✗ Upload completed with errors")
                print(f"Successfully uploaded: {len(uploaded_files)} files")
                print(f"Failed to upload: {len(failed_files)} files")
                
                if failed_files:
                    print("\nFailed files:")
                    for f in list(failed_files)[:10]:
                        print(f"  - {f}")
                    if len(failed_files) > 10:
                        print(f"  ... and {len(failed_files) - 10} more")
                
                return False
                
        except Exception as e:
            logger.error(f"Error during Aspera upload: {str(e)}")
            print(f"\nError during Aspera upload: {str(e)}")
            return False
        finally:
            # Clean up the temporary directory
            if 'temp_dir' in locals():
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"Removed temporary directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Could not remove temporary directory {temp_dir}: {str(e)}")
    
    def _find_aspera_path(self):
        """Find the Aspera client executable in common locations."""
        possible_paths = [
            "~/.aspera/connect/bin/ascp",                          # Linux/Unix default
            "~/Applications/Aspera Connect.app/Contents/Resources/ascp",  # macOS
            "C:/Program Files/Aspera/Aspera Connect/bin/ascp.exe",  # Windows
            "/Applications/Aspera Connect.app/Contents/Resources/ascp",   # macOS alternate
            # Add the ascp command directly in case it's in PATH
            "ascp"
        ]
        
        # Expand user paths and check if they exist
        for path in possible_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                logger.info(f"Found Aspera client at: {expanded_path}")
                return expanded_path
        
        logger.warning("Could not automatically find Aspera Connect client (ascp)")
        print("\nWarning: Could not automatically find Aspera Connect client (ascp).")
        print("Trying 'ascp' command directly, which may fail if not in your PATH.")
        return "ascp"


def main():
    """Main entry point for the SRA submission tool."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="SRA Metagenomic Data Submission Tool (Optimized for Large Datasets)"
    )
    
    parser.add_argument('--config', help='Path to configuration JSON file')
    parser.add_argument('--sample-metadata', help='Path to sample metadata file (tab-delimited TXT or Excel)')
    parser.add_argument('--bioproject-metadata', help='Path to bioproject metadata file (tab-delimited TXT or Excel)')
    parser.add_argument('--files-dir', help='Directory containing sequence files')
    parser.add_argument('--output', default='sra_submission', help='Directory to store output files')
    parser.add_argument('--generate-templates', action='store_true', help='Generate template metadata files from sequence files')
    parser.add_argument('--validate-only', action='store_true', help='Only validate files and metadata without preparing submission')
    parser.add_argument('--submit', action='store_true', help='Submit to SRA after preparing')
    parser.add_argument('--aspera-key', help='Path to Aspera key file')
    parser.add_argument('--aspera-path', help='Full path to the Aspera Connect (ascp) executable')
    parser.add_argument('--upload-destination', help='NCBI upload destination (e.g., subasp@upload.ncbi.nlm.nih.gov:uploads/your_folder)')
    parser.add_argument('--submission-name', help='Custom name for this submission (used in log filename)')
    parser.add_argument('--batch-size', type=int, help='Number of files to upload per batch')
    parser.add_argument('--max-workers', type=int, help='Maximum number of parallel workers for file checking')
    parser.add_argument('--no-checkpoints', action='store_true', help='Disable checkpoint creation')
    
    args = parser.parse_args()
    
    # Re-initialize logging with submission name if provided
    if args.submission_name:
        global log_filename
        log_filename = setup_logging(args.submission_name)
        logger.info(f"Using submission name: {args.submission_name}")
    
    # Initialize submission object
    submission = SRASubmission(args.config)
    
    # Override performance settings from command line if provided
    if args.batch_size:
        submission.performance_config['batch_size'] = args.batch_size
    if args.max_workers:
        submission.performance_config['max_workers'] = args.max_workers
    if args.no_checkpoints:
        submission.performance_config['enable_checkpoints'] = False
    
    # Handle template generation
    if args.generate_templates:
        if not args.files_dir:
            print("Error: --files-dir parameter is required with --generate-templates")
            sys.exit(1)
        
        output_dir = args.output
        submission.generate_template_metadata(args.files_dir, output_dir)
        sys.exit(0)
    
    # Handle metadata loading
    if args.sample_metadata:
        num_samples = submission.load_sample_metadata(args.sample_metadata)
        print(f"Loaded {num_samples} samples from sample metadata file")
    
    if args.bioproject_metadata:
        submission.load_bioproject_metadata(args.bioproject_metadata)
        print("Loaded bioproject metadata file")
    
    # If validate-only, exit after validation
    if args.validate_only:
        print("\nMetadata validation completed.")
        print("No errors found. Your metadata files are ready for submission.")
        sys.exit(0)
    
    # Collect sequence files
    if args.files_dir and (submission.sample_metadata_df is not None):
        num_files = submission.collect_sequence_files(args.files_dir)
        
        if num_files == 0:
            print("No files found for upload. Please check your metadata file and file paths.")
            sys.exit(1)
    
    # Submit if requested
    if args.submit:
        print("\nPreparing to submit to NCBI SRA...")
        
        # Ask for Aspera key path if not provided
        key_path = args.aspera_key
        while not key_path or not os.path.exists(key_path):
            if key_path:
                print(f"Key file not found: {key_path}")
            key_path = input("Enter path to Aspera key file: ")
            if not key_path:
                print("Submission canceled.")
                sys.exit(0)
        
        # Ask for upload destination if not provided
        upload_destination = args.upload_destination
        while not upload_destination:
            upload_destination = input("Enter NCBI upload destination (e.g., subasp@upload.ncbi.nlm.nih.gov:uploads/your_folder): ")
            if not upload_destination:
                print("Submission canceled.")
                sys.exit(0)
        
        # Use Aspera to upload files
        if submission.upload_files_with_aspera(key_path, upload_destination, args.aspera_path):
            print("\nFile upload process completed.")
            print("\nNext steps:")
            print("1. Go to https://submit.ncbi.nlm.nih.gov/subs/sra/ and click 'New Submission'")
            print("2. Follow the steps in the README.md to complete your submission with your validated metadata files")
        else:
            print("File upload failed. See log file for details.")
            sys.exit(1)
    else:
        print("\nFiles identified but not uploaded (--submit flag not used).")
        print("To upload files, run again with the --submit flag.")


if __name__ == "__main__":
    main()