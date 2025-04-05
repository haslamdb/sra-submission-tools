# SRA Metagenomic Data Submission Tool

A Python package to automate the submission of metagenomic data to NCBI's Sequence Read Archive (SRA).

## Overview

This package provides tools to streamline the preparation and submission of metagenomic sequence data to the SRA database. It helps with:

- Creating required metadata files in the correct format
- Organizing sequence files according to SRA requirements
- Automating the submission process via the NCBI Submission Portal API

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

```bash
# Clone the repository
git clone https://github.com/yourusername/sra-metagenome-submission.git
cd sra-metagenome-submission

# Install the package and dependencies
pip install -e .
```

Or install directly using pip:

```bash
pip install sra-metagenome-submission
```

## Quick Start

```bash
# Interactive mode - will prompt for required information
python sra_submission.py --output my_submission

# Use existing metadata file
python sra_submission.py --metadata my_metadata.csv --files /path/to/fastq_files

# Submit to SRA (requires authentication)
python sra_submission.py --config config.json --metadata my_metadata.csv --submit
```

## Understanding the SRA Submission Process

### What is SRA?

The Sequence Read Archive (SRA) is NCBI's primary archive of high-throughput sequencing data. It stores raw sequencing data and alignment information from various sequencing platforms.

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
python sra_submission.py --output submission_package

# Using metadata file and auto-detecting sequence files
python sra_submission.py --metadata metadata.csv --files /path/to/fastq_files --output submission_package

# Full submission with authentication
python sra_submission.py --config config.json --metadata metadata.csv --files /path/to/fastq_files --output submission_package --submit
```

### Command-line Arguments

- `--config`: Path to JSON configuration file with authentication and defaults
- `--metadata`: Path to CSV/Excel file containing sample metadata
- `--files`: Directory containing sequence files (will auto-detect FASTQ/FQ/FASTQ.GZ files)
- `--output`: Directory to store generated submission files (default: sra_submission)
- `--submit`: Flag to submit data to SRA (requires authentication)

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

## Troubleshooting

### Common Submission Errors

1. **Missing Required Metadata**:
   - Ensure all required fields are completed
   - Pay attention to format (dates as YYYY-MM-DD, lat/lon as decimal degrees)

2. **Authentication Issues**:
   - Verify your NCBI username/password or API key
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
