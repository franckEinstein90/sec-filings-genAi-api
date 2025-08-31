import json
import os
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any

# Metadata Model
class DocumentMetadata(BaseModel):
    file_name: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="MIME type of the file")
    collection_id: int = Field(..., alias="collection", description="Collection ID")
    title: Optional[str] = Field(None, description="Document title")
    
    
    class Config:
        # Allow field aliases (collection -> collection_id)
        allow_population_by_field_name = True
        # Allow extra fields
        extra = "allow"
    
    @field_validator('file_name')
    def validate_file_name(cls, v):
        if not v or not v.strip():
            raise ValueError('File name cannot be empty')
        original_filename = secure_filename(v)
        return original_filename.strip()

    @field_validator('collection_id')
    def validate_collection_id(cls, v):
        if v <= 0:
            raise ValueError('Collection ID must be positive')
        return v
    
    @classmethod
    def from_flask_request(cls, request_obj):
        """Create DocumentMetadata from Flask request object"""
        try:
            # Get metadata from form
            metadata_str = request_obj.form.get('metadata')
            if not metadata_str:
                raise ValueError("No metadata provided in request")
            
            # Parse JSON string
            metadata_dict = json.loads(metadata_str)
            
            # Create and validate model
            return cls(**metadata_dict)
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in metadata: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error parsing metadata: {str(e)}")