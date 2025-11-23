"""
AUTOSAR Architecture Agent - CLI
=================================
Command-line interface for ARXML generation with multi-model support.
"""

import sys
import json
import argparse
import time
import os
from src.planner import Planner
from src.generator import Generator
from src.executor import Executor
from src.fixer import Fixer
from src.utils import (
    load_api_key,
    get_available_providers,
    set_provider,
    list_available_models,
    SUPPORTED_PROVIDERS
)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="AUTOSAR Architecture Agent - Generate ARXML files using AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default provider (auto-detected)
  python -m src.main "Create a CAN cluster with 500kbps"

  # Use specific provider
  python -m src.main --provider openai "Create CAN frames"

  # Use specific model
  python -m src.main --provider anthropic --model claude-3-opus-20240229 "Create ECU"

  # List available providers
  python -m src.main --list-providers

  # Auto-approve plan (no confirmation)
  python -m src.main --yes "Create a simple CAN message"

  # Edit an existing ARXML file
  python -m src.main --edit existing.arxml "Add a new CAN frame"
        """
    )

    parser.add_argument(
        "requirement",
        nargs="*",
        help="AUTOSAR requirement to generate (can be provided interactively if not specified)"
    )

    parser.add_argument(
        "--provider", "-p",
        choices=["gemini", "openai", "anthropic"],
        help="AI provider to use (default: auto-detect based on available API keys)"
    )

    parser.add_argument(
        "--model", "-m",
        help="Specific model to use (default: provider's default model)"
    )

    parser.add_argument(
        "--list-providers", "-l",
        action="store_true",
        help="List available AI providers and their models"
    )

    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Auto-approve the generated plan without confirmation"
    )

    parser.add_argument(
        "--max-retries", "-r",
        type=int,
        default=10,
        help="Maximum number of fix attempts (default: 10)"
    )

    parser.add_argument(
        "--output", "-o",
        default="output.arxml",
        help="Output ARXML file name (default: output.arxml)"
    )

    parser.add_argument(
        "--edit", "-e",
        metavar="FILE",
        help="Edit an existing ARXML file (add/modify elements)"
    )

    return parser.parse_args()


def show_provider_banner(provider, model):
    """Show the current provider/model configuration."""
    print(f"\n🤖 AI Provider: {provider.upper()}")
    print(f"   Model: {model}")


def main():
    args = parse_args()

    print("=" * 60)
    print("      AUTOSAR ARCHITECTURE AGENT (MULTI-MODEL)")
    print("=" * 60)

    # Handle --list-providers
    if args.list_providers:
        list_available_models()
        return

    # 1. Setup provider
    available = get_available_providers()
    available_providers = [p for p, info in available.items() if info['available']]

    if not available_providers:
        print("\n⚠️  No API keys found!")
        print("Please set one of the following environment variables:")
        for provider, info in SUPPORTED_PROVIDERS.items():
            print(f"   {info['env_key']} - for {provider.upper()}")
        print("\nRunning in MOCK mode for demonstration...")

    # Determine provider and model
    provider = args.provider
    model = args.model

    if provider:
        # User specified provider
        if provider not in available_providers:
            env_key = SUPPORTED_PROVIDERS[provider]['env_key']
            print(f"\n⚠️  {provider.upper()} selected but {env_key} not set!")
            if available_providers:
                print(f"   Falling back to {available_providers[0].upper()}")
                provider = available_providers[0]
            else:
                print("   Running in MOCK mode...")
                provider = None
    else:
        # Auto-detect provider
        if available_providers:
            provider = available_providers[0]

    if provider:
        if not model:
            model = SUPPORTED_PROVIDERS[provider]['default']
        try:
            set_provider(provider, model)
            show_provider_banner(provider, model)
        except Exception as e:
            print(f"\n⚠️  Error setting provider: {e}")
    else:
        print("\n⚠️  Running in MOCK mode (no API key configured)")

    try:
        load_api_key(provider)
    except Exception as e:
        print(f"Error: {e}")
        return

    # 2. User Input
    if args.requirement:
        user_input = " ".join(args.requirement)
    else:
        print("\nWhat kind of ARXML do you want to generate?")
        print("(Type your requirement and press Enter)")
        user_input = input("> ")

    if not user_input.strip():
        print("No requirement provided. Exiting.")
        return

    # 2.5. Check for edit mode
    edit_context = None
    source_file = args.edit

    if source_file:
        if os.path.exists(source_file):
            print(f"\n📂 Edit mode: Loading existing file {source_file}")
            edit_context = {
                'source_file': source_file,
                'output_file': args.output
            }
        else:
            print(f"\n⚠️  File not found: {source_file}")
            print("Will create new file instead.")

    # 3. Planning Phase
    print("\n[1/3] Thinking & Planning...")
    planner = Planner()
    plan = planner.create_plan(user_input, edit_context=edit_context)

    print("\n" + "-" * 40)
    print("PROPOSED PLAN:")
    print("-" * 40)
    print(f"Task: {plan.get('description', 'N/A')}")
    print("Checklist:")
    for i, step in enumerate(plan.get('checklist', []), 1):
        print(f"  {i}. {step}")
    print("-" * 40)

    # 4. User Approval
    if args.yes:
        print("\n✅ Auto-approved (--yes flag)")
    else:
        print("\nDo you approve this plan? (y/n)")
        approval = input("> ").lower()
        if approval != 'y':
            print("Aborting.")
            return

    # 5. Generation Phase
    output_file = args.output

    print("\n[2/3] Generating Code...")
    generator = Generator()
    code = generator.generate_code(plan, output_file=output_file, edit_context=edit_context)

    # 6. Execution & Verification Phase
    print("\n[3/3] Executing & Verifying...")
    executor = Executor()
    fixer = Fixer()

    max_retries = args.max_retries
    success = False
    last_error = ""

    for attempt in range(max_retries + 1):
        print(f"\n--- Attempt {attempt + 1} ---")

        # Run
        run_success, run_msg = executor.run_script(code)
        if not run_success:
            print(f"❌ Runtime Error: {run_msg[:500]}...")
            last_error = run_msg
        else:
            print(f"✅ Script Executed.")
            # Verify
            verify_success, verify_msg = executor.verify_arxml(output_file, plan)
            if verify_success:
                print(f"✅ Verification Passed: {verify_msg}")
                success = True
                break
            else:
                print(f"❌ Verification Failed: {verify_msg}")
                run_success = False
                run_msg = verify_msg
                last_error = verify_msg

        # Fix
        if attempt < max_retries:
            print(f"   Attempting fix {attempt + 1}/{max_retries}...")
            code = fixer.fix_code(code, run_msg, plan)
        else:
            print("\nFailed after max retries.")

    if success:
        print("\n" + "=" * 60)
        if edit_context:
            print(f"SUCCESS! ARXML modified at '{output_file}'")
        else:
            print(f"SUCCESS! ARXML generated at '{output_file}'")
        if provider and model:
            print(f"Generated using: {provider.upper()} / {model}")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("GENERATION INCOMPLETE")
        print("=" * 60)
        print("\nThe code generation encountered errors that could not be automatically fixed.")
        print("The generated script has been saved to 'generated_script.py'.")
        print("\nLast error encountered:")
        print(last_error[:1000] if len(last_error) > 1000 else last_error)
        print("\nSuggestions:")
        print("1. Review the generated_script.py for any obvious issues")
        print("2. Check if the requested AUTOSAR elements are supported by autosarfactory")
        print("3. Try a simpler request first to verify the setup works")
        print("4. Check the API documentation for correct method signatures")
        if provider:
            print(f"5. Try a different model: --provider {provider} --model <model_name>")


if __name__ == "__main__":
    main()
