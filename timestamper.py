import sys
import time
import glob
import argparse
import datetime
import os
import logging
from exif_editor import ExifEditor # Import the refactored class

# Configure logging (can be adjusted, e.g., add file logging)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_arguments():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Adjust EXIF DateTimeOriginal for photos in a directory based on a starting time and interval.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python timestamper.py ./photos "2023:10:26 10:00:00" 30
  python timestamper.py /path/to/images "2024:01:01 00:00:00" -5 --sort-by name
  python timestamper.py "C:\\My Pictures" "2022:05:15 14:30:00" 1.5 --sort-by modified

Notes:
- Ensure ExifTool is installed and accessible in your system's PATH.
- Files are processed in the order determined by the sorting option.
- The script appends a comment to the EXIF UserComment tag indicating the change.
"""
    )
    parser.add_argument('directory', help='Directory containing the photos.')
    parser.add_argument('start_time', help='Starting timestamp in "YYYY:MM:DD HH:MM:SS" format.')
    parser.add_argument('interval', type=float, help='Time interval in seconds between consecutive photos (can be positive, negative, or fractional).')
    parser.add_argument(
        '--sort-by',
        choices=['name', 'created', 'modified'],
        default='name',
        help='Sort files by name (default), creation time, or modification time before processing.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Perform a dry run: show what changes would be made without actually modifying files."
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help="Enable verbose logging (DEBUG level)."
    )

    if len(sys.argv) < 4:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    # Set logging level based on verbosity
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate start_time format using the method from ExifEditor
    if not ExifEditor.is_valid_datetime_format(args.start_time):
        logging.error(f"Invalid start_time format: '{args.start_time}'. Expected 'YYYY:MM:DD HH:MM:SS'.")
        parser.print_help()
        sys.exit(1)

    # Validate directory existence
    if not os.path.isdir(args.directory):
        logging.error(f"Directory not found: {args.directory}")
        sys.exit(1)

    return args

def get_sorted_files(directory: str, sort_key: str) -> list[str]:
    """Gets and sorts files from the directory based on the specified key."""
    try:
        # Use recursive=False to only get files directly in the folder
        files = [os.path.join(directory, f) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        # files = glob.glob(os.path.join(directory, "*")) # Original glob approach (includes subdirs if not filtered)
        # files = [f for f in files if os.path.isfile(f)] # Filter out directories if using glob
    except FileNotFoundError:
        logging.error(f"Error accessing directory: {directory}")
        return [] # Return empty list on error

    if not files:
        logging.warning(f"No files found in directory: {directory}")
        return []

    if sort_key == 'name':
        files.sort()
    elif sort_key == 'created':
        files.sort(key=os.path.getctime)
    elif sort_key == 'modified':
        files.sort(key=os.path.getmtime)

    logging.info(f"Found {len(files)} files, sorted by {sort_key}.")
    return files

def process_files(files: list[str], start_dt: datetime.datetime, interval_sec: float, fix_id: str, dry_run: bool):
    """Processes each file, adjusting the timestamp."""
    processed_count = 0
    skipped_count = 0
    error_count = 0
    file_index = 0  # Counter for successfully processed files
    interval_delta = datetime.timedelta(seconds=interval_sec)

    for index, file_path in enumerate(files):
        filename = os.path.basename(file_path)
        logging.info(f"Processing [{index + 1}/{len(files)}] {filename}...")  # Still use 'index' for total file count

        try:
            editor = ExifEditor(file_path)

            # Read existing metadata first
            if not editor.read_metadata():
                logging.warning(f"Skipping {filename}: Could not read initial metadata.")
                skipped_count += 1
                continue # Skip if we can't even read it

            # Check writability *after* reading, as reading might still be useful
            if not dry_run and not editor.is_writable():
                logging.warning(f"Skipping {filename}: File is not writable or not supported by exiftool.")
                skipped_count += 1
                continue

            # Calculate new timestamp based on the number of *processed* files
            current_dt = start_dt + (interval_delta * file_index)
            new_datetime_str = ExifEditor.format_datetime(current_dt)

            original_dt_str = editor.date_time_original if editor.date_time_original else "None"

            # Create comment (ensure quotes are handled if necessary, though ExifEditor should manage this)
            fix_comment = f"AdjustedDateTime_{fix_id}[{original_dt_str} -> {new_datetime_str}]"

            logging.info(f"  Original DateTime: {original_dt_str}")
            logging.info(f"  Calculated New DateTime: {new_datetime_str}")
            logging.info(f"  Comment to add: {fix_comment}")


            if dry_run:
                logging.info(f"  DRY RUN: Would update {filename}")
                processed_count += 1 # Count as processed in dry run
            else:
                # Write EXIF data using the refactored method
                if editor.update_datetime_and_comment(new_datetime_str, fix_comment):
                    logging.info(f"  Successfully updated {filename}")
                    processed_count += 1
                    file_index += 1  # Increment only on successful processing
                else:
                    logging.error(f"  Failed to update {filename}")
                    error_count += 1

        except FileNotFoundError:
            logging.error(f"Error processing {filename}: File not found (should not happen if initial check passed).")
            error_count += 1
        except Exception as e:
            logging.error(f"Error processing {filename}: {e}", exc_info=logging.getLogger().level == logging.DEBUG) # Show traceback if verbose
            error_count += 1

    print("-" * 30)
    logging.info("Processing Summary:")
    logging.info(f"  Total Files Attempted: {len(files)}")
    logging.info(f"  Successfully Processed{' (Dry Run)' if dry_run else ''}: {processed_count}")
    logging.info(f"  Skipped (Read Error/Not Writable): {skipped_count}")
    logging.info(f"  Errors: {error_count}")
    print("-" * 30)


def main():
    """Main execution function."""
    print("+-----------------------------+")
    print("|         Timestamper         |")
    print("+-----------------------------+")

    args = parse_arguments()

    fix_id = str(int(time.time())) # Unique ID for this run's comments
    logging.info(f"Starting run with Fix ID: {fix_id}")
    logging.info(f"Target Directory: {args.directory}")
    logging.info(f"Start Time: {args.start_time}")
    logging.info(f"Interval: {args.interval} seconds")
    logging.info(f"Sort By: {args.sort_by}")
    if args.dry_run:
        logging.warning("--- DRY RUN MODE ENABLED: No files will be modified. ---")

    try:
        start_datetime_obj = ExifEditor.parse_datetime(args.start_time)
    except ValueError as e:
         # This case should ideally be caught by is_valid_datetime_format earlier,
         # but catch it here just in case of edge cases (e.g., invalid date like Feb 30th)
         logging.error(f"Error parsing start_time '{args.start_time}': {e}")
         sys.exit(1)


    files_to_process = get_sorted_files(args.directory, args.sort_by)

    if not files_to_process:
        logging.info("No files to process. Exiting.")
        sys.exit(0)

    print("-" * 30) # Separator before processing starts
    process_files(files_to_process, start_datetime_obj, args.interval, fix_id, args.dry_run)

    if args.dry_run:
        print("--- DRY RUN COMPLETE ---")
    else:
        print("+----------------------+")
        print("| ✨ Adjustment Done ✨ |")
        print("+----------------------+")

if __name__ == "__main__":
    main()