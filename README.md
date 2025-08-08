# Qaamuus - Somali Dictionary Web App

A modern web application for browsing and searching Somali words and their definitions, extracted from the qaam.pdf dictionary file.

## Features

- 📚 **PDF Extraction**: Automatically extracts words and definitions from qaam.pdf
- 🔍 **Smart Search**: Search for words with real-time results and highlighting
- 📱 **Responsive Design**: Works beautifully on desktop and mobile devices
- ⚡ **Fast Performance**: Cached dictionary data for quick searches
- 🎨 **Modern UI**: Clean, intuitive interface with smooth animations

## Setup Instructions

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Application**
   ```bash
   python app.py
   ```

3. **Access the Dictionary**
   Open your browser and go to: `http://localhost:5000`

## How It Works

1. **First Run**: The app extracts all words and definitions from `qaam.pdf` and caches them in `dictionary_cache.json`
2. **Subsequent Runs**: Uses the cached data for faster loading
3. **Search**: Type any Somali word to find matches and definitions
4. **Browse**: Click "Show All" to see all available words

## Technical Details

- **Backend**: Flask (Python)
- **PDF Processing**: PyPDF2
- **Frontend**: HTML5, CSS3, JavaScript
- **Data Storage**: JSON cache file
- **Search**: Real-time client-side and server-side search

## File Structure

```
Qaamuus App/
├── app.py                 # Main Flask application
├── qaam.pdf              # Source dictionary PDF
├── requirements.txt      # Python dependencies
├── dictionary_cache.json # Cached extracted data (auto-generated)
├── templates/
│   └── index.html        # Web interface
└── README.md            # This file
```

## Usage Tips

- Search works with partial matches
- Results are highlighted for easy reading
- The app automatically caches extracted data for better performance
- If the PDF format changes, delete `dictionary_cache.json` to re-extract

## Troubleshooting

- If no words appear, check that `qaam.pdf` is in the same directory as `app.py`
- Delete `dictionary_cache.json` and restart if you update the PDF file
- Check the console output for extraction progress and any errors
