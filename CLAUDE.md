# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application

```bash
# Quick start (recommended)
./run.sh

# Manual start
uv sync
cd backend && uv run uvicorn app:app --reload --port 8000
```

### Environment Setup

- Create `.env` file in root with `ANTHROPIC_API_KEY=your_key_here`
- Application runs at http://localhost:8000
- API docs available at http://localhost:8000/docs

### Development Server

- Uses uvicorn with --reload for auto-restart on changes
- Backend runs from `backend/` directory using uv package manager
- **Always use `uv` for package management - never use `pip` directly**
- Frontend served as static files from `frontend/` directory

## Architecture Overview

### RAG System Pipeline

The application implements a Retrieval-Augmented Generation system with these core components:

1. **Document Processing Pipeline** (`document_processor.py`):

   - Parses structured course documents with metadata (title, instructor, lessons)
   - Implements sentence-aware chunking with configurable overlap
   - Enhances chunks with contextual information (course + lesson context)

2. **Vector Storage Layer** (`vector_store.py`):

   - ChromaDB for persistent vector storage with sentence-transformers embeddings
   - Dual storage: course metadata + content chunks with semantic search
   - Smart filtering by course name and lesson number

3. **AI Integration** (`ai_generator.py`):

   - Anthropic Claude API with tool calling capabilities
   - Autonomous decision making: search vs general knowledge responses
   - Conversation history management and context building

4. **Tool-Based Search** (`search_tools.py`):

   - Implements Tool interface for Claude's function calling
   - CourseSearchTool handles semantic search with course/lesson filtering
   - Source tracking for frontend citation display

5. **Session Management** (`session_manager.py`):
   - Maintains conversation context across queries
   - Configurable history limits (MAX_HISTORY in config)

### Component Relationships

- **RAG System** (`rag_system.py`) orchestrates all components
- **FastAPI App** (`app.py`) provides REST API with Pydantic models
- **Frontend** (`frontend/`) is vanilla HTML/CSS/JS with markdown rendering
- **Configuration** (`config.py`) centralizes all settings with environment variables

### Document Structure Expected

```
Course Title: [title]
Course Link: [url]
Course Instructor: [instructor]

Lesson 0: [lesson title]
Lesson Link: [lesson url]
[lesson content...]
```

### Key Design Patterns

- **Tool-based architecture**: Claude autonomously chooses when to search course materials
- **Dual-phase AI calls**: Initial call → tool execution → synthesis call
- **Context injection**: Chunks enhanced with "Course X Lesson Y content: ..." prefixes
- **Source propagation**: Search sources tracked through tool execution to frontend display
- **Session-based conversations**: Maintains context while allowing independent queries

### Configuration Points

All settings in `config.py`:

- `CHUNK_SIZE`: Text chunk size for vector storage (default: 800)
- `CHUNK_OVERLAP`: Character overlap between chunks (default: 100)
- `MAX_RESULTS`: Search results returned (default: 5)
- `MAX_HISTORY`: Conversation messages remembered (default: 2)
- `EMBEDDING_MODEL`: Sentence transformer model (default: "all-MiniLM-L6-v2")

### Data Models

- **Course**: Contains title, instructor, lessons list
- **Lesson**: lesson_number, title, optional lesson_link
- **CourseChunk**: content, course_title, lesson_number, chunk_index

### Development Notes

- No test framework currently implemented
- ChromaDB data stored in `backend/chroma_db/` (gitignored)
- Frontend uses marked.js for markdown rendering
- Static file serving integrated into FastAPI app
- Document loading happens on server startup from `../docs` folder
- make usre to use uv to manage all dependecies
- make sure to use uv to manage all dependecies
- don't run the server using ./run.sh. I will start it myself
- Always use descripitive variable name
