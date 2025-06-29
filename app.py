import gradio as gr
from huggingface_hub import InferenceClient
import os
import zipfile
from io import BytesIO

# --- Authentication ---
token = os.getenv("HUGGING_FACE_HUB_TOKEN") or os.getenv("HF_API_KEY")
if not token:
    raise ValueError("Hugging Face token not found. Set HUGGING_FACE_HUB_TOKEN or HF_API_KEY.")

# --- MODEL SELECTION ---
# Switched to a top-tier, Hugging Face-hosted model that is fully compatible.
# This model is excellent for coding and uses the conversational format.
try:
    client = InferenceClient("codellama/CodeLlama-70b-Instruct-hf", token=token)
except Exception as e:
    raise RuntimeError(f"Failed to initialize InferenceClient. Check model name and token. Error: {e}")

# --- System Prompts ---
CODE_ASSISTANT_PROMPTS = {
    "Generate Code": "You are an expert programmer using the Code Llama model. Write clean, efficient, and well-documented code based on the user's request. Provide the code in a fenced code block.",
    "Explain Code": "You are a senior software engineer and teacher. Explain the provided code snippet, breaking down its logic and purpose for a junior developer.",
    "Debug Code": "You are a debugging expert. Analyze the code, identify any bugs or errors, explain the root cause, and provide the corrected code.",
    "Refactor Code": "You are a code refactoring specialist. Improve the provided code for readability, efficiency, and maintainability without changing its behavior. Explain the improvements.",
    "Write Unit Tests": "You are a quality assurance engineer. Write comprehensive unit tests for the given code using a common testing framework for the language.",
}
APP_BUILDER_PROMPTS = {
    "Python Flask API": (
        "You are a full-stack application architect. Your task is to generate a complete, multi-file Flask application based on the user's description. "
        "Create all necessary files, including `app.py`, `requirements.txt`, and a `README.md`. "
        "Strictly format your output by clearly separating each file's content with a header like `--- FILE: path/to/filename.ext ---`. "
        "Do not include any other commentary outside of the file blocks."
    ),
    "React Frontend App": (
        "You are a frontend development expert specializing in React. Generate a functional, multi-file React application using functional components and hooks based on the user's description. "
        "Create all necessary files, like `src/App.js`, `src/index.css`, and `package.json`. "
        "Strictly format your output by clearly separating each file's content with a header like `--- FILE: path/to/filename.ext ---`. "
        "Do not include any other commentary outside of the file blocks."
    ),
     "Simple HTML/CSS/JS Website": (
        "You are a web designer. Create the code for a simple static website based on the user's description. "
        "Generate the `index.html`, `style.css`, and `script.js` files. "
        "Strictly format your output by clearly separating each file's content with a header like `--- FILE: path/to/filename.ext ---`. "
        "Do not include any other commentary outside of the file blocks."
    )
}

# --- Backend Functions ---
def se_dev_assistant(user_input, file_obj, task, max_tokens, temperature, top_p):
    if file_obj is not None:
        file_content = file_obj.read().decode('utf-8')
        user_input = f"Based on the following file content:\n\n```\n{file_content}\n```\n\nUser Request: {user_input}"
    if not user_input.strip():
        gr.Warning("Input is empty.")
        return "", None
    system_prompt = CODE_ASSISTANT_PROMPTS.get(task)
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}]
    try:
        response = client.chat_completion(messages=messages, max_tokens=max_tokens, temperature=max(0.1, temperature), top_p=top_p)
        result = response.choices[0].message.content
        output_file = (BytesIO(result.encode('utf-8')), "ai_assistant_output.txt")
        return result, output_file
    except Exception as e:
        gr.Error(f"API Error: {e}")
        return str(e), None

