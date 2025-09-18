import requests
import json
from typing import List, Dict, Any
import time
from dataclasses import dataclass
import pandas as pd
from datetime import datetime
import re

@dataclass
class CommentAnalysis:
    """Data class for comment analysis results"""
    comment_id: str
    sentiment: str  # positive, negative, neutral
    confidence: float
    topics: List[str]
    toxicity: str  # low, medium, high
    emotion: str  # anger, joy, fear, sadness, neutral, etc.
    summary: str
    raw_response: str

class RedditCommentAnalyzer:
    """
    Analyzes Reddit comments using local LLM via Ollama
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434", 
                 model_name: str = "llama3.2:3b"):
        """
        Initialize the analyzer
        
        Args:
            ollama_url: Ollama server URL
            model_name: Model to use (recommended: llama3.2:3b, phi3:mini, or gemma2:2b)
        """
        self.ollama_url = ollama_url
        self.model_name = model_name
        self.session = requests.Session()
        
        # Test connection
        self._test_ollama_connection()
    
    def _test_ollama_connection(self):
        """Test if Ollama is running and model is available"""
        try:
            # Check if Ollama is running
            response = self.session.get(f"{self.ollama_url}/api/tags")
            if response.status_code != 200:
                raise ConnectionError("Ollama server not responding")
            
            # Check if model is available
            models = response.json().get('models', [])
            model_names = [model['name'] for model in models]
            
            if self.model_name not in model_names:
                print(f"Model {self.model_name} not found. Available models:")
                for model in model_names:
                    print(f"  - {model}")
                print(f"\nTo install {self.model_name}, run:")
                print(f"ollama pull {self.model_name}")
                raise ValueError(f"Model {self.model_name} not available")
            
            print(f"✓ Connected to Ollama with model {self.model_name}")
            
        except requests.exceptions.ConnectionError:
            print("❌ Cannot connect to Ollama. Make sure it's running:")
            print("1. Install Ollama: https://ollama.ai/download")
            print("2. Run: ollama serve")
            print(f"3. Install model: ollama pull {self.model_name}")
            raise
    
    def _query_llm(self, prompt: str, max_retries: int = 3) -> str:
        """Query the local LLM with retries"""
        for attempt in range(max_retries):
            try:
                payload = {
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for consistent analysis
                        "top_p": 0.9,
                        "top_k": 40
                    }
                }
                
                response = self.session.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    timeout=60
                )
                
                if response.status_code == 200:
                    return response.json()['response'].strip()
                else:
                    print(f"HTTP {response.status_code}: {response.text}")
                    
            except requests.exceptions.Timeout:
                print(f"Timeout on attempt {attempt + 1}")
            except Exception as e:
                print(f"Error on attempt {attempt + 1}: {e}")
            
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
        
        return "Error: Could not analyze comment"
    
    def analyze_comment(self, comment_text: str, comment_id: str = "") -> CommentAnalysis:
        """
        Analyze a single comment for sentiment, topics, toxicity, etc.
        """
        # Clean the comment text
        cleaned_text = self._clean_text(comment_text)
        
        if len(cleaned_text.strip()) < 5:
            return CommentAnalysis(
                comment_id=comment_id,
                sentiment="neutral",
                confidence=0.0,
                topics=[],
                toxicity="low",
                emotion="neutral",
                summary="Comment too short to analyze",
                raw_response=""
            )
        
        # Create comprehensive analysis prompt
        prompt = f"""Analyze this Reddit comment and provide a structured analysis:

Comment: "{cleaned_text}"

