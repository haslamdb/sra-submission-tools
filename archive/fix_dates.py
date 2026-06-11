#!/usr/bin/env python3
"""
Fix collection_date format in SRA metadata files
"""

import pandas as pd
import re
import sys
import os

def validate_date_format(date_str):
    """
    Validate and convert date to ISO 8601 format.
    
    Supported formats:
    - "DD-Mmm-YYYY" (e.g., 30-Oct-1990)
    - "Mmm-YYYY" (e.g., Oct-1990)
    - "YYYY" (e.g., 1990)
    - ISO 8601: "YYYY-mm-dd" (e.g., 1990-10-30)
    - ISO 8601: "YYYY-mm" (e.g., 1990-10)
    - Range: "DD-Mmm-YYYY/DD-Mmm-YYYY" (e.g., 21-Oct-1952/15-Feb-1953)
    - With time: "YYYY-mm-ddThh:mm:ssZ" (e.g., 2015-10-11T17:53:03Z)
    - MM/DD/YYYY or DD/MM/YYYY: (e.g., 7/24/2017 or 24/7/2017)
    
    Returns:
        str: Validated date in ISO 8601 format
    """
    if not date_str or pd.isna(date_str) or str(date_str).strip() == "":
        return "not collected"
    
    if str(date_str).strip().lower() in ["not collected", "not provided", "unknown"]:
        return str(date_str).strip()
    
    # Convert to string and strip whitespace
    date_str = str(date_str).strip()
    
    # ISO 8601 with time (already correct format)
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$', date_str):
        return date_str
    
    # ISO 8601 date (already correct format)
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    
    # ISO 8601 year-month (already correct format)
    if re.match(r'^\d{4}-\d{2}$', date_str):
        return date_str
    
    # Year only
    if re.match(r'^\d{4}$', date_str):
        return date_str
    
    # Date range with slash
    if '/' in date_str and not re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', date_str):
        dates = date_str.split('/')
        if len(dates) == 2:
            start_date = validate_date_format(dates[0])
            end_date = validate_date_format(dates[1])
            if start_date and end_date:
                return f"{start_date}/{end_date}"
    
    # MM/DD/YYYY or DD/MM/YYYY format - common US date format
    mdy_or_dmy = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str)
    if mdy_or_dmy:
        d1, d2, year = mdy_or_dmy.groups()
        
        try:
            # Convert to integers for comparison
            d1_int = int(d1)
            d2_int = int(d2)
            
            # Assume MM/DD/YYYY for US format
            # But if d1 > 12, it's probably DD/MM/YYYY
            if d1_int > 12:
                day, month = d1, d2
            else:
                month, day = d1, d2
            
            # Ensure values are in valid ranges
            month_int = int(month)
            day_int = int(day)
            
            if month_int < 1 or month_int > 12:
                month = "01"  # Default to January if invalid
            
            if day_int < 1 or day_int > 31:
                day = "01"  # Default to 1st if invalid
            
            # Ensure two digits
            month = month.zfill(2)
            day = day.zfill(2)
            
            # Return in ISO format
            return f"{year}-{month}-{day}"
        except ValueError:
            # Try to recover with defaults
            return f"{year}-01-01"
    
    # DD-Mmm-YYYY format
    dd_mmm_yyyy = re.match(r'^(\d{1,2})[-/\s]([A-Za-z]{3})[-/\s](\d{4})$', date_str)
    if dd_mmm_yyyy:
        day, month, year = dd_mmm_yyyy.groups()
        
        # Convert month abbreviation to month number
        month_abbr = month.capitalize()
        month_dict = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        
        if month_abbr in month_dict:
            month_num = month_dict[month_abbr]
            day = day.zfill(2)  # Ensure two-digit day
            return f"{year}-{month_num}-{day}"
    
    # Mmm-YYYY format
    mmm_yyyy = re.match(r'^([A-Za-z]{3})[-/\s](\d{4})$', date_str)
    if mmm_yyyy:
        month, year = mmm_yyyy.groups()
        
        # Convert month abbreviation to month number
        month_abbr = month.capitalize()
        month_dict = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        
        if month_abbr in month_dict:
            month_num = month_dict[month_abbr]
            return f"{year}-{month_num}"
    
    # YYYY/MM/DD format
    ymd = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$', date_str)
    if ymd:
        year, month, day = ymd.groups()
        
        # Ensure two digits
        month = month.zfill(2)
        day = day.zfill(2)
        
        return f"{year}-{month}-{day}"
    
    # If we can't recognize the format, use default
    return "not collected"

def fix_metadata_dates(file_path, output_path=None):
    """
    Fix collection_date format in metadata file
    
    Args:
        file_path (str): Path to metadata file
        output_path (str): Path to save fixed file (if None, will use original with _fixed suffix)
    
    Returns:
        str: Path to fixed file
    """
    # Determine output path
    if not output_path:
        file_dir = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        file_base, file_ext = os.path.splitext(file_name)
        output_path = os.path.join(file_dir, f"{file_base}_fixed{file_ext}")
    
    # Determine file format
    file_ext = os.path.splitext(file_path)[1].lower()
    
    # Load file
    if file_ext == '.txt':
        df = pd.read_csv(file_path, sep='\t')
    elif file_ext in ['.xlsx', '.xls']:
        df = pd.read_excel(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_ext}. Only tab-delimited .txt or Excel .xlsx/.xls files are supported.")
    
    # Check if collection_date column exists
    if 'collection_date' not in df.columns:
        print(f"Warning: No collection_date column found in {file_path}")
        return file_path
    
    # Count values before validation
    empty_before = df['collection_date'].isna().sum() + (df['collection_date'] == '').sum()
    print(f"Before: {empty_before} empty collection_date values")
    
    # Fix collection_date format
    print(f"Fixing collection_date format in {file_path}...")
    df['collection_date'] = df['collection_date'].apply(validate_date_format)
    
    # Count values after validation
    empty_after = df['collection_date'].isna().sum() + (df['collection_date'] == '').sum()
    print(f"After: {empty_after} empty collection_date values")
    
    # Show sample of changes
    print("\nSample of changes:")
    for i in range(min(5, len(df))):
        print(f"{i+1}: {df['collection_date'].iloc[i]}")
    
    # Save fixed file
    if file_ext == '.txt':
        df.to_csv(output_path, sep='\t', index=False)
    elif file_ext in ['.xlsx', '.xls']:
        df.to_excel(output_path, index=False)
    
    print(f"Fixed file saved to {output_path}")
    return output_path

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python fix_dates.py <metadata_file> [output_file]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        fixed_path = fix_metadata_dates(file_path, output_path)
        print(f"Successfully processed {file_path}")
        print(f"Try running validation with the fixed file: {fixed_path}")
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()