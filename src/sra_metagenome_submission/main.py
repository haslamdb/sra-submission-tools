#!/usr/bin/env python3
"""
SRA Metagenomic Data Submission Script

This script automates the process of preparing and submitting metagenomic data
to NCBI's Sequence Read Archive (SRA). It generates required metadata files and
uploads sequence data using IBM Aspera (ascp).

Uploads are batched with a resumable checkpoint, per-batch retries with backoff,
and a per-file fallback so a single bad file never sinks a whole batch. Aspera is
invoked through subprocess with an argument list (no shell quoting pitfalls) and
its output is parsed to detect partial-completion failures that still exit 0.
"""

import os
import sys
import json
import re
import time
import shlex
import argparse
import logging
import tempfile
import shutil
import subprocess
from datetime import datetime

import pandas as pd

# Import utility functions from the same package
try:
    from sra_metagenome_submission.sra_utils import (
        detect_file_pairs,
        collect_fastq_files,
        build_sample_metadata,
    )
    from sra_metagenome_submission.sra_validate import (
        validate_sample_metadata,
        validate_bioproject_metadata,
        load_metadata_file,
        save_metadata_file,
    )
except ImportError:
    # If not installed, try local import
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(current_dir)
    try:
        from sra_utils import (
            detect_file_pairs,
            collect_fastq_files,
            build_sample_metadata,
        )
        from sra_validate import (
            validate_sample_metadata,
            validate_bioproject_metadata,
            load_metadata_file,
            save_metadata_file,
        )
    except ImportError:
        print("Error: required modules not found. Please ensure sra_utils.py and "
              "sra_validate.py are in the same directory.")
        sys.exit(1)


CHECKPOINT_DIR = ".sra_checkpoints"


