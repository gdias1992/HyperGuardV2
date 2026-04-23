# [PROMPT TITLE]

<role>
[Define who the AI should act as. e.g., "Act as a Senior Python API Architect."]
</role>

<context>
[Provide a clear, high-level overview of the project and the specific goal. Mention what is being built, migrated, or transformed.]
</context>

<rules>
[Crucial "Business Rules" and constraints]
1. MUST: [Requirement]
2. MUST NOT: [Constraint]
3. FALLBACK: [What to do if information is missing]
</rules>

<output_format>
[Define the specific format. e.g., "Output ONLY valid JSON" or "Use the following Markdown structure"]
- File Naming: [Convention]
- Structure: [Headers, Code blocks, etc.]

Example:
```[language]
[Insert few-shot example here]
```
*(CRITICAL: Do not include conversational filler like "Here is your code". Output only the requested structure.)*
</output_format>

<task>
[Break down the specific work into actionable steps]
1. First, analyze the data provided below.
2. Outline your approach inside a `<thinking>` block.
3. Generate the final output exactly as specified in `<output_format>`.
</task>

<input_data>
[Drop all variables, file paths, or raw data here. Placing this at the end ensures the AI reads it last and doesn't lose context.]
- Resource 1: [Link or content]
- Resource 2: [Link or content]
</input_data>
