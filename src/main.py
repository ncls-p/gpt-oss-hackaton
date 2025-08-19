"""
Main application demonstrating clean architecture with proper port usage and dependency injection.
"""

import sys
import os

# Add src directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from container import container
from exceptions import FileRepositoryError, LLMError


def demonstrate_file_operations():
    """Demonstrate file listing and searching operations using proper clean architecture."""
    print("=" * 60)
    print("FILE OPERATIONS DEMONSTRATION")
    print("=" * 60)

    # Get use cases from container (dependencies already injected)
    list_files_use_case = container.get_list_files_use_case()
    search_files_use_case = container.get_search_files_use_case()

    # Demonstrate file listing
    try:
        directory = "/Users/ncls/work/perso/gpt-oss-hackaton/src"
        print(f"\n📁 Listing files in: {directory}")

        # Use case has dependencies injected - just call execute()
        files = list_files_use_case.execute(directory)

        print(f"Found {len(files)} files:")
        for file in files[:10]:  # Show first 10 files
            details = file.get_details()
            print(
                f"  • {details['name']} ({details['size_mb']} MB) - {details['type']}"
            )

        if len(files) > 10:
            print(f"  ... and {len(files) - 10} more files")

    except FileRepositoryError as e:
        print(f"❌ Error listing files: {e}")

    # Demonstrate file searching
    try:
        print(f"\n🔍 Searching for Python files (*.py) in: {directory}")

        # Use case has dependencies injected - just call execute()
        python_files = search_files_use_case.execute(directory, "*.py")

        print(f"Found {len(python_files)} Python files:")
        for file in python_files[:5]:  # Show first 5 Python files
            details = file.get_details()
            print(f"  • {details['name']} ({details['size_mb']} MB)")

        if len(python_files) > 5:
            print(f"  ... and {len(python_files) - 5} more Python files")

    except FileRepositoryError as e:
        print(f"❌ Error searching files: {e}")


def demonstrate_llm_operations():
    """Demonstrate LLM text generation operations using proper clean architecture."""
    print("\n" + "=" * 60)
    print("LLM TEXT GENERATION DEMONSTRATION")
    print("=" * 60)

    # Get use case from container (dependencies already injected)
    generate_text_use_case = container.get_generate_text_use_case()

    # Get LLM adapter for model info
    llm_adapter = container.get_llm_adapter()

    # Show model info
    try:
        model_info = llm_adapter.get_model_info()
        print(
            f"\n🤖 Using LLM: {model_info.get('model', 'Unknown')} from {model_info.get('provider', 'Unknown')}"
        )
    except Exception as e:
        print(f"⚠️  Could not get model info: {e}")

    # Demonstrate basic text generation
    try:
        prompt = "Write a short haiku about programming."
        print(f"\n📝 Generating text for prompt: '{prompt}'")

        # Use case has dependencies injected - just call execute()
        response = generate_text_use_case.execute(
            prompt=prompt, temperature=0.7, max_tokens=100
        )

        print("🎯 Generated response:")
        print(f"   {response}")

    except LLMError as e:
        print(f"❌ Error generating text: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

    # Demonstrate text generation with system message
    try:
        prompt = "Explain clean architecture in software development."
        system_message = "You are a senior software architect. Provide concise, technical explanations."

        print("\n📝 Generating text with custom system message...")
        print(f"   Prompt: '{prompt}'")
        print(f"   System: '{system_message}'")

        # Use case has dependencies injected - just call execute_with_system_message()
        response = generate_text_use_case.execute_with_system_message(
            prompt=prompt,
            system_message=system_message,
            temperature=0.3,
            max_tokens=200,
        )

        print("🎯 Generated response:")
        print(f"   {response}")

    except LLMError as e:
        print(f"❌ Error generating text: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def main():
    """Main application entry point."""
    print("🚀 Clean Architecture Demo Application")
    print("This application demonstrates clean architecture principles with:")
    print("  • Proper port usage (dependency inversion)")
    print("  • Constructor dependency injection")
    print("  • Use cases with injected dependencies")
    print("  • Separation of concerns")
    print("  • Proper error handling")

    try:
        # Demonstrate file operations
        demonstrate_file_operations()

        # Demonstrate LLM operations
        demonstrate_llm_operations()

        print("\n" + "=" * 60)
        print("✅ Demo completed successfully!")
        print("✅ Clean architecture with proper port usage implemented!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Application error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
