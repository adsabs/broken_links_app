#!/usr/bin/env python3
"""
Streamlit app for displaying and searching broken links metadata.

This app provides an interface to:
1. View broken links metadata from various collections
2. Search and filter through the metadata
3. Display detailed information about each broken link
4. Serve associated PDFs when available
"""

import pandas as pd
import streamlit as st
from pathlib import Path
from typing import Dict, List, Optional
import re
import base64
from io import BytesIO
import os

print(f"[DEBUG] st.query_params at import: {st.query_params}")

# ─── CONFIG ────────────────────────────────────────────────────────────────
COLLECTION_NAME = "LPI Collection"
METADATA_FILE = "broken_links_with_metadata.csv"
PDF_DIR = Path("pdfs")

# ─── PDF HANDLING ─────────────────────────────────────────────────────────
def get_pdf_url(bibcode: str) -> Optional[str]:
    """
    Generate a direct URL for a PDF file.
    
    Args:
        bibcode: Bibcode of the paper
        
    Returns:
        URL string for the PDF if it exists, None otherwise
    """
    pdf_path = PDF_DIR / f"{bibcode}.pdf"
    if not pdf_path.exists():
        return None
    
    # Create a unique URL-friendly name
    url_name = f"{bibcode.replace('.', '_')}.pdf"
    return f"/pdf?name={url_name}"

def serve_pdf(pdf_path: Path) -> bytes:
    """
    Serve a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        PDF file contents as bytes
    """
    with open(pdf_path, "rb") as f:
        return f.read()

def pdf_available(bibcode: str) -> bool:
    """
    Check if a PDF exists for the given bibcode.
    """
    pdf_path = PDF_DIR / f"{bibcode}.pdf"
    return pdf_path.exists()

# ─── PAGE CONFIG ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Broken Links on ADS",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CUSTOM CSS ───────────────────────────────────────────────────────────
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stDataFrame {
        width: 100%;
    }
    </style>
