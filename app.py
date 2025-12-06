"""
AUTOSAR Architecture Agent - Web UI
====================================
Streamlit-based web application for ARXML generation with multi-model support.
"""

import streamlit as st
import os
import sys
import tempfile

# Ensure src is in path
sys.path.append(os.getcwd())

from src.planner import Planner
from src.generator import Generator
from src.executor import Executor
from src.fixer import Fixer
from src.utils import (
    load_api_key,
    get_available_providers,
    set_provider,
    get_current_provider,
    SUPPORTED_PROVIDERS
)


@st.cache_resource
def init_rag_system():
    """
    Initialize RAG Knowledge Bases.
    Cached resource to run only once per session.
    """
    try:
        print("Initializing RAG System...")
        from src.rag_tps import TPSKnowledgeBase
        from src.rag_codebase import CodebaseKnowledgeBase
        # Force initialization/ingestion
        TPSKnowledgeBase()
        CodebaseKnowledgeBase()
        print("RAG System Initialized.")
        return True
    except Exception as e:
        print(f"Failed to init RAG: {e}")
        return False

def check_rag_status():
    """
    Updates session state based on cached init status.
    """
    if init_rag_system():
        st.session_state.rag_initialized = True

def init_session_state():
    """Initialize all session state variables."""
    # Initialize Knowledge Manager
    from src.knowledge_manager import KnowledgeManager
    import os
    
    # Check if knowledge graph exists, if not, generate it
    base_dir = os.path.dirname(os.path.abspath(__file__))
    kb_path = os.path.join(base_dir, "src", "knowledge_graph.json")
    if not os.path.exists(kb_path):
        st.info("Generating knowledge base... This may take a minute.")
        try:
            from src.build_knowledge_base import build_knowledge_graph, save_knowledge_base
            kb = build_knowledge_graph()
            save_knowledge_base(kb, kb_path)
            st.success("Knowledge base generated!")
        except Exception as e:
            st.error(f"Failed to generate knowledge base: {e}")

    # Pre-load KM
    KnowledgeManager()

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_plan" not in st.session_state:
        st.session_state.current_plan = None
    if "generated_code" not in st.session_state:
        st.session_state.generated_code = None
    if "logs" not in st.session_state:
        st.session_state.logs = []
    if "selected_provider" not in st.session_state:
        st.session_state.selected_provider = None
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = None
    if "rag_initialized" not in st.session_state:
        st.session_state.rag_initialized = False
        # Trigger background initialization
        check_rag_status()
    # Edit mode state
    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = False
    if "source_file_path" not in st.session_state:
        st.session_state.source_file_path = None
    if "source_file_content" not in st.session_state:
        st.session_state.source_file_content = None
    if "output_file_name" not in st.session_state:
        st.session_state.output_file_name = "output.arxml"
    # Deep thinking and error fixing configuration
    if "enable_deep_thinking" not in st.session_state:
        st.session_state.enable_deep_thinking = True
    if "max_fix_attempts" not in st.session_state:
        st.session_state.max_fix_attempts = 5


