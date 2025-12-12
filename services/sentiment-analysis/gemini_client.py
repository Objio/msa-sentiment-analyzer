"""
Gemini API Client for Sentiment Analysis

Handles communication with Gemini 2.0 Flash for sentiment analysis.
"""

import os
import logging
import json
import asyncio
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
import google.generativeai as genai

# Add parent directory to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.models import SentimentResult, SentimentType, EmotionScores

logger = logging.getLogger(__name__)

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class GeminiClient:
    """Client for Gemini API sentiment analysis."""
    
    def __init__(self, model_name: str = "gemini-2.0-flash-exp"):
        """
        Initialize Gemini client.
        
        Args:
            model_name: Gemini model to use
        """
        self.model_name = model_name
        self.model = genai.GenerativeModel(model_name)
        logger.info(f"Gemini client initialized with model: {model_name}")
    
    def _build_prompt(self, text: str) -> str:
        """
        Build prompt for sentiment analysis.
        
        Args:
            text: Text to analyze
            
        Returns:
            Formatted prompt
        """
        prompt = f"""Analyze the sentiment of the following text and provide a detailed analysis.

Text: "{text}"

Provide your response as a valid JSON object with the following structure:
{{
  "overall_sentiment": "positive|negative|neutral|mixed",
  "sentiment_score": <number between -1.0 and 1.0>,
  "confidence": <number between 0.0 and 1.0>,
  "emotions": {{
    "joy": <0.0 to 1.0>,
    "anger": <0.0 to 1.0>,
    "sadness": <0.0 to 1.0>,
    "fear": <0.0 to 1.0>,
    "surprise": <0.0 to 1.0>
  }},
  "key_phrases": [
    {{"phrase": "text", "sentiment": "positive|negative|neutral", "score": 0.0-1.0}}
  ],
  "entities": [
    {{"text": "entity name", "type": "PERSON|ORGANIZATION|LOCATION|etc", "sentiment": "positive|negative|neutral"}}
  ],
  "toxicity": {{
    "is_toxic": false,
    "toxicity_score": 0.0,
    "categories": {{"profanity": 0.0, "hate_speech": 0.0, "harassment": 0.0}}
  }}
}}

Guidelines:
- overall_sentiment: The primary sentiment classification
- sentiment_score: -1.0 (very negative) to +1.0 (very positive)
- confidence: How confident you are in the analysis
- emotions: Breakdown of detected emotions
- key_phrases: Important phrases that convey sentiment
- entities: Named entities mentioned
- toxicity: Content safety analysis

Respond ONLY with the JSON, no additional text."""
        return prompt
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def analyze_sentiment(self, text: str) -> Optional[SentimentResult]:
        """
        Analyze sentiment of text using Gemini.
        
        Args:
            text: Text to analyze
            
        Returns:
            SentimentResult or None if failed
        """
        try:
            # Build prompt
            prompt = self._build_prompt(text)
            
            # Generate response
            logger.debug(f"Sending request to Gemini for text: {text[:50]}...")
            
            # Run in executor since genai is synchronous
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.1,  # Low temperature for consistency
                        top_p=0.95,
                        top_k=40,
                        max_output_tokens=2048,
                    )
                )
            )
            
            # Extract JSON from response
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
            if "```json" in response_text:
                response_text = response_text.replace("```json", "").replace("```", "")
            
            # Parse JSON
            result_dict = json.loads(response_text)
            
            # Convert to SentimentResult
            sentiment_result = self._parse_result(result_dict)
            
            logger.info(
                f"Sentiment analysis complete",
                sentiment=sentiment_result.overall_sentiment,
                score=sentiment_result.sentiment_score
            )
            
            return sentiment_result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.debug(f"Response text: {response_text}")
            return None
        except Exception as e:
            logger.error(f"Error in Gemini sentiment analysis: {e}")
            raise
    
    def _parse_result(self, result_dict: Dict[str, Any]) -> SentimentResult:
        """
        Parse Gemini response into SentimentResult.
        
        Args:
            result_dict: Parsed JSON response
            
        Returns:
            SentimentResult
        """
        # Parse emotions
        emotions_data = result_dict.get("emotions", {})
        emotions = EmotionScores(
            joy=emotions_data.get("joy", 0.0),
            anger=emotions_data.get("anger", 0.0),
            sadness=emotions_data.get("sadness", 0.0),
            fear=emotions_data.get("fear", 0.0),
            surprise=emotions_data.get("surprise", 0.0)
        )
        
        # Create SentimentResult
        sentiment_result = SentimentResult(
            overall_sentiment=SentimentType(result_dict.get("overall_sentiment", "neutral")),
            sentiment_score=float(result_dict.get("sentiment_score", 0.0)),
            confidence=float(result_dict.get("confidence", 0.5)),
            emotions=emotions,
            key_phrases=result_dict.get("key_phrases"),
            entities=result_dict.get("entities"),
            toxicity=result_dict.get("toxicity")
        )
        
        return sentiment_result
