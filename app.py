#!/usr/bin/env python3
"""
Streamlit app for displaying and searching broken links metadata.

This app provides an interface to:
1. View broken links metadata from various collections
2. Search and filter through the metadata
3. Display detailed information about each broken link
"""

import pandas as pd
import streamlit as st
from pathlib import Path
from typing import Dict, List, Optional
import re

# ─── CONFIG ────────────────────────────────────────────────────────────────
COLLECTION_NAME = "LPI Collection"
METADATA_FILE = "broken_links_with_metadata.csv"

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
    Filter DataFrame based on advanced search syntax and general search.
    """
    if not search_term:
        return df
    filters, general = parse_advanced_search(search_term)
    mask = pd.Series(True, index=df.index)
    # Field-specific filters
    for field, value in filters.items():
        if field in ['author', 'authors'] and 'author' in df.columns:
            mask &= df['author'].apply(lambda x: any(value.lower() in str(a).lower() for a in x))
        elif field in ['keyword', 'keywords'] and 'keywords' in df.columns:
            mask &= df['keywords'].apply(lambda x: any(value.lower() in str(k).lower() for k in x))
        elif field in ['title', 'abstract', 'collection', 'bibcode'] and field in df.columns:
            mask &= df[field].str.lower().fillna('').str.contains(value.lower(), na=False)
        elif field in ['year', 'pubdate'] and 'pubdate' in df.columns:
            mask &= df['pubdate'].str.contains(value, na=False)
    # General search
    if general:
        general = general.lower()
        general_mask = pd.Series(False, index=df.index)
        text_columns = ['title', 'abstract', 'bibcode']
        for col in text_columns:
            if col in df.columns:
                general_mask |= df[col].str.lower().fillna('').str.contains(general, na=False)
        list_columns = ['author', 'keywords']
        for col in list_columns:
            if col in df.columns:
                general_mask |= df[col].apply(lambda x: any(general in str(k).lower() for k in x))
        mask &= general_mask
    return df[mask]

# ─── MAIN APP ───────────────────────────────────────────────────────────
def main():
    """Main app function."""
    st.title("Broken Links on ADS")
    
    # Load data
    df = load_data()
    if df.empty:
        st.stop()
    
    # Search box (concise label, help tooltip)
    st.text_input(
        "Advanced search",
        key="search",
        help="Examples: year:2000 author:Smith title:Mars (or just type general search terms)"
    )
    search_term = st.session_state["search"]
    
    # Filter data
    filtered_df = filter_dataframe_advanced(df, search_term)
    
    # Display results
    st.markdown(f"### Found {len(filtered_df)} results")
    
    # Create expandable sections for each result
    for idx, row in filtered_df.iterrows():
        # Collapsed: title, authors, pubdate
        authors = ", ".join(row['author']) if row['author'] else "No authors available"
        pubdate = row['pubdate'] if pd.notna(row['pubdate']) else "No date available"
        label = f"{row['title']} | {authors} | {pubdate}"
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
                st.markdown("#### Broken Link")
                st.markdown(f"[{row['url']}]({row['url']})")
                st.markdown("#### Bibcode")
                st.markdown(f"[{row['bibcode']}](https://ui.adsabs.harvard.edu/abs/{row['bibcode']})")

if __name__ == "__main__":
    main() 