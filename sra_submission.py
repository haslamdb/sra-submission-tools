#!/usr/bin/env python3
"""
SRA Metagenomic Data Submission Script

This script automates the process of preparing and submitting metagenomic data
to NCBI's Sequence Read Archive (SRA). It helps generate required metadata
files and uploads data using the NCBI submission portal API.
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
NCBI_SUBMIT_URL = "https://www.ncbi.nlm.nih.gov/projects/r_submit/api/submit"

class SRASubmission:
    """Class to handle SRA submission process for metagenomic data."""
    
    def __init__(self, config_file=None):
        """Initialize the submission class with configuration settings."""
        self.config = {}
        self.metadata = {}
        self.files = []
        self.session_token = None
        
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
    
# In the authenticate method of our SRASubmission class:

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
        """Load metadata from a CSV or Excel file."""
        try:
            if metadata_file.endswith('.csv'):
                df = pd.read_csv(metadata_file)
            elif metadata_file.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(metadata_file)
            else:
                logger.error(f"Unsupported metadata file format: {metadata_file}")
                sys.exit(1)
            
            # Convert first row to metadata dictionary
            if len(df) > 0:
                self.metadata = df.iloc[0].to_dict()
                # Handle environment-specific metadata columns
                env_cols = [col for col in df.columns if col.startswith('env_')]
                if env_cols:
                    self.metadata['environment_metadata'] = {}
                    for col in env_cols:
                        self.metadata['environment_metadata'][col] = df.iloc[0][col]
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
        """Collect sequence files for submission."""
        if file_dir:
            # Auto-detect sequence files from directory
            path = Path(file_dir)
            fastq_files = list(path.glob("*.fastq")) + list(path.glob("*.fq")) + \
                         list(path.glob("*.fastq.gz")) + list(path.glob("*.fq.gz"))
            
            if not fastq_files:
                logger.warning(f"No FASTQ files found in {file_dir}")
            else:
                self.files = [str(f) for f in fastq_files]
                logger.info(f"Found {len(self.files)} sequence files in {file_dir}")
        else:
            # Interactive file collection
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


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Automate SRA submission for metagenomic data")
    parser.add_argument("--config", help="Path to configuration file (JSON)")
    parser.add_argument("--metadata", help="Path to metadata file (CSV/Excel)")
    parser.add_argument("--files", help="Directory containing sequence files")
    parser.add_argument("--output", default="sra_submission", help="Output directory for submission package")
    parser.add_argument("--submit", action="store_true", help="Submit to SRA (requires authentication)")
    
    args = parser.parse_args()
    
    # Initialize submission handler
    submission = SRASubmission(args.config)
    
    # Collect metadata
    if args.metadata:
        submission.collect_metadata_from_file(args.metadata)
    else:
        submission.collect_metadata_interactive()
    
    # Validate metadata
    if not submission.validate_metadata():
        logger.error("Metadata validation failed. Please correct the issues and try again.")
        sys.exit(1)
    
    # Collect sequence files
    submission.collect_sequence_files(args.files)
    
    if not submission.files:
        logger.error("No sequence files specified")
        sys.exit(1)
    
    # Prepare submission package
    submission_xml_path = submission.prepare_submission_package(args.output)
    
    # Submit if requested
    if args.submit:
        submission.authenticate()
        if submission.upload_files():
            submission.submit(submission_xml_path)
    else:
        logger.info(f"Submission package prepared in {args.output}")
        logger.info("Run with --submit to submit to SRA")


if __name__ == "__main__":
    main()
