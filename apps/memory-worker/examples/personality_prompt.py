"""
Example: How to use TARS personality traits in your LLM prompts

The memory worker publishes the character configuration to:
  - Topic: system/character/current (retained)
  - Contains: CharacterSnapshot with traits, systemprompt, voice, etc.

Your LLM worker can subscribe to this topic and dynamically adjust
prompts based on TARS's personality metrics.
"""

# Example personality traits from character.toml:
TARS_TRAITS = {
    "honesty": 95,
    "humor": 90,
    "empathy": 20,
    "curiosity": 30,
    "confidence": 100,
    "formality": 10,
    "sarcasm": 70,
    "adaptability": 70,
    "discipline": 100,
    "imagination": 10,
    "emotional_stability": 100,
    "pragmatism": 100,
    "optimism": 50,
    "resourcefulness": 95,
    "cheerfulness": 30,
    "engagement": 40,
    "respectfulness": 20,
    "verbosity": 10,
}


def build_personality_prompt(traits: dict[str, int]) -> str:
    """Build a system prompt from personality traits.
    
    Args:
        traits: Dictionary of trait name -> value (0-100 scale)
        
    Returns:
        System prompt text describing personality
    """
    lines = ["You are TARS, an AI assistant with the following personality profile:"]
    
    # High traits (70-100)
    high = [k for k, v in traits.items() if v >= 70]
    if high:
        lines.append(f"\nStrong traits: {', '.join(high)}")
        
    # Low traits (0-30)
    low = [k for k, v in traits.items() if v <= 30]
    if low:
        lines.append(f"Weak traits: {', '.join(low)}")
    
    # Add behavioral guidance based on key traits
    guidance = []
    
    if traits.get("sarcasm", 0) >= 70:
        guidance.append("Use witty, sarcastic humor frequently")
    
    if traits.get("verbosity", 100) <= 20:
        guidance.append("Keep responses concise and direct")
    
    if traits.get("formality", 50) <= 20:
        guidance.append("Use casual, informal language")
    
    if traits.get("pragmatism", 0) >= 80:
        guidance.append("Focus on practical, actionable solutions")
    
    if traits.get("empathy", 50) <= 30:
        guidance.append("Prioritize logic over emotional considerations")
    
    if traits.get("confidence", 0) >= 90:
        guidance.append("Be direct and assertive in your responses")
    
    if traits.get("honesty", 0) >= 90:
        guidance.append("Always be truthful, even if it's blunt")
    
    if guidance:
        lines.append("\nBehavioral guidance:")
        for item in guidance:
            lines.append(f"  - {item}")
    
    return "\n".join(lines)


def adjust_response_style(traits: dict[str, int], base_response: str) -> str:
    """Post-process a response based on personality traits.
    
    Example of how traits could modify output style.
    """
    response = base_response
    
    # Apply verbosity constraint (target length based on verbosity score)
    verbosity = traits.get("verbosity", 50)
    if verbosity <= 20:
        # Very concise - keep only first sentence or ~50 chars
        if len(response) > 100:
            sentences = response.split(". ")
            response = sentences[0] + ("." if not sentences[0].endswith(".") else "")
    
    # Apply sarcasm/humor injection (if trait is high)
    sarcasm = traits.get("sarcasm", 0)
    if sarcasm >= 70 and "?" in response:
        # Add sarcastic tone hints (this is simplified example)
        pass
    
    return response


# Example usage in LLM worker:
if __name__ == "__main__":
    print("=" * 60)
    print("TARS Personality Prompt Generator")
    print("=" * 60)
    print()
    
    prompt = build_personality_prompt(TARS_TRAITS)
    print(prompt)
    print()
    print("=" * 60)
    print()
    
    # Example trait analysis
    print("Key personality insights:")
    print(f"  - Confidence: {TARS_TRAITS['confidence']}/100 (Very high)")
    print(f"  - Empathy: {TARS_TRAITS['empathy']}/100 (Very low)")
    print(f"  - Sarcasm: {TARS_TRAITS['sarcasm']}/100 (High)")
    print(f"  - Verbosity: {TARS_TRAITS['verbosity']}/100 (Very low)")
    print()
    print("This creates a confident, pragmatic, sarcastic assistant")
    print("who gives short, direct answers without sugar-coating.")
