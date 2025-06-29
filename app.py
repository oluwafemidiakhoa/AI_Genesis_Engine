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
import threading

# --- CONSTANTS & CONFIGURATION ---
CODE_LLAMA_MODEL = "codellama/CodeLlama-70b-Instruct-hf"
GEMINI_MODEL = "gemini-1.5-pro-latest"
PROJECT_DIR = "generated_project"

# --- API & STATE MANAGEMENT ---
hf_client, gemini_model = None, None
active_processes = {} # To manage running app and ngrok processes

def initialize_clients(hf_token, google_key, ngrok_token):
    global hf_client, gemini_model
    status_messages = []
    try:
        # Hugging Face
        print("Validating Hugging Face token...")
        HfApi().whoami(token=hf_token)
        hf_client = InferenceClient(CODE_LLAMA_MODEL, token=hf_token, timeout=180)
        status_messages.append("✅ Hugging Face Client Initialized")
        print("HF client OK.")
    except Exception as e:
        status_messages.append(f"❌ HF Error: {e}")

    try:
        # Gemini
        print("Validating Google API key...")
        genai.configure(api_key=google_key)
        gemini_model = genai.GenerativeModel(GEMINI_MODEL)
        gemini_model.generate_content("test", generation_config=genai.types.GenerationConfig(max_output_tokens=5))
        status_messages.append("✅ Gemini Client Initialized")
        print("Gemini client OK.")
    except Exception as e:
        status_messages.append(f"❌ Google/Gemini Error: {e}")

    try:
        # Ngrok
        if ngrok_token:
            print("Configuring ngrok...")
            conf.get_default().auth_token = ngrok_token
            status_messages.append("✅ Ngrok Configured")
            print("Ngrok OK.")
        else:
            status_messages.append("⚠️ Ngrok token not provided. Deployment may be unstable.")
    except Exception as e:
        status_messages.append(f"❌ Ngrok Error: {e}")

    success = "✅" in "".join(status_messages) and "Gemini" in "".join(status_messages)
    return "\n".join(status_messages), success

# --- CORE AI & SHELL LOGIC ---
def get_model_response(model_name, messages, max_tokens=8192, temperature=0.3):
    if model_name == "Code Llama" and hf_client:
        response = hf_client.chat_completion(messages, max_tokens=max_tokens, temperature=max(0.1, temperature), seed=42)
        return response.choices[0].message.content
    elif model_name == "Gemini Pro" and gemini_model:
        system_prompt = next((msg['content'] for msg in messages if msg['role'] == 'system'), "")
        user_prompt = "\n---\n".join([msg['content'] for msg in messages if msg['role'] == 'user'])
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        response = gemini_model.generate_content(full_prompt, generation_config=genai.types.GenerationConfig(max_output_tokens=max_tokens, temperature=temperature))
        return response.text
    raise ValueError("Model/client not ready.")

def run_shell_command(command, cwd=PROJECT_DIR):
    try:
        print(f"Running command: `{command}` in `{cwd}`")
        result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120)
        output = f"$ {command}\n"
        output += result.stdout
        output += result.stderr
        return output, result.returncode == 0
    except subprocess.TimeoutExpired:
        return f"$ {command}\nError: Command timed out after 120 seconds.", False
    except Exception as e:
        return f"$ {command}\nError: {e}", False