def render_provider_selector():
    """Render the AI provider selection UI in the sidebar."""
    st.header("AI Model Selection")

    # Get available providers
    available = get_available_providers()

    # Build list of available providers
    available_providers = [p for p, info in available.items() if info['available']]
    all_providers = list(SUPPORTED_PROVIDERS.keys())

    if not available_providers:
        st.warning("No API keys found. Using Mock LLM.")
        st.info("Set one of these environment variables:")
        for provider, info in available.items():
            st.code(f"{info['env_key']}")
        return None, None

    # Provider selection
    provider_options = []
    provider_status = {}
    for provider in all_providers:
        info = available[provider]
        if info['available']:
            provider_options.append(provider)
            provider_status[provider] = "Available"
        else:
            provider_status[provider] = f"No Key ({info['env_key']})"

    # Default to first available provider
    default_idx = 0
    if st.session_state.selected_provider in provider_options:
        default_idx = provider_options.index(st.session_state.selected_provider)

    selected_provider = st.selectbox(
        "Provider",
        options=provider_options,
        index=default_idx,
        format_func=lambda x: f"{x.upper()}",
        help="Select the AI provider to use for generation"
    )

    # Model selection based on provider
    if selected_provider:
        provider_info = available[selected_provider]
        model_options = provider_info['models']
        default_model = provider_info['default']

        # Default to stored model if valid, otherwise use provider default
        default_model_idx = 0
        if st.session_state.selected_model in model_options:
            default_model_idx = model_options.index(st.session_state.selected_model)
        elif default_model in model_options:
            default_model_idx = model_options.index(default_model)

        selected_model = st.selectbox(
            "Model",
            options=model_options,
            index=default_model_idx,
            help="Select the specific model to use"
        )

        # Update session state
        st.session_state.selected_provider = selected_provider
        st.session_state.selected_model = selected_model

        # Apply the selection
        try:
            set_provider(selected_provider, selected_model)
            st.success(f"Using: {selected_provider.upper()} / {selected_model}")
        except Exception as e:
            st.error(f"Error setting provider: {e}")

        # Show provider status
        st.divider()
        st.caption("Provider Status:")
        for provider, status in provider_status.items():
            if provider in available_providers:
                st.markdown(f"- **{provider.upper()}**: :green[{status}]")
            else:
                st.markdown(f"- **{provider.upper()}**: :red[{status}]")

        return selected_provider, selected_model

    return None, None


def inject_custom_css():
    """Inject custom CSS for modern dark theme with gradient accents."""
    st.markdown("""
    <style>
    /* Modern Dark Theme with Gradient Accents */
    :root {
        --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        --accent-color: #667eea;
        --accent-hover: #764ba2;
        --success-color: #10b981;
        --warning-color: #f59e0b;
        --error-color: #ef4444;
    }
    
    /* Main container styling */
    .stApp {
        background: linear-gradient(180deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
    }
    
    /* Sidebar styling with glassmorphism */
    [data-testid="stSidebar"] {
        background: rgba(26, 26, 46, 0.95);
        backdrop-filter: blur(10px);
        border-right: 1px solid rgba(102, 126, 234, 0.2);
    }
    
    [data-testid="stSidebar"] .stButton > button {
        background: var(--primary-gradient);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    [data-testid="stSidebar"] .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
    }
    
    /* Headers with gradient text */
    h1, h2, h3 {
        background: var(--primary-gradient);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    /* Chat input styling */
    [data-testid="stChatInput"] textarea {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(102, 126, 234, 0.3);
        border-radius: 12px;
        color: white;
    }
    
    [data-testid="stChatInput"] textarea:focus {
        border-color: var(--accent-color);
        box-shadow: 0 0 15px rgba(102, 126, 234, 0.2);
    }
    
    /* Chat message containers */
    [data-testid="stChatMessage"] {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    /* Success/Error message styling */
    .stSuccess {
        background: rgba(16, 185, 129, 0.1);
        border-left: 4px solid var(--success-color);
        border-radius: 8px;
    }
    
    .stError {
        background: rgba(239, 68, 68, 0.1);
        border-left: 4px solid var(--error-color);
        border-radius: 8px;
    }
    
    .stWarning {
        background: rgba(245, 158, 11, 0.1);
        border-left: 4px solid var(--warning-color);
        border-radius: 8px;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        border: 1px solid rgba(102, 126, 234, 0.2);
    }
    
    /* Metric cards */
    [data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.03);
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid rgba(102, 126, 234, 0.2);
    }
    
    [data-testid="stMetricValue"] {
        color: var(--accent-color) !important;
    }
    
    /* Download buttons */
    .stDownloadButton > button {
        background: transparent;
        border: 2px solid var(--accent-color);
        color: var(--accent-color);
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    
    .stDownloadButton > button:hover {
        background: var(--primary-gradient);
        border-color: transparent;
        color: white;
    }
    
    /* Selectbox styling */
    [data-testid="stSelectbox"] > div > div {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 8px;
    }
    
    /* Slider styling */
    .stSlider > div > div > div {
        background: var(--primary-gradient);
    }
    
    /* Quick start button container */
    .quick-start-btn {
        display: inline-block;
        margin: 4px;
    }
    
    /* Animated progress indicator */
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    .stSpinner > div {
        animation: pulse 1.5s ease-in-out infinite;
    }
    
    /* Code block styling */
    .stCodeBlock {
        border-radius: 12px;
        border: 1px solid rgba(102, 126, 234, 0.2);
    }
    
    /* Divider styling */
    hr {
        border-color: rgba(102, 126, 234, 0.2);
    }
    </style>
    """, unsafe_allow_html=True)


