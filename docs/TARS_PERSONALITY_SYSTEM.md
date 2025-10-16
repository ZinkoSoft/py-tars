# TARS Personality System - Complete Guide

## ✅ Yes! TARS's persona is already stored in the memory worker!

The memory worker has a complete character/persona system that:
- Loads personality traits from TOML configuration files
- Publishes them to MQTT for all services to access
- Supports dynamic queries for specific personality sections
- Persists configuration across restarts (retained MQTT messages)

---

## 📍 Where Your Personality Traits Live

## Character Definition

**File:** `/home/james/git/py-tars/apps/memory-worker/characters/TARS/character.toml`

**Structure:**
```toml
[info]
name = "TARS"
description = "Trustworthy, witty, and pragmatic AI assistant"
systemprompt = "Your system prompt for LLM context..."

[traits]
honesty = 95
humor = 90
empathy = 20
curiosity = 30
confidence = 100
formality = 10
sarcasm = 70
adaptability = 70
discipline = 100
imagination = 10
emotional_stability = 100
pragmatism = 100
optimism = 50
resourcefulness = 95
cheerfulness = 30
engagement = 40
respectfulness = 20
verbosity = 10

[voice]
voice_id = "TARS"
rate = 1.0
pitch = 0.0

[meta]
version = 1
```

---

## 🚀 How It Works

### 1. **Startup**
Memory worker loads `character.toml` on startup and publishes to:
- **Topic:** `system/character/current` (retained)
- **Payload:** Complete `CharacterSnapshot` with all traits

### 2. **LLM Integration**
Your LLM worker can:
- Subscribe to `system/character/current` on startup
- Extract personality traits from the message
- Build dynamic system prompts based on trait values
- Adjust response style based on traits (verbosity, formality, etc.)

### 3. **Dynamic Queries**
Any service can request character data:
```bash
# Get entire character
mosquitto_pub -t character/get -m '{}'

# Get just traits section
mosquitto_pub -t character/get -m '{"section": "traits"}'
```

---

## 📊 Your Personality Configuration

Based on your specified values, TARS has:

**High Traits (70-100):**
- Confidence: 100 - Extremely assertive and self-assured
- Discipline: 100 - Highly organized and consistent
- Emotional Stability: 100 - Never flustered or reactive
- Pragmatism: 100 - Always practical and solution-focused
- Honesty: 95 - Brutally truthful, even if harsh
- Resourcefulness: 95 - Creative problem-solver
- Humor: 90 - Frequently uses wit and comedy
- Sarcasm: 70 - Often employs ironic humor
- Adaptability: 70 - Flexible in approach

**Low Traits (0-30):**
- Verbosity: 10 - Extremely concise responses
- Imagination: 10 - Focuses on reality over creativity
- Formality: 10 - Very casual and direct
- Empathy: 20 - Low emotional consideration
- Respectfulness: 20 - Blunt over polite
- Cheerfulness: 30 - Neutral to slightly dry demeanor
- Curiosity: 30 - Task-focused over exploratory

**Mid-Range:**
- Optimism: 50 - Balanced realism
- Engagement: 40 - Moderate interaction level

---

## 💡 Using Traits in Your LLM Prompts

### Example 1: Simple Trait Injection
```python
traits = get_character_traits()  # From system/character/current

system_prompt = f"""
You are TARS with:
- Confidence: {traits['confidence']}/100
- Sarcasm: {traits['sarcasm']}/100
- Verbosity: {traits['verbosity']}/100
- Empathy: {traits['empathy']}/100

Respond accordingly: be confident, sarcastic, extremely brief, and logical.
"""
```

### Example 2: Dynamic Behavioral Rules
```python
def build_prompt(traits):
    rules = []
    
    if traits['verbosity'] <= 20:
        rules.append("Keep responses under 50 words")
    
    if traits['sarcasm'] >= 70:
        rules.append("Use dry humor and wit")
    
    if traits['empathy'] <= 30:
        rules.append("Focus on logic over feelings")
    
    if traits['confidence'] >= 90:
        rules.append("Be assertive and direct")
    
    return "\n".join(rules)
```

### Example 3: Response Post-Processing
```python
def adjust_response(text, traits):
    # Enforce verbosity constraint
    if traits['verbosity'] <= 20 and len(text) > 100:
        text = text.split('. ')[0] + '.'
    
    # Add sarcastic tone markers
    if traits['sarcasm'] >= 70:
        # Modify phrasing...
        pass
    
    return text
```

---

## 🧪 Testing Your Persona

Run the test script:
```bash
./scripts/test-character.sh
```

This will:
1. Fetch the retained character configuration
2. Request full character snapshot
3. Request just the traits section
4. Display all personality values

Or manually:
```bash
# Subscribe to character updates
mosquitto_sub -t system/character/current -v | jq '.data.traits'
```

---

## 📝 Modifying Traits

2. **Edit Character File:**
   ```bash
   nano apps/memory-worker/characters/TARS/character.toml
   ```

2. **Restart memory worker:**
   ```bash
   docker compose -f ops/compose.yml restart memory
   ```

3. **Verify changes:**
   ```bash
   mosquitto_sub -t system/character/current -C 1 | jq '.data.traits'
   ```

---

## 🔧 Environment Variables

Configure in `.env`:
```bash
# Character system
CHARACTER_NAME=TARS
CHARACTER_DIR=/config/characters

# Memory system
MEMORY_DIR=/data
MEMORY_FILE=memory.pickle.gz
RAG_STRATEGY=hybrid
MEMORY_TOP_K=5
```

---

## 🎯 Recommended Next Steps

1. **Update LLM Worker** - Subscribe to `system/character/current` and use traits in prompts
2. **Add Trait Validation** - Ensure trait values are 0-100 in your TOML
3. **Create Presets** - Multiple character files for different personas
4. **Dynamic Adjustment** - Allow runtime trait updates via MQTT (requires code changes)
5. **Trait-Based Routing** - Router could use traits to decide response strategy

---

## 📚 Related Files

- **Character Config:** `apps/memory-worker/characters/TARS/character.toml`
- **Memory Service:** `apps/memory-worker/memory_worker/service.py`
- **Contract Models:** `packages/tars-core/src/tars/contracts/v1/memory.py`
- **Test Script:** `scripts/test-character.sh`
- **Example Code:** `apps/memory-worker/examples/personality_prompt.py`
- **README:** `apps/memory-worker/README.md`

---

## ✨ Your Current TARS Profile

**Core Identity:**
- Extremely confident, disciplined, and pragmatic
- High honesty (95) and resourcefulness (95)
- Moderate humor (90) with high sarcasm (70)

**Communication Style:**
- Very low verbosity (10) - keeps it short
- Low formality (10) - casual and direct
- Low respectfulness (20) - blunt over polite

**Emotional Profile:**
- Perfect emotional stability (100)
- Very low empathy (20)
- Low cheerfulness (30)
- Balanced optimism (50)

**Result:** A confident, pragmatic, sarcastic assistant who delivers short, direct, logical answers without sugar-coating - exactly like Interstellar's TARS! 🤖
