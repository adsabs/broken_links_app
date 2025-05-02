# Broken Links on ADS

A Streamlit web application for searching and exploring broken links in the NASA ADS (Astrophysics Data System) collections. This app allows users to search, filter, and view metadata for publications with broken links, supporting advanced field-specific queries.

## Features
- **Advanced Search:**
  - Search by year, author, title, keywords, or any combination (e.g., `year:2000 author:Smith title:Mars`).
  - General search across all fields is also supported.
- **Metadata Display:**
  - Collapsed view shows title, authors, and publication date.
  - Expandable view reveals full metadata, including abstract, keywords, collection, and broken link.
- **Collection Labeling:**
  - Each record is tagged with its collection (e.g., "LPI Collection").
- **Modern UI:**
  - Clean, responsive, and user-friendly interface.

## Getting Started

### Prerequisites
- Python 3.9+
- [pip](https://pip.pypa.io/en/stable/)

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/adsabs/broken_links_app.git
   cd broken_links_app
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Make sure you have a `broken_links_with_metadata.csv` file in the project directory.

### Running Locally
```bash
streamlit run app.py
```
The app will be available at [http://localhost:8501](http://localhost:8501).

## Deployment on Render
This app is ready for deployment on [Render](https://render.com/):
- The `render.yaml` file is included for easy setup.
- After pushing to GitHub, create a new Web Service on Render and connect your repo.
- Add your custom domain (e.g., `brokenlinks.sjarmak.ai`) in the Render dashboard and update your DNS as instructed.

## Search Syntax
- **Field-specific search:**
  - `year:2000 author:Smith title:Mars`
  - `keywords:astrobiology`
- **General search:**
  - `Mars exploration`
- **Quoted values:**
  - `title:"Mars Exploration"`
- **Combine filters:**
  - `year:2000 author:Smith Mars`

## File Structure
```
.
├── app.py                  # Streamlit app
├── requirements.txt        # Python dependencies
├── render.yaml             # Render deployment config
├── broken_links_with_metadata.csv  # Data file
└── README.md               # This file
```

## License
MIT License

## Contact
For questions or contributions, open an issue or pull request on [GitHub](https://github.com/adsabs/broken_links_app). 