# Quick-start templates for common AUTOSAR patterns
QUICK_START_TEMPLATES = {
    "🚗 CAN Network": "Create a CAN cluster named 'VehicleCAN' with 500kbps baudrate, a physical channel, a frame with ID 0x100, and a signal named 'VehicleSpeed' (16 bits).",
    "🌐 Ethernet Network": "Create an Ethernet cluster with a VLAN, a physical channel, and a SOME/IP service interface for vehicle diagnostics.",
    "📦 Software Component": "Create an ApplicationSwComponentType with a sender-receiver port, an internal behavior with a runnable triggered every 100ms.",
    "🔗 Signal Routing": "Create a gateway that routes signals from CAN frame 0x100 to CAN frame 0x200.",
}


def main():
    st.set_page_config(
        page_title="AUTOSAR Agent (Multi-Model)",
        page_icon="🚗",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Inject custom CSS
    inject_custom_css()

    st.title("🚗 AUTOSAR Architecture Agent")
    st.caption("Plan → Approve → Generate → Verify | AI-Powered ARXML Generation")

    # Initialize session state
    init_session_state()

    # Sidebar setup
    with st.sidebar:
        # Provider selection
        selected_provider, selected_model = render_provider_selector()

        st.divider()

        # Edit Mode Section
        st.header("Edit Mode")
        st.session_state.edit_mode = st.checkbox(
            "Edit existing ARXML",
            value=st.session_state.edit_mode,
            help="Enable to modify an existing ARXML file"
        )

        if st.session_state.edit_mode:
            uploaded_file = st.file_uploader(
                "Upload ARXML file",
                type=['arxml', 'xml'],
                help="Upload the ARXML file you want to edit"
            )

            if uploaded_file is not None:
                # Save uploaded file temporarily (cross-platform)
                temp_dir = tempfile.gettempdir()
                temp_path = os.path.join(temp_dir, uploaded_file.name)
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getvalue())
                st.session_state.source_file_path = temp_path
                st.session_state.source_file_content = uploaded_file.getvalue().decode('utf-8')

                # Analyze the file
                try:
                    from src.arxml_analyzer import analyze_arxml
                    analysis = analyze_arxml(temp_path)
                    if analysis.is_valid:
                        st.success(f"Loaded: {uploaded_file.name}")
                        with st.expander("File Contents"):
                            st.text(analysis.get_summary())
                    else:
                        st.error(f"Invalid ARXML: {analysis.error_message}")
                except ImportError:
                    st.warning("ARXML analyzer not available (lxml required)")
                except Exception as e:
                    st.error(f"Error analyzing file: {e}")

            st.session_state.output_file_name = st.text_input(
                "Output filename",
                value=st.session_state.output_file_name,
                help="Name for the output ARXML file"
            )

        st.divider()
        
        # Configuration Section
        st.header("⚙️ Configuration")
        
        # Deep Thinking Toggle
        st.session_state.enable_deep_thinking = st.checkbox(
            "🧠 Enable Deep Thinking",
            value=st.session_state.get('enable_deep_thinking', True),
            help="Analyze the plan before generating code (adds 10-20s)"
        )
        
        # Max Fix Attempts Slider
        st.session_state.max_fix_attempts = st.slider(
            "Max Fix Attempts",
            min_value=1,
            max_value=10,
            value=st.session_state.get('max_fix_attempts', 5),
            help="Maximum number of times to attempt fixing errors"
        )
        
        st.divider()
        
        # Error Statistics Section
        st.header("📊 Error Statistics")
        try:
            from src.error_feedback_manager import get_error_feedback_manager
            efm = get_error_feedback_manager()
            stats = efm.get_statistics()
            
            st.metric("Total Errors", stats.get('total_errors', 0))
            st.metric("Fix Success Rate", f"{stats.get('success_rate', 0)}%")
            
            with st.expander("View Details"):
                st.json(stats)
        except Exception as e:
            st.caption(f"Error stats not available: {e}")

        st.divider()

        # RAG Status
        st.header("🧠 Knowledge Base")
        if st.session_state.rag_initialized:
             st.success("✅ RAG System Active")
             st.caption("TPS + Codebase Context Loaded")
        else:
             st.warning("⏳ Initializing RAG System...")
             st.caption("First run may take a minute to ingest data.")

        st.divider()

        # Reset button
        if st.button("🔄 Reset State"):
            # Preserve provider settings
            saved_provider = st.session_state.selected_provider
            saved_model = st.session_state.selected_model
            st.session_state.clear()
            st.session_state.selected_provider = saved_provider
            st.session_state.selected_model = saved_model
            # Reset edit mode state
            st.session_state.edit_mode = False
            st.session_state.source_file_path = None
            st.session_state.source_file_content = None
            st.session_state.output_file_name = "output.arxml"
            st.rerun()

    # Quick Start Templates (shown when no messages)
    if not st.session_state.messages:
        st.markdown("### 🚀 Quick Start")
        st.markdown("Click a template to get started, or type your own requirement below:")
        
        cols = st.columns(len(QUICK_START_TEMPLATES))
        for i, (label, template) in enumerate(QUICK_START_TEMPLATES.items()):
            with cols[i]:
                if st.button(label, key=f"template_{i}", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": template})
                    st.session_state.quick_start_triggered = True
                    st.rerun()
        
        st.divider()
        
        # Help section
        with st.expander("💡 Tips & Examples"):
            st.markdown("""
            **How to use this tool:**
            1. Describe your AUTOSAR requirement in natural language
            2. Review the generated plan
            3. Click "Generate Code" to create the ARXML
            4. Download the output file
            
            **Example requests:**
            - "Create a CAN bus with 2 frames and signals for speed and RPM"
            - "Add an Ethernet cluster with SOME/IP service for diagnostics"
            - "Create a software component with timing events every 10ms"
            """)

    # Chat Interface
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # User Input
    if prompt := st.chat_input("Describe your AUTOSAR requirement..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Proceed directly to planning
        with st.chat_message("assistant"):
            model_info = ""
            if selected_provider and selected_model:
                model_info = f" (using {selected_provider.upper()}/{selected_model})"

            with st.spinner(f"Thinking & Planning{model_info}..."):
                planner = Planner()

                # Build context for edit mode
                edit_context = None
                if st.session_state.edit_mode and st.session_state.source_file_path:
                    edit_context = {
                        'source_file': st.session_state.source_file_path,
                        'output_file': st.session_state.output_file_name
                    }

                plan = planner.create_plan(prompt, edit_context=edit_context)
                st.session_state.current_plan = plan

                # Format plan for display
                plan_text = f"**Proposed Plan:** {plan.get('description', '')}\n\n"
                for i, step in enumerate(plan.get('checklist', []), 1):
                    plan_text += f"{i}. {step}\n"

                st.markdown(plan_text)
                st.session_state.messages.append({"role": "assistant", "content": plan_text})

                st.info("Review the plan above. Click 'Generate' in the sidebar to proceed.")

    # Execution Control (Sidebar)
    with st.sidebar:
        st.divider()
        st.header("Actions")

        can_generate = st.session_state.current_plan is not None

        if st.button("🚀 Generate Code", disabled=not can_generate, type="primary"):
            run_generation_pipeline(selected_provider, selected_model)


def run_generation_pipeline(provider=None, model=None):
    """Run the code generation pipeline."""
    plan = st.session_state.current_plan
    status_container = st.empty()
    log_container = st.expander("Execution Logs", expanded=True)

    # Determine output file
    output_file = st.session_state.output_file_name

    model_info = ""
    if provider and model:
        model_info = f" ({provider.upper()}/{model})"

    # Show edit mode info
    if st.session_state.edit_mode and st.session_state.source_file_path:
        log_container.write(f"📂 Edit Mode: Modifying {st.session_state.source_file_path}")

    with status_container:
        st.info(f"Generating Python Code{model_info}...")

    # Get deep thinking setting
    enable_deep_thinking = st.session_state.get('enable_deep_thinking', True)
    generator = Generator(enable_deep_thinking=enable_deep_thinking)

    # Pass edit mode context to generator
    edit_context = None
    if st.session_state.edit_mode and st.session_state.source_file_path:
        edit_context = {
            'source_file': st.session_state.source_file_path,
            'output_file': output_file
        }

    code = generator.generate_code(plan, output_file=output_file, edit_context=edit_context)
    st.session_state.generated_code = code
    log_container.write("✅ Code Generated")

    with status_container:
        st.info("Executing & Verifying...")

    executor = Executor()
    
    # Get configuration from session state
    # Dynamic retry calculation
    base_retries = st.session_state.get('max_fix_attempts', 5)
    
    # Calculate retries proportional to plan complexity (approx 1 retry per 2 steps, min base_retries)
    # Calculate retries proportional to plan complexity (approx 1 retry per 2 steps, min base_retries)
    checklist = plan.get('checklist', [])
    if isinstance(checklist, list):
        plan_steps = len(checklist)
    else:
        plan_steps = len(str(checklist).split('\n'))
        
    dynamic_retries = max(base_retries, int(plan_steps / 2))
    
    max_retries = dynamic_retries
    enable_deep_thinking = st.session_state.get('enable_deep_thinking', True)
    
    # Initialize fixer with configuration
    fixer = Fixer(max_attempts=max_retries, enable_deep_analysis=enable_deep_thinking)
    
    # Initialize error feedback manager
    from src.error_feedback_manager import get_error_feedback_manager
    from datetime import datetime
    efm = get_error_feedback_manager()


    success = False

    log_container.write(f"Configuration: Max Retries = {max_retries}, Deep Thinking = {enable_deep_thinking}")

    consecutive_unchanged = 0
    
    for attempt in range(max_retries + 1):
        log_container.write(f"--- Attempt {attempt + 1} ---")

        # Run
        run_success, run_msg = executor.run_script(code)
        if not run_success:
            # run_msg is now a dict with error info
            error_display = run_msg.get('message', str(run_msg)) if isinstance(run_msg, dict) else str(run_msg)
            log_container.write(f"❌ Runtime Error: {error_display[:200]}...")
            
            # Record error to feedback system
            efm.record_error({
                "timestamp": datetime.now().isoformat(),
                "error_type": run_msg.get('type', 'Unknown') if isinstance(run_msg, dict) else 'Unknown',
                "error_message": run_msg.get('message', str(run_msg)) if isinstance(run_msg, dict) else str(run_msg),
                "error_line": run_msg.get('line') if isinstance(run_msg, dict) else None,
                "code_snippet": code[:500],  # First 500 chars
                "plan_context": plan.get('description', ''),
                "fix_attempt_number": attempt + 1,
                "fix_applied": None,  # Will update after fix
                "fix_successful": False,
                "traceback": run_msg.get('traceback', str(run_msg)) if isinstance(run_msg, dict) else str(run_msg)
            })
        else:
            log_container.write("✅ Script Executed")
            # Verify
            verify_success, verify_msg = executor.verify_arxml(output_file, plan)
            if verify_success:
                log_container.write(f"✅ Verification Passed: {verify_msg}")
                success = True
                break
            else:
                log_container.write(f"❌ Verification Failed: {verify_msg}")
                run_success = False
                run_msg = verify_msg

        # Fix
        if attempt < max_retries:
            with status_container:
                st.warning(f"Fixing Code (Attempt {attempt + 1}/{max_retries}){model_info}...")
            
            log_container.write(f"🔧 Calling Fixer (Attempt {attempt + 1})...")
            fixed_code = fixer.fix_code(code, run_msg, plan)
            
            if fixed_code == code:
                consecutive_unchanged += 1
                log_container.write(f"⚠️ Fixer returned same code (Attempt {consecutive_unchanged}/5 unchanged). Retrying...")
                
                if consecutive_unchanged >= 5:
                     log_container.write("🛑 Stopping: Code unchanged for 5 consecutive attempts. The fixer is stuck.")
                     break
            else:
                log_container.write("✅ Fixer applied changes. Continuing...")
                consecutive_unchanged = 0
            
            # Check if fix was actually attempted (not max attempts reached)
            if fixed_code != code:
                # Update last error record with fix info
                if efm.feedback_data["errors"]:
                    efm.feedback_data["errors"][-1]["fix_applied"] = "LLM fix attempted"
                    efm.save_feedback()
            
            code = fixed_code
            st.session_state.generated_code = code

    if success:
        # Record successful generation
        if efm.feedback_data["errors"] and len(efm.feedback_data["errors"]) > 0:
            # Mark last error as fixed
            efm.feedback_data["errors"][-1]["fix_successful"] = True
            efm.save_feedback()
        
        with status_container:
            if st.session_state.edit_mode:
                st.success(f"SUCCESS! ARXML Modified: {output_file}")
            else:
                st.success(f"SUCCESS! ARXML Generated: {output_file}")

        # Download buttons
        try:
            with open(output_file, "rb") as f:
                st.sidebar.download_button(
                    "📥 Download ARXML",
                    f,
                    output_file,
                    "application/xml"
                )
        except:
            pass

        st.sidebar.download_button(
            "📥 Download Script",
            code,
            "generate.py",
            "text/x-python"
        )

        # Show code
        with st.expander("View Generated Code"):
            st.code(code, language="python")
    else:
        # FAILURE - show detailed info
        with status_container:
            st.error(f"⚠️ Failed to generate valid ARXML after {max_retries} attempts.")
        
        # Show error statistics
        st.warning(f"**Last Error:**")
        if isinstance(run_msg, dict):
            st.code(f"Type: {run_msg.get('type', 'Unknown')}\nMessage: {run_msg.get('message', 'N/A')}\nLine: {run_msg.get('line', 'N/A')}", language="text")
        else:
            st.code(str(run_msg)[:500], language="text")
        
        # Show generated code for debugging
        with st.expander("🔍 View Last Generated Code (for debugging)", expanded=True):
            st.code(code, language="python")
        
        # Download button for problematic code
        st.sidebar.download_button(
            "📥 Download Failed Script",
            code,
            "failed_script.py",
            "text/x-python",
            help="Download the script that failed for manual debugging"
        )
        
        # Show error feedback stats
        st.info("💡 **Tip:** Check the Error Statistics in the sidebar to see if similar errors have occurred before.")


if __name__ == "__main__":
    main()
