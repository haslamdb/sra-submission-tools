#!/usr/bin/env python3
"""
Enhanced SRA Metagenomic Data Submission Script

This script automates the process of preparing and submitting metagenomic data
to NCBI's Sequence Read Archive (SRA). It helps generate required metadata
files and uploads data using the NCBI submission portal API.

Enhancements:
- Metadata preparation from various input formats
- File verification to ensure all files exist
- Automatic detection of paired-end files
- Support for building metadata from files directly
"""

import os
import sys
import json
import argparse
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import logging
import re
from datetime import datetime
from pathlib import Path

# Import utility functions
try:
    from sra_utils import (
        prepare_metadata, 
        verify_files, 
        detect_file_pairs,
        collect_fastq_files,
        build_sample_metadata
    )
except ImportError:
    # If sra_utils is not installed, check if it exists in the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(current_dir)
    try:
        from sra_utils import (
            prepare_metadata, 
            verify_files, 
            detect_file_pairs,
            collect_fastq_files,
            build_sample_metadata
        )
    except ImportError:
        print("Error: sra_utils module not found. Please ensure sra_utils.py is in the same directory.")
        sys.exit(1)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("sra_submission.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# NCBI API endpoints
# Note: These are example URLs; you'll need to use the actual NCBI API endpoints
NCBI_AUTH_URL = "https://www.ncbi.nlm.nih.gov/projects/r_submit/api/auth"
NCBI_UPLOAD_URL = "https://www.ncbi.nlm.nih.gov/projects/r_submit/api/upload"
NCBI_SUBMIT_URL = "https://submit.ncbi.nlm.nih.gov/subs/"

class SRASubmission:
    """Class to handle SRA submission process for metagenomic data."""
    
    def __init__(self, config_file=None):
        """Initialize the submission class with configuration settings."""
        self.config = {}
        self.metadata = {}
        self.files = []
        self.session_token = None
        self.config_file = config_file  # Store config_file path for later use
        
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

    def upload_files_with_aspera(self, files_dir=None, key_path=None, upload_destination=None, aspera_path=None):
        """
        Upload files using Aspera command line.
        
        Args:
            files_dir: Directory containing files to upload (defaults to directory of first file)
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
        
        # If no directory is specified, use the directory of the first file
        if not files_dir and self.files:
            files_dir = str(Path(self.files[0]).parent)
        
        if not files_dir:
            logger.error("Files directory is required")
            return False
        
        try:
            # If aspera_path is not provided, try to find it in common locations
            if not aspera_path:
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
                        aspera_path = expanded_path
                        logger.info(f"Found Aspera client at: {aspera_path}")
                        break
                
                if not aspera_path:
                    logger.warning("Could not automatically find Aspera Connect client (ascp)")
                    print("\nWarning: Could not automatically find Aspera Connect client (ascp).")
                    print("Trying 'ascp' command directly, which may fail if not in your PATH.")
                    aspera_path = "ascp"
            
            logger.info(f"Using Aspera client at: {aspera_path}")
            logger.info(f"Uploading files with Aspera from {files_dir}")
            
            # Construct the Aspera command for uploading all files
            # Use proper quoting to handle paths with spaces
            cmd = f'"{aspera_path}" -i "{key_path}" -QT -l100m -k1 -d "{files_dir}" {upload_destination}'
            
            # Log the command
            logger.info(f"Running command: {cmd}")
            print(f"\nStarting Aspera upload from {files_dir}...")
            print(f"This may take a while depending on the size of your files.")
            
            # Execute the command using os.system()
            return_code = os.system(cmd)
            
            if return_code == 0:
                logger.info("File upload completed successfully")
                print("\nFile upload completed successfully!")
                
                # Create an empty submit.ready file
                ready_file = os.path.join(files_dir, "submit.ready")
                with open(ready_file, "w") as f:
                    f.write("    ")
                
                # Determine the destination directory name
                files_dir_name = os.path.basename(os.path.normpath(files_dir))
                upload_destination_with_dir = f"{upload_destination}/{files_dir_name}"
                
                # Upload the submit.ready file to signal completion
                print("\nUploading submit.ready file to complete submission...")
                submit_cmd = f'"{aspera_path}" -i "{key_path}" -QT "{ready_file}" {upload_destination_with_dir}'
                logger.info(f"Running command: {submit_cmd}")
                
                submit_return_code = os.system(submit_cmd)
                
                if submit_return_code == 0:
                    logger.info("Submit.ready file uploaded successfully")
                    print("\nSubmission completed successfully!")
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

    def authenticate(self):
        """Authenticate with NCBI SRA using API key or username/password."""
        if 'api_key' in self.config:
            # Preferred method - API key
            auth_data = {'api_key': self.config['api_key']}
            auth_type = "API key"
        elif 'access_token' in self.config:
            # Alternative - existing access token
            self.session_token = self.config['access_token'] 
            logger.info("Using provided access token for authentication")
            return
        elif 'username' in self.config and 'password' in self.config:
            # Traditional username/password
            auth_data = {
                'username': self.config['username'],
                'password': self.config['password']
            }
            auth_type = "username/password"
        else:
            logger.error("Authentication credentials not found in config. "
                        "Please provide an API key, access token, or username/password.")
            print("\nAuthentication Error: No valid credentials found.")
            print("If you use Gmail or other third-party login for NCBI:")
            print("1. Generate an API key at https://www.ncbi.nlm.nih.gov/account/settings/")
            print("2. Add this key to your config.json file as 'api_key'")
            sys.exit(1)
        
        try:
            logger.info(f"Authenticating with NCBI using {auth_type}")
            response = requests.post(NCBI_AUTH_URL, json=auth_data)
            response.raise_for_status()
            self.session_token = response.json().get('session_token')
            if not self.session_token:
                raise ValueError("Session token not found in response")
            logger.info("Successfully authenticated with NCBI")
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            print("\nAuthentication failed. Please verify your credentials.")
            print("If you use Gmail or third-party login, generate an API key at:")
            print("https://www.ncbi.nlm.nih.gov/account/settings/")
            sys.exit(1)
    
    def collect_metadata_interactive(self):
        """Interactively collect metadata from user input."""
        print("\n=== BioProject Information ===")
        bioproject_id = input("BioProject ID (leave blank to create new): ").strip()
        project_title = input("Project Title: ").strip()
        project_description = input("Project Description: ").strip()
        
        print("\n=== BioSample Information ===")
        sample_source = input("Sample Source (environmental, host-associated, etc.): ").strip()
        collection_date = input("Collection Date (YYYY-MM-DD): ").strip()
        geo_loc_name = input("Geographic Location (country:region): ").strip()
        lat_lon = input("Latitude and Longitude (decimal degrees): ").strip()
        
        print("\n=== Library Information ===")
        library_strategy = input("Library Strategy (e.g., WGS, AMPLICON): ").strip() or "WGS"
        library_source = input("Library Source (e.g., METAGENOMIC, GENOMIC): ").strip() or "METAGENOMIC"
        library_selection = input("Library Selection (e.g., RANDOM, PCR): ").strip() or "RANDOM"
        
        print("\n=== Sequencing Platform ===")
        platform = input("Sequencing Platform (ILLUMINA, OXFORD_NANOPORE, etc.): ").strip() or "ILLUMINA"
        instrument_model = input("Instrument Model (e.g., Illumina MiSeq): ").strip() or "Illumina MiSeq"
        
        # Collect sample-specific metadata
        print("\n=== Environment-specific Metadata ===")
        env_metadata = {}
        if sample_source.lower() == "environmental":
            env_metadata["env_biome"] = input("Environmental Biome: ").strip()
            env_metadata["env_feature"] = input("Environmental Feature: ").strip()
            env_metadata["env_material"] = input("Environmental Material: ").strip()
            env_metadata["depth"] = input("Depth (m): ").strip()
            env_metadata["altitude"] = input("Altitude (m): ").strip()
        elif sample_source.lower() == "host-associated":
            env_metadata["host"] = input("Host Scientific Name: ").strip()
            env_metadata["host_tissue"] = input("Host Tissue: ").strip()
            env_metadata["isolation_source"] = input("Isolation Source: ").strip()
        
        self.metadata = {
            "bioproject_id": bioproject_id,
            "project_title": project_title,
            "project_description": project_description,
            "sample_source": sample_source,
            "collection_date": collection_date,
            "geo_loc_name": geo_loc_name,
            "lat_lon": lat_lon,
            "library_strategy": library_strategy,
            "library_source": library_source,
            "library_selection": library_selection,
            "platform": platform,
            "instrument_model": instrument_model,
            "environment_metadata": env_metadata
        }
        
        logger.info("Collected metadata through interactive input")
    
    def collect_metadata_from_file(self, metadata_file):
        """Load metadata from a CSV or Excel file with enhanced processing."""
        try:
            # Use the prepare_metadata utility for enhanced processing
            sra_df = prepare_metadata(metadata_file, config_file=self.config_file if hasattr(self, 'config_file') else None)
            
            # Convert first row to metadata dictionary
            if len(sra_df) > 0:
                self.metadata = sra_df.iloc[0].to_dict()
                
                # Handle environment-specific metadata columns
                env_cols = [col for col in sra_df.columns if col.startswith('env_')]
                if env_cols:
                    self.metadata['environment_metadata'] = {}
                    for col in env_cols:
                        self.metadata['environment_metadata'][col] = sra_df.iloc[0][col]
                        
                logger.info(f"Loaded metadata from {metadata_file}")
            else:
                logger.error("Metadata file is empty")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to load metadata from file: {str(e)}")
            sys.exit(1)
    
    def validate_metadata(self):
        """Validate the collected metadata for required fields."""
        required_fields = [
            "project_title", "library_strategy", "library_source", 
            "library_selection", "platform", "instrument_model"
        ]
        
        missing_fields = [field for field in required_fields if not self.metadata.get(field)]
        
        if missing_fields:
            logger.error(f"Missing required metadata fields: {', '.join(missing_fields)}")
            return False
        
        # Validate date format
        if self.metadata.get('collection_date'):
            try:
                datetime.strptime(self.metadata['collection_date'], '%Y-%m-%d')
            except ValueError:
                logger.error("Invalid collection date format. Use YYYY-MM-DD")
                return False
        
        logger.info("Metadata validation successful")
        return True
    
    def collect_sequence_files(self, file_dir=None):
        """Collect sequence files for submission, only including files mentioned in metadata."""
        if not hasattr(self, 'metadata') or not self.metadata:
            logger.warning("No metadata available for file filtering")
            return
            
        # Check if we have filename information in the metadata
        filename_keys = ['filename', 'filename2', 'filepath', 'filepath2', 'file1', 'file2']
        available_keys = [key for key in filename_keys if key in self.metadata and self.metadata[key]]
        
        if not available_keys:
            logger.warning("No filename information found in metadata")
            return
        
        self.files = []
        file_count = 0
        missing_files = []
        
        # Process file entries from metadata
        for key in available_keys:
            filename = self.metadata[key]
            if not filename or pd.isna(filename):
                continue
                
            # Handle both absolute and relative paths
            if os.path.isabs(filename):
                file_path = filename
            elif file_dir:
                file_path = os.path.join(file_dir, filename)
            else:
                file_path = filename
                
            # Check if file exists
            if os.path.exists(file_path):
                self.files.append(file_path)
                file_count += 1
            else:
                missing_files.append(file_path)
        
        if missing_files:
            logger.warning(f"Could not find {len(missing_files)} files mentioned in metadata:")
            for file in missing_files[:5]:  # Show first 5 missing files
                logger.warning(f"  - {file}")
            if len(missing_files) > 5:
                logger.warning(f"  ... and {len(missing_files) - 5} more")
                
            print(f"\nWarning: {len(missing_files)} files mentioned in metadata are missing.")
            print("You may need to check file paths in your metadata file.")
            
        if file_count > 0:
            logger.info(f"Found {file_count} sequence files from metadata")
        else:
            logger.warning("No files found from metadata information")
            
            # If no files found from metadata, offer to scan directory as fallback
            if file_dir:
                print("\nNo files found using metadata information.")
                print("Would you like to scan the directory for FASTQ files? [y/N]")
                response = input("> ").strip().lower()
                if response == 'y':
                    # Use the collect_fastq_files utility for file detection
                    fastq_files = collect_fastq_files(file_dir)
                    
                    if not fastq_files:
                        logger.warning(f"No FASTQ files found in {file_dir}")
                    else:
                        # Detect paired files
                        file_pairs = detect_file_pairs(fastq_files)
                        
                        # Flatten the pairs into a list of files
                        self.files = []
                        for file1, file2 in file_pairs:
                            self.files.append(file1)
                            if file2:
                                self.files.append(file2)
                        
                        logger.info(f"Found {len(self.files)} sequence files in {file_dir}")
                        
                        # Ask if user wants to build metadata from files
                        if not self.metadata:
                            print(f"\nFound {len(file_pairs)} sample(s) in {file_dir}.")
                            print("Would you like to build metadata from these files? [y/N]")
                            response = input("> ").strip().lower()
                            if response == 'y':
                                # Build metadata from file pairs
                                sra_df = build_sample_metadata(
                                    file_pairs, 
                                    config_file=self.config_file if hasattr(self, 'config_file') else None
                                )
                                if len(sra_df) > 0:
                                    self.metadata = sra_df.iloc[0].to_dict()
                                    logger.info("Built metadata from sequence files")
            else:
                # Interactive file collection as fallback
                print("\n=== Sequence Files ===")
                print("Enter file paths (one per line, empty line to finish):")
                while True:
                    file_path = input("> ").strip()
                    if not file_path:
                        break
                    if os.path.exists(file_path):
                        self.files.append(file_path)
                    else:
                        logger.warning(f"File not found: {file_path}")
                
                logger.info(f"Added {len(self.files)} sequence files")

    def verify_sequence_files(self):
        """Verify that all sequence files exist."""
        missing_files = []
        
        for file_path in self.files:
            if not os.path.exists(file_path):
                missing_files.append(file_path)
        
        if missing_files:
            logger.error(f"Missing {len(missing_files)} sequence files:")
            for file in missing_files[:10]:  # Show first 10 missing files
                logger.error(f"  - {file}")
            if len(missing_files) > 10:
                logger.error(f"  ... and {len(missing_files) - 10} more")
            
            print(f"\nWarning: {len(missing_files)} sequence files are missing.")
            print("Would you like to continue anyway? [y/N]")
            response = input("> ").strip().lower()
            
            return response == 'y'
        
        logger.info(f"All {len(self.files)} sequence files verified")
        return True
    
    def upload_files(self):
        """Upload sequence files to NCBI SRA."""
        if not self.session_token:
            logger.error("Not authenticated. Call authenticate() first")
            return False
        
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        for file_path in self.files:
            try:
                file_name = os.path.basename(file_path)
                logger.info(f"Uploading {file_name}...")
                
                with open(file_path, 'rb') as f:
                    files = {'file': (file_name, f)}
                    response = requests.post(
                        NCBI_UPLOAD_URL,
                        headers=headers,
                        files=files
                    )
                    response.raise_for_status()
                
                logger.info(f"Successfully uploaded {file_name}")
            except Exception as e:
                logger.error(f"Failed to upload {file_name}: {str(e)}")
                return False
        
        return True
    
    def submit(self, submission_xml_path):
        """Submit the prepared package to NCBI SRA."""
        if not self.session_token:
            logger.error("Not authenticated. Call authenticate() first")
            return False
        
        try:
            logger.info("Submitting to NCBI SRA...")
            
            headers = {"Authorization": f"Bearer {self.session_token}"}
            
            with open(submission_xml_path, 'rb') as f:
                files = {'submission_xml': f}
                response = requests.post(
                    NCBI_SUBMIT_URL,
                    headers=headers,
                    files=files
                )
                response.raise_for_status()
            
            result = response.json()
            if result.get('status') == 'success':
                logger.info(f"Submission successful! Submission ID: {result.get('submission_id')}")
                return True
            else:
                logger.error(f"Submission failed: {result.get('message', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to submit: {str(e)}")
            return False
    
    def prepare_submission_package(self, output_dir):
        """Prepare the XML submission package."""
        os.makedirs(output_dir, exist_ok=True)
        
        # Create submission XML
        submission = ET.Element("Submission")
        
        # BioProject section
        bioproject = ET.SubElement(submission, "BioProject")
        if self.metadata.get('bioproject_id'):
            bioproject.set("accession", self.metadata['bioproject_id'])
        else:
            project = ET.SubElement(bioproject, "Project")
            title = ET.SubElement(project, "Title")
            title.text = self.metadata.get('project_title', 'Metagenomic Project')
            description = ET.SubElement(project, "Description")
            description.text = self.metadata.get('project_description', '')
        
        # BioSample section
        biosample = ET.SubElement(submission, "BioSample")
        sample_attributes = ET.SubElement(biosample, "Attributes")
        
        # Add basic attributes
        for key, label in [
            ("sample_source", "sample_source"),
            ("collection_date", "collection_date"),
            ("geo_loc_name", "geo_loc_name"),
            ("lat_lon", "lat_lon")
        ]:
            if self.metadata.get(key):
                attr = ET.SubElement(sample_attributes, "Attribute")
                attr.set("name", label)
                attr.text = self.metadata[key]
        
        # Add environment-specific attributes
        if 'environment_metadata' in self.metadata:
            for key, value in self.metadata['environment_metadata'].items():
                if value:
                    attr = ET.SubElement(sample_attributes, "Attribute")
                    attr.set("name", key)
                    attr.text = value
        
        # SRA section
        sra = ET.SubElement(submission, "SRA")
        
        # Library descriptors
        library_descriptor = ET.SubElement(sra, "LibraryDescriptor")
        for key, label in [
            ("library_strategy", "LIBRARY_STRATEGY"),
            ("library_source", "LIBRARY_SOURCE"),
            ("library_selection", "LIBRARY_SELECTION")
        ]:
            element = ET.SubElement(library_descriptor, label)
            element.text = self.metadata.get(key, '')
        
        # Platform
        platform_elem = ET.SubElement(sra, "Platform")
        platform_type = ET.SubElement(platform_elem, self.metadata.get('platform', 'ILLUMINA'))
        model = ET.SubElement(platform_type, "INSTRUMENT_MODEL")
        model.text = self.metadata.get('instrument_model', '')
        
        # Files
        files_elem = ET.SubElement(sra, "Files")
        for file_path in self.files:
            file_elem = ET.SubElement(files_elem, "File")
            file_elem.set("name", os.path.basename(file_path))
            file_elem.set("type", "fastq")
            
            # Try to determine paired-end info from filename
            if re.search(r'_R?1[_\.]', os.path.basename(file_path)):
                file_elem.set("read", "1")
            elif re.search(r'_R?2[_\.]', os.path.basename(file_path)):
                file_elem.set("read", "2")
        
        # Write to XML file
        submission_xml_path = os.path.join(output_dir, "submission.xml")
        tree = ET.ElementTree(submission)
        tree.write(submission_xml_path, encoding="UTF-8", xml_declaration=True)
        
        # Generate metadata TSV file
        metadata_path = os.path.join(output_dir, "metadata.tsv")
        with open(metadata_path, 'w') as f:
            # Write header
            f.write("\t".join(self.metadata.keys()) + "\n")
            
            # Write values
            values = []
            for key in self.metadata.keys():
                if key == 'environment_metadata' and isinstance(self.metadata[key], dict):
                    values.append(json.dumps(self.metadata[key]))
                else:
                    values.append(str(self.metadata.get(key, '')))
            f.write("\t".join(values) + "\n")
        
        logger.info(f"Created submission package in {output_dir}")
        logger.info(f"Submission XML: {submission_xml_path}")
        logger.info(f"Metadata TSV: {metadata_path}")
        
        return submission_xml_path
    
def main():
    """Main entry point for the SRA submission tool."""
    # Set up argument parsing
    parser = argparse.ArgumentParser(
        description="SRA Metagenomic Data Submission Tool"
    )
    
    # Add command-line arguments
    parser.add_argument('--config', help='Path to configuration JSON file')
    parser.add_argument('--metadata', help='Path to metadata CSV or Excel file')
    parser.add_argument('--files', help='Directory containing sequence files')
    parser.add_argument('--output', default='sra_submission', help='Output directory for submission package')
    parser.add_argument('--submit', action='store_true', help='Submit to SRA after preparing package')
    parser.add_argument('--prepare-metadata', help='Prepare SRA-compatible metadata and save to specified file')
    parser.add_argument('--verify-only', action='store_true', help='Only verify files, do not create submission package')
    parser.add_argument('--auto-pair', action='store_true', help='Automatically detect paired-end files')
    # Add command-line arguments for Aspera
    parser.add_argument('--aspera-key', help='Path to Aspera key file')
    parser.add_argument('--aspera-path', help='Full path to the Aspera Connect (ascp) executable')
    parser.add_argument('--upload-destination', help='NCBI upload destination (e.g., subasp@upload.ncbi.nlm.nih.gov:uploads/your_folder)')
    
    args = parser.parse_args()
    
    # Handle metadata preparation only mode
    if args.prepare_metadata:
        if not args.metadata:
            print("Error: --metadata argument is required with --prepare-metadata")
            sys.exit(1)
        try:
            sra_df = prepare_metadata(args.metadata, args.prepare_metadata, args.config)
            print(f"Prepared SRA metadata saved to {args.prepare_metadata}")
            sys.exit(0)
        except Exception as e:
            print(f"Error preparing metadata: {str(e)}")
            sys.exit(1)
    
    # Initialize SRA submission object
    submission = SRASubmission(args.config)
    
    # Collect metadata (from file or interactively)
    if args.metadata:
        submission.collect_metadata_from_file(args.metadata)
    else:
        submission.collect_metadata_interactive()
    
    # Validate metadata
    if not submission.validate_metadata():
        print("Metadata validation failed. Please correct the issues and try again.")
        sys.exit(1)
    
    # Collect sequence files
    if args.files:
        submission.collect_sequence_files(args.files)
    else:
        submission.collect_sequence_files()
    
    # Verify files exist
    if not submission.verify_sequence_files():
        print("File verification failed. Some files are missing.")
        sys.exit(1)
    
    # If only verifying files, exit here
    if args.verify_only:
        print("File verification completed successfully.")
        sys.exit(0)
    
    # Prepare submission package
    submission_xml_path = submission.prepare_submission_package(args.output)
    print(f"\nSubmission package prepared in {args.output}")
    
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
        if submission.upload_files_with_aspera(args.files, key_path, upload_destination, args.aspera_path):
            print("\nFiles uploaded successfully!")
            print("\nTo complete your submission:")
            print("1. Log into NCBI Submission Portal: https://submit.ncbi.nlm.nih.gov/")
            print("2. Select 'New Submission' and choose 'Sequence Read Archive (SRA)'")
            print("3. Follow the prompts to associate your uploaded files with your metadata")
            print(f"4. You can use the metadata files in {args.output} to help complete the submission")
        else:
            print("File upload failed. See log file for details.")
            sys.exit(1)
    else:
        print("\nSubmission package prepared. To upload files and submit to SRA later:")
        print(f"1. Use Aspera to upload your files:")
        print(f"   ascp -i /path/to/key_file -QT -l100m -k1 -d {args.files} subasp@upload.ncbi.nlm.nih.gov:uploads/your_folder")
        print(f"2. Complete the submission through the NCBI Submission Portal: https://submit.ncbi.nlm.nih.gov/")


if __name__ == "__main__":
    main()