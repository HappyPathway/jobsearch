import json
import re
import logging
from typing import Any, Dict, List, Optional, Union
import google.generativeai as genai

logger = logging.getLogger(__name__)

class StructuredPrompt:
    def __init__(self, model_name: str = 'gemini-1.5-pro', max_retries: int = 3, max_output_tokens: int = 2000):
        self.model = genai.GenerativeModel(model_name)
        self.max_retries = max_retries
        self.max_output_tokens = max_output_tokens

    def _clean_json_string(self, json_str: str) -> str:
        """Clean up common JSON formatting issues"""
        # Remove markdown code block formatting
        json_str = re.sub(r'^```.*?\n', '', json_str)
        json_str = re.sub(r'\n```$', '', json_str)
        
        # Try to extract just the JSON if there's other text
        if match := re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', json_str):
            json_str = match.group(1)
        
        # Fix common JSON issues
        json_str = re.sub(r'(?<!["\\])"(?![":{},\s\]])', '\\"', json_str)  # Escape unescaped quotes
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)  # Remove trailing commas
        json_str = re.sub(r'}\s*{', '},{', json_str)  # Fix object separation
        json_str = re.sub(r'\\n|\\r', ' ', json_str)  # Remove newlines in strings
        json_str = re.sub(r'\s+', ' ', json_str)  # Normalize whitespace
        json_str = re.sub(r'(?<=[\[{,])\s*([^"{\[]+?):\s*"', r'"\1":"', json_str)  # Fix unquoted property names
        
        return json_str

    def _validate_json_structure(self, data: Any, expected_structure: Dict) -> bool:
        """Validate that the parsed JSON matches the expected structure"""
        if isinstance(expected_structure, dict):
            if not isinstance(data, dict):
                return False
            for key, value_type in expected_structure.items():
                if key not in data:
                    return False
                if not self._validate_json_structure(data[key], value_type):
                    return False
            return True
        elif isinstance(expected_structure, list):
            if not isinstance(data, list):
                return False
            if not data:  # Empty list is valid
                return True
            return all(self._validate_json_structure(item, expected_structure[0]) for item in data)
        else:
            return isinstance(data, expected_structure)

    def get_structured_response(
        self,
        prompt: str,
        expected_structure: Union[Dict, List],
        example_data: Optional[Union[Dict, List]] = None,
        temperature: float = 0.1
    ) -> Optional[Any]:
        """
        Get a structured response from the model with validation and retry logic.
        
        Args:
            prompt: The base prompt to send to the model
            expected_structure: Dictionary or List describing the expected JSON structure
            example_data: Optional example of the expected data structure
            temperature: Model temperature (default: 0.1 for consistent structured output)
            
        Returns:
            Parsed JSON data matching the expected structure, or None if failed
        """
        attempts = 0
        while attempts < self.max_retries:
            try:
                # Enhance prompt with structure requirements
                enhanced_prompt = prompt
                if example_data:
                    enhanced_prompt += f"\n\nExpected format:\n{json.dumps(example_data, indent=2)}"
                enhanced_prompt += "\n\nReturn only valid JSON matching this structure. No other text."

                # Get model response
                response = self.model.generate_content(
                    enhanced_prompt,
                    generation_config={
                        "max_output_tokens": self.max_output_tokens,
                        "temperature": temperature,
                    }
                )

                if not response or not response.text:
                    logger.error("Empty response from model")
                    attempts += 1
                    continue

                # Clean and parse JSON
                json_str = self._clean_json_string(response.text)
                data = json.loads(json_str)

                # Validate structure
                if self._validate_json_structure(data, expected_structure):
                    return data

                # If structure validation failed, retry with explicit error
                logger.warning("Response didn't match expected structure, retrying...")
                attempts += 1
                
                # Add structure validation error to next attempt
                enhanced_prompt += f"\n\nPrevious response didn't match expected structure. Please fix and return only valid JSON."

            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing error: {str(e)}")
                attempts += 1
                
                # If JSON parsing failed, ask model to fix the JSON
                fix_prompt = f"""The previous response was not valid JSON. Please fix the JSON formatting issues and return only valid JSON:

Previous response:
{response.text}

Fix the JSON formatting and return ONLY the corrected JSON."""

                try:
                    fix_response = self.model.generate_content(
                        fix_prompt,
                        generation_config={
                            "max_output_tokens": self.max_output_tokens,
                            "temperature": 0.1,
                        }
                    )
                    
                    if fix_response and fix_response.text:
                        json_str = self._clean_json_string(fix_response.text)
                        data = json.loads(json_str)
                        
                        if self._validate_json_structure(data, expected_structure):
                            return data
                            
                except Exception as e:
                    logger.warning(f"Error fixing JSON: {str(e)}")
                    continue

            except Exception as e:
                logger.error(f"Error getting structured response: {str(e)}")
                attempts += 1

        logger.error(f"Failed to get valid structured response after {self.max_retries} attempts")
        return None