def parse_and_create_zip(ai_output):
    files = {}
    current_filename = None
    current_content = []
    for line in ai_output.split('\n'):
        if line.startswith("--- FILE:"):
            if current_filename and current_content:
                files[current_filename] = "\n".join(current_content).strip()
            current_filename = line.split(":", 1)[1].strip()
            current_content = []
        elif current_filename is not None:
            current_content.append(line)
    if current_filename and current_content:
         files[current_filename] = "\n".join(current_content).strip()
    if not files: return None, ai_output
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)
    zip_buffer.seek(0)
    downloadable_zip = (zip_buffer, "generated_app.zip")
    summary = "✅ App files generated successfully!\n\n" + "\n".join(files.keys())
    return downloadable_zip, summary

def build_app(app_description, app_type, max_tokens, temperature, top_p):
    if not app_description.strip():
        gr.Warning("Please describe the application you want to build.")
        return None, "Error: App description cannot be empty."
    system_prompt = APP_BUILDER_PROMPTS.get(app_type)
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": app_description}]
    try:
        response = client.chat_completion(messages=messages, max_tokens=max_tokens, temperature=max(0.1, temperature), top_p=top_p)
        result = response.choices[0].message.content
        return parse_and_create_zip(result)
    except Exception as e:
        gr.Error(f"API Error: {e}")
        return None, str(e)

# --- Gradio UI ---
with gr.Blocks(theme=gr.themes.Soft(), title="Dev Assistant Pro") as demo:
    gr.Markdown("# 🚀 Dev Assistant Pro (Powered by Code Llama 70B)")
    with gr.Tabs():
        with gr.TabItem("Code Assistant"):
            with gr.Row():
                with gr.Column(scale=1):
                    task_selector = gr.Dropdown(label="Select Task", choices=list(CODE_ASSISTANT_PROMPTS.keys()), value="Generate Code")
                    user_input_box = gr.Textbox(label="Prompt or Instructions", lines=10, placeholder="Enter your request...")
                    file_uploader = gr.File(label="Upload File (Optional)", type="binary")
                    with gr.Accordion("Advanced Settings", open=False):
                        ca_max_tokens = gr.Slider(200, 4096, value=1500, label="Max Tokens")
                        ca_temp = gr.Slider(0.1, 1.0, value=0.2, label="Temperature")
                        ca_top_p = gr.Slider(0.1, 1.0, value=0.9, label="Top-p")
                    ca_submit_btn = gr.Button("Generate", variant="primary")
                with gr.Column(scale=2):
                    ca_output_box = gr.Code(label="AI Response", language="markdown", lines=22)
                    ca_download_btn = gr.DownloadButton(label="Download Response", visible=True)
        with gr.TabItem("App Builder"):
            with gr.Row():
                with gr.Column(scale=1):
                    app_type_selector = gr.Dropdown(label="Select Application Type", choices=list(APP_BUILDER_PROMPTS.keys()), value="Python Flask API")
                    app_desc_box = gr.Textbox(label="Describe Your Application", lines=15, placeholder="e.g., A simple to-do list API with endpoints to add, list, and delete tasks. Use an in-memory list to store tasks.")
                    with gr.Accordion("Advanced Settings", open=False):
                        ab_max_tokens = gr.Slider(500, 8192, value=4000, label="Max Tokens (use more for full apps)")
                        ab_temp = gr.Slider(0.1, 1.0, value=0.2, label="Temperature")
                        ab_top_p = gr.Slider(0.1, 1.0, value=0.9, label="Top-p")
                    ab_submit_btn = gr.Button("Build App", variant="primary")
                with gr.Column(scale=2):
                    ab_output_summary = gr.Textbox(label="Generated App Summary", lines=10, interactive=False)
                    ab_download_btn = gr.DownloadButton(label="Download App as .zip", visible=True)
    ca_submit_btn.click(fn=se_dev_assistant, inputs=[user_input_box, file_uploader, task_selector, ca_max_tokens, ca_temp, ca_top_p], outputs=[ca_output_box, ca_download_btn])
    ab_submit_btn.click(fn=build_app, inputs=[app_desc_box, app_type_selector, ab_max_tokens, ab_temp, ab_top_p], outputs=[ab_download_btn, ab_output_summary])

if __name__ == "__main__":
    demo.launch(debug=True)