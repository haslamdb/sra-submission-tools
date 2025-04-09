# SRA Metagenomic Data Submission Tool

A Python package to automate metadata preparation and submission of metagenomic data to NCBI's Sequence Read Archive (SRA).

## Overview

Submission of raw sequence files to the SRA database can be confusing and frustraing, even for experienced users. Navigating the submission process is complex and metadata formatting requirements are strict and unforgiving. 

This package provides tools to make preparation and submission of metagenomic sequence data to the SRA database somewhat less painful. It helps with:

- Creating required metadata files in the correct format
- Validating metadata against SRA requirements
- Organizing sequence files according to SRA requirements
- Automating the submission process via the NCBI Submission Portal
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

### Other Options
## Using Conda

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

## From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/sra-metagenome-submission.git
cd sra-metagenome-submission

# Install using pip with pyproject.toml
pip install .
```

### Quick Start

```bash
# Using pipx-installed command-line tool
sra-submit --config config.json --metadata sample-metadata.txt --bioproject-metadata bioproject-metadata.txt --files /path/to/sequence/files --output submission_package

# Or, if using conda environment
conda activate sra-tools
sra-submit --config config.json --metadata sample-metadata.txt --bioproject-metadata bioproject-metadata.txt --files /path/to/sequence/files --output submission_package

# Validate metadata files
sra-validate --config config.json --sample-metadata sample-metadata.txt --bioproject-metadata bioproject-metadata.txt
```

## The SRA Submission Process : First-Time Setup and Subsequent Submision Steps

### First-Time Setup

1. **Create NCBI Account**:
   - Go to [NCBI](https://www.ncbi.nlm.nih.gov/)
   - Click "Log in" and then "Register" if you don't have an account

2. **Generate NCBI API Key**:
   - Sign in to your NCBI account
   - Access your account settings by clicking on your username in the top right corner of any NCBI page
   - Scroll down to the "API Key Management" section
   - Click "Create an API Key" button to generate your key
   - Save this key for use in your config.json configuration file

3. **Install Aspera Connect**:
   - Download the Aspera Connect installer from [IBM's website](https://www.ibm.com/products/aspera/downloads#cds)
   - For Linux users, this will download a bash script that you will run to complete the installation as follows:
     ```bash
     wget https://d3gcli72yxqn2z.cloudfront.net/downloads/connect/latest/bin/ibm-aspera-connect_4.2.13.820_linux_x86_64.tar.gz
     
     tar -xzf ibm-aspera-connect_4.2.13.820_linux_x86_64.tar.gz
     
     ./ibm-aspera-connect_4.2.13.820_linux_x86_64.sh
     ```
   - Make note of the filepath to ascp (e.g., `/home/username/.aspera/connect/bin/ascp`) as it will be needed during each submission process
   - You can provide this path using the `--aspera-path` parameter or add to the config.json file created below

4. **Obtain Aspera Key File**:
   - Download the `aspera.openssh` key file from NCBI: [https://submit.ncbi.nlm.nih.gov/preload/aspera_key/](https://submit.ncbi.nlm.nih.gov/preload/aspera_key/)
   - **Important**: Copy and paste the downloaded file from your downloads folder to a secure location. Do not open and save it as a text file, as this would corrupt the file format.
   - Make note of the path to this key file as you'll need it for the submission process
   - You can provide this path using the `--aspera-key` parameter

5. **Obtain Upload Destination Path**:
   - The destination path will be your personal staging ground for uploaded files for this and subsequent submissions
   - Navigate to SRA submission start page [https://submit.ncbi.nlm.nih.gov/subs/sra/](https://submit.ncbi.nlm.nih.gov/subs/sra/)
   - Click "New Submission"
   - Request a personal account folder to pre-upload your sequence data files (for first-time users) by clicking on the button "Request preload folder" 
      - More instructions here: [https://www.ncbi.nlm.nih.gov/sra/docs/submitportal/](https://www.ncbi.nlm.nih.gov/sra/docs/submitportal/) 
   - You will receive an upload destination path in the format: `subasp@upload.ncbi.nlm.nih.gov:uploads/your_username_XYZ123`
   - Save this destination path for use in all subsequent submission processes
   - You can provide this path using the `--upload-destination` parameter

   - **Note:** Subsequent uploads will reuse your aspera.openssh key and submission destination

### Processes for Each Submission

After completing the first-time setup, follow these steps for each submission:

1. **Configure Default Settings in config.json (Optional but recommene)**:
   - Modify `config.json` with your information and defaults for required fields
   - This will save time by automatically filling in common fields across samples

2. **Generate Metadata Files**:
   - Create draft versions of two required metadata files:
     - `sample-metadata.txt` (or `.xlsx`) - Contains information about each sample and its files
     - `bioproject-metadata.txt` (or `.xlsx`) - Contains project-level information
   - Minimal input is a list of sample names and matching file names
   - Other values will be filled in using defaults from `config.json` or through runtime prompts

3. **Validate Metadata Files**:
   ```bash
   sra-validate --config config.json --sample-metadata sample-metadata.txt --bioproject-metadata bioproject-metadata.txt
   ```
   - This ensures your metadata meets SRA requirements
   - Fixes common formatting issues (dates, geographic coordinates, etc.)
   - Produces validated versions of both metadata files

4. **Submit through the NCBI Portal**:
   - Go to https://submit.ncbi.nlm.nih.gov/subs/sra/ and click "New Submission"
   - Follow these steps in the submission wizard:
     1. **Submitter**: Fill in your contact information
     2. **General Info**: Use default answers (No) for all questions
     3. **SRA Metadata**: 
        - Fill in Project Title and Information
        - Add Grants information if appropriate
        - Use default answers (No) for remaining questions
     4. **Select Biosample Type**: Choose "**Metagenome or environmental"
     5. **Biosample Attributes**: 
        - Select "Upload a file using Excel or text format (tab-delimited) that includes the attributes for each of your BioSamples"
        - Click "Choose File" and select your validated bioproject-metadata file
     6. **SRA Metadata**: Upload your validated sample-metadata file
     7. **Files**: 
        - Select the sample-metadata file
        - Verify as directed
        - Select "Automatically complete submission"
     8. **Review and Submit**: Verify all information is correct, then submit

### Track Submission Status

After completing your submission:
   - Monitor the status at [NCBI Submission Portal](https://submit.ncbi.nlm.nih.gov/)
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

This toolset includes scripts to streamline the SRA submission process, reducing manual steps and potential errors.

### Metadata Validation Script: `sra_validate.py`

This script validates your metadata files against SRA requirements and fixes common formatting issues.

```bash
# Basic usage
sra-validate --sample-metadata sample-metadata.txt --bioproject-metadata bioproject-metadata.txt

