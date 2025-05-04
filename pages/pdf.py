"""
PDF serving page for the Broken Links app.
This page handles direct PDF access through URLs.
"""

import streamlit as st
from pathlib import Path
import re
from typing import Optional, Tuple
import base64

# ─── CONFIG ────────────────────────────────────────────────────────────────
PDF_DIR = Path("pdfs")

def get_bibcode_from_url(url_name: str) -> str:
    """
    Convert URL-friendly name back to Bibcode.
    
    Args:
        url_name: URL-friendly filename
        
    Returns:
        Original Bibcode
    """
    # Remove .pdf extension and convert underscores back to dots
    bibcode = url_name.replace('.pdf', '').replace('_', '.')
    return bibcode

def get_pdf_data(bibcode: str) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Get PDF data and filename for a given Bibcode.
    
    Args:
        bibcode: Bibcode of the paper
        
    Returns:
        Tuple of (PDF bytes, error message if any)
    """
    pdf_path = PDF_DIR / f"{bibcode}.pdf"
    # Debug: print the path being checked
    print(f"[DEBUG] Looking for PDF at: {pdf_path.resolve()}")
    
    if not pdf_path.exists():
        return None, f"PDF not found at {pdf_path.resolve()}"
    
    try:
        with open(pdf_path, "rb") as f:
            return f.read(), None
    except Exception as e:
        return None, f"Error reading PDF: {str(e)} (Path: {pdf_path.resolve()})"

def main():
    """Main function to serve PDFs."""
    st.set_page_config(page_title="PDF Viewer", layout="wide")
    
    # Get the PDF name from the URL
    query_params = st.query_params
    pdf_name = query_params.get('name', [None])[0]
    print(f"[DEBUG] pdf_name from query params: {pdf_name}")
    
    if not pdf_name:
        st.error("No PDF specified")
        return
    
    # Convert URL name back to Bibcode
    bibcode = get_bibcode_from_url(pdf_name)
    print(f"[DEBUG] bibcode after conversion: {bibcode}")
    
    # Get PDF data
    pdf_bytes, error = get_pdf_data(bibcode)
    
    if error:
        st.error(error)
        return
    
    # Display PDF viewer and download button
    st.title(f"PDF Viewer: {bibcode}")
    
    # Create two columns for viewer and download button
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Display PDF in viewer
        st.components.v1.iframe(
            f"data:application/pdf;base64,{base64.b64encode(pdf_bytes).decode()}",
            height=800,
            scrolling=True
        )
    
    with col2:
        st.markdown("### Download Options")
        st.download_button(
            label="Download PDF",
            data=pdf_bytes,
            file_name=f"{bibcode}.pdf",
            mime="application/pdf"
        )
        
        # Add a link back to the main app
        st.markdown("---")
        st.markdown("[← Back to Main App](/app)")

if __name__ == "__main__":
    main() 