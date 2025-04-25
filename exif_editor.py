import os
import subprocess
import datetime
import logging
import shlex

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class ExifEditor:
    """
    Manages reading and writing EXIF metadata for a single file using exiftool.
    """
    EXIFTOOL_COMMAND = "exiftool" # Assumes exiftool is in the system PATH

    def __init__(self, file_path: str):
        """
        Initializes the ExifEditor for a specific file.

        Args:
            file_path: The path to the target file.
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        self.file_path = file_path
        self._date_time_original = None
        self._user_comment = None
        self._writable = None
        self._metadata_read = False

    def _run_exiftool(self, args: list) -> tuple[str, str, int]:
        """
        Runs the exiftool command with the given arguments.

        Args:
            args: A list of arguments to pass to exiftool.

        Returns:
            A tuple containing (stdout, stderr, return_code).
        """
        command = [self.EXIFTOOL_COMMAND] + args + [self.file_path]
        logging.debug(f"Running command: {' '.join(shlex.quote(str(arg)) for arg in command)}")
        try:
            process = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8', # Assume utf-8 output, adjust if needed
                errors='replace', # Handle potential decoding errors
                check=False # Don't raise exception on non-zero exit code
            )
            logging.debug(f"Exiftool stdout:\n{process.stdout}")
            logging.debug(f"Exiftool stderr:\n{process.stderr}")
            logging.debug(f"Exiftool return code: {process.returncode}")
            return process.stdout.strip(), process.stderr.strip(), process.returncode
        except FileNotFoundError:
            logging.error(f"'{self.EXIFTOOL_COMMAND}' command not found. Please ensure ExifTool is installed and in your PATH.")
            raise
        except Exception as e:
            logging.error(f"Error running exiftool: {e}")
            return "", str(e), 1 # Simulate an error return

    def read_metadata(self) -> bool:
        """
        Reads DateTimeOriginal and UserComment from the file's EXIF data.

        Returns:
            True if metadata was read successfully, False otherwise.
        """
        if self._metadata_read:
            return True

        stdout, stderr, return_code = self._run_exiftool(['-s', '-s', '-DateTimeOriginal', '-UserComment'])

        if return_code != 0:
            logging.warning(f"Exiftool could not read metadata for {self.file_path}. Error: {stderr}")
            return False

        lines = stdout.splitlines()
        metadata = {}
        for line in lines:
            if ': ' in line:
                tag, value = line.split(': ', 1)
                metadata[tag.strip()] = value.strip()

        self._date_time_original = metadata.get('DateTimeOriginal')
        self._user_comment = metadata.get('UserComment', '') # Default to empty string if not present
        self._metadata_read = True
        logging.debug(f"Read metadata for {self.file_path}: DateTimeOriginal='{self._date_time_original}', UserComment='{self._user_comment}'")
        return True

    @property
    def date_time_original(self) -> str | None:
        """Returns the DateTimeOriginal tag value (reads if necessary)."""
        if not self._metadata_read:
            self.read_metadata()
        return self._date_time_original

    @property
    def user_comment(self) -> str:
        """Returns the UserComment tag value (reads if necessary)."""
        if not self._metadata_read:
            self.read_metadata()
        # Ensure user_comment is never None after reading
        return self._user_comment if self._user_comment is not None else ""


    def is_writable(self) -> bool:
        """
        Checks if the file is writable by the user and likely supported by exiftool.
        Relies on a test write command succeeding.
        """
        if self._writable is not None:
            return self._writable

        if not os.access(self.file_path, os.W_OK):
            logging.warning(f"File is not writable (OS permissions): {self.file_path}")
            self._writable = False
            return False

        # Attempt a harmless write to check exiftool support/write capability
        # Writing an empty comment shouldn't change much if it doesn't exist
        # or overwrite if it does (but we restore later if needed).
        # Using -m (ignore minor errors) to handle warnings about existing tags etc.
        _, stderr, return_code = self._run_exiftool(['-m', '-overwrite_original_in_place', '-UserComment='])

        if return_code == 0:
            logging.debug(f"File appears writable by exiftool: {self.file_path}")
            self._writable = True
        else:
            logging.warning(f"File may not be supported or writable by exiftool: {self.file_path}. Error: {stderr}")
            self._writable = False

        return self._writable

    def update_datetime_and_comment(self, new_datetime_str: str, comment_addition: str) -> bool:
        """
        Updates the DateTimeOriginal and appends to the UserComment.

        Args:
            new_datetime_str: The new timestamp in "YYYY:MM:DD HH:MM:SS" format.
            comment_addition: The string to append to the existing UserComment.

        Returns:
            True if the update was successful, False otherwise.
        """
        if not self.is_writable():
             logging.warning(f"Attempted to write to non-writable file: {self.file_path}")
             return False

        # Ensure metadata is read before constructing the new comment
        if not self._metadata_read:
            if not self.read_metadata():
                 logging.error(f"Failed to read metadata before writing to {self.file_path}")
                 return False # Cannot proceed without knowing original comment

        current_comment = self.user_comment
        separator = " " if current_comment and comment_addition else ""
        new_comment = f"{current_comment}{separator}{comment_addition}"

        # Use -m to ignore minor errors (like tag not existing initially)
        # Use -overwrite_original_in_place for efficiency
        args = [
            '-m',
            '-overwrite_original_in_place',
            f'-DateTimeOriginal={new_datetime_str}',
            f'-UserComment={new_comment}'
        ]
        stdout, stderr, return_code = self._run_exiftool(args)

        if return_code == 0:
            logging.info(f"Successfully updated EXIF for {self.file_path}")
            # Update internal state
            self._date_time_original = new_datetime_str
            self._user_comment = new_comment
            return True
        else:
            logging.error(f"Failed to update EXIF for {self.file_path}. Error: {stderr}\nStdout: {stdout}")
            return False

    @staticmethod
    def is_valid_datetime_format(dt_str: str) -> bool:
        """Checks if a string matches the 'YYYY:MM:DD HH:MM:SS' format."""
        try:
            ExifEditor.parse_datetime(dt_str)
            return True
        except ValueError:
            return False

    @staticmethod
    def parse_datetime(dt_str: str) -> datetime.datetime:
        """Parses a 'YYYY:MM:DD HH:MM:SS' string into a datetime object."""
        return datetime.datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')

    @staticmethod
    def format_datetime(dt_obj: datetime.datetime) -> str:
        """Formats a datetime object into 'YYYY:MM:DD HH:MM:SS' string."""
        return dt_obj.strftime('%Y:%m:%d %H:%M:%S')