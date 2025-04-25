# Timestamper
Timestamper is a python script that adjusts the EXIF DateTimeOriginal metadata for photos in a directory based on a starting time and specified interval between photos. The script can process images in different sort orders and leaves an audit trail in the EXIF comments.

# Options
```
--sort-by: Sort files by name (default), created, or modified before processing
--dry-run: Perform a dry run without modifying files
--verbose or -v: Enable verbose logging
```

# Examples
python timestamper.py <directory> "<start_time>" <interval> [options]

```
  python timestamper.py ./photos "2023:10:26 10:00:00" 30
  python timestamper.py /path/to/images "2024:01:01 00:00:00" -5 --sort-by created
  python timestamper.py "C:\\My Pictures" "2022:05:15 14:30:00" 1.5 --sort-by modified
```

# Requirements
- Python 3.x
- ExifTool (must be installed and accessible in system PATH)

# Notes
- Ensure ExifTool is installed and accessible in your system's PATH.
- Files are processed in the order determined by the sorting option.
- The script appends a comment to the EXIF UserComment tag indicating the change.

# License
MIT