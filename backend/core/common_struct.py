from pydantic import BaseModel, Field
from core.gen_ai_provider import GenAIProvider

class SuggestedQuestions(BaseModel):
    """ Structured output to capture suggested questions based on LLM response """
    suggested_questions: list[str] = Field(description="List of suggested questions based on context")

class SuggestionModel:
    
    def build_suggestion_model(self):
        suggestions_llm = GenAIProvider().build_oci_client()

        return suggestions_llm.with_structured_output(SuggestedQuestions)
    
SUGGESTION_QUERY = """
Based on the given context, generate a list of at least 1-3 suggested follow up questions that the user might want to ask next.
These should be relevant to the information provided and help the user explore the topic further.
Always provide suggestions, even if the information is limited.
Consider questions will be shown in UI, in buttons, so build them short or clean to show good on UI.
Do not make questions related to UI, or the structure, just the raw data that is presented.
"""