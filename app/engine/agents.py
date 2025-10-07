import os
import google.generativeai as genai

class Strategist:
    """
    The Strategist agent uses the Google Gemini API to generate a
    Product Requirements Document (PRD) from a given business idea.
    """
    def __init__(self):
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')

    def generate_prd(self, business_idea: str) -> str:
        """
        Takes a business idea and generates a PRD.

        Args:
            business_idea: A string describing the business idea.

        Returns:
            A string containing the generated PRD.
        """
        prompt = f"""
        As an expert Product Manager, create a detailed Product Requirements Document (PRD)
        for the following business idea:

        **Business Idea:** {business_idea}

        The PRD should include the following sections:
        1.  **Introduction & Vision:** What is the product, who is it for, and what problem does it solve?
        2.  **Target Audience:** Describe the ideal user personas.
        3.  **Core Features:** List and describe the key features of the Minimum Viable Product (MVP).
        4.  **Monetization Strategy:** How will the product generate revenue (e.g., subscription tiers, one-time purchase)?
        5.  **Tech Stack Recommendation:** Suggest a suitable technology stack (frontend, backend, database) for building this product.

        Please format the output in clear, well-structured Markdown.
        """
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"An error occurred while generating the PRD: {e}")
            return "Error: Could not generate PRD."