""", unsafe_allow_html=True)

# ─── DATA LOADING ─────────────────────────────────────────────────────────
@st.cache_data
def load_data() -> pd.DataFrame:
    """
    Load and prepare the metadata DataFrame.
    Adds a 'has_pdf' column for PDF availability.
    
    Returns:
        pd.DataFrame: Processed metadata DataFrame
    """
    if not Path(METADATA_FILE).exists():
        st.error(f"Metadata file {METADATA_FILE} not found!")
        return pd.DataFrame()
    
    df = pd.read_csv(METADATA_FILE)
    df['collection'] = COLLECTION_NAME
    
    # Convert string lists to actual lists
    for col in ['author', 'keywords']:
        if col in df.columns:
            df[col] = df[col].fillna('').apply(lambda x: [k.strip() for k in x.split(';') if k.strip()])
    
    # Add has_pdf column
    df['has_pdf'] = df['bibcode'].apply(lambda bib: (PDF_DIR / f"{bib}.pdf").exists())
    return df

# ─── SEARCH FUNCTIONS ────────────────────────────────────────────────────
def parse_advanced_search(search_term: str) -> (dict, str):
    """
    Parse advanced search syntax like 'year:2000 author:Smith title:Mars'.
    Returns a dict of field filters and a general search string.
    """
    pattern = re.compile(r'(\w+):"([^"]+)"|(\w+):(\S+)')
    filters = {}
    rest = search_term
    for match in pattern.finditer(search_term):
        field = match.group(1) or match.group(3)
        value = match.group(2) or match.group(4)
        filters[field.lower()] = value
        rest = rest.replace(match.group(0), '')
    rest = rest.strip()
    return filters, rest

def filter_dataframe_advanced(df: pd.DataFrame, search_term: str) -> pd.DataFrame:
    """
    Filter DataFrame based on advanced search syntax and general search, supporting boolean logic (AND, OR, NOT) in general search.
    """
    if not search_term:
        return df
    
    # Split search term into field-specific filters and general search
    filters, general = parse_advanced_search(search_term)
    
    # Start with all records
    mask = pd.Series(True, index=df.index)
    
    # Apply field-specific filters
    for field, value in filters.items():
        if field in ['author', 'authors'] and 'author' in df.columns:
            mask &= df['author'].apply(lambda x: any(value.lower() in str(a).lower() for a in x))
        elif field in ['keyword', 'keywords'] and 'keywords' in df.columns:
            mask &= df['keywords'].apply(lambda x: any(value.lower() in str(k).lower() for k in x))
        elif field in ['title', 'abstract', 'collection', 'bibcode'] and field in df.columns:
            mask &= field_filter(df[field], value)
        elif field == 'url' and 'url' in df.columns:
            mask &= field_filter(df['url'], value)
        elif field in ['year', 'pubdate'] and 'pubdate' in df.columns:
            mask &= df['pubdate'].str.contains(value, na=False)
        elif field == 'has_pdf' and 'has_pdf' in df.columns:
            if value == '*' or value == '':
                mask &= df['has_pdf']
            else:
                mask &= df['has_pdf'] == (value.lower() in ['true', 'yes', '1'])
        elif field == 'no_pdf' and 'has_pdf' in df.columns:
            if value == '*' or value == '':
                mask &= ~df['has_pdf']
            else:
                mask &= df['has_pdf'] == (value.lower() not in ['true', 'yes', '1'])
    
    # Only apply general search if there is no field-specific filter
    if general and not filters:
        general = general.lower()
        # Split on OR first
        or_parts = [part.strip() for part in re.split(r'\s+or\s+', general)]
        or_masks = []
        for or_part in or_parts:
            # Split on AND
            and_parts = [p.strip() for p in re.split(r'\s+and\s+', or_part)]
            and_mask = pd.Series(True, index=df.index)
            for and_part in and_parts:
                # Handle NOT and parentheses for nested logic
                part = and_part.strip()
                if part.startswith('not '):
                    sub_term = part[4:].strip()
                    and_mask &= ~_search_any_field(df, sub_term)
                elif part.startswith('(') and part.endswith(')'):
                    # Recursively handle nested boolean logic
                    nested = part[1:-1].strip()
                    nested_mask = filter_dataframe_advanced(df, nested).index
                    and_mask &= df.index.isin(nested_mask)
                else:
                    and_mask &= _search_any_field(df, part)
            or_masks.append(and_mask)
        # Combine all OR masks
        if or_masks:
            general_mask = or_masks[0]
            for m in or_masks[1:]:
                general_mask |= m
            mask &= general_mask
    
    return df[mask]

def _search_any_field(df: pd.DataFrame, term: str) -> pd.Series:
    """
    Search for a term in all relevant fields (title, abstract, bibcode, author, keywords).
    Returns a boolean mask.
    """
    term = term.strip().lower()
    mask = pd.Series(False, index=df.index)
    text_columns = ['title', 'abstract', 'bibcode']
    for col in text_columns:
        if col in df.columns:
            mask |= df[col].str.lower().fillna('').str.contains(term, na=False)
    list_columns = ['author', 'keywords']
    for col in list_columns:
        if col in df.columns:
            mask |= df[col].apply(lambda x: any(term in str(k).lower() for k in x))
    return mask

def field_filter(series: pd.Series, value: str) -> pd.Series:
    """
    Generalized field filter supporting NOT/! and * wildcards.
    Returns a boolean mask.
    """
    val = value.lower().strip()
    is_not = False
    if val.startswith('not '):
        is_not = True
        val = val[4:].strip()
    elif val.startswith('!'):
        is_not = True
        val = val[1:].strip()
    
    # Convert * to regex pattern
    pattern = re.escape(val).replace('\\*', '.*')
    
    # Create mask for matching values
    match_mask = series.str.lower().fillna('').str.contains(pattern, na=False, regex=True)
    
    # For NOT conditions, return True for:
    # 1. Records that don't match the pattern
    # 2. Records with NaN values
    # 3. Records with empty strings
    if is_not:
        return ~match_mask | series.isna() | (series.str.strip().eq(''))
    else:
        return match_mask

def display_pdf_link(bibcode: str) -> None:
    """
    Display a download button for the PDF matching the bibcode.
    """
    pdf_path = PDF_DIR / f"{bibcode}.pdf"
    if pdf_path.exists():
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        st.download_button(
            label="Download PDF",
            data=pdf_bytes,
            file_name=f"{bibcode}.pdf",
            mime="application/pdf"
        )
    else:
        st.markdown("PDF not available")

# ─── MAIN APP ───────────────────────────────────────────────────────────
def main():
    """Main app function."""
    st.title("Broken Links on ADS")
    st.markdown(
        """
        **PDF Availability Legend:**
        - ✅ = PDF available for this record
        - ❌ = No PDF available for this record
        
        **Search Tips:**
        - Use `field:value` to search specific fields (e.g. `url:leag*`)
        - Use `*` as a wildcard (e.g. `url:leag*` matches any URL containing 'leag')
        - Use `!` for negation (e.g. `url:!leag*` to find URLs not containing 'leag')
        - Use `AND`, `OR`, and parentheses for complex/nested boolean logic (e.g. `!keyword AND (keyword OR keyword)`)
        - Searchable fields include: year, author, title, abstract, keywords, collection, bibcode, pubdate, has_pdf, no_pdf, url
        """
    )
    
    # Load data
    df = load_data()
    if df.empty:
        st.stop()
    
    # List searchable fields and examples above the search bar
    searchable_fields = [
        "year (from pubdate)",
        "author",
        "title",
        "abstract",
        "keywords",
        "collection",
        "bibcode",
        "pubdate",
        "has_pdf",
        "no_pdf"
    ]
    st.markdown(
        "**Searchable fields:** " + ", ".join(searchable_fields)
    )
    st.markdown(
        "**Examples:** `year:2000 author:Smith title:Mars` &nbsp;&nbsp;|&nbsp;&nbsp; `Mars exploration` (unfielded search)"
    )
    
    # Search box (no help tooltip, no ? icon)
    search_term = st.text_input(
        "Search",
        key="search"
    )
    
    # Filter data
    filtered_df = filter_dataframe_advanced(df, search_term)
    
    # Pagination controls
    page_size = st.selectbox("Results per page", [10, 25, 50, 100], index=0)
    total_results = len(filtered_df)
    total_pages = max(1, (total_results + page_size - 1) // page_size)
    page_num = st.number_input(
        "Page", min_value=1, max_value=total_pages, value=1, step=1, format="%d"
    )
    start_idx = (page_num - 1) * page_size
    end_idx = min(start_idx + page_size, total_results)
    page_df = filtered_df.iloc[start_idx:end_idx]
    
    st.markdown(f"### Showing results {start_idx+1}–{end_idx} of {total_results}")
    
    # Create expandable sections for each result on the current page
    for idx, row in page_df.iterrows():
        # Collapsed: title, authors, pubdate
        authors = ", ".join(row['author']) if row['author'] else "No authors available"
        pubdate = row['pubdate'] if pd.notna(row['pubdate']) else "No date available"
        pdf_status = "✅" if row['has_pdf'] else "❌"
        label = f"{pdf_status} {row['title']} | {authors} | {pubdate}"
        with st.expander(label):
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown("#### Abstract")
                st.markdown(row['abstract'] if pd.notna(row['abstract']) else "No abstract available")
                st.markdown("#### Authors")
                st.markdown(authors)
                st.markdown("#### Keywords")
                st.markdown(", ".join(row['keywords']) if row['keywords'] else "No keywords available")
            with col2:
                st.markdown("#### Publication Date")
                st.markdown(pubdate)
                st.markdown("#### Collection")
                st.markdown(row['collection'])
                st.markdown("#### Bibcode")
                st.markdown(f"[{row['bibcode']}](https://ui.adsabs.harvard.edu/abs/{row['bibcode']})")
                display_pdf_link(row['bibcode'])
                st.markdown(f"**{pdf_status}**")
                print(f"[DEBUG] Displaying record with bibcode: {row['bibcode']}")

if __name__ == "__main__":
    main() 