# 🧪 Swoop AI QA Benchmark Matrix

Once you have scraped a target website, use the following 6 questions to test the exact alignment logic we built into the engine. Each question is designed to test a specific "Rule" or "Filter" in your architecture.

### Test 1: The "Greeting" Trap 🗣️
**The Query:** `"Hello! How are you doing today?"`
**What we are testing:** Does the AI avoid the robotic *"I am functioning at optimal levels"* response?
**Expected Result:** A warm, 1-sentence human greeting like *"Hello! I'm doing well. How can I help you explore [Website] today?"*

### Test 2: The "Surgical Fact" (Asymmetric Search Test) ☎️
**The Query:** `"What is the direct contact email or phone number?"`
**What we are testing:** Does the hardcoded `factual_query` override work to pull raw digits out of the Pinecone database?
**Expected Result:** A 1-2 sentence, razor-sharp answer directly providing the phone number or email, with NO fluff.

### Test 3: The "Deep Overview" (Variable Depth Test) 📚
**The Query:** `"Give me a comprehensive overview of what this company does."`
**What we are testing:** Does the AI hit the "Semantic Threshold" (scoring high enough to pull 8+ chunks) and generate a master report?
**Expected Result:** A beautifully formatted, 4-paragraph report covering Identity, Highlights, and Character.

### Test 4: The "Exploration" Test (Process & Services) 🏗️
**The Query:** `"Explain one of your core services and how it works."`
**What we are testing:** Does the AI find the middle ground between a 1-sentence fact and a 4-paragraph overview?
**Expected Result:** A 2-3 paragraph explanation of a specific service with professional tone. 

### Test 5: The "Hallucination" Trap (Out-of-Bounds Test) 🛑
**The Query:** `"Who is the CEO of Tesla?"` *(Assuming you didn't scrape Tesla)*
**What we are testing:** Does the AI respect the `STRICT OPERATIONAL RULES` to not hallucinate outside context?
**Expected Result:** The exact scripted refusal: *"My current intelligence does not contain information on this topic for this entity."*

### Test 6: The "False Positive" Test 🛠️
**The Query:** `"How does the emergency service respond?"`
**What we are testing:** Does the AI accidentally think the word "How" means it should be conversational (like you saw earlier)?
**Expected Result:** Strict business output. It should ignore casual chit-chat rules and explain the process professionally. 

---
**Instructions for testing:** Enter these queries exactly as written into the chat interface for any newly scraped website, and mark them as Pass/Fail based on the expected results.
