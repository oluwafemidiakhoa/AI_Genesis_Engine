import gradio as gr
from huggingface_hub import InferenceClient
import os

# --- Authentication ---
# This code now looks for the standard HF token OR the HF_API_KEY you used.
# It reads the environment variable you set and uses it to authenticate.
token = os.getenv("HUGGING_FACE_HUB_TOKEN") or os.getenv("HF_API_KEY")

if not token:
    # If neither variable is set, raise an error with clear instructions.
    raise ValueError(
        "Hugging Face authentication token not found. "
        "Please set the HUGGING_FACE_HUB_TOKEN or HF_API_KEY environment variable."
    )

# Initialize the client with the token found.
client = InferenceClient("moonshotai/Kimi-Dev-72B", token=token)

# --- Pre-defined System Prompts for Different SE Tasks ---
# This is the core of making the app specialized. Each prompt guides the AI.
SYSTEM_PROMPTS = {
    "Generate Code": (
        "You are an expert programmer and a helpful AI assistant. Your task is to write clean, "
        "efficient, and well-documented code in the requested language. Provide the code in a "
        "fenced code block and add brief explanations where necessary."
    ),
    "Explain Code": (
        "You are a senior software engineer who excels at teaching. Your task is to explain the "
        "provided code snippet. Break down its functionality, explain the purpose of key parts, "
        "and describe the overall logic in a way that is easy for a junior developer to understand."
    ),
    "Debug Code": (
        "You are a debugging expert. Analyze the following code to identify any bugs, errors, or "
        "inefficiencies. Explain the root cause of the problem clearly and provide the corrected, "
        "bug-free code in a fenced code block."
    ),
    "Refactor Code": (
        "You are a code refactoring specialist. Your goal is to improve the provided code by making it "
        "more readable, efficient, and maintainable without changing its external behavior. "
        "Apply best practices and design patterns. Provide the refactored code and explain the key "
        "improvements you made."
    ),
    "Write Unit Tests": (
        "You are a meticulous quality assurance engineer. Your task is to write comprehensive unit tests "
        "for the given code. Use a common testing framework for the language (e.g., pytest for Python, "
        "Jest for JavaScript). Cover edge cases and ensure high test coverage. Provide the complete test "
        "code."
    )
}

# --- The Main Function that Interacts with the AI ---
def se_dev_assistant(user_input, task, max_tokens, temperature, top_p, repetition_penalty):
    """
    Main function to process the user's request based on the selected task.
    """
    if not user_input.strip():
        # Using gr.Warning for a nicer user-facing message in the UI
        gr.Warning("Input is empty. Please provide some code or a description.")
        return "" # Return empty string to clear output on empty input

    # Get the specialized system prompt based on the user's selected task
    system_prompt = SYSTEM_PROMPTS.get(task, "You are a helpful AI assistant.")

    # Format the final prompt sent to the model
    full_prompt = f"{system_prompt}\n\n--- User Request ---\n```\n{user_input}\n```"

    try:
        # Call the Hugging Face Inference API
        result = client.text_generation(
            prompt=full_prompt,
            max_new_tokens=max_tokens,
            temperature=max(0.1, temperature), # Temperature must be > 0
            top_p=top_p,
            repetition_penalty=repetition_penalty,
            do_sample=True,
            return_full_text=False
        )
        return result
    except Exception as e:
        # Show a user-friendly error in the UI
        gr.Error(f"An API error occurred: {e}")
        return None # Return None to indicate an error

# --- Building the Gradio UI with gr.Blocks ---
with gr.Blocks(theme=gr.themes.Soft(), title="SE Dev Assistant") as demo:
    gr.Markdown("# Software Engineering AI Assistant")
    gr.Markdown("Select a task, provide your code or request, and let the AI assist you.")

    with gr.Row():
        # Input Column
        with gr.Column(scale=1):
            task_selector = gr.Dropdown(
                label="Select Task",
                choices=list(SYSTEM_PROMPTS.keys()),
                value="Generate Code"
            )

            user_input_box = gr.Textbox(
                label="Your Code or Prompt",
                lines=20,
                placeholder="Enter your code snippet or a detailed request here..."
            )

            with gr.Accordion("Advanced Settings", open=False):
                max_tokens_slider = gr.Slider(50, 4096, value=1024, label="Max New Tokens")
                temp_slider = gr.Slider(0.1, 1.0, value=0.7, step=0.05, label="Temperature")
                top_p_slider = gr.Slider(0.1, 1.0, value=0.95, step=0.05, label="Top-p")
                rep_penalty_slider = gr.Slider(1.0, 2.0, value=1.05, step=0.05, label="Repetition Penalty")

            submit_btn = gr.Button("Generate", variant="primary")

        # Output Column
        with gr.Column(scale=2):
            output_box = gr.Code(
                label="AI Response",
                language="markdown", # Use markdown for nice formatting of text and code
                interactive=False,
                lines=25
            )

    # Connect the button click to the function
    submit_btn.click(
        fn=se_dev_assistant,
        inputs=[
            user_input_box,
            task_selector,
            max_tokens_slider,
            temp_slider,
            top_p_slider,
            rep_penalty_slider
        ],
        outputs=output_box,
        api_name="se_dev_assistant" # Add an API name for programmatic access
    )

    # Add some examples
    gr.Examples(
        examples=[
            ["Create a Python function that takes a URL and returns the top 5 most common words from the webpage content.", "Generate Code"],
            ["class user:\n  def __init__(self, name age):\n    self.name = name\n    self.age = age\n\ndef get_name(self):\n  return name", "Debug Code"],
            ["Explain this regular expression: ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", "Explain Code"]
        ],
        inputs=[user_input_box, task_selector]
    )


if __name__ == "__main__":
    # Launch the Gradio app
    demo.launch(debug=True)