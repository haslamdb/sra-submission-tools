# SRA Metagenomic Data Submission Tool

A Python package to automate the submission of metagenomic data to NCBI's Sequence Read Archive (SRA).

## Overview

Submission of raw sequence files to the SRA database is a pain. 

This package provides tools to make preparation and submission of metagenomic sequence data to the SRA database somewhat less painful. It helps with:

- Creating required metadata files in the correct format
- Organizing sequence files according to SRA requirements
- Automating the submission process via the NCBI Submission Portal API
- Verifying files and metadata before submission
- Detecting paired-end sequencing files automatically

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

### Using Conda (Recommended)

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

### Using pip

```bash
# Install directly using pip
pip install sra-metagenome-submission
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
# Activate the conda environment
conda activate sra-tools

# Using the command-line tool (installed via pyproject.toml)
sra-submit --config config.json --metadata test_metadata.csv --files /path/to/sequence/files --output submission_package

# Or run the script directly
python sra_submission.py --config config.json --metadata test_metadata.csv --files /path/to/sequence/files --output submission_package

# Submit to SRA (requires authentication)
sra-submit --config config.json --metadata test_metadata.csv --files /path/to/sequence/files --output submission_package --submit
```

## Understanding the SRA Submission Process


### NCBI Submission Process Overview

The SRA submission process involves several steps:

1. **Registration**:
   - Create an NCBI account if you don't have one
   - Register your BioProject (provides an umbrella for your submissions)
   - Register your BioSamples (describes the source of your DNA/RNA)

2. **Data Preparation**:
   - Organize sequence files (FASTQ, BAM, etc.)
   - Prepare metadata files

3. **Submission**:
   - Upload files to SRA
   - Provide experiment and run metadata
   - Submit and track your submission

## SRA Submission Process

### Prerequisites

Before submitting metagenomic data to SRA, you need to complete several setup steps:

1. **Install Aspera Connect**:
   - Download the Aspera Connect installer from [IBM's website](https://www.ibm.com/products/aspera/downloads#cds)
   - For Linux users, this will download a bash script that you need to run to complete the installation
   - Verify installation by running `ascp --version` in your terminal
   - On Linux you may need to add an alias to your ~/.bashrc   (e.g. alias ascp='/home/your-username/.aspera/connect/bin/ascp')

2. **Obtain Aspera Key File**:
   - Download the `aspera.openssh` key file from NCBI: [https://submit.ncbi.nlm.nih.gov/preload/aspera_key/](https://submit.ncbi.nlm.nih.gov/preload/aspera_key/)
   - **Important**: Copy and paste the downloaded file from your downloads folder to a secure location. Do not open and save it as a text file, as this would corrupt the file format.
   - Make note of the path to this key file as you'll need it for the submission process

3. **Request a Preload Folder**:
   - Log into your NCBI account at [https://submit.ncbi.nlm.nih.gov/](https://submit.ncbi.nlm.nih.gov/)
   - Request a preload folder for your submission
   - You will receive an upload destination path in the format: `subasp@upload.ncbi.nlm.nih.gov:uploads/your_username_XYZ123`
   - Save this destination path for use in the submission process



### Running the Submission Process

The submission process is split into two main steps:

1. **Prepare the Submission Package**:
   ```bash
   sra-submit --config config.json --metadata your_metadata.csv --files /path/to/sequence/files --output submission_package

### Manual Submission Steps

If you prefer to submit manually instead of using our automation tool, follow these steps:

1. **Create NCBI Account**:
   - Go to [NCBI](https://www.ncbi.nlm.nih.gov/)
   - Click "Log in" and then "Register" if you don't have an account

2. **Register BioProject**:
   - Go to [BioProject Submission Portal](https://submit.ncbi.nlm.nih.gov/subs/bioproject/)
   - Click "New Submission"
   - Fill out the required information about your project

3. **Register BioSamples**:
   - Go to [BioSample Submission Portal](https://submit.ncbi.nlm.nih.gov/subs/biosample/)
   - Click "New Submission"
   - Choose the appropriate sample type and attributes
   - For metagenomes, include environmental metadata (MIxS standards)

4. **Submit SRA Data**:
   - Go to [SRA Submission Portal](https://submit.ncbi.nlm.nih.gov/subs/sra/)
   - Click "New Submission"
   - Link to your BioProject and BioSamples
   - Upload sequence files or provide FTP links
   - Fill out metadata for each experiment and run

5. **Track Submission Status**:
   - Monitor your submission at [NCBI Submission Portal](https://submit.ncbi.nlm.nih.gov/)
   - Address any validation errors or issues
   - Receive accession numbers once submission is accepted

### Important URLs

- NCBI Homepage: https://www.ncbi.nlm.nih.gov/
- SRA Homepage: https://www.ncbi.nlm.nih.gov/sra
- NCBI Submission Portal: https://submit.ncbi.nlm.nih.gov/
- BioProject Submission: https://submit.ncbi.nlm.nih.gov/subs/bioproject/
- BioSample Submission: https://submit.ncbi.nlm.nih.gov/subs/biosample/
- SRA Submission: https://submit.ncbi.nlm.nih.gov/subs/sra/

## Using the Scripts

Our toolset includes scripts to streamline the SRA submission process, reducing manual steps and potential errors.

### Main Script: `sra_submission.py`

This is the primary script for preparing and submitting metagenomic data to SRA.

```bash
# Basic usage with interactive prompts
sra-submit --output submission_package

# Using metadata file and auto-detecting sequence files
sra-submit --metadata metadata.csv --files /path/to/fastq_files --output submission_package

# Full submission with authentication
sra-submit --config config.json --metadata metadata.csv --files /path/to/fastq_files --output submission_package --submit

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

3. **File Format Problems**:
   - SRA accepts FASTQ, BAM, and SFF formats
   - Ensure files are properly compressed if using gzip

4. **Validation Errors**:
   - Read error messages carefully
   - Address each issue before resubmitting

### Getting Help

If you encounter issues with the submission process:

1. Check NCBI's [SRA Submission Guide](https://www.ncbi.nlm.nih.gov/sra/docs/submit/)
2. Contact NCBI Help Desk at info@ncbi.nlm.nih.gov
3. Open an issue on our GitHub repository

## License

This project is licensed under the MIT License - see the LICENSE file for details.
