# ⚡ INVINCIBLE

**INVINCIBLE** is a powerful, student-focused AI assistant powered by **Retrieval-Augmented Generation (RAG)**. Upload your notes, slides, PDFs, reports, datasets, and images to get intelligent, cited answers powered by Google Gemini.

## Features

✅ **Multi-format support** — PDFs, PowerPoint, Word docs, Markdown, CSV, images (PNG, JPG, BMP, WebP)  
✅ **Smart OCR** — Built-in Tesseract + Gemini vision fallback for scanned documents  
✅ **Hybrid retrieval** — Dense embeddings + keyword search + user feedback memory  
✅ **Cross-encoder reranking** — Ranked results for better relevance  
✅ **Conversation memory** — Multi-turn chat with context awareness  
✅ **Feedback learning** — Stores corrections for improved future answers  
✅ **Multiple UIs** — FastAPI backend, React frontend, and Streamlit demo  

## Project Structure

- [rag.py](rag.py) — Core RAG engine (ingestion, retrieval, generation)
- [api.py](api.py) — FastAPI REST service
- [app.py](app.py) — Streamlit UI
- [frontend/](frontend/) — React + TypeScript frontend

## Architecture

The system uses a standard RAG pipeline with OCR-enhanced ingestion:

1. File ingestion
2. Text extraction and OCR
3. Chunking
4. Dense embedding
5. Chroma vector storage
6. Hybrid retrieval
7. Cross-encoder reranking
8. Gemini answer generation

## Models And Methods

### LLM / generation

- Primary family: Google Gemini
- Configured in `GENERATION_MODEL`
- Current fallback list is built from:
  - `models/gemini-flash-lite-latest`
  - `gemini-flash-lite-latest`
  - `models/gemini-2.5-flash-lite`
  - `gemini-2.5-flash-lite`
  - `models/gemma-3-1b-it`
  - `gemma-3-1b-it`

### Embeddings

- Embedding provider: Google Generative AI embeddings via `langchain_google_genai`
- Default embedding model: `models/gemini-embedding-001`
- Used for:
  - document chunks
  - query embeddings
  - memory embeddings
  - feedback embeddings

### Vector database

- Vector database: ChromaDB persistent client
- Persistence folder: `./chroma_db`
- Distance metric: cosine similarity
- Collections:
  - main knowledge collection
  - feedback collection
  - memory collection

### Retrieval strategy

The app uses hybrid retrieval:

- Dense retrieval from Chroma using query embeddings
- Keyword retrieval using Chroma `where_document`
- Feedback retrieval from a separate correction store

The candidate chunks are then reranked using:

- Cross-encoder model: `cross-encoder/ms-marco-MiniLM-L-6-v2`

### Chunking

- Splitter: `RecursiveCharacterTextSplitter`
- Default chunk size: `800`
- Default overlap: `150`
- Separators:
  - paragraph
  - newline
  - sentence-level punctuation
  - word boundaries

## Supported File Types

- PDF
- PPTX
- DOCX
- TXT
- MD
- CSV
- PNG
- JPG / JPEG
- BMP
- WEBP

## OCR And Image Support

INVINCIBLE now supports OCR in two layers:

### Local OCR

- Engine: Tesseract via `pytesseract`
- Used automatically when `tesseract` is available in `PATH`

### Gemini OCR fallback

If Tesseract is not installed, INVINCIBLE falls back to Gemini vision-based OCR for:

- uploaded images
- embedded PDF images
- scanned PDF pages with little or no text layer

This means image-heavy PDFs such as academic calendars can still be ingested even without Tesseract installed.

## How PDF Extraction Works

For each PDF page:

1. Try normal text extraction with PyMuPDF (`fitz`)
2. OCR embedded images on the page
3. If the text layer is too weak, render the whole page as an image
4. Run OCR on the rendered page
5. Merge extracted text and OCR text before chunking

This is especially useful for:

- scanned PDFs
- notice boards
- academic calendars
- timetable images embedded in PDFs

## Conversation Memory

The app stores recent chat turns in a dedicated Chroma collection.

- Memory is embedded and stored per `session_id`
- Recent turns are included in prompt construction
- Old turns are trimmed using `MAX_MEMORY_TURNS`

## Feedback Memory

The system can store user corrections:

- wrong answer
- corrected answer
- query hash
- session metadata

These corrections are embedded and retrieved in future similar questions.

## Main Backend Flow

### Ingestion

