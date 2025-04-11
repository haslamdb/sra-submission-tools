#!/usr/bin/env python3
"""
Test script for date validation
"""

import logging
import re
import sys
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    if not date_str or date_str.strip() == "":
        return ""
    
    if date_str == "not collected" or date_str == "not provided" or date_str == "unknown":
        return date_str 
    
    # Special case handling for "not collected" and similar values
    if str(date_str).strip().lower() in ["not collected", "not provided", "unknown"]:
        return str(date_str).strip()
    
    # Convert to string and strip whitespace
    date_str = str(date_str).strip()
    
    # Log the input date for debugging
    logger.info(f"Validating date format: '{date_str}'")
    
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
                logger.warning(f"Invalid month value {month_int} in date {date_str}")
                month = "01"  # Default to January if invalid
            
            if day_int < 1 or day_int > 31:
                logger.warning(f"Invalid day value {day_int} in date {date_str}")
                day = "01"  # Default to 1st if invalid
            
            # Ensure two digits
            month = month.zfill(2)
            day = day.zfill(2)
            
            # Return in ISO format
            return f"{year}-{month}-{day}"
        except ValueError as e:
            logger.warning(f"Error converting date parts to integers: {e}")
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
    
    # If we can't recognize the format, return as is with a warning
    logger.warning(f"Unrecognized date format: {date_str}")
    return date_str

def test_date_validation():
    """Test the date validation function with various formats"""
    test_dates = [
        "7/24/2017",        # MM/DD/YYYY
        "24/7/2017",        # DD/MM/YYYY
        "2017-07-24",       # ISO 8601
        "2017-07",          # ISO 8601 year-month
        "2017",             # Year only
        "24-Jul-2017",      # DD-Mmm-YYYY
        "Jul-2017",         # Mmm-YYYY
        "2017/07/24",       # YYYY/MM/DD
        "not collected",    # Special value
        "unknown",          # Special value
        "12/1/2016",        # MM/DD/YYYY with single digit
        "1/12/2016",        # MM/DD/YYYY with single digit (ambiguous)
        "13/12/2016",       # DD/MM/YYYY (>12 means it must be day)
        ""                  # Empty
    ]
    
    for date in test_dates:
        result = validate_date_format(date)
        print(f"Original: '{date}' -> Converted: '{result}'")

def test_pandas_date_handling():
    """Test how pandas handles dates in the actual bioproject metadata file"""
    try:
        import pandas as pd
        
        # Load the bioproject metadata file
        print("\nTesting pandas date handling on bioproject metadata file...")
        file_path = "/home/david/Documents/Code/sra-submission-tools/metadata_files/hellman-bioproject-metadata1.txt"
        df = pd.read_csv(file_path, sep='\t')
        
        # Print the first few collection_date values
        print("\nFirst 5 collection_date values from file:")
        for i in range(min(5, len(df))):
            value = df['collection_date'].iloc[i]
            print(f"Row {i+1}: '{value}' (type: {type(value)})")
        
        # Test validating these dates
        print("\nValidating the first 5 dates:")
        for i in range(min(5, len(df))):
            date_str = df['collection_date'].iloc[i]
            print(f"Original: '{date_str}'")
            try:
                result = validate_date_format(date_str)
                print(f"Converted: '{result}' (Success)")
            except Exception as e:
                print(f"ERROR: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # Test applying validation to the entire column
        print("\nAttempting to validate entire collection_date column...")
        try:
            df['validated_date'] = df['collection_date'].apply(validate_date_format)
            print("Success! First 5 validated dates:")
            for i in range(min(5, len(df))):
                print(f"{df['collection_date'].iloc[i]} -> {df['validated_date'].iloc[i]}")
        except Exception as e:
            print(f"ERROR validating column: {str(e)}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"Error in pandas date test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_date_validation()
    
    # Test pandas date handling
    test_pandas_date_handling()
    
    # If a date is provided as an argument, test that specific date
    if len(sys.argv) > 1:
        test_date = sys.argv[1]
        result = validate_date_format(test_date)
        print(f"\nValidating specific date: '{test_date}' -> '{result}'")