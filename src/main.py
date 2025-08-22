"""
Main application demonstrating clean architecture with proper port usage and dependency injection.
"""

import logging
import sys

from fastapi import FastAPI

from src.api.routers import router as api_router
from src.container import container
from src.exceptions import FileRepositoryError, LLMError

# Create FastAPI app
app = FastAPI(title="Clean Architecture API")
app.include_router(api_router)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Get logger for this module
logger = logging.getLogger(__name__)


def demonstrate_file_operations():
    """Demonstrate file listing and searching operations using proper clean architecture."""
    logger.info("=" * 60)
    logger.info("FILE OPERATIONS DEMONSTRATION")
    logger.info("=" * 60)

    # Get use cases from container (dependencies already injected)
    list_files_use_case = container.get_list_files_use_case()
    search_files_use_case = container.get_search_files_use_case()

    # Set directory for file operations
    directory = "/Users/ncls/work/perso/gpt-oss-hackaton/src"

    # Demonstrate file listing
    try:
        logger.info(f"Listing files in: {directory}")

        # Use case has dependencies injected - just call execute()
        files = list_files_use_case.execute(directory)

        logger.info(f"Found {len(files)} files:")
        for file in files[:10]:  # Show first 10 files
            details = file.get_details()
            logger.info(
                f"  • {details['name']} ({details['size_mb']} MB) - {details['type']}"
            )

        if len(files) > 10:
            logger.info(f"  ... and {len(files) - 10} more files")

    except FileRepositoryError as e:
        logger.error(f"Error listing files: {e}")

    # Demonstrate file searching
    try:
        logger.info(f"Searching for Python files (*.py) in: {directory}")

        # Use case has dependencies injected - just call execute()
        python_files = search_files_use_case.execute(directory, "*.py")

        logger.info(f"Found {len(python_files)} Python files:")
        for file in python_files[:5]:  # Show first 5 Python files
            details = file.get_details()
            logger.info(f"  • {details['name']} ({details['size_mb']} MB)")

        if len(python_files) > 5:
            logger.info(f"  ... and {len(python_files) - 5} more Python files")

    except FileRepositoryError as e:
        logger.error(f"Error searching files: {e}")


def demonstrate_llm_operations():
    """Demonstrate LLM text generation operations using proper clean architecture."""
    logger.info("\n" + "=" * 60)
    logger.info("LLM TEXT GENERATION DEMONSTRATION")
    logger.info("=" * 60)

    # Get use case from container (dependencies already injected)
    from typing import Protocol

    class GenerateTextUseCaseProtocol(Protocol):
        def execute(self, prompt: str, **kwargs: dict[str, object]) -> str: ...
        def execute_with_system_message(
            self, prompt: str, system_message: str, **kwargs: dict[str, object]
        ) -> str: ...

    generate_text_use_case: GenerateTextUseCaseProtocol = (
        container.get_generate_text_use_case()
    )

    # Get LLM adapter for model info
    llm_adapter = container.get_llm_adapter()

    # Show model info
    try:
        model_info = llm_adapter.get_model_info()
        logger.info(
            f"Using LLM: {model_info.get('model', 'Unknown')} from {model_info.get('provider', 'Unknown')}"
        )
    except Exception as e:
        logger.warning(f"Could not get model info: {e}")

    # Demonstrate basic text generation
    try:
        prompt = "Write a short haiku about programming."
        logger.info(f"Generating text for prompt: '{prompt}'")

        # Use case has dependencies injected - just call execute()
        response = generate_text_use_case.execute(
            prompt=prompt, temperature=0.7, max_tokens=100
        )

        logger.info("Generated response:")
        logger.info(f"   {response}")

    except LLMError as e:
        logger.error(f"Error generating text: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

    # Demonstrate text generation with system message
    try:
        prompt = "Explain clean architecture in software development."
        system_message = "You are a senior software architect. Provide concise, technical explanations."

        logger.info("Generating text with custom system message...")
        logger.info(f"   Prompt: '{prompt}'")
        logger.info(f"   System: '{system_message}'")

        # Use case has dependencies injected - just call execute_with_system_message()
        response = generate_text_use_case.execute_with_system_message(
            prompt=prompt,
            system_message=system_message,
            temperature=0.3,
            max_tokens=200,
        )

        logger.info("Generated response:")
        logger.info(f"   {response}")

    except LLMError as e:
        logger.error(f"Error generating text: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


def main():
    """Main application entry point."""
    logger.info("Clean Architecture Demo Application")
    logger.info("This application demonstrates clean architecture principles with:")
    logger.info("  • Proper port usage (dependency inversion)")
    logger.info("  • Constructor dependency injection")
    logger.info("  • Use cases with injected dependencies")
    logger.info("  • Separation of concerns")
    logger.info("  • Proper error handling")

    try:
        # Demonstrate file operations
        demonstrate_file_operations()

        # Demonstrate LLM operations
        demonstrate_llm_operations()

        logger.info("\n" + "=" * 60)
        logger.info("Demo completed successfully!")
        logger.info("Clean architecture with proper port usage implemented!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Application error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
