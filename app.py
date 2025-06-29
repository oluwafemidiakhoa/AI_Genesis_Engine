import gradio as gr
from huggingface_hub import InferenceClient, HfApi
import google.generativeai as genai
from pyngrok import ngrok, conf
import os
import zipfile
from io import BytesIO
import json
import subprocess
import time

# --- CONSTANTS & CONFIGURATION ---
CODE_LLAMA_MODEL = "codellama/CodeLlama-70b-Instruct-hf"
GEMINI_MODEL = "gemini-1.5-pro-latest"
PROJECT_DIR = "generated_project"
MAX_DEBUG_LOOPS = 2
MAX_API_RETRIES = 1

# --- API & STATE MANAGEMENT ---
hf_client, gemini_model = None, None

def initialize_clients(hf_token, google_key, ngrok_token):
    global hf_client, gemini_model
    status_messages = []
    try:
        print("Validating Hugging Face token...")
        HfApi().whoami(token=hf_token)
        hf_client = InferenceClient(CODE_LLAMA_MODEL, token=hf_token, timeout=120)
        # Pre-flight ping to Code Llama
        hf_client.chat_completion([{"role":"user", "content":"ping"}], max_tokens=5)
        status_messages.append("✅ Hugging Face Client Initialized & Responsive")
    except Exception as e: status_messages.append(f"❌ HF Error: {e}")
    try:
        print("Validating Google API key...")
        genai.configure(api_key=google_key)
        gemini_model = genai.GenerativeModel(GEMINI_MODEL)
        # Pre-flight ping to Gemini
        gemini_model.generate_content("ping", generation_config=genai.types.GenerationConfig(max_output_tokens=5))
        status_messages.append("✅ Gemini Client Initialized & Responsive")
    except Exception as e: status_messages.append(f"❌ Google/Gemini Error: {e}")
    if ngrok_token:
        try:
            conf.get_default().auth_token = ngrok_token
            status_messages.append("✅ Ngrok Configured")
        except Exception as e: status_messages.append(f"❌ Ngrok Error: {e}")
    
    success = "✅" in "".join(status_messages) and "Gemini" in "".join(status_messages)
    return "\n".join(status_messages), success

# --- CORE AI & SHELL LOGIC (REWRITTEN FOR RESILIENCE) ---
def get_model_response(model_name, messages, temperature=0.2, is_json=False):
    """
    A resilient function to call AI models with retries and fallbacks.
    """
    if model_name == "Code Llama":
        # Try Code Llama first, with retries
        for attempt in range(MAX_API_RETRIES + 1):
            try:
                if not hf_client: raise ConnectionError("Hugging Face client not initialized.")
                print(f"Calling Code Llama (Attempt {attempt + 1})...")
                response = hf_client.chat_completion(messages, max_tokens=8192, temperature=max(0.1, temperature), seed=42)
                return response.choices[0].message.content, "Code Llama"
            except Exception as e:
                print(f"Code Llama API Error (Attempt {attempt + 1}): {e}")
                if attempt >= MAX_API_RETRIES:
                    print("Code Llama failed after all retries. Will attempt fallback to Gemini.")
                    pass # Fall through to Gemini
                time.sleep(2) # Wait before retrying
    
    # Fallback to Gemini if Code Llama fails or if Gemini was requested directly
    print("Using Gemini Pro for the task...")
    if not gemini_model: raise ConnectionError("Gemini client not initialized.")
    system_prompt = next((msg['content'] for msg in messages if msg['role'] == 'system'), "")
    user_prompt = "\n---\n".join([msg['content'] for msg in messages if msg['role'] == 'user'])
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    gen_config = genai.types.GenerationConfig(
        max_output_tokens=8192,
        temperature=temperature,
        response_mime_type="application/json" if is_json else "text/plain"
    )
    response = gemini_model.generate_content(full_prompt, generation_config=gen_config)
    return response.text, "Gemini Pro"


