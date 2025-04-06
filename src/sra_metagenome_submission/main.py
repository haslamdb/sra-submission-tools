#!/usr/bin/env python3
"""
SRA Metagenomic Data Submission Script

This script automates the process of preparing and submitting metagenomic data
to NCBI's Sequence Read Archive (SRA). It helps generate required metadata
files and uploads data using Aspera.
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
from pathlib import Path
from datetime import datetime

# Import utility functions from the same package
try:
    from sra_metagenome_submission.sra_utils import (
        prepare_metadata,
        detect_file_pairs,
        collect_fastq_files,
        build_sample_metadata
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
    except ImportError:
        print("Error: sra_utils module not found. Please ensure sra_utils.py is in the same directory.")
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
    """Class to handle SRA submission process for metagenomic data."""
    
    def __init__(self, config_file=None):
        """Initialize the submission class with configuration settings."""
        self.config = {}
        self.metadata_df = None
        self.files = []
        
        if config_file:
            self.load_config(config_file)
    
    def load_config(self, config_file):
        """Load configuration from JSON file."""
        try:
            with open(config_file, 'r') as f:
                self.config = json.load(f)
                logger.info(f"Loaded configuration from {config_file}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            sys.exit(1)

    def load_metadata(self, metadata_file):
        """Load metadata from a CSV or Excel file."""
        try:
            # Use the prepare_metadata utility for processing
            self.metadata_df = prepare_metadata(metadata_file, config_file=self.config.get('defaults', {}))
            
            if len(self.metadata_df) > 0:
                logger.info(f"Loaded metadata from {metadata_file} with {len(self.metadata_df)} samples")
            else:
                logger.error("Metadata file is empty")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to load metadata from file: {str(e)}")
            sys.exit(1)
            
        return len(self.metadata_df)
    
    def collect_sequence_files(self, file_dir=None):
        """Collect sequence files for submission, only including files mentioned in metadata."""
        if self.metadata_df is None or len(self.metadata_df) == 0:
            logger.error("No metadata available for file filtering")
            return 0
        
        # Define filename columns to check
        filename_keys = ['filename', 'filename2', 'filepath', 'filepath2', 'file1', 'file2']
        available_keys = [key for key in filename_keys if key in self.metadata_df.columns]
        
        if not available_keys:
            logger.warning("No filename columns found in metadata")
            return 0
        
        self.files = []
        file_count = 0
        missing_files = []
        
        # Process each row in the metadata DataFrame
        for idx, row in self.metadata_df.iterrows():
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
                
                # Check if file exists
                if os.path.exists(file_path):
                    self.files.append(file_path)
                    file_count += 1
                else:
                    missing_files.append(file_path)
        
        # Remove duplicates while preserving order
        self.files = list(dict.fromkeys(self.files))
        file_count = len(self.files)
        
        # Handle missing files reporting
        if missing_files:
            logger.warning(f"Could not find {len(missing_files)} files mentioned in metadata:")
            for file in missing_files[:5]:  # Show first 5 missing files
                logger.warning(f"  - {file}")
            if len(missing_files) > 5:
                logger.warning(f"  ... and {len(missing_files) - 5} more")
                
            print(f"\nWarning: {len(missing_files)} files mentioned in metadata are missing.")
            print("You may need to check file paths in your metadata file.")
            
        if file_count > 0:
            logger.info(f"Found {file_count} unique sequence files from metadata")
            print(f"\nFound {file_count} unique sequence files to upload")
        else:
            logger.warning("No files found from metadata information")
            
        return file_count
    
    def upload_files_with_aspera(self, key_path=None, upload_destination=None, aspera_path=None):
        """
        Upload files using Aspera command line.
        
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
            
            # If log file exists, create a new one with the temp directory name
            if os.path.exists(log_filename):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_log = f"sra_submission_{temp_dir_name}_{timestamp}.log"
                
                # Copy existing log content to the new file
                with open(log_filename, 'r') as source:
                    content = source.read()
                with open(new_log, 'w') as target:
                    target.write(content)
                
                # Update the logging configuration to use the new file
                for handler in logging.root.handlers[:]:
                    if isinstance(handler, logging.FileHandler):
                        handler.close()
                        logging.root.removeHandler(handler)
                
                file_handler = logging.FileHandler(new_log)
                file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
                logging.root.addHandler(file_handler)
                
                log_filename = new_log
                logger.info(f"Log file renamed to include submission ID: {log_filename}")
            
            # Create symbolic links or copy files to the temporary directory
            print(f"\nPreparing {len(self.files)} files for upload...")
            
            for i, file_path in enumerate(self.files):
                file_name = os.path.basename(file_path)
                target_path = os.path.join(temp_dir, file_name)
                
                try:
                    # Try to create a symbolic link first (more efficient)
                    os.symlink(os.path.abspath(file_path), target_path)
                    logger.debug(f"Created symlink for {file_name}")
                except (OSError, AttributeError):
                    # If symlink fails (e.g., on Windows), copy the file
                    shutil.copy2(file_path, target_path)
                    logger.debug(f"Copied {file_name} to temporary directory")
                
                # Show progress
                if (i+1) % 10 == 0 or i == len(self.files) - 1:
                    print(f"  Processed {i+1}/{len(self.files)} files...")
            
            # Construct the Aspera command to upload the temporary directory
            cmd = f'"{aspera_path}" -i "{key_path}" -QT -l100m -k1 -d "{temp_dir}" {upload_destination}'
            
            # Log the command
            logger.info(f"Running command: {cmd}")
            print(f"\nStarting Aspera upload of {len(self.files)} files...")
            print(f"This may take a while depending on the size of your files.")
            
            # Execute the command using os.system()
            return_code = os.system(cmd)
            
            if return_code == 0:
                logger.info("File upload completed successfully")
                print("\nFile upload completed successfully!")
                
                # Create an empty submit.ready file
                ready_file = os.path.join(temp_dir, "submit.ready")
                with open(ready_file, "w") as f:
                    f.write("    ")
                
                # Determine the destination directory name
                temp_dir_name = os.path.basename(os.path.normpath(temp_dir))
                upload_destination_with_dir = f"{upload_destination}/{temp_dir_name}"
                
                # Upload the submit.ready file to signal completion
                print("\nUploading submit.ready file to complete submission...")
                submit_cmd = f'"{aspera_path}" -i "{key_path}" -QT "{ready_file}" {upload_destination_with_dir}'
                logger.info(f"Running command: {submit_cmd}")
                
                submit_return_code = os.system(submit_cmd)
                
                if submit_return_code == 0:
                    logger.info("Submit.ready file uploaded successfully")
                    print("\nSubmission completed successfully!")
                    print("\nTo complete your submission:")
                    print("1. Log into NCBI Submission Portal: https://submit.ncbi.nlm.nih.gov/")
                    print("2. Select 'New Submission' and choose 'Sequence Read Archive (SRA)'")
                    print("3. Follow the prompts to associate your uploaded files with your metadata")
                    return True
                else:
                    logger.error(f"Failed to upload submit.ready file: {submit_return_code}")
                    print("\nWarning: Files were uploaded but the submission marker failed.")
                    print("Please contact NCBI SRA support for assistance.")
                    return False
            else:
                logger.error(f"Aspera upload failed with return code: {return_code}")
                print(f"\nAspera upload failed with return code: {return_code}")
                print("If you haven't specified the full path to ascp, try using --aspera-path")
                print("Common locations are:")
                print("  Linux: ~/.aspera/connect/bin/ascp")
                print("  macOS: ~/Applications/Aspera Connect.app/Contents/Resources/ascp")
                print("  Windows: C:/Program Files/Aspera/Aspera Connect/bin/ascp.exe")
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
        description="SRA Metagenomic Data Submission Tool"
    )
    
    parser.add_argument('--config', help='Path to configuration JSON file')
    parser.add_argument('--metadata', required=True, help='Path to metadata CSV or Excel file')
    parser.add_argument('--files', help='Directory containing sequence files')
    parser.add_argument('--submit', action='store_true', help='Submit to SRA after preparing')
    parser.add_argument('--aspera-key', help='Path to Aspera key file')
    parser.add_argument('--aspera-path', help='Full path to the Aspera Connect (ascp) executable')
    parser.add_argument('--upload-destination', help='NCBI upload destination (e.g., subasp@upload.ncbi.nlm.nih.gov:uploads/your_folder)')
    parser.add_argument('--submission-name', help='Custom name for this submission (used in log filename)')
    
    args = parser.parse_args()
    
    # Re-initialize logging with submission name if provided
    if args.submission_name:
        global log_filename
        log_filename = setup_logging(args.submission_name)
        logger.info(f"Using submission name: {args.submission_name}")
    
    # Initialize submission object
    submission = SRASubmission(args.config)
    
    # Load and process metadata
    num_samples = submission.load_metadata(args.metadata)
    print(f"Loaded {num_samples} samples from metadata file")
    
    # Collect sequence files
    num_files = submission.collect_sequence_files(args.files)
    
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
            print("\nSubmission process completed.")
        else:
            print("File upload failed. See log file for details.")
            sys.exit(1)
    else:
        print("\nFiles identified but not uploaded (--submit flag not used).")
        print("To upload files, run again with the --submit flag.")


if __name__ == "__main__":
    main()