def save_files_to_disk(files_dict):
    if not os.path.exists(PROJECT_DIR):
        os.makedirs(PROJECT_DIR)
    for filename, content in files_dict.items():
        path = os.path.join(PROJECT_DIR, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

def generate_code_and_plan(description):
    yield "Initializing...", {}, [], None, gr.update(interactive=False), gr.update(interactive=False)
    
    # Phase 1: Planning with Gemini
    yield "Phase 1/4: Generating architectural plan with Gemini Pro...", {}, [], None, None, None
    plan_prompt = (
        "You are an expert software architect. Create a detailed plan for a new application based on the user's description. "
        "The plan must be a JSON object containing one key: `files`. The value of `files` should be an array of objects, "
        "where each object has two keys: `path` (e.g., 'src/app.py') and `description` (a detailed explanation of the file's purpose, functions, and logic). "
        "Do not output any text other than the raw JSON object."
    )
    messages = [{"role": "system", "content": plan_prompt}, {"role": "user", "content": description}]
    try:
        plan_json_str = get_model_response("Gemini Pro", messages)
        plan_data = json.loads(plan_json_str.strip().replace("```json", "").replace("```", ""))
        files_to_create = plan_data['files']
    except Exception as e:
        yield f"Error in planning phase: {e}", {}, [], None, gr.update(interactive=True), gr.update(interactive=True)
        return

    # Phase 2: Code Generation with Code Llama
    yield "Phase 2/4: Generating code with Code Llama 70B...", {}, [], None, None, None
    code_prompt = (
        "You are Code Llama, an elite code generation AI. Based on the following JSON plan, generate the complete, functional code for all files. "
        "Strictly format your output with a separator `--- FILE: path/to/filename.ext ---` followed by the raw code for that file. "
        "Do not add any commentary or explanations outside the file blocks."
    )
    messages = [{"role": "system", "content": code_prompt}, {"role": "user", "content": json.dumps(files_to_create, indent=2)}]
    try:
        generated_code = get_model_response("Code Llama", messages)
        files = {}
        for block in generated_code.split("--- FILE:"):
            if block.strip():
                parts = block.split('\n', 1)
                filename = parts[0].strip()
                content = parts[1] if len(parts) > 1 else ""
                files[filename] = content
        if not files: raise ValueError("Code generation produced no files.")
    except Exception as e:
        yield f"Error in code generation phase: {e}", {}, [], None, gr.update(interactive=True), gr.update(interactive=True)
        return

    save_files_to_disk(files)
    
    # Phase 3: Install Dependencies
    yield "Phase 3/4: Installing dependencies from requirements.txt...", files, [], None, None, None
    terminal_output = ""
    if 'requirements.txt' in files:
        output, success = run_shell_command("pip install -r requirements.txt")
        terminal_output += output
        if not success:
            yield "Installation failed. Check terminal output.", files, [], terminal_output, gr.update(interactive=True), gr.update(interactive=True)
            return
            
    # Phase 4: Initial Run Test
    yield "Phase 4/4: Performing initial run test...", files, [], terminal_output, None, None
    main_script = next((f for f in files if f.endswith('app.py') or f.endswith('main.py')), None)
    if main_script:
        output, success = run_shell_command(f"python {main_script}", cwd=PROJECT_DIR)
        terminal_output += "\n" + output
        if success or "Running on" in output:
             yield "✅ Build successful! App is ready. You can now chat to refine it or deploy it.", files, [], terminal_output, gr.update(interactive=True), gr.update(interactive=True, visible=True)
        else:
             yield "⚠️ Build complete, but initial run failed. The AI can now try to debug this. Chat with it!", files, [], terminal_output, gr.update(interactive=True), gr.update(interactive=True)
    else:
        yield "✅ Build successful (no runnable script found).", files, [], terminal_output, gr.update(interactive=True), gr.update(interactive=True)


def chat_and_refine(chat_history, files_dict, terminal_content):
    user_query = chat_history[-1][0]
    yield chat_history, "⏳ Thinking...", gr.update(interactive=False)
    context_prompt = (
        "You are an AI software engineer. You are in a refinement session. "
        "Below is the current state of the file system, the latest terminal output, and the user's request. "
        "Your task is to respond to the user. If they ask for code changes, provide the full, updated code for ONLY the files that need to change, using the `--- FILE: path/to/file.ext ---` format. "
        "If they ask a question, answer it directly.\n\n"
        "--- CURRENT FILE SYSTEM ---\n"
    )
    for filename, content in files_dict.items():
        context_prompt += f"**`{filename}`**\n```\n{content}\n```\n\n"
    context_prompt += f"--- LATEST TERMINAL OUTPUT ---\n```\n{terminal_content}\n```\n"
    messages = [{"role": "system", "content": context_prompt}, {"role": "user", "content": user_query}]
    try:
        ai_response = get_model_response("Gemini Pro", messages)
        if "--- FILE:" in ai_response:
            for block in ai_response.split("--- FILE:"):
                if block.strip():
                    parts = block.split('\n', 1)
                    filename = parts[0].strip()
                    content = parts[1] if len(parts) > 1 else ""
                    if filename in files_dict:
                        files_dict[filename] = content
            save_files_to_disk(files_dict)
            response_to_user = "I have updated the files as you requested."
        else:
            response_to_user = ai_response
        chat_history.append((None, response_to_user))
    except Exception as e:
        chat_history.append((None, f"Error during refinement: {e}"))
    yield chat_history, "", gr.update(interactive=True)

def deploy_with_ngrok():
    global active_processes
    for p in active_processes.values(): p.kill()
    ngrok.kill()
    yield "Deploying... Starting app and ngrok tunnel.", gr.update(interactive=False)
    main_script = os.path.join(PROJECT_DIR, next((f for f in os.listdir(PROJECT_DIR) if f.endswith('app.py') or f.endswith('main.py')), None))
    if not main_script:
        yield "Error: No 'app.py' or 'main.py' found to run.", gr.update(interactive=True)
        return
    app_process = subprocess.Popen(f"python {os.path.basename(main_script)}", shell=True, cwd=PROJECT_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    active_processes['app'] = app_process
    time.sleep(5)
    port = 5000
    try:
        output = app_process.stdout.read(1024)
        for line in output.split('\n'):
            if "Running on http" in line:
                port = int(line.split(':')[-1].split('/')[0])
                break
    except Exception: pass
    try:
        public_url = ngrok.connect(port).public_url
        yield f"✅ Deployed! Your app is live at: {public_url}", gr.update(interactive=True)
    except Exception as e:
        yield f"❌ Ngrok deployment failed: {e}", gr.update(interactive=True)

# --- UI HELPER FUNCTIONS ---
def update_file_tree_and_editor(files_dict):
    return gr.update(choices=list(files_dict.keys())), gr.update(value="", language=None)
def show_file_content(selected_file, files_dict):
    content = files_dict.get(selected_file, "")
    lang = selected_file.split('.')[-1]
    if lang not in ['py', 'js', 'html', 'css', 'md', 'json', 'sql']: lang = 'text'
    return gr.update(value=content, language=lang)

# --- GRADIO UI ---
with gr.Blocks(theme=gr.themes.Soft(primary_hue="emerald", secondary_hue="green"), title="AI Genesis Engine") as demo:
    files_state = gr.State({})
    chat_history_state = gr.State([])
    gr.Markdown("# 🧬 AI Genesis Engine")
    status_bar = gr.Textbox("Enter API keys to activate the engine.", interactive=False, container=False)
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Accordion("🔑 API Credentials & Controls", open=True):
                # *** FIX APPLIED HERE ***
                hf_token_input = gr.Textbox(label="Hugging Face Token", type="password")
                google_key_input = gr.Textbox(label="Google AI Studio Key", type="password")
                ngrok_token_input = gr.Textbox(label="Ngrok Authtoken (Optional)", type="password")
                validate_btn = gr.Button("Activate Engine")
            with gr.Group(visible=False) as main_controls:
                gr.Markdown("### 🌳 Project Files")
                file_tree = gr.Radio(label="File System", interactive=True)
                download_zip_btn = gr.DownloadButton(label="Download Project .zip", visible=False)
        with gr.Column(scale=5):
             with gr.Group(visible=False) as workspace:
                gr.Markdown("### 📝 Code Editor")
                code_editor = gr.Code(label="Selected File Content", interactive=True, language=None)
        with gr.Column(scale=3):
            with gr.Group(visible=False) as action_panel:
                gr.Markdown("### 💬 Chat & Actions")
                chatbot = gr.Chatbot(label="Refinement Chat", height=400)
                chat_input = gr.Textbox(label="Your Request", placeholder="e.g., A Python Flask API for a to-do list.")
                gr.Markdown("### 🖥️ Live Terminal")
                terminal = gr.Textbox(label="Terminal Output", interactive=False, lines=10)
                with gr.Row():
                    generate_btn = gr.Button("▶️ Build New App", variant="primary")
                    deploy_btn = gr.Button("🚀 Deploy App", variant="secondary", visible=False)

    # --- Event Wiring ---
    def handle_validation(hf_key, google_key, ngrok_key):
        status, success = initialize_clients(hf_key, google_key, ngrok_key)
        if success:
            return {
                status_bar: gr.update(value=status), main_controls: gr.update(visible=True), 
                workspace: gr.update(visible=True), action_panel: gr.update(visible=True),
                validate_btn: gr.update(interactive=False),
                chat_input: gr.update(label="Initial App Description", placeholder="e.g., A Python Flask API for a to-do list...")
            }
        return {status_bar: gr.update(value=status)}
    validate_btn.click(handle_validation, [hf_token_input, google_key_input, ngrok_token_input], [status_bar, main_controls, workspace, action_panel, validate_btn, chat_input])
    generate_btn.click(fn=generate_code_and_plan, inputs=[chat_input], outputs=[status_bar, files_state, chat_history_state, terminal, generate_btn, deploy_btn]).then(fn=update_file_tree_and_editor, inputs=[files_state], outputs=[file_tree, code_editor]).then(lambda: "Describe changes or ask questions.", outputs=[chat_input])
    file_tree.select(show_file_content, [file_tree, files_state], [code_editor])
    chat_input.submit(fn=lambda q, h: (h + [[q, None]], ""), inputs=[chat_input, chat_history_state], outputs=[chatbot, chat_input]).then(fn=chat_and_refine, inputs=[chatbot, files_state, terminal], outputs=[chatbot, status_bar, generate_btn]).then(fn=update_file_tree_and_editor, inputs=[files_state], outputs=[file_tree, code_editor])
    deploy_btn.click(deploy_with_ngrok, [], [status_bar, deploy_btn])

if __name__ == "__main__":
    demo.launch(debug=True, share=False)