def setup_logging(submission_name=None):
    """Configure root logging to a timestamped file and the console.

    Safe to call more than once: existing handlers are cleared first so a
    submission name supplied on the command line can rename the log cleanly.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if submission_name:
        log_filename = f"sra_submission_{submission_name}_{timestamp}.log"
    else:
        log_filename = f"sra_submission_{timestamp}.log"

    root = logging.getLogger()
    for handler in root.handlers[:]:
        handler.close()
        root.removeHandler(handler)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler(log_filename), logging.StreamHandler()],
    )
    logging.getLogger(__name__).info(f"Logging to {log_filename}")
    return log_filename


log_filename = setup_logging()
logger = logging.getLogger(__name__)


class SRASubmission:
    """Handle the SRA submission process for metagenomic data."""

    # Default upload behaviour; overridable via config["performance"] or CLI flags.
    DEFAULT_PERFORMANCE = {
        'batch_size': 50,          # files per ascp invocation
        'bandwidth': '100m',       # ascp -l target rate
        'resume_level': 1,         # ascp -k resume level
        'policy': 'fair',          # ascp --policy
        'max_retries': 3,          # retries per batch before per-file fallback
        'aspera_timeout': 3600,    # seconds per ascp invocation
        'enable_checkpoints': True,
    }

    def __init__(self, config_file=None):
        self.config = {}
        self.sample_metadata_df = None
        self.bioproject_metadata_df = None
        self.files = []
        self.performance_config = dict(self.DEFAULT_PERFORMANCE)

        if config_file:
            self.load_config(config_file)

    def load_config(self, config_file):
        """Load configuration from a JSON file."""
        try:
            with open(config_file, 'r') as f:
                self.config = json.load(f)
            if 'performance' in self.config:
                self.performance_config.update(self.config['performance'])
            logger.info(f"Loaded configuration from {config_file}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            sys.exit(1)

    # ------------------------------------------------------------------ #
    # Metadata loading
    # ------------------------------------------------------------------ #
    def load_sample_metadata(self, metadata_file):
        """Load and validate sample metadata from a tab-delimited TXT or Excel file."""
        try:
            self.sample_metadata_df = load_metadata_file(metadata_file)
            self.sample_metadata_df = validate_sample_metadata(self.sample_metadata_df, self.config)

            if len(self.sample_metadata_df) > 0:
                logger.info(f"Loaded sample metadata from {metadata_file} "
                            f"with {len(self.sample_metadata_df)} samples")
            else:
                logger.error("Sample metadata file is empty")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to load sample metadata: {str(e)}")
            sys.exit(1)

        return len(self.sample_metadata_df)

    def load_bioproject_metadata(self, metadata_file):
        """Load and validate bioproject metadata from a tab-delimited TXT or Excel file."""
        try:
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

    # ------------------------------------------------------------------ #
    # File collection
    # ------------------------------------------------------------------ #
    def collect_sequence_files(self, file_dir=None):
        """Collect the sequence files referenced in the sample metadata.

        Absolute paths in the metadata are used as-is; relative paths are
        resolved against ``file_dir`` when provided.
        """
        if self.sample_metadata_df is None or len(self.sample_metadata_df) == 0:
            logger.error("No sample metadata available for file filtering")
            return 0

        filename_keys = ['filename', 'filename2', 'filepath', 'filepath2', 'file1', 'file2']
        available_keys = [key for key in filename_keys if key in self.sample_metadata_df.columns]

        if not available_keys:
            logger.warning("No filename columns found in sample metadata")
            return 0

        self.files = []
        missing_files = []

        for _, row in self.sample_metadata_df.iterrows():
            for key in available_keys:
                filename = row.get(key)
                if filename is None or pd.isna(filename) or str(filename).strip() == "":
                    continue

                filename = str(filename).strip()
                if os.path.isabs(filename):
                    file_path = filename
                elif file_dir:
                    file_path = os.path.join(file_dir, filename)
                else:
                    file_path = filename

                if os.path.exists(file_path):
                    self.files.append(file_path)
                else:
                    missing_files.append(file_path)

        # Remove duplicates while preserving order
        self.files = list(dict.fromkeys(self.files))
        file_count = len(self.files)

        if missing_files:
            logger.warning(f"Could not find {len(missing_files)} files mentioned in sample metadata:")
            for file in missing_files[:5]:
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

    # ------------------------------------------------------------------ #
    # Template generation
    # ------------------------------------------------------------------ #
    def generate_template_metadata(self, file_dir, output_dir):
        """Generate template metadata files from a directory of sequence files."""
        try:
            os.makedirs(output_dir, exist_ok=True)

            fastq_files = collect_fastq_files(file_dir, recursive=True)
            if not fastq_files:
                logger.error(f"No FASTQ files found in {file_dir}")
                return None, None

            logger.info(f"Found {len(fastq_files)} FASTQ files")

            file_pairs = detect_file_pairs(fastq_files)
            logger.info(f"Detected {len(file_pairs)} file pairs/singles")

            sample_df = build_sample_metadata(file_pairs, self.config)

            bioproject_columns = [
                'bioproject_id', 'project_title', 'project_description',
                'sample_source', 'collection_date', 'geo_loc_name',
                'lat_lon', 'library_strategy', 'library_source',
                'library_selection', 'platform', 'instrument_model',
                'env_biome', 'env_feature', 'env_material',
                'depth', 'altitude', 'host', 'host_tissue', 'isolation_source',
            ]

            bioproject_data = {col: [''] for col in bioproject_columns}
            if self.config and 'default_values' in self.config:
                for col in bioproject_columns:
                    if col in self.config['default_values']:
                        bioproject_data[col] = [self.config['default_values'][col]]

            bioproject_df = pd.DataFrame(bioproject_data)

            sample_output_path = os.path.join(output_dir, 'sample-metadata-template.txt')
            bioproject_output_path = os.path.join(output_dir, 'bioproject-metadata-template.txt')

            save_metadata_file(sample_df, sample_output_path)
            save_metadata_file(bioproject_df, bioproject_output_path)

            logger.info(f"Generated template files in {output_dir}")
            print("\nGenerated template metadata files:")
            print(f"  - Sample metadata: {sample_output_path}")
            print(f"  - Bioproject metadata: {bioproject_output_path}")
            print("\nPlease fill in the required fields before submission.")

            return sample_output_path, bioproject_output_path

        except Exception as e:
            logger.error(f"Error generating template metadata: {str(e)}")
            print(f"\nError generating template metadata: {str(e)}")
            return None, None

    # ------------------------------------------------------------------ #
    # Checkpointing
    # ------------------------------------------------------------------ #
    @staticmethod
    def _checkpoint_path(submission_folder):
        return os.path.join(CHECKPOINT_DIR, f"{submission_folder}.json")

    def save_checkpoint(self, submission_folder, uploaded_files, failed_files):
        """Persist upload progress so an interrupted run can resume."""
        os.makedirs(CHECKPOINT_DIR, exist_ok=True)
        data = {
            'submission_folder': submission_folder,
            'uploaded_files': sorted(uploaded_files),
            'failed_files': sorted(failed_files),
            'timestamp': datetime.now().isoformat(),
        }
        with open(self._checkpoint_path(submission_folder), 'w') as f:
            json.dump(data, f, indent=2)
        logger.debug(f"Saved checkpoint with {len(uploaded_files)} uploaded files")

    def load_checkpoint(self, submission_folder):
        """Return ``(uploaded_files, failed_files)`` sets from a prior run, if any."""
        path = self._checkpoint_path(submission_folder)
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                uploaded = set(data.get('uploaded_files', []))
                failed = set(data.get('failed_files', []))
                logger.info(f"Loaded checkpoint from {data.get('timestamp', 'unknown time')} "
                            f"with {len(uploaded)} uploaded files")
                return uploaded, failed
            except Exception as e:
                logger.warning(f"Could not load checkpoint file {path}: {e}")
        return set(), set()

    def clear_checkpoint(self, submission_folder):
        path = self._checkpoint_path(submission_folder)
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.debug(f"Removed checkpoint file {path}")
            except OSError as e:
                logger.warning(f"Could not remove checkpoint file {path}: {e}")

    # ------------------------------------------------------------------ #
    # Aspera invocation
    # ------------------------------------------------------------------ #
    def _build_ascp_cmd(self, aspera_path, key_path, sources, destination):
        """Build an ascp argument list (never a shell string)."""
        pc = self.performance_config
        cmd = [
            aspera_path,
            '-i', key_path,
            '-QT',
            '-l', str(pc['bandwidth']),
            '-k', str(pc['resume_level']),
            f"--policy={pc['policy']}",
            '-d',
        ]
        cmd.extend(sources)
        cmd.append(destination)
        return cmd

    def _run_ascp(self, cmd):
        """Run an ascp command. Returns ``(ok, combined_output)``.

        ``ok`` is False on a non-zero exit, a timeout, a missing executable, or
        an Aspera 'partial completion' (some files failed) that still exits 0.
        """
        logger.info("Running: %s", " ".join(shlex.quote(c) for c in cmd))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.performance_config['aspera_timeout'],
            )
        except subprocess.TimeoutExpired:
            logger.error("ascp timed out after %ss", self.performance_config['aspera_timeout'])
            return False, "TimeoutExpired"
        except FileNotFoundError:
            logger.error("ascp executable not found: %s", cmd[0])
            return False, "ascp executable not found"

        output = (result.stdout or "") + "\n" + (result.stderr or "")

        if result.returncode != 0:
            logger.error("ascp exited with code %s", result.returncode)
            if result.stderr:
                logger.error("stderr: %s", result.stderr.strip())
            return False, output

        # ascp can exit 0 on "partial completion" - scan output for failures.
        if re.search(r'Session Stop', output):
            logger.error("ascp reported a session stop")
            return False, output
        failed_match = re.search(r'(\d+)\s+files?\s+failed', output, re.IGNORECASE)
        if failed_match and int(failed_match.group(1)) > 0:
            logger.error("ascp reported %s failed file(s)", failed_match.group(1))
            return False, output

        return True, output

    def _upload_sources(self, aspera_path, key_path, sources, destination, retries):
        """Upload one set of source files, retrying the whole set with backoff."""
        for attempt in range(1, retries + 1):
            if attempt > 1:
                wait = (attempt - 1) * 10
                print(f"    Retry {attempt - 1}/{retries - 1} in {wait}s...")
                time.sleep(wait)
            cmd = self._build_ascp_cmd(aspera_path, key_path, sources, destination)
            ok, _ = self._run_ascp(cmd)
            if ok:
                return True
        return False

    def upload_files_with_aspera(self, key_path=None, upload_destination=None,
                                 aspera_path=None, submission_folder=None,
                                 auto_finalize=False, restart=False):
        """Upload ``self.files`` to NCBI via Aspera in resumable batches.

        Args:
            key_path: Path to the Aspera key file (required).
            upload_destination: NCBI preload root, e.g.
                ``subasp@upload.ncbi.nlm.nih.gov:uploads/your_folder`` (required).
            aspera_path: Full path to the ``ascp`` executable (auto-detected if omitted).
            submission_folder: Subfolder created under the preload root for this
                submission. Stable across runs so uploads resume cleanly.
            auto_finalize: Upload a ``submit.ready`` marker after a fully successful
                upload so NCBI auto-creates the submission. Default is the manual
                portal flow.
            restart: Ignore and clear any existing checkpoint for this folder.

        Returns:
            bool: True if every file uploaded successfully.
        """
        if not key_path:
            logger.error("Aspera key file path is required")
            return False
        if not upload_destination:
            logger.error("NCBI upload destination is required")
            return False
        if not self.files:
            logger.error("No files specified for upload")
            print("\nError: No files specified for upload. Please check your metadata file.")
            return False

        if not aspera_path:
            aspera_path = self._find_aspera_path()
        logger.info(f"Using Aspera client at: {aspera_path}")

        submission_folder = re.sub(r'[^A-Za-z0-9_.-]', '_', submission_folder or "sra_submission")
        destination = f"{upload_destination.rstrip('/')}/{submission_folder}"
        logger.info(f"Upload destination: {destination}")

        use_checkpoints = self.performance_config['enable_checkpoints']
        uploaded_files, failed_files = set(), set()
        if restart:
            self.clear_checkpoint(submission_folder)
        elif use_checkpoints:
            uploaded_files, failed_files = self.load_checkpoint(submission_folder)
            if uploaded_files:
                print(f"\nResuming submission '{submission_folder}': "
                      f"{len(uploaded_files)} file(s) already uploaded, skipping them.")

        pending = [f for f in self.files if f not in uploaded_files]
        batch_size = self.performance_config['batch_size']
        max_retries = self.performance_config['max_retries']

        if not pending:
            print("\nAll files already uploaded according to the checkpoint.")
        else:
            total = len(pending)
            num_batches = (total + batch_size - 1) // batch_size
            print(f"\nUploading {total} file(s) to {destination}")
            print(f"In {num_batches} batch(es) of up to {batch_size} file(s) each.\n")

            for batch_num, start in enumerate(range(0, total, batch_size), 1):
                batch = pending[start:start + batch_size]
                print(f"{'=' * 60}")
                print(f"Batch {batch_num}/{num_batches} ({len(batch)} file(s))")
                print(f"{'=' * 60}")

                if self._upload_sources(aspera_path, key_path, batch, destination, max_retries):
                    print(f"✓ Batch {batch_num} uploaded successfully")
                    uploaded_files.update(batch)
                    failed_files.difference_update(batch)
                else:
                    print(f"✗ Batch {batch_num} failed; retrying files individually...")
                    for file_path in batch:
                        if self._upload_sources(aspera_path, key_path, [file_path],
                                                 destination, max_retries):
                            print(f"    ✓ {os.path.basename(file_path)}")
                            uploaded_files.add(file_path)
                            failed_files.discard(file_path)
                        else:
                            print(f"    ✗ {os.path.basename(file_path)}")
                            failed_files.add(file_path)

                if use_checkpoints:
                    self.save_checkpoint(submission_folder, uploaded_files, failed_files)
                print()

        all_uploaded = set(self.files) <= uploaded_files and not failed_files

        if not all_uploaded:
            failed_list = f"{submission_folder}_failed_files.txt"
            with open(failed_list, 'w') as f:
                f.write("\n".join(sorted(failed_files)) + "\n")
            print(f"{'=' * 60}")
            print("Upload incomplete.")
            print(f"  Uploaded: {len(uploaded_files)}/{len(self.files)}")
            print(f"  Failed:   {len(failed_files)} (written to {failed_list})")
            print("\nRe-run the same command to resume - already-uploaded files are skipped\n"
                  "and failed files are retried. Add --restart to start over from scratch.")
            return False

        print(f"{'=' * 60}")
        print(f"✓ All {len(uploaded_files)} file(s) uploaded successfully.")

        if auto_finalize:
            if self._upload_submit_ready(aspera_path, key_path, destination):
                print("✓ submit.ready uploaded - NCBI will auto-create the submission.")
            else:
                print("✗ Files uploaded but the submit.ready marker failed.")
                print("  Complete the submission manually in the portal, or contact NCBI SRA support.")
                return False

        if use_checkpoints:
            self.clear_checkpoint(submission_folder)

        print("\nTo complete your submission:")
        print("1. Log in to the NCBI Submission Portal: https://submit.ncbi.nlm.nih.gov/subs/sra/")
        print("2. Start a New Submission and proceed to the Files step.")
        print("3. Choose 'FTP or Aspera Command Line file preload' and select the folder:")
        print(f"       {submission_folder}")
        print("4. Review and submit.")
        return True

    def _upload_submit_ready(self, aspera_path, key_path, destination):
        """Upload an empty submit.ready marker into the submission folder."""
        tmp_dir = tempfile.mkdtemp(prefix="sra_submit_ready_")
        try:
            ready_file = os.path.join(tmp_dir, "submit.ready")
            with open(ready_file, "w") as f:
                f.write("    ")
            return self._upload_sources(aspera_path, key_path, [ready_file], destination,
                                        self.performance_config['max_retries'])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _find_aspera_path(self):
        """Find the ascp executable in common locations."""
        possible_paths = [
            "~/.aspera/connect/bin/ascp",                                  # Linux/Unix default
            "~/Applications/Aspera Connect.app/Contents/Resources/ascp",   # macOS
            "C:/Program Files/Aspera/Aspera Connect/bin/ascp.exe",         # Windows
            "/Applications/Aspera Connect.app/Contents/Resources/ascp",    # macOS alternate
            "ascp",                                                        # rely on PATH
        ]
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
    parser = argparse.ArgumentParser(description="SRA Metagenomic Data Submission Tool")

    parser.add_argument('--config', help='Path to configuration JSON file')
    parser.add_argument('--sample-metadata', help='Path to sample metadata file (tab-delimited TXT or Excel)')
    parser.add_argument('--bioproject-metadata', help='Path to bioproject metadata file (tab-delimited TXT or Excel)')
    parser.add_argument('--files-dir', help='Directory containing sequence files')
    parser.add_argument('--output', default='sra_submission', help='Directory to store output files')
    parser.add_argument('--generate-templates', action='store_true',
                        help='Generate template metadata files from sequence files')
    parser.add_argument('--validate-only', action='store_true',
                        help='Only validate files and metadata without preparing submission')
    parser.add_argument('--submit', action='store_true', help='Upload files to SRA via Aspera')
    parser.add_argument('--aspera-key', help='Path to Aspera key file')
    parser.add_argument('--aspera-path', help='Full path to the Aspera Connect (ascp) executable')
    parser.add_argument('--upload-destination',
                        help='NCBI upload destination (e.g., subasp@upload.ncbi.nlm.nih.gov:uploads/your_folder)')
    parser.add_argument('--submission-name',
                        help='Name for this submission; used for the log file, the upload subfolder, '
                             'and the resume checkpoint')
    parser.add_argument('--batch-size', type=int, help='Number of files to upload per Aspera batch')
    parser.add_argument('--aspera-limit', help='Target bandwidth for ascp (-l), e.g. 100m')
    parser.add_argument('--max-retries', type=int, help='Retries per batch before falling back to per-file uploads')
    parser.add_argument('--auto-finalize', action='store_true',
                        help='Upload a submit.ready marker after a fully successful upload so NCBI '
                             'auto-creates the submission (default: manual portal completion)')
    parser.add_argument('--restart', action='store_true',
                        help='Ignore and clear any existing checkpoint and re-upload from scratch')
    parser.add_argument('--no-checkpoints', action='store_true', help='Disable checkpoint creation')

    args = parser.parse_args()

    if args.submission_name:
        global log_filename
        log_filename = setup_logging(args.submission_name)
        logger.info(f"Using submission name: {args.submission_name}")

    submission = SRASubmission(args.config)

    if args.batch_size:
        submission.performance_config['batch_size'] = args.batch_size
    if args.aspera_limit:
        submission.performance_config['bandwidth'] = args.aspera_limit
    if args.max_retries:
        submission.performance_config['max_retries'] = args.max_retries
    if args.no_checkpoints:
        submission.performance_config['enable_checkpoints'] = False

    # Template generation
    if args.generate_templates:
        if not args.files_dir:
            print("Error: --files-dir is required with --generate-templates")
            sys.exit(1)
        submission.generate_template_metadata(args.files_dir, args.output)
        sys.exit(0)

    # Metadata loading
    if args.sample_metadata:
        num_samples = submission.load_sample_metadata(args.sample_metadata)
        print(f"Loaded {num_samples} samples from sample metadata file")

    if args.bioproject_metadata:
        submission.load_bioproject_metadata(args.bioproject_metadata)
        print("Loaded bioproject metadata file")

    if args.validate_only:
        print("\nMetadata validation completed.")
        print("No errors found. Your metadata files are ready for submission.")
        sys.exit(0)

    # Collect sequence files referenced in the metadata (absolute paths work
    # even without --files-dir).
    if submission.sample_metadata_df is not None and (args.submit or args.files_dir):
        num_files = submission.collect_sequence_files(args.files_dir)
        if num_files == 0 and args.submit:
            print("No files found for upload. Please check your metadata file and file paths.")
            sys.exit(1)

    if args.submit:
        print("\nPreparing to submit to NCBI SRA...")

        key_path = args.aspera_key
        while not key_path or not os.path.exists(key_path):
            if key_path:
                print(f"Key file not found: {key_path}")
            key_path = input("Enter path to Aspera key file: ")
            if not key_path:
                print("Submission canceled.")
                sys.exit(0)

        upload_destination = args.upload_destination
        while not upload_destination:
            upload_destination = input(
                "Enter NCBI upload destination "
                "(e.g., subasp@upload.ncbi.nlm.nih.gov:uploads/your_folder): ")
            if not upload_destination:
                print("Submission canceled.")
                sys.exit(0)

        ok = submission.upload_files_with_aspera(
            key_path=key_path,
            upload_destination=upload_destination,
            aspera_path=args.aspera_path,
            submission_folder=args.submission_name,
            auto_finalize=args.auto_finalize,
            restart=args.restart,
        )
        if not ok:
            print("\nFile upload incomplete. See the log file for details.")
            sys.exit(1)
    else:
        print("\nFiles identified but not uploaded (--submit flag not used).")
        print("To upload files, run again with the --submit flag.")


if __name__ == "__main__":
    main()
