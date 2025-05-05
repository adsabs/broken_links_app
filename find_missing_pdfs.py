#!/usr/bin/env python3
"""
Script to identify records that don't have associated PDFs and output their metadata.
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict
import csv

def find_missing_pdfs(metadata_file: str = "broken_links_with_metadata.csv", 
                     pdf_dir: str = "pdfs") -> pd.DataFrame:
    """
    Find records that don't have associated PDFs.
    
    Args:
        metadata_file: Path to the metadata CSV file
        pdf_dir: Directory containing PDF files
        
    Returns:
        DataFrame containing records without PDFs
    """
    # Load metadata
    df = pd.read_csv(metadata_file)
    
    # Check which records have PDFs
    pdf_path = Path(pdf_dir)
    df['has_pdf'] = df['bibcode'].apply(lambda bib: (pdf_path / f"{bib}.pdf").exists())
    
    # Filter for records without PDFs
    missing_pdfs = df[~df['has_pdf']]
    
    return missing_pdfs

def save_missing_pdfs_report(df: pd.DataFrame, output_file: str = "missing_pdfs_report.csv") -> None:
    """
    Save the missing PDFs report to a CSV file.
    
    Args:
        df: DataFrame containing records without PDFs
        output_file: Path to save the report
    """
    # Select relevant columns
    columns = ['bibcode', 'title', 'author', 'pubdate', 'url', 'abstract', 'keywords']
    df = df[columns]
    
    # Save to CSV
    df.to_csv(output_file, index=False)
    print(f"Report saved to {output_file}")
    print(f"Total records without PDFs: {len(df)}")

def main() -> None:
    """Main function to run the script."""
    try:
        # Find records without PDFs
        missing_pdfs = find_missing_pdfs()
        
        # Save report
        save_missing_pdfs_report(missing_pdfs)
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 