# With configuration file
sra-validate --config config.json --sample-metadata sample-metadata.txt --bioproject-metadata bioproject-metadata.txt

# Output validated files to specific locations
sra-validate --sample-metadata sample-metadata.txt --bioproject-metadata bioproject-metadata.txt --output-sample-metadata validated-sample-metadata.txt --output-bioproject-metadata validated-bioproject-metadata.txt
```

### Main Submission Script: `sra_submission.py`

This is the primary script for preparing and submitting metagenomic data to SRA.

```bash
# Basic usage with interactive prompts
sra-submit --output submission_package

# Using metadata files and auto-detecting sequence files
sra-submit --sample-metadata sample-metadata.txt --bioproject-metadata bioproject-metadata.txt --files /path/to/fastq_files --output submission_package

# Generate template metadata files from existing sequence files
sra-submit --files /path/to/fastq_files --generate-templates --output templates
```

### Command-line Arguments

- `--config`: Path to JSON configuration file with authentication and defaults
- `--sample-metadata`: Path to tab-delimited TXT or Excel file containing sample metadata
- `--bioproject-metadata`: Path to tab-delimited TXT or Excel file containing bioproject metadata
- `--files`: Directory containing sequence files (will auto-detect FASTQ/FQ/FASTQ.GZ files)
- `--output`: Directory to store generated submission files (default: sra_submission)
- `--generate-templates`: Generate template metadata files from detected sequence files
- `--validate-only`: Only validate files and metadata without creating submission package
- `--auto-pair`: Automatically detect paired-end files

### Interactive Mode

If you run the script without specifying metadata files, it will enter interactive mode to collect required information:

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

- Validated metadata files
- Log files with details of the validation and submission process

## Configuration

Create a JSON configuration file to store credentials and default values.

Example `config.json`:

```json
{
  "username": "your_ncbi_username",
  "password": "your_ncbi_password",
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

- Sample collection date (supported formats include "DD-Mmm-YYYY", "Mmm-YYYY", "YYYY" or ISO 8601 standard "YYYY-mm-dd", "YYYY-mm", "YYYY-mm-ddThh:mm:ss"; e.g., 30-Oct-1990, Oct-1990, 1990, 1990-10-30, 1990-10, 21-Oct-1952/15-Feb-1953, 2015-10-11T17:53:03Z)
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

### Example Bioproject Metadata File (tab-separated)

```
bioproject_id	project_title	project_description	sample_source	collection_date	geo_loc_name	lat_lon	library_strategy	library_source	library_selection	platform	instrument_model	env_biome	env_feature	env_material	depth	altitude	host	host_tissue	isolation_source
PRJXXXXX	Marine Metagenome Project	Characterization of microbial communities in coastal waters	environmental	2023-07-15	USA:California	36.9513 N 122.0733 W	WGS	METAGENOMIC	RANDOM	ILLUMINA	Illumina NovaSeq 6000	marine biome	coastal water	sea water	10	0			
```

### Example Sample Metadata File (tab-separated)

```
sample_name	library_ID	title	library_strategy	library_source	library_selection	library_layout	platform	instrument_model	design_description	filetype	filename	filename2
Sample1	Lib1	Marine sample 1	WGS	METAGENOMIC	RANDOM	paired	ILLUMINA	Illumina MiSeq	Metagenomic sequencing	fastq	Sample1_R1.fastq.gz	Sample1_R2.fastq.gz
Sample2	Lib2	Marine sample 2	WGS	METAGENOMIC	RANDOM	paired	ILLUMINA	Illumina MiSeq	Metagenomic sequencing	fastq	Sample2_R1.fastq.gz	Sample2_R2.fastq.gz
```

## Python API

You can also use the package as a Python library:

```python
from sra_metagenome_submission import SRASubmission, validate_metadata
from sra_metagenome_submission.sra_utils import prepare_metadata, verify_files

# Validate metadata
validated_sample_df, validated_bioproject_df = validate_metadata(
    "sample-metadata.txt", 
    "bioproject-metadata.txt", 
    "config.json"
)

# Initialize submission
submission = SRASubmission("config.json")

# Collect metadata and files
submission.collect_metadata(validated_sample_df, validated_bioproject_df)
submission.collect_sequence_files("/path/to/sequence/files")

# Verify files
if submission.verify_sequence_files():
    # Prepare submission package
    submission.prepare_submission_package("submission_package")
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
│       ├── sra_validate.py    # Metadata validation script
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

1. **Metadata Format Issues**:
   - Ensure metadata files are tab-separated text files (.txt) or Excel files (.xlsx)
   - CSV files are not accepted
   - Use the validation script to check for and fix formatting issues

2. **Date Format Problems**:
   - Collection dates must be in one of these formats:
     - "DD-Mmm-YYYY" (e.g., 30-Oct-1990)
     - "Mmm-YYYY" (e.g., Oct-1990)
     - "YYYY" (e.g., 1990)
     - ISO 8601: "YYYY-mm-dd" (e.g., 1990-10-30)
     - ISO 8601: "YYYY-mm" (e.g., 1990-10)
     - Range: "DD-Mmm-YYYY/DD-Mmm-YYYY" (e.g., 21-Oct-1952/15-Feb-1953)
     - With time: "YYYY-mm-ddThh:mm:ssZ" (e.g., 2015-10-11T17:53:03Z)
   - The validation script will automatically convert valid dates to ISO format

3. **Missing Required Metadata**:
   - Ensure all required fields are completed
   - Pay attention to format (geographic coordinates, etc.)

4. **File Format Problems**:
   - SRA accepts FASTQ, BAM, and SFF formats
   - Ensure files are properly compressed if using gzip
   - File names should not contain spaces or special characters

5. **Validation Errors**:
   - Read error messages carefully
   - Address each issue before resubmitting
   - Use the validation script to check your metadata before submission

### Getting Help

If you encounter issues with the submission process:

1. Check NCBI's [SRA Submission Guide](https://www.ncbi.nlm.nih.gov/sra/docs/submit/)
2. Review the generated log files for detailed error messages
3. Contact NCBI Help Desk at info@ncbi.nlm.nih.gov
4. Open an issue on our GitHub repository with your log file attached (remove any sensitive information)

## License

This project is licensed under the MIT License - see the LICENSE file for details.
