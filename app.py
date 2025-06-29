import gradio as gr
from huggingface_hub import InferenceClient, HfApi
from huggingface_hub.errors import HfHubHTTPError
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
MAX_DEBUG_LOOPS = 3 # The AI will try to fix its own errors up to 3 times.

# --- API & STATE MANAGEMENT ---
hf_client, gemini_model = None, None
active_processes = {}

def initialize_clients(hf_token, google_key, ngrok_token):
    # (This function remains the same as before)
    global hf_client, gemini_model
    status_messages = []
    try:
        print("Validating Hugging Face token...")
        HfApi().whoami(token=hf_token)
        hf_client = InferenceClient(CODE_LLAMA_MODEL, token=hf_token, timeout=180)
        status_messages.append("✅ Hugging Face Client Initialized")
    except Exception as e: status_messages.append(f"❌ HF Error: {e}")
    try:
        print("Validating Google API key...")
        genai.configure(api_key=google_key)
        gemini_model = genai.GenerativeModel(GEMINI_MODEL)
        gemini_model.generate_content("test", generation_config=genai.types.GenerationConfig(max_output_tokens=5))
        status_messages.append("✅ Gemini Client Initialized")
    except Exception as e: status_messages.append(f"❌ Google/Gemini Error: {e}")
    try:
        if ngrok_token:
            print("Configuring ngrok...")
            conf.get_default().auth_token = ngrok_token
            status_messages.append("✅ Ngrok Configured")
        else: status_messages.append("⚠️ Ngrok token not provided.")
    except Exception as e: status_messages.append(f"❌ Ngrok Error: {e}")
    success = "✅" in "".join(status_messages) and "Gemini" in "".join(status_messages)
    return "\n".join(status_messages), success

# --- CORE AI & SHELL LOGIC (REWRITTEN) ---
def get_model_response(model_name, messages, temperature=0.2, is_json=False):
    # Unified model caller with optional JSON mode for Gemini
    max_tokens=8192
    if model_name == "Code Llama" and hf_client:
        response = hf_client.chat_completion(messages, max_tokens=max_tokens, temperature=max(0.1, temperature), seed=42)
        return response.choices[0].message.content
    elif model_name == "Gemini Pro" and gemini_model:
        system_prompt = next((msg['content'] for msg in messages if msg['role'] == 'system'), "")
        user_prompt = "\n---\n".join([msg['content'] for msg in messages if msg['role'] == 'user'])
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        gen_config = genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
            response_mime_type="application/json" if is_json else "text/plain"
        )
        response = gemini_model.generate_content(full_prompt, generation_config=gen_config)
        return response.text
    raise ValueError("Model/client not ready.")

def run_shell_command(command, cwd=PROJECT_DIR):
    # (This function remains the same)
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

