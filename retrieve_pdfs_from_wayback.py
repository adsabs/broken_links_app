#!/usr/bin/env python3
"""
Script to retrieve PDFs for broken links using the Internet Archive Wayback Machine.
"""

import os
import csv
import requests
from pathlib import Path
from typing import Optional, List
import time

WAYBACK_API = "http://archive.org/wayback/available"
CDX_API = "http://web.archive.org/cdx/search/cdx"
IA_SEARCH_API = "https://archive.org/advancedsearch.php"
PDF_DIR = "retrieved_pdfs"
CSV_FILE = "broken_links_with_metadata.csv"
LOG_FILE = "wayback_retrieval_log.csv"
NOT_FOUND_FILE = "not_found_pdfs.csv"

os.makedirs(PDF_DIR, exist_ok=True)

def get_all_wayback_snapshots(original_url: str) -> List[str]:
    """
    Get all snapshot URLs for a given URL from the Wayback Machine (oldest to newest).
    """
    params = {
        "url": original_url,
        "output": "json",
        "fl": "timestamp,original",
        "filter": "statuscode:200",
        "collapse": "digest"
    }
    try:
        resp = requests.get(CDX_API, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if len(data) > 1:
            # Skip header row
            snapshots = [
                f"http://web.archive.org/web/{row[0]}/{row[1]}"
                for row in data[1:]
            ]
            return snapshots
    except Exception as e:
        print(f"Error querying CDX for {original_url}: {e}")
    return []

def download_pdf(url: str, out_path: Path) -> (bool, str):
    """
    Download a PDF from the given URL to the specified path. Returns (success, reason).
    """
    try:
        resp = requests.get(url, timeout=30, stream=True)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "pdf" not in content_type.lower():
            return False, f"Content-Type not PDF: {content_type}"
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True, "Downloaded"
    except Exception as e:
        return False, f"Error: {e}"

def search_internet_archive(query: str) -> Optional[str]:
    """
    Search the Internet Archive for a PDF by query (bibcode or title).
    Returns the first PDF URL found, or None.
    """
    params = {
        "q": query,
        "fl[]": ["identifier", "title", "mediatype"],
        "output": "json",
        "rows": 10
    }
    try:
        resp = requests.get(IA_SEARCH_API, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        for doc in data.get("response", {}).get("docs", []):
            if doc.get("mediatype") == "texts":
                identifier = doc.get("identifier")
                # Try to construct a PDF URL
                pdf_url = f"https://archive.org/download/{identifier}/{identifier}.pdf"
                # Check if it exists
                head = requests.head(pdf_url, timeout=10)
                if head.status_code == 200:
                    return pdf_url
    except Exception as e:
        print(f"Error searching Internet Archive for '{query}': {e}")
    return None

def main():
    not_found_rows = []
    with open(CSV_FILE, newline='', encoding='utf-8') as csvfile, \
         open(LOG_FILE, 'w', newline='', encoding='utf-8') as logfile:
        reader = csv.DictReader(csvfile)
        fieldnames = reader.fieldnames + ["wayback_url", "pdf_downloaded", "attempts", "not_found_reason"]
        writer = csv.DictWriter(logfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            url = row.get("url", "")
            bibcode = row.get("bibcode", "")
            title = row.get("title", "")
            out_path = Path(PDF_DIR) / f"{bibcode or 'unknown'}.pdf"
            attempts = []
            pdf_downloaded = False
            not_found_reason = ""

            # Skip if already downloaded
            if out_path.exists():
                attempts.append("Already downloaded")
                pdf_downloaded = True
                row["wayback_url"] = ""
                row["pdf_downloaded"] = "True"
                row["attempts"] = "; ".join(attempts)
                row["not_found_reason"] = ""
                writer.writerow(row)
                print(f"{bibcode}: Already downloaded, skipping.")
                continue

            # 1. Try all Wayback snapshots for original URL
            snapshots = get_all_wayback_snapshots(url)
            for snap_url in snapshots:
                attempts.append(f"Wayback snapshot: {snap_url}")
                success, reason = download_pdf(snap_url, out_path)
                if success:
                    pdf_downloaded = True
                    row["wayback_url"] = snap_url
                    row["pdf_downloaded"] = "True"
                    row["attempts"] = "; ".join(attempts)
                    row["not_found_reason"] = ""
                    writer.writerow(row)
                    print(f"{bibcode}: PDF downloaded from Wayback snapshot.")
                    break
                else:
                    not_found_reason = f"Wayback snapshot not PDF: {reason}"
            if pdf_downloaded:
                continue
            if not snapshots:
                attempts.append("No Wayback snapshots found")
                not_found_reason = "No Wayback snapshots found"

            # 2. Try all Wayback snapshots for .pdf variant
            if not pdf_downloaded and not url.lower().endswith('.pdf'):
                pdf_url = url.rstrip('/') + '.pdf'
                pdf_snapshots = get_all_wayback_snapshots(pdf_url)
                for snap_url in pdf_snapshots:
                    attempts.append(f"Wayback snapshot (.pdf): {snap_url}")
                    success, reason = download_pdf(snap_url, out_path)
                    if success:
                        pdf_downloaded = True
                        row["wayback_url"] = snap_url
                        row["pdf_downloaded"] = "True"
                        row["attempts"] = "; ".join(attempts)
                        row["not_found_reason"] = ""
                        writer.writerow(row)
                        print(f"{bibcode}: PDF downloaded from Wayback snapshot (.pdf).")
                        break
                    else:
                        not_found_reason += f"; Wayback .pdf not PDF: {reason}"
                if pdf_downloaded:
                    continue
                if not pdf_snapshots:
                    attempts.append("No Wayback .pdf snapshots found")
                    not_found_reason += "; No Wayback .pdf snapshots found"

            # 3. Try original URL directly
            if not pdf_downloaded:
                attempts.append("Tried original URL directly")
                success, reason = download_pdf(url, out_path)
                if success:
                    pdf_downloaded = True
                    row["wayback_url"] = ""
                    row["pdf_downloaded"] = "True"
                    row["attempts"] = "; ".join(attempts)
                    row["not_found_reason"] = ""
                    writer.writerow(row)
                    print(f"{bibcode}: PDF downloaded from original URL.")
                    continue
                else:
                    not_found_reason += f"; Original URL not PDF: {reason}"

            # 4. Search Internet Archive by bibcode and title
            if not pdf_downloaded:
                for query in [bibcode, title]:
                    if not query:
                        continue
                    attempts.append(f"Searched IA for '{query}'")
                    ia_pdf_url = search_internet_archive(query)
                    if ia_pdf_url:
                        success, reason = download_pdf(ia_pdf_url, out_path)
                        if success:
                            pdf_downloaded = True
                            row["wayback_url"] = ia_pdf_url
                            row["pdf_downloaded"] = "True"
                            row["attempts"] = "; ".join(attempts)
                            row["not_found_reason"] = ""
                            writer.writerow(row)
                            print(f"{bibcode}: PDF downloaded from Internet Archive search.")
                            break
                        else:
                            not_found_reason += f"; IA search not PDF: {reason}"
                if pdf_downloaded:
                    continue
                not_found_reason += "; No PDF found in IA search"

            # If not found, log to not_found_pdfs.csv
            if not pdf_downloaded:
                row["wayback_url"] = ""
                row["pdf_downloaded"] = "False"
                row["attempts"] = "; ".join(attempts)
                row["not_found_reason"] = not_found_reason.strip('; ')
                writer.writerow(row)
                not_found_rows.append({
                    "bibcode": bibcode,
                    "url": url,
                    "reason": not_found_reason.strip('; ')
                })
                print(f"{bibcode}: PDF not found. {not_found_reason.strip('; ')}")

    # Write not found list
    if not_found_rows:
        with open(NOT_FOUND_FILE, 'w', newline='', encoding='utf-8') as nf:
            nf_writer = csv.DictWriter(nf, fieldnames=["bibcode", "url", "reason"])
            nf_writer.writeheader()
            for row in not_found_rows:
                nf_writer.writerow(row)

if __name__ == "__main__":
    main()