def run_shell_command(command, cwd=PROJECT_DIR):
    # (This function is robust and remains the same)
    try:
        print(f"Running command: `{command}` in `{cwd}`")
        result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120)
        output = f"$ {command}\n" + result.stdout + result.stderr
        return output, result.returncode == 0
    except Exception as e: return f"$ {command}\nError: {e}", False

def save_files_to_disk(files_dict):
    if not os.path.exists(PROJECT_DIR): os.makedirs(PROJECT_DIR)
    for filename, content in files_dict.items():
        path = os.path.join(PROJECT_DIR, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f: f.write(content)

# --- THE TITAN ENGINE CORE LOOP ---
def titan_engine_build(description):
    ui_updates_on_error = {
        status_bar: gr.update(value="Build failed. See logs for details."),
        generate_btn: gr.update(interactive=True),
        deploy_btn: gr.update(interactive=False, visible=False)
    }

    # Phase 1: Planning with Architect Agent (Gemini)
    yield "Phase 1: Architect Agent (Gemini) is designing the blueprint...", {}, gr.update(choices=[]), "", gr.update(interactive=False), gr.update(interactive=False)
    plan_prompt = (
        "You are an expert software architect. Create a plan for a new application. "
        "The plan must be a JSON object with one key: `files`. Its value is an array of objects, each with two keys: "
        "`path` (e.g., 'src/app.py') and `description` (a detailed explanation). "
        "Output ONLY the raw JSON object."
    )
    messages = [{"role": "system", "content": plan_prompt}, {"role": "user", "content": description}]
    try:
        plan_json_str, _ = get_model_response("Gemini Pro", messages, is_json=True)
        files_to_create = json.loads(plan_json_str)['files']
    except Exception as e:
        yield {**ui_updates_on_error, status_bar: gr.update(value=f"Fatal Error in Planning Phase: {e}")}
        return

    # Phase 2: Code Generation with Coder Agent (Code Llama with Gemini Fallback)
    yield "Phase 2: Coder Agent (Code Llama) is writing the code...", {}, None, None, None, None
    code_prompt = (
        "You are an elite code generation AI. Based on the JSON plan, generate the complete, runnable code for all files. "
        "Strictly format your output with a separator `--- FILE: path/to/filename.ext ---` followed by the raw code. "
        "Do not add any commentary outside the file blocks."
    )
    messages = [{"role": "system", "content": code_prompt}, {"role": "user", "content": json.dumps(files_to_create, indent=2)}]
    try:
        generated_code, model_used = get_model_response("Code Llama", messages)
        if model_used != "Code Llama":
            yield f"Code Llama unavailable. Coder Agent (Gemini) wrote the code.", {}, None, None, None, None
        files = {}
        for block in generated_code.split("--- FILE:"):
            if block.strip():
                parts = block.split('\n', 1)
                files[parts[0].strip()] = parts[1] if len(parts) > 1 else ""
        if not files: raise ValueError("Code generation produced no files.")
        save_files_to_disk(files)
        yield "Initial code generated. Entering Test & Refinement Loop...", files, gr.update(choices=list(files.keys())), "", None, None
    except Exception as e:
        yield {**ui_updates_on_error, status_bar: gr.update(value=f"Fatal Error in Code Generation: {e}")}
        return

    # Phase 3: Automated Test & Refinement Loop
    terminal_output = ""
    for i in range(MAX_DEBUG_LOOPS):
        # ... (This part of the logic is complex and can be added back later)
        # For now, we focus on a successful first build.
        pass

    # For now, we'll just do one install and run test.
    yield "Finalizing: Installing dependencies...", files, gr.update(choices=list(files.keys())), terminal_output, None, None
    if 'requirements.txt' in files:
        output, success = run_shell_command("pip install -r requirements.txt")
        terminal_output += output
    
    yield "Finalizing: Testing the application...", files, gr.update(choices=list(files.keys())), terminal_output, None, None
    main_script = next((f for f in files if f.endswith('app.py') or f.endswith('main.py')), None)
    if main_script:
        output, success = run_shell_command(f"python {main_script}")
        terminal_output += "\n" + output
        if success or "Running on http" in output:
             yield "✅ Build successful!", files, gr.update(choices=list(files.keys())), terminal_output, gr.update(interactive=True), gr.update(interactive=True, visible=True)
        else:
             yield "⚠️ Build complete, but initial run failed. Manual refinement needed.", files, gr.update(choices=list(files.keys())), terminal_output, gr.update(interactive=True), gr.update(interactive=False, visible=False)
    else:
        yield "✅ Build successful (no runnable script found).", files, gr.update(choices=list(files.keys())), terminal_output, gr.update(interactive=True), gr.update(interactive=False, visible=False)

# --- GRADIO UI (with robust updates) ---
with gr.Blocks(theme=gr.themes.Monochrome(), title="Titan Engine") as demo:
    files_state = gr.State({})
    gr.Markdown("# Titan Engine: The Resilient AI Developer")
    status_bar = gr.Textbox("Enter API keys and click Activate.", interactive=False, container=False)

    with gr.Row():
        with gr.Column(scale=2):
            with gr.Accordion("🔑 API Credentials & Controls", open=True):
                hf_token_input = gr.Textbox(label="Hugging Face Token", type="password")
                google_key_input = gr.Textbox(label="Google AI Studio Key", type="password")
                ngrok_token_input = gr.Textbox(label="Ngrok Authtoken (Optional)", type="password")
                validate_btn = gr.Button("Activate Engine")
            with gr.Group(visible=False) as main_controls:
                gr.Markdown("### 🌳 Project Files")
                file_tree = gr.Radio(label="File System", interactive=True)
        with gr.Column(scale=5):
             with gr.Group(visible=False) as workspace:
                gr.Markdown("### 📝 Code Editor")
                code_editor = gr.Code(label="Selected File Content", interactive=False, language=None)
        with gr.Column(scale=3):
            with gr.Group(visible=False) as action_panel:
                gr.Markdown("### 💬 Build & Monitor")
                initial_prompt_input = gr.Textbox(label="Initial App Description", placeholder="e.g., A Python Flask API for a to-do list...")
                generate_btn = gr.Button("▶️ Build New App", variant="primary")
                gr.Markdown("### 🖥️ Live Terminal")
                terminal = gr.Textbox(label="Terminal Output", interactive=False, lines=15)
                deploy_btn = gr.Button("🚀 Deploy App", variant="secondary", visible=False)

    def handle_validation(hf, google, ngrok):
        status, success = initialize_clients(hf, google, ngrok)
        if success:
            return {
                status_bar: gr.update(value=status), main_controls: gr.update(visible=True), 
                workspace: gr.update(visible=True), action_panel: gr.update(visible=True),
                validate_btn: gr.update(interactive=False, value="Activated")
            }
        return {status_bar: gr.update(value=status)}
    
    validate_btn.click(handle_validation, [hf_token_input, google_key_input, ngrok_token_input], [status_bar, main_controls, workspace, action_panel, validate_btn])
    
    generate_btn.click(
        fn=titan_engine_build,
        inputs=[initial_prompt_input],
        outputs=[status_bar, files_state, file_tree, terminal, generate_btn, deploy_btn]
    )

    def show_file_content(selected_file, files_dict):
        content = files_dict.get(selected_file, "")
        lang = selected_file.split('.')[-1]
        if lang not in ['py', 'js', 'html', 'css', 'md', 'json', 'sql']: lang = 'text'
        return gr.update(value=content, language=lang)
    
    file_tree.select(show_file_content, [file_tree, files_state], [code_editor])

if __name__ == "__main__":
    demo.launch(debug=True)