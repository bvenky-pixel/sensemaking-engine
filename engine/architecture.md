2026-07-02 — First Working Understanding Engine
Objective

Build the first working version of Confidant's Understanding Layer without relying on an LLM.

What we built
User
   │
   ▼
Conversation Runner
   │
   ▼
Understanding Engine
   │
   ▼
Conversation State
   │
   ▼
State Inspector
Responsibilities
Conversation Runner – Orchestrates the conversation and coordinates the flow.
Understanding Engine – Converts natural language into structured understanding.
Conversation State – Stores the engine's current understanding of the user's situation.
State Inspector – Visualizes the internal state for debugging and development.
Why it matters

This architecture separates understanding from response generation. Rather than sending user input directly to an LLM for an answer, Confidant first builds a structured model of the user's thinking. This model becomes the foundation for reasoning, question generation, and decision support.

Key insight

The response is not the product. The evolving model of the user's judgment is the product.