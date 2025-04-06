# SRA Metagenomic Data Submission Tool

A Python package to automate the submission of metagenomic data to NCBI's Sequence Read Archive (SRA).

## Overview

Submission of raw sequence files to the SRA database is a pain. Metadata file formatting requirements are unforgiving. Navigating the project and sample submission process is complex for first time users. 

This package provides tools to make preparation and submission of metagenomic sequence data to the SRA database somewhat less painful. It helps with:

- Creating required metadata files in the correct format
- Organizing sequence files according to SRA requirements
- Automating the submission process via the NCBI Submission Portal API
- Verifying files and metadata before submission
- Handling file uploads using IBM Aspera Connect

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Understanding the SRA Submission Process](#understanding-the-sra-submission-process)
- [Using the Scripts](#using-the-scripts)
- [Configuration](#configuration)
- [Metadata Requirements](#metadata-requirements)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Installation

### Using pipx (Recommended)

[pipx](https://pypa.github.io/pipx/) is the recommended installation method as it creates an isolated environment for the package, avoids dependency conflicts with other Python applications, and makes the command-line tools accessible system-wide.

```bash
# Install pipx if you don't have it already
python -m pip install --user pipx
python -m pipx ensurepath

# Install the package
pipx install git+https://github.com/yourusername/sra-metagenome-submission.git

# The sra-submit command should now be available in your PATH
sra-submit --help
```

### Using Conda

```bash
# Create and activate a conda environment with required dependencies
conda create -n sra-tools python=3.12 pandas requests openpyxl
conda activate sra-tools

# Clone the repository
git clone https://github.com/yourusername/sra-metagenome-submission.git
cd sra-metagenome-submission

# Install in development mode
pip install -e .
```

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/sra-metagenome-submission.git
cd sra-metagenome-submission

# Install using pip with pyproject.toml
pip install .
```

## Quick Start

```bash
# Using pipx-installed command-line tool
sra-submit --config config.json --metadata test_metadata.csv --files /path/to/sequence/files --output submission_package

# Or, if using conda environment
conda activate sra-tools
sra-submit --config config.json --metadata test_metadata.csv --files /path/to/sequence/files --output submission_package

# Submit to SRA (requires authentication)
sra-submit --config config.json --metadata test_metadata.csv --files /path/to/sequence/files --output submission_package --submit --submission-name my_project_name
```

## Understanding the SRA Submission Process

### First-Time Setup

1. **Create NCBI Account**:
   - Go to [NCBI](https://www.ncbi.nlm.nih.gov/)
   - Click "Log in" and then "Register" if you don't have an account

2. **Install Aspera Connect**:
   - Download the Aspera Connect installer from [IBM's website](https://www.ibm.com/products/aspera/downloads#cds)
   - For Linux users, this will download a bash script that you need to run to complete the installation
   - The filepath to ascp (e.g., `/home/username/.aspera/connect/bin/ascp`) will be needed during the submission process
   - You can provide this path using the `--aspera-path` parameter

3. **Obtain Aspera Key File**:
   - Download the `aspera.openssh` key file from NCBI: [https://submit.ncbi.nlm.nih.gov/preload/aspera_key/](https://submit.ncbi.nlm.nih.gov/preload/aspera_key/)
   - **Important**: Copy and paste the downloaded file from your downloads folder to a secure location. Do not open and save it as a text file, as this would corrupt the file format.
   - Make note of the path to this key file as you'll need it for the submission process
   - You can provide this path using the `--aspera-key` parameter

4. **Obtain Upload Destination Path**:
   - Navigate to SRA submission start page [https://submit.ncbi.nlm.nih.gov/subs/sra/](https://submit.ncbi.nlm.nih.gov/subs/sra/)
   - Click "New Submission"
   - Request a personal account folder to pre-upload your sequence data files (for first-time users) by clicking on the button "Request preload folder" 
      - More instructions here: [https://www.ncbi.nlm.nih.gov/sra/docs/submitportal/](https://www.ncbi.nlm.nih.gov/sra/docs/submitportal/) 
   - You will receive an upload destination path in the format: `subasp@upload.ncbi.nlm.nih.gov:uploads/your_username_XYZ123`
   - Save this destination path for use in all subsequent submission processes
   - You can provide this path using the `--upload-destination` parameter

   - **Note:** Subsequent uploads will reuse your aspera.openssh key and submission destination `subasp@upload.ncbi.nlm.nih.gov:uploads/your_username_XYZ123`


### Complete Submission Process

The submission process is split into two main steps:

1. **Prepare and Upload Files**:
   ```bash
   sra-submit --config config.json --metadata your_metadata.csv --files /path/to/sequence/files --output submission_package --submit --submission-name my_project_name --aspera-key /path/to/aspera.openssh --upload-destination subasp@upload.ncbi.nlm.nih.gov:uploads/your_username_XYZ123
   ```
   
   The `--submission-name` parameter is optional but recommended as it:
   - Creates a descriptive name for your submission folder
   - Makes it easier to identify your submission in NCBI's system
   - Labels your log files for better organization
   - Helps with tracking multiple submissions

2. **Associate BioProject with the Preload Folder**:
   After successfully uploading your files, you'll need to associate them with your BioProject:
   
   - Log into [NCBI Submission Portal](https://submit.ncbi.nlm.nih.gov/)
   - Select "New Submission" and choose "Sequence Read Archive (SRA)"
   - Follow the submission wizard steps:
     - Select your BioProject ID (create one if needed)
     - Select your preload folder from the dropdown list
     - The system will automatically detect your uploaded files
     - Complete the submission wizard by providing any additional required metadata
     - The system will validate your submission and assign SRA accession numbers

   This second step must be done through NCBI's web interface as it requires interactive validation and confirmation of your submission metadata.

### Track Submission Status

After completing both steps:
   - Monitor your submission at [NCBI Submission Portal](https://submit.ncbi.nlm.nih.gov/)
   - Address any validation errors or issues
   - Receive accession numbers once submission is accepted
   - Note that processing can take several days to complete

### Important URLs

- NCBI Homepage: https://www.ncbi.nlm.nih.gov/
- SRA Homepage: https://www.ncbi.nlm.nih.gov/sra
- NCBI Submission Portal: https://submit.ncbi.nlm.nih.gov/
- BioProject Submission: https://submit.ncbi.nlm.nih.gov/subs/bioproject/
- BioSample Submission: https://submit.ncbi.nlm.nih.gov/subs/biosample/
- SRA Submission: https://submit.ncbi.nlm.nih.gov/subs/sra/

## Using the Scripts

this toolset includes scripts to streamline the SRA submission process, reducing manual steps and potential errors.

### Main Script: `sra_submission.py`

This is the primary script for preparing and submitting metagenomic data to SRA.

```bash
# Basic usage with interactive prompts
sra-submit --output submission_package

# Using metadata file and auto-detecting sequence files
sra-submit --metadata metadata.csv --files /path/to/fastq_files --output submission_package

# Full submission with authentication
sra-submit --config config.json --metadata metadata.csv --files /path/to/fastq_files --output submission_package --submit --submission-name my_project_name

# Prepare SRA-compatible metadata from your existing metadata file
sra-submit --config config.json --metadata your_metadata.csv --prepare-metadata sra_metadata.csv

# Verify that all sequence files exist
sra-submit --config config.json --metadata sra_metadata.csv --files /path/to/sequence/files --verify-only
```

### Command-line Arguments

- `--config`: Path to JSON configuration file with authentication and defaults
- `--metadata`: Path to CSV/Excel file containing sample metadata
- `--files`: Directory containing sequence files (will auto-detect FASTQ/FQ/FASTQ.GZ files)
- `--output`: Directory to store generated submission files (default: sra_submission)
- `--submit`: Flag to submit data to SRA (requires authentication)
- `--submission-name`: Provide a descriptive name for your submission (used in log files and NCBI folder names)
- `--aspera-key`: Path to your Aspera key file (required for submission)
- `--aspera-path`: Full path to the Aspera Connect (ascp) executable
- `--upload-destination`: NCBI upload destination (e.g., subasp@upload.ncbi.nlm.nih.gov:uploads/your_username_XYZ123)
- `--prepare-metadata`: Prepare SRA-compatible metadata from input file and save to specified output file
- `--verify-only`: Only verify files without creating submission package
- `--auto-pair`: Automatically detect paired-end files

### Interactive Mode

If you run the script without specifying a metadata file, it will enter interactive mode to collect required information:

1. **BioProject Information**:
   - BioProject ID (if existing)
   - Project title and description

2. **BioSample Information**:
   - Sample source
   - Collection date
   - Geographic location
   - Latitude and longitude

3. **Library Information**:
   - Library strategy, source, and selection
   - Sequencing platform and instrument

4. **Environment-specific Metadata**:
   - For environmental samples: biome, feature, material, depth
   - For host-associated samples: host, tissue, isolation source

5. **Sequence Files**:
   - Paths to FASTQ files for submission

### Output Files

The script generates the following in your output directory:

- `submission.xml`: XML file formatted for SRA submission
- `metadata.tsv`: Tab-separated file containing all metadata
- Log files with details of the submission process

## Configuration

Create a JSON configuration file to store authentication credentials and default values.

Example `config.json`:

```json
{
  "api_key": "your_ncbi_api_key",
  "default_values": {
    "library_strategy": "WGS",
    "library_source": "METAGENOMIC",
    "library_selection": "RANDOM",
    "platform": "ILLUMINA",
    "instrument_model": "Illumina MiSeq"
  },
  "contact": {
    "name": "Your Name",
    "email": "your.email@example.com",
    "organization": "Your Organization"
  }
}
```

## Metadata Requirements

### Required Fields for Metagenomic Submissions

SRA submissions require specific metadata depending on the sample type. For metagenomic samples, ensure you include:

#### Basic Required Fields

- Project title
- Library strategy (e.g., WGS, AMPLICON)
- Library source (typically METAGENOMIC)
- Library selection (e.g., RANDOM, PCR)
- Platform (e.g., ILLUMINA, OXFORD_NANOPORE)
- Instrument model (e.g., Illumina MiSeq, MinION)

#### Environmental Sample Fields (MIxS Standards)

- Sample collection date (YYYY-MM-DD)
- Geographic location (country:region)
- Latitude and longitude (decimal degrees)
- Environmental biome
- Environmental feature
- Environmental material
- Depth (if applicable)
- Altitude (if applicable)

#### Host-associated Sample Fields

- Host scientific name
- Host tissue
- Isolation source

### Example Metadata CSV

```csv
bioproject_id,project_title,project_description,sample_source,collection_date,geo_loc_name,lat_lon,library_strategy,library_source,library_selection,platform,instrument_model,env_biome,env_feature,env_material,depth,altitude,host,host_tissue,isolation_source
PRJXXXXX,Marine Metagenome Project,Characterization of microbial communities in coastal waters,environmental,2023-07-15,USA:California,36.9513 N 122.0733 W,WGS,METAGENOMIC,RANDOM,ILLUMINA,Illumina NovaSeq 6000,marine biome,coastal water,sea water,10,0,,,
```

### Using the Submission Name Parameter

The `--submission-name` parameter offers several benefits:

1. **Organizationally** - Creates a descriptive folder name in your NCBI submission account, making it easier to identify your submission among multiple projects
2. **Traceability** - Creates dedicated log files with your submission name, which is helpful for troubleshooting or tracking
3. **Clarity** - Improves communication with NCBI support if you need to reference a specific submission
4. **Reusability** - Makes it easier to identify files for potential reuse in future submissions

Example usage:
```bash
sra-submit --config config.json --metadata my_samples.csv --files /data/fastq_files --submit --submission-name coral_microbiome_may2023
```

This will create both a log file and submission folder labeled with `coral_microbiome_may2023` for easy identification.

## Python API

You can also use the package as a Python library:

```python
from sra_submission import SRASubmission
from sra_utils import prepare_metadata, verify_files

# Prepare metadata
sra_df = prepare_metadata("your_metadata.csv", "sra_metadata.csv", "config.json")

# Initialize submission
submission = SRASubmission("config.json")

# Collect metadata and files
submission.collect_metadata_from_file("sra_metadata.csv")
submission.collect_sequence_files("/path/to/sequence/files")

# Verify files
if submission.verify_sequence_files():
    # Prepare submission package
    submission_xml_path = submission.prepare_submission_package("submission_package")
    
    # Submit to SRA
    submission.authenticate()
    if submission.upload_files():
        submission.submit(submission_xml_path)
```

## Development

### Package Structure

This package uses `pyproject.toml` for modern Python packaging:

```
sra-metagenome-submission/
├── pyproject.toml         # Package build configuration
├── README.md              # This file
├── LICENSE                # License file
├── src/                   # Source code directory
│   └── sra_metagenome_submission/
│       ├── __init__.py    # Package initialization
│       ├── sra_submission.py  # Main submission script
│       ├── sra_utils.py   # Utility functions
│       └── _version.py    # Version information
```

### Building and Testing

```bash
# Make sure you have build tools
pip install build

# Build the package
python -m build

# Install in development mode
pip install -e .
```

## Troubleshooting

### Common Submission Errors

1. **Missing Required Metadata**:
   - Ensure all required fields are completed
   - Pay attention to format (dates as YYYY-MM-DD, lat/lon as decimal degrees)

2. **Authentication Issues**:
   - Verify your NCBI API key in the config.json file
   - Check your network connection
   - Ensure your Aspera key file is valid and not corrupted

3. **File Format Problems**:
   - SRA accepts FASTQ, BAM, and SFF formats
   - Ensure files are properly compressed if using gzip
   - File names should not contain spaces or special characters

4. **Validation Errors**:
   - Read error messages carefully
   - Address each issue before resubmitting

5. **BioProject Association Issues**:
   - If your preload folder isn't showing up in the web interface, wait up to 30 minutes for NCBI's system to register it
   - Ensure you've completed the file upload step successfully before attempting to associate with a BioProject
   - Check that the submit.ready file was uploaded correctly (this signals to NCBI that your upload is complete)

6. **Aspera Connection Problems**:
   - Ensure your firewall allows Aspera's ports (typically 33001)
   - Verify you're using the correct path to the ascp executable 
   - Check that the aspera.openssh key file has not been corrupted (don't open it with text editors)

### Getting Help

If you encounter issues with the submission process:

1. Check NCBI's [SRA Submission Guide](https://www.ncbi.nlm.nih.gov/sra/docs/submit/)
2. Review the generated log files for detailed error messages
3. Contact NCBI Help Desk at info@ncbi.nlm.nih.gov
4. Open an issue on our GitHub repository with your log file attached (remove any sensitive information)

## License

This project is licensed under the MIT License - see the LICENSE file for details.