Please analyze and respond in this EXACT format:
SENTIMENT: [positive/negative/neutral]
CONFIDENCE: [0.0-1.0]
TOPICS: [topic1, topic2, topic3] (max 5 topics)
TOXICITY: [low/medium/high]
EMOTION: [anger/joy/fear/sadness/surprise/disgust/neutral]
SUMMARY: [brief 1-sentence summary of the comment's main point]

Be concise and objective. Focus on the actual content and tone."""

        raw_response = self._query_llm(prompt)
        
        # Parse the structured response
        analysis = self._parse_analysis_response(raw_response, comment_id)
        analysis.raw_response = raw_response
        
        return analysis
    
    def _clean_text(self, text: str) -> str:
        """Clean comment text for analysis"""
        # Remove Reddit formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # Italic
        text = re.sub(r'~~(.*?)~~', r'\1', text)      # Strikethrough
        text = re.sub(r'\^(\w+)', r'\1', text)        # Superscript
        text = re.sub(r'&gt;.*?\n', '', text)         # Quotes
        text = re.sub(r'/u/\w+', '[USER]', text)      # User mentions
        text = re.sub(r'/r/\w+', '[SUBREDDIT]', text) # Subreddit mentions
        text = re.sub(r'https?://\S+', '[LINK]', text) # URLs
        
        # Clean whitespace
        text = re.sub(r'\n+', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _parse_analysis_response(self, response: str, comment_id: str) -> CommentAnalysis:
        """Parse the structured LLM response"""
        try:
            lines = response.split('\n')
            result = {
                'sentiment': 'neutral',
                'confidence': 0.5,
                'topics': [],
                'toxicity': 'low',
                'emotion': 'neutral',
                'summary': 'No summary available'
            }
            
            for line in lines:
                line = line.strip()
                if line.startswith('SENTIMENT:'):
                    sentiment = line.split(':', 1)[1].strip().lower()
                    if sentiment in ['positive', 'negative', 'neutral']:
                        result['sentiment'] = sentiment
                
                elif line.startswith('CONFIDENCE:'):
                    try:
                        conf = float(line.split(':', 1)[1].strip())
                        result['confidence'] = max(0.0, min(1.0, conf))
                    except:
                        pass
                
                elif line.startswith('TOPICS:'):
                    topics_str = line.split(':', 1)[1].strip()
                    # Parse topics from [topic1, topic2] format
                    topics_str = topics_str.strip('[]')
                    if topics_str:
                        topics = [t.strip() for t in topics_str.split(',')]
                        result['topics'] = [t for t in topics if t and t != 'none'][:5]
                
                elif line.startswith('TOXICITY:'):
                    toxicity = line.split(':', 1)[1].strip().lower()
                    if toxicity in ['low', 'medium', 'high']:
                        result['toxicity'] = toxicity
                
                elif line.startswith('EMOTION:'):
                    emotion = line.split(':', 1)[1].strip().lower()
                    valid_emotions = ['anger', 'joy', 'fear', 'sadness', 'surprise', 'disgust', 'neutral']
                    if emotion in valid_emotions:
                        result['emotion'] = emotion
                
                elif line.startswith('SUMMARY:'):
                    summary = line.split(':', 1)[1].strip()
                    if summary:
                        result['summary'] = summary
            
            return CommentAnalysis(
                comment_id=comment_id,
                sentiment=result['sentiment'],
                confidence=result['confidence'],
                topics=result['topics'],
                toxicity=result['toxicity'],
                emotion=result['emotion'],
                summary=result['summary'],
                raw_response=""
            )
            
        except Exception as e:
            print(f"Error parsing response: {e}")
            return CommentAnalysis(
                comment_id=comment_id,
                sentiment="neutral",
                confidence=0.0,
                topics=[],
                toxicity="low",
                emotion="neutral",
                summary="Analysis failed",
                raw_response=response
            )
    
    def analyze_comments_batch(self, comments: List[Dict[str, Any]], 
                             batch_delay: float | None = None) -> List[CommentAnalysis]:
        """
        Analyze multiple comments with progress tracking
        
        Args:
            comments: List of comment dictionaries from Reddit API
            batch_delay: Delay between analyses to prevent overloading
            
        Returns:
            List of CommentAnalysis objects
        """
        results = []
        total = len(comments)
        
        print(f"Analyzing {total} comments...")
        
        for i, comment in enumerate(comments, 1):
            comment_text = comment.get('body', '')
            comment_id = comment.get('id', f'comment_{i}')
            
            print(f"Analyzing comment {i}/{total} (ID: {comment_id})")
            
            analysis = self.analyze_comment(comment_text, comment_id)
            results.append(analysis)
            
            # Progress update every 10 comments
            if i % 10 == 0:
                print(f"Progress: {i}/{total} ({i/total*100:.1f}%)")
            
            # Delay to prevent overwhelming the system
            if batch_delay is not None and i < total:
                time.sleep(batch_delay)
        
        print(f"✓ Analysis complete! Processed {len(results)} comments")
        return results
    
    def export_results(self, analyses: List[CommentAnalysis], 
                      filename: str = None) -> str:
        """Export analysis results to CSV"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"reddit_analysis_{timestamp}.csv"
        
        # Convert to DataFrame
        data = []
        for analysis in analyses:
            data.append({
                'comment_id': analysis.comment_id,
                'sentiment': analysis.sentiment,
                'confidence': analysis.confidence,
                'topics': ', '.join(analysis.topics),
                'toxicity': analysis.toxicity,
                'emotion': analysis.emotion,
                'summary': analysis.summary
            })
        
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        print(f"Results exported to {filename}")
        return filename
    
    def get_summary_stats(self, analyses: List[CommentAnalysis]) -> Dict[str, Any]:
        """Generate summary statistics from analyses"""
        if not analyses:
            return {}
        
        # Sentiment distribution
        sentiments = [a.sentiment for a in analyses]
        sentiment_counts = {s: sentiments.count(s) for s in set(sentiments)}
        
        # Toxicity distribution
        toxicity = [a.toxicity for a in analyses]
        toxicity_counts = {t: toxicity.count(t) for t in set(toxicity)}
        
        # Emotion distribution
        emotions = [a.emotion for a in analyses]
        emotion_counts = {e: emotions.count(e) for e in set(emotions)}
        
        # Top topics
        all_topics = []
        for a in analyses:
            all_topics.extend(a.topics)
        topic_counts = {}
        for topic in all_topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Average confidence
        avg_confidence = sum(a.confidence for a in analyses) / len(analyses)
        
        return {
            'total_comments': len(analyses),
            'sentiment_distribution': sentiment_counts,
            'toxicity_distribution': toxicity_counts,
            'emotion_distribution': emotion_counts,
            'top_topics': top_topics,
            'average_confidence': round(avg_confidence, 3)
        }

# Example usage
if __name__ == "__main__":
    # Initialize analyzer (make sure Ollama is running!)
    analyzer = RedditCommentAnalyzer(model_name="llama3.2:3b")
    
    # Example comments for testing
    test_comments = [
        {
            'id': 'test1',
            'body': 'This is absolutely amazing! I love how well this works.'
        },
        {
            'id': 'test2', 
            'body': 'This is complete garbage. Worst thing I have ever seen.'
        },
        {
            'id': 'test3',
            'body': 'The new update has some interesting features regarding machine learning and AI development.'
        }
    ]
    
    # Analyze comments
    results = analyzer.analyze_comments_batch(test_comments, batch_delay=0.5)
    
    # Print results
    for result in results:
        print(f"\nComment {result.comment_id}:")
        print(f"  Sentiment: {result.sentiment} (confidence: {result.confidence})")
        print(f"  Topics: {', '.join(result.topics)}")
        print(f"  Toxicity: {result.toxicity}")
        print(f"  Emotion: {result.emotion}")
        print(f"  Summary: {result.summary}")
    
    # Export results
    analyzer.export_results(results)
    
    # Get summary statistics
    stats = analyzer.get_summary_stats(results)
    print(f"\nSummary Statistics:")
    print(json.dumps(stats, indent=2))