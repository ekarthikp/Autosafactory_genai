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


def init_session_state():
    """Initialize all session state variables."""
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
    # Edit mode state
    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = False
    if "source_file_path" not in st.session_state:
        st.session_state.source_file_path = None
    if "source_file_content" not in st.session_state:
        st.session_state.source_file_content = None
    if "output_file_name" not in st.session_state:
        st.session_state.output_file_name = "output.arxml"


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


def main():
    st.set_page_config(
        page_title="AUTOSAR Agent (Multi-Model)",
        page_icon="🚗",
        layout="wide"
    )

    st.title("🚗 AUTOSAR Architecture Agent")
    st.caption("Plan -> Approve -> Generate -> Verify | Multi-Model Support")

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

    generator = Generator()

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
    fixer = Fixer()

    success = False
    max_retries = 10

    for attempt in range(max_retries + 1):
        log_container.write(f"--- Attempt {attempt + 1} ---")

        # Run
        run_success, run_msg = executor.run_script(code)
        if not run_success:
            log_container.write(f"❌ Runtime Error: {run_msg[:200]}...")
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
                st.warning(f"Fixing Code (Attempt {attempt + 1}){model_info}...")
            code = fixer.fix_code(code, run_msg, plan)
            st.session_state.generated_code = code

    if success:
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
        with status_container:
            st.error("Failed to generate valid ARXML after retries.")


if __name__ == "__main__":
    main()