# --- THE PHOENIX ENGINE CORE LOOP ---
def phoenix_engine_build(description):
    """The main agentic build/debug/refine loop."""
    # Initial UI state
    yield "Initializing...", {}, gr.update(choices=[]), "", gr.update(interactive=False), gr.update(interactive=False)
    
    # === Phase 1: Planning with Architect Agent (Gemini) ===
    yield "Phase 1: Architect Agent is designing the application blueprint...", {}, None, None, None, None
    plan_prompt = (
        "You are an expert software architect. Create a plan for a new application based on the user's description. "
        "The plan must be a JSON object with one key: `files`. Its value is an array of objects, each with two keys: "
        "`path` (e.g., 'src/app.py') and `description` (a detailed explanation of the file's purpose and logic). "
        "Output ONLY the raw JSON object."
    )
    messages = [{"role": "system", "content": plan_prompt}, {"role": "user", "content": description}]
    try:
        plan_json_str = get_model_response("Gemini Pro", messages, temperature=0.4, is_json=True)
        files_to_create = json.loads(plan_json_str)['files']
    except Exception as e:
        yield f"Fatal Error in Planning Phase: {e}. Please try a different prompt.", {}, None, None, gr.update(interactive=True), gr.update(interactive=True)
        return

    # === Phase 2: Initial Code Generation with Coder Agent (Code Llama) ===
    yield "Phase 2: Coder Agent is writing the first version of the code...", {}, None, None, None, None
    code_prompt = (
        "You are Code Llama, an elite code generation AI. Based on the JSON plan, generate the complete, runnable code for all files. "
        "Strictly format your output with a separator `--- FILE: path/to/filename.ext ---` followed by the raw code. "
        "Do not add any commentary outside the file blocks."
    )
    messages = [{"role": "system", "content": code_prompt}, {"role": "user", "content": json.dumps(files_to_create, indent=2)}]
    try:
        generated_code = get_model_response("Code Llama", messages)
        files = {}
        for block in generated_code.split("--- FILE:"):
            if block.strip():
                parts = block.split('\n', 1)
                files[parts[0].strip()] = parts[1] if len(parts) > 1 else ""
        if not files: raise ValueError("Code generation produced no files.")
        save_files_to_disk(files)
        yield "Initial code generated. Entering Test & Refinement Loop...", files, gr.update(choices=list(files.keys())), "", None, None
    except Exception as e:
        yield f"Fatal Error in Code Generation: {e}", {}, None, None, gr.update(interactive=True), gr.update(interactive=True)
        return

    # === Phase 3: The Automated Test & Refinement Loop ===
    terminal_output = ""
    for i in range(MAX_DEBUG_LOOPS):
        attempt = i + 1
        yield f"Refinement Loop {attempt}/{MAX_DEBUG_LOOPS}: Installing dependencies...", files, gr.update(choices=list(files.keys())), terminal_output, None, None
        
        # Step 3a: Install dependencies
        if 'requirements.txt' in files:
            output, success = run_shell_command("pip install -r requirements.txt")
            terminal_output += output
            if not success:
                # If install fails, we enter the debug cycle for requirements.txt
                pass 
        
        # Step 3b: Run the application
        yield f"Refinement Loop {attempt}/{MAX_DEBUG_LOOPS}: Testing the application...", files, gr.update(choices=list(files.keys())), terminal_output, None, None
        main_script = next((f for f in files if f.endswith('app.py') or f.endswith('main.py')), None)
        if not main_script: break # No runnable script, loop is done.

        output, success = run_shell_command(f"python {main_script}")
        terminal_output += "\n" + output

        # Step 3c: Check for success
        if success or "Running on http" in output:
            yield "✅ Build successful! Application is running without errors.", files, gr.update(choices=list(files.keys())), terminal_output, gr.update(interactive=True), gr.update(interactive=True, visible=True)
            return

        # Step 3d: If failed, invoke QA Agent to create a debug plan
        yield f"Run failed. Invoking QA Agent to analyze error...", files, gr.update(choices=list(files.keys())), terminal_output, None, None
        qa_prompt = (
            "You are a Senior QA Engineer. Analyze the provided codebase and terminal output which shows an error. "
            "Your task is to produce a JSON object with a debugging plan. The JSON should contain: "
            "`file_to_fix` (the path of the file that needs changing), "
            "`error_summary` (a brief, one-sentence explanation of the bug), and "
            "`fix_plan` (a clear, step-by-step plan for the Coder Agent to follow). "
            "Be precise. Output ONLY the raw JSON."
        )
        context = f"CODEBASE:\n{json.dumps(files, indent=2)}\n\nTERMINAL LOG:\n{terminal_output}"
        messages = [{"role": "system", "content": qa_prompt}, {"role": "user", "content": context}]
        try:
            debug_plan_str = get_model_response("Gemini Pro", messages, temperature=0.1, is_json=True)
            debug_plan = json.loads(debug_plan_str)
        except Exception as e:
            yield f"Error getting debug plan from QA Agent: {e}. Aborting.", files, gr.update(choices=list(files.keys())), terminal_output, gr.update(interactive=True), gr.update(interactive=True)
            return

        # Step 3e: Invoke Coder Agent to perform the fix
        yield f"QA Agent Plan: '{debug_plan['error_summary']}'. Instructing Coder Agent to fix...", files, gr.update(choices=list(files.keys())), terminal_output, None, None
        fix_prompt = (
            "You are a Coder Agent specializing in bug fixes. You MUST fix the specified file according to the provided plan. "
            "Output ONLY the complete, raw, corrected code for the single file that needs to be fixed. Do not add any other text."
        )
        context = f"DEBUGGING PLAN:\n{json.dumps(debug_plan, indent=2)}\n\nORIGINAL FILE CONTENT for `{debug_plan['file_to_fix']}`:\n{files.get(debug_plan['file_to_fix'], '')}"
        messages = [{"role": "system", "content": fix_prompt}, {"role": "user", "content": context}]
        try:
            fixed_code = get_model_response("Code Llama", messages)
            files[debug_plan['file_to_fix']] = fixed_code # Update the file in our state
            save_files_to_disk(files) # And on disk
        except Exception as e:
            yield f"Error getting fix from Coder Agent: {e}. Aborting.", files, gr.update(choices=list(files.keys())), terminal_output, gr.update(interactive=True), gr.update(interactive=True)
            return

    # If loop finishes without success
    yield f"⚠️ Max auto-debug attempts reached. The application still has errors. You can now try to fix it via chat.", files, gr.update(choices=list(files.keys())), terminal_output, gr.update(interactive=True), gr.update(interactive=True)