- Parse file content
- Run OCR when needed
- Split into chunks
- Embed chunks with Gemini embeddings
- Upsert to Chroma

### Question answering

- Embed the user query
- Retrieve dense matches
- Retrieve keyword matches
- Retrieve saved corrections
- Merge candidates
- Rerank with cross-encoder
- Build a grounded prompt
- Generate a cited answer with Gemini

## Environment Variables

Important configuration values:

- `GEMINI_API_KEY`
- `CHROMA_PERSIST_DIR`
- `COLLECTION_NAME`
- `FEEDBACK_COLLECTION`
- `MEMORY_COLLECTION`
- `EMBEDDING_MODEL`
- `GENERATION_MODEL`
- `RERANKER_MODEL`
- `CHUNK_SIZE`
- `CHUNK_OVERLAP`
- `TOP_K_RETRIEVAL`
- `TOP_K_RERANKED`
- `MAX_MEMORY_TURNS`
- `OCR_MIN_TEXT_THRESHOLD`

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (optional but recommended)

### Setup

1. **Clone and install Python dependencies:**
   ```bash
   python -m venv .venv312
   source .venv312/bin/activate  # On Windows: .venv312\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Get a free Gemini API key:**
   - Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Create a new API key
   - Add to `.env`:
     ```
     GEMINI_API_KEY=your_key_here
     ```

3. **Install Tesseract (macOS):**
   ```bash
   brew install tesseract
   ```
   Or use Docker / system package manager for other OSes.

4. **Set up the frontend:**
   ```bash
   cd frontend
   npm install
   ```

## Run The Project

### Backend API

```bash
.venv312/bin/uvicorn api:app --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

### Streamlit app

```bash
streamlit run app.py
```

Then open:
- **API**: http://localhost:8000
- **Frontend**: http://localhost:5173
- **Streamlit**: http://localhost:8501

## How It Works

1. **Upload documents** — Drop PDFs, slides, notes, datasets, or images
2. **Intelligent parsing** — Automatic OCR, text extraction, and content analysis
3. **Chunking & embedding** — Documents split into semantic chunks and embedded with Gemini embeddings
4. **Storage** — Chunks stored in ChromaDB for fast retrieval
5. **Ask questions** — Query is embedded and compared against your documents
6. **Smart retrieval** — Hybrid search combines dense embeddings + keyword matching + saved corrections
7. **Reranking** — Cross-encoder model re-scores results for better relevance
8. **Generation** — Gemini generates cited answers based on top matches
9. **Learning** — Corrections stored to improve future answers

## Installation Notes

### Python dependencies

The project uses packages such as:

- `chromadb`
- `google-generativeai`
- `langchain-google-genai`
- `sentence-transformers`
- `pymupdf`
- `python-docx`
- `python-pptx`
- `pandas`
- `Pillow`
- `pytesseract`
- `streamlit`
- `fastapi`
- `uvicorn`

### Optional but recommended

Install Tesseract for faster local OCR:

```bash
brew install tesseract
```

Even without Tesseract, the app now has Gemini OCR fallback for images and scanned PDFs.

## Current Limitations

- OCR quality depends on image clarity
- Vision OCR can be slower than local Tesseract
- Large scanned PDFs may take longer to ingest
- The code currently uses `google.generativeai`, which shows a deprecation warning and should be migrated to `google.genai` later

## Files Guide

- [rag.py](rag.py) — InvincibleRAG engine (ingestion, OCR, retrieval, reranking, generation)
- [api.py](api.py) — FastAPI REST wrapper
- [app.py](app.py) — Streamlit UI
- [frontend/src/App.tsx](frontend/src/App.tsx) — React app shell
- [frontend/src/components/ui/claude-style-chat-input.tsx](frontend/src/components/ui/claude-style-chat-input.tsx) — Chat composer

## Troubleshooting

**"GEMINI_API_KEY not found"**
- Ensure `.env` file exists in the root directory with your API key

**"Tesseract not found"**
- Install via homebrew: `brew install tesseract`
- Or let INVINCIBLE fall back to Gemini vision OCR (slower but works)

**"ChromaDB persistence error"**
- Check `CHROMA_PERSIST_DIR` permissions
- Try deleting old backups in the directory

**"Slow OCR on large PDFs"**
- Install local Tesseract for 10-100x faster performance
- Or split large scanned PDFs into smaller files

## Contributing

Found a bug? Have a feature idea? Contributions welcome!

## License

MIT
