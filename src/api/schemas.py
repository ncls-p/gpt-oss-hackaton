"""
Pydantic models for API requests and responses.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    """Schema for file information."""

    name: str = Field(..., description="File name")
    path: str = Field(..., description="Full file path")
    size_mb: float = Field(..., description="File size in megabytes")
    type: str = Field(..., description="File type/extension")

    @classmethod
    def from_entity(cls, file_entity):
        """Create a FileInfo schema from a File entity."""
        details = file_entity.get_details()
        return cls(
            name=details["name"],
            path=details["path"],
            size_mb=details["size_mb"],
            type=details["type"],
        )


class FileListRequest(BaseModel):
    """Schema for file list request parameters."""

    directory: str = Field(..., description="Directory path to list files from")


class FileSearchRequest(BaseModel):
    """Schema for file search request parameters."""

    directory: str = Field(..., description="Directory path to search in")
    pattern: str = Field(..., description="Search pattern (e.g., '*.py')")
    recursive: Optional[bool] = Field(
        False, description="Whether to search recursively"
    )


class FileListResponse(BaseModel):
    """Schema for file list response."""

    files: List[FileInfo] = Field(..., description="List of files")


class GenerateTextRequest(BaseModel):
    """Schema for text generation request."""

    prompt: str = Field(..., description="Input prompt for text generation")
    system_message: Optional[str] = Field(None, description="Optional system message")
    temperature: Optional[float] = Field(0.7, description="Temperature for generation")
    max_tokens: Optional[int] = Field(1000, description="Maximum tokens to generate")


class GenerateTextResponse(BaseModel):
    """Schema for text generation response."""

    text: str = Field(..., description="Generated text")
    model: Optional[str] = Field(None, description="Model used for generation")
    provider: Optional[str] = Field(None, description="Provider of the model")


class ErrorResponse(BaseModel):
    """Schema for error responses."""

    detail: str = Field(..., description="Error message")
