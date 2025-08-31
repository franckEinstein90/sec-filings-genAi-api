# app/rag.py
import os
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from openai import OpenAIError, RateLimitError, APITimeoutError, APIConnectionError
from langchain_community.vectorstores import FAISS
from .class_OpenAIClient import OpenAIClient, RAGError
# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

def validate_inputs(prompt: str, temperature: float, system_prompt: str) -> None:
    """Validate input parameters"""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Prompt must be a non-empty string")
    
    if not isinstance(system_prompt, str) or not system_prompt.strip():
        raise ValueError("System prompt must be a non-empty string")
    
    if not isinstance(temperature, (int, float)) or not (0.0 <= temperature <= 2.0):
        raise ValueError("Temperature must be a number between 0.0 and 2.0")
def get_completion(
    prompt: str, 
    temperature: float = 0.7,
    system_prompt: str = "You are a helpful assistant.",
    model: str = "gpt-4o",
    max_tokens: Optional[int] = None,
    timeout: int = 30,
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    Get completion from OpenAI API with comprehensive error handling and recovery.
    
    Args:
        prompt: The user prompt
        temperature: Sampling temperature (0.0 to 2.0)
        system_prompt: System message for the model
        model: OpenAI model to use
        max_tokens: Maximum tokens in response
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
    
    Returns:
        Dict containing:
            - success: bool indicating if request succeeded
            - content: str with the response content or error message
            - usage: dict with token usage info (if successful)
            - error_type: str with error classification (if failed)
    
    Raises:
        RAGError: For configuration or validation errors
        ValueError: For invalid input parameters
    """
    
    # Validate inputs
    validate_inputs(prompt, temperature, system_prompt)
    
    # Get OpenAI client
    try:
        client = OpenAIClient().get_client()
    except RAGError as e:
        logger.error(f"Client initialization failed: {e}")
        return {
            "success": False,
            "content": "Configuration error: Unable to initialize OpenAI client",
            "error_type": "configuration_error"
        }
    
    # Prepare request parameters
    request_params = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": prompt.strip()}
        ],
        "temperature": temperature,
        "timeout": timeout
    }
    
    if max_tokens is not None:
        request_params["max_tokens"] = max_tokens
    
    # Attempt completion with retries
    last_error = None
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting completion (attempt {attempt + 1}/{max_retries})")
            
            response = client.responses.create(**request_params)
            content = response.output_text
            if content is None:
                content = "No content generated"
            
            logger.info("Completion successful")
            return {
                "success": True,
                "content": content,
                "usage": {
                    "imput_token": response.usage.input_tokens if response.usage else None, 
                    "output_tokens": response.usage.output_tokens if response.usage else None, 
                } if response.usage else None
            }
            
        except RateLimitError as e:
            error_msg = f"Rate limit exceeded: {str(e)}"
            logger.warning(f"{error_msg} (attempt {attempt + 1}/{max_retries})")
            last_error = e
            
            if attempt < max_retries - 1:
                # Exponential backoff for rate limiting
                import time
                wait_time = (2 ** attempt) * 1
                logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                continue
            
            return {
                "success": False,
                "content": "Request failed due to rate limiting. Please try again later.",
                "error_type": "rate_limit_error"
            }
            
        except APITimeoutError as e:
            error_msg = f"Request timeout: {str(e)}"
            logger.warning(f"{error_msg} (attempt {attempt + 1}/{max_retries})")
            last_error = e
            
            if attempt < max_retries - 1:
                continue
            
            return {
                "success": False,
                "content": "Request timed out. Please try again.",
                "error_type": "timeout_error"
            }
            
        except APIConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            logger.warning(f"{error_msg} (attempt {attempt + 1}/{max_retries})")
            last_error = e
            
            if attempt < max_retries - 1:
                continue
            
            return {
                "success": False,
                "content": "Unable to connect to OpenAI API. Please check your connection.",
                "error_type": "connection_error"
            }
            
        except OpenAIError as e:
            error_msg = f"OpenAI API error: {str(e)}"
            logger.error(error_msg)
            
            return {
                "success": False,
                "content": "An error occurred with the OpenAI API. Please try again.",
                "error_type": "api_error"
            }
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            
            return {
                "success": False,
                "content": "An unexpected error occurred while processing your request.",
                "error_type": "unexpected_error"
            }
    
    # If we get here, all retries failed
    logger.error(f"All {max_retries} attempts failed. Last error: {last_error}")
    return {
        "success": False,
        "content": "Request failed after multiple attempts. Please try again later.",
        "error_type": "max_retries_exceeded"
    }
def get_completion_simple(
    prompt: str, 
    temperature: float = 0.7,
    system_prompt: str = "You are a helpful assistant."
) -> str:
    """
    Simplified version that returns just the content string for backward compatibility.
    
    Args:
        prompt: The user prompt
        temperature: Sampling temperature (0.0 to 2.0)
        system_prompt: System message for the model
    
    Returns:
        str: The response content or error message
    """
    result = get_completion(prompt, temperature, system_prompt)
    return result["content"]