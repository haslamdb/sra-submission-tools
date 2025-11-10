"""
SRA Metagenomic Data Submission Package

This package provides tools to simplify the submission of metagenomic 
sequence data to NCBI's Sequence Read Archive (SRA) database.
"""

from ._version import __version__

# Import key functions for easier access
from .sra_validate import (
    validate_sample_metadata,
    validate_bioproject_metadata,
    load_metadata_file,
    save_metadata_file
)

from .sra_utils import (
    prepare_metadata,
    verify_files,
    detect_file_pairs,
    collect_fastq_files,
    build_sample_metadata
)

from .main import SRASubmission

# Define what's available for import with "from sra_metagenome_submission import *"
__all__ = [
    'SRASubmission',
    'validate_sample_metadata',
    'validate_bioproject_metadata', 
    'load_metadata_file',
    'save_metadata_file',
    'prepare_metadata',
    'verify_files',
    'detect_file_pairs',
    'collect_fastq_files',
    'build_sample_metadata',
    '__version__'
]
