
# AUTOSAR Architecture Agent
 
An AI-powered tool for generating and editing AUTOSAR ARXML files using natural language. Supports multiple AI providers (Gemini, OpenAI, Anthropic) and provides both CLI and Web UI interfaces.
 
## Features
 
- **Multi-AI Model Support**: Choose from Gemini, OpenAI, or Anthropic models
- **Natural Language Input**: Describe what you want in plain English
- **Edit Mode**: Modify existing ARXML files without recreating from scratch
- **Automatic Error Recovery**: Up to 10 retry attempts with intelligent code fixing
- **Web UI & CLI**: Use Streamlit web interface or command line
- **Knowledge-Based Generation**: Uses autosarfactory library patterns for accurate code
- **RAG-Enhanced Intelligence**: Uses Retrieval-Augmented Generation to understand complex AUTOSAR concepts (from TPS PDF) and ensure accurate API usage (from codebase).
 
## Installation
 
### Prerequisites
 
- Python 3.10+
- pip
 
### Install Dependencies
 
```bash
pip install -r requirements.txt
```
 
*Note: This will install packages for RAG support including `langchain`, `chromadb`, and `sentence-transformers`.*

### API Keys
 
Set at least one of these environment variables:
 
```bash
# Google Gemini (recommended)
export GEMINI_API_KEY="your-api-key"
 
# OpenAI
export OPENAI_API_KEY="your-api-key"
 
# Anthropic Claude
export ANTHROPIC_API_KEY="your-api-key"
```
 
## Usage
 
### Web UI (Streamlit)
 
```bash
streamlit run app.py
```
 
Then open http://localhost:8501 in your browser.

**Features:**
- Select AI provider and model from sidebar
- Upload existing ARXML files for editing
- Chat-based interface for requirements
- Download generated ARXML and Python scripts
- **Automatic Knowledge Base**: The system automatically ingests the AUTOSAR TPS specification and Codebase API on first run.

### Command Line Interface
 
```bash
# Basic usage
python -m src.main "Create a CAN cluster with 500kbps baudrate"
 
# Specify provider and model
python -m src.main --provider openai --model gpt-4o "Create CAN frames"
 
# Edit existing file
python -m src.main --edit existing.arxml "Add a new CAN frame with ID 0x200"
 
# Auto-approve plan (skip confirmation)
python -m src.main --yes "Create a simple CAN message"
 
# List available providers
python -m src.main --list-providers
```
 
**CLI Options:**
| Option | Description |
|--------|-------------|
| `--provider, -p` | AI provider: gemini, openai, anthropic |
| `--model, -m` | Specific model to use |
| `--edit, -e FILE` | Edit an existing ARXML file |
| `--output, -o FILE` | Output filename (default: output.arxml) |
| `--yes, -y` | Auto-approve the plan |
| `--max-retries, -r N` | Max fix attempts (default: 10) |
| `--list-providers, -l` | Show available providers |
 
## RAG System (Knowledge Base)

The agent uses a dual RAG (Retrieval-Augmented Generation) system to improve accuracy:

1.  **TPS Knowledge Base**: Indexes the `AUTOSAR_CP_TPS_SystemTemplate.pdf` to understand high-level concepts (e.g., "Ethernet Cluster", "Service Oriented Architecture"). This helps in the **Planning Phase**.
2.  **Codebase Knowledge Base**: Indexes the `autosarfactory` library to understand the exact Python API (classes, methods, signatures). This helps in the **Code Generation Phase**.

**Initialization**:
- The knowledge bases are automatically initialized the first time you run the application.
- This process may take 1-2 minutes as it ingests the PDF and codebase.
- Data is persisted locally in `tps_knowledge_db/` and `codebase_knowledge_db/`.

## Examples
 
### Create a CAN Network
 
```bash
python -m src.main "Create a CAN cluster named HS_CAN with 500kbps baudrate,
a physical channel, and a frame with ID 0x100"
```
 
### Add Software Component
 
```bash
python -m src.main "Create an ApplicationSwComponentType with a sender-receiver
interface, an internal behavior with a runnable triggered every 100ms"
```
 
### Edit Existing File
 
```bash
python -m src.main --edit network.arxml "Change the timing event period to 10ms"
```
 
### Signal Routing
 
```bash
python -m src.main "Create a signal routing from frame 0x100 to frame 0x200
with a gateway software component"
```

### Complex Architectures (New!)

```bash
python -m src.main "Create a Service Oriented Architecture for Ethernet with SomeIP"
```
 
## Architecture
 
```
Autosafactory_gen/
├── app.py                 # Streamlit Web UI
├── src/
│   ├── main.py           # CLI entry point
│   ├── planner.py        # AI planning phase (uses TPS RAG)
│   ├── generator.py      # Code generation (uses Codebase RAG)
│   ├── rag_tps.py        # TPS PDF Knowledge Base
│   ├── rag_codebase.py   # Codebase API Knowledge Base
│   ├── rag_utils.py      # Shared RAG utilities
│   ├── executor.py       # Script execution & verification
│   ├── fixer.py          # Error recovery & code fixing
│   ├── utils.py          # Multi-provider LLM utilities
│   ├── knowledge.py      # API introspection
│   ├── patterns.py       # Working code patterns
│   └── arxml_analyzer.py # Parse existing ARXML files
├── autosarfactory/       # AUTOSAR factory library
├── tps_knowledge_db/     # Vector store for TPS (generated)
├── codebase_knowledge_db/# Vector store for API (generated)
└── providers/            # Provider implementations
```
 
## How It Works
 
1.  **Planning**: AI analyzes your requirement using **TPS RAG** to understand the architectural needs.
2.  **Generation**: Generates Python code using **Codebase RAG** to find the correct `autosarfactory` classes and methods.
3.  **Execution**: Runs the script to create/modify ARXML.
4.  **Verification**: Validates the generated ARXML structure.
5.  **Fixing**: If errors occur, AI analyzes and fixes the code (up to 10 retries).
 
## Supported AUTOSAR Elements
 
- **Communication**: CAN Clusters, Frames, Signals, PDUs, Physical Channels
- **Software Components**: Application SWC, Composition SWC, Ports, Interfaces
- **Behavior**: Internal Behaviors, Runnables, Timing Events
- **Data Types**: Base Types, Implementation Data Types
- **ECU**: ECU Instances, Communication Controllers
- **System**: System descriptions, Mappings
 
## Edit Mode
 
Edit mode allows modifying existing ARXML files:
 
```python
# The tool automatically:
# 1. Loads the file with autosarfactory.read()
# 2. Discovers existing elements by TYPE (not assumed names)
# 3. Navigates to find what needs modification
# 4. Makes changes and saves
```
 
**Key behaviors:**
- Searches by element TYPE, not hardcoded names
- Creates missing elements if needed
- Preserves existing structure
- Supports saveAs for new output files
 
## Troubleshooting
 
### No API Key Found
```
Set one of: GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY
```
 
### Edit Mode File Not Found
- Ensure the file path is correct
- Use absolute paths on Windows
 
### Generation Failures
- The tool retries up to 10 times automatically
- Check the execution logs for specific errors
- Try a simpler request first
 
## Contributing
 
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request
 
## License
 
MIT License - see [LICENSE](LICENSE) for details.
 
## Acknowledgments
 
- Built on the [autosarfactory](https://github.com/girishchandranc/autosarfactory) library
- Powered by Gemini, OpenAI, and Anthropic AI models