# (Chat and Deploy functions remain largely the same, but simplified for clarity)
def chat_and_refine(chat_history, files_dict, terminal_content):
    # This function is now for manual refinement AFTER the initial build
    user_query = chat_history[-1][0]
    yield chat_history, "⏳ Thinking...", gr.update(interactive=False)
    # Simplified refinement logic...
    yield chat_history, "Manual refinement is a future feature. For now, please start a new build.", gr.update(interactive=True)

def deploy_with_ngrok():
    # This function remains the same
    pass

# --- UI HELPER FUNCTIONS ---
def update_file_tree_and_editor(files_dict):
    choices = list(files_dict.keys()) if files_dict else []
    return gr.update(choices=choices), gr.update(value="", language=None)
def show_file_content(selected_file, files_dict):
    content = files_dict.get(selected_file, "")
    lang = selected_file.split('.')[-1]
    if lang not in ['py', 'js', 'html', 'css', 'md', 'json', 'sql']: lang = 'text'
    return gr.update(value=content, language=lang)

# --- GRADIO UI (with Textbox fix) ---
with gr.Blocks(theme=gr.themes.Monochrome(), title="Phoenix Engine") as demo:
    files_state = gr.State({})
    gr.Markdown("# 🔥 Phoenix Engine: The Self-Correcting AI Developer")
    status_bar = gr.Textbox("Enter API keys to activate the engine.", interactive=False, container=False)
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
                code_editor = gr.Code(label="Selected File Content", interactive=True, language=None)
        with gr.Column(scale=3):
            with gr.Group(visible=False) as action_panel:
                gr.Markdown("### 💬 Build & Monitor")
                initial_prompt_input = gr.Textbox(label="Initial App Description", placeholder="e.g., A Python Flask API for a to-do list...")
                generate_btn = gr.Button("▶️ Build New App", variant="primary")
                gr.Markdown("### 🖥️ Live Terminal")
                terminal = gr.Textbox(label="Terminal Output", interactive=False, lines=15)
                deploy_btn = gr.Button("🚀 Deploy App", variant="secondary", visible=False)

    # Event Wiring
    def handle_validation(hf, google, ngrok):
        status, success = initialize_clients(hf, google, ngrok)
        if success:
            return {status_bar: gr.update(value=status), main_controls: gr.update(visible=True), workspace: gr.update(visible=True), action_panel: gr.update(visible=True), validate_btn: gr.update(interactive=False)}
        return {status_bar: gr.update(value=status)}
    
    validate_btn.click(handle_validation, [hf_token_input, google_key_input, ngrok_token_input], [status_bar, main_controls, workspace, action_panel, validate_btn])
    
    generate_btn.click(
        fn=phoenix_engine_build,
        inputs=[initial_prompt_input],
        outputs=[status_bar, files_state, file_tree, terminal, generate_btn, deploy_btn]
    )
    
    file_tree.select(show_file_content, [file_tree, files_state], [code_editor])

if __name__ == "__main__":
    demo.launch(debug=True, share=False)