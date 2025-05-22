from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import secrets
import os
import time
import base64
import re
from uuid import uuid4
from functools import wraps
from runwayml import RunwayML

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Increased security with longer key

# Authentication service URL
AUTH_URL = "https://atom-auth-prod.onrender.com"

# Initialize RunwayML client
client = RunwayML(api_key='key_516ff97d1cc691701b86a677a407511d9840c658f3aad8e6c95a64da6c9f5eb77563e46843479e0942b9a9721199fe618ff20560e5a6ef5e183b352bc446b877')  # Replace with your actual API key

# Directory to store generated files
OUTPUT_DIR = "static/generated"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Rename requests session to avoid conflict
http_session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
http_session.mount('http://', HTTPAdapter(max_retries=retries))
http_session.mount('https://', HTTPAdapter(max_retries=retries))

# In-memory storage for user-generated scenes (will be updated to store per user)
user_scenes = {}

# Function to scan the generated directory and populate user scenes
def scan_generated_directory():
    """
    Scans the OUTPUT_DIR directory for generated images and videos and adds them to user_scenes
    if they are not already included. This ensures all generated media files are displayed.
    """
    global user_scenes
    
    # If no users exist yet, create a default user
    if not user_scenes:
        user_scenes['default_user'] = []
    
    # Get the first user (or default user if no registered users)
    first_user = next(iter(user_scenes.keys()))
    
    # Get list of files in the OUTPUT_DIR
    files = os.listdir(OUTPUT_DIR)
    
    # Filter for image and video files
    image_files = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')) and f.startswith('image_')]
    video_files = [f for f in files if f.lower().endswith(('.mp4', '.mov', '.webm')) and f.startswith('video_')]
    
    # Extract existing media paths for the user
    existing_paths = set()
    for scene in user_scenes.get(first_user, []):
        for path_key in ['image_path', 'thumbnail', 'video_path']:
            if path_key in scene and scene[path_key]:
                path = scene[path_key].replace('/', '', 1) if scene[path_key].startswith('/') else scene[path_key]
                existing_paths.add(path)
    
    # UPDATED: Add new image files to user_scenes with improved filename extraction
    for image_file in image_files:
        image_path = os.path.join(OUTPUT_DIR, image_file)
        
        # Check if this image is already in user scenes
        if image_path not in existing_paths and f"/{image_path}" not in existing_paths:
            # Try to extract prompt from filename with improved regex
            prompt = ""
            print(f"Processing image file: {image_file}")  # Debug log
            
            # Clean the filename first - remove any path components
            clean_filename = os.path.basename(image_file)
            
            # Match pattern: image_prompt_text_12345678.jpg
            match = re.search(r'image_(.+?)_[a-f0-9]{8}\.(jpg|jpeg|png|gif)$', clean_filename, re.IGNORECASE)
            if match:
                prompt_part = match.group(1)
                # Replace underscores with spaces and capitalize
                prompt = prompt_part.replace('_', ' ').title()
                print(f"  Extracted prompt from pattern 1: {prompt}")
            else:
                # Fallback: try to get everything between image_ and the extension, then remove UUID
                fallback_match = re.search(r'image_(.+)\.(jpg|jpeg|png|gif)$', clean_filename, re.IGNORECASE)
                if fallback_match:
                    prompt_part = fallback_match.group(1)
                    # Remove potential UUID at the end
                    prompt_part = re.sub(r'_[a-f0-9]{8}$', '', prompt_part)
                    prompt = prompt_part.replace('_', ' ').title()
                    print(f"  Extracted prompt from pattern 2: {prompt}")
                else:
                    # Last resort: try to extract anything meaningful from the filename
                    no_prefix = clean_filename.replace('image_', '', 1)
                    no_extension = re.sub(r'\.(jpg|jpeg|png|gif)$', '', no_prefix, flags=re.IGNORECASE)
                    no_uuid = re.sub(r'_[a-f0-9]{8}$', '', no_extension)
                    if no_uuid and len(no_uuid.strip()) > 0:
                        prompt = no_uuid.replace('_', ' ').title()
                        print(f"  Extracted prompt from last resort: {prompt}")
                    else:
                        prompt = "Generated Image"
                        print(f"  Using default prompt: {prompt}")
                
            # Create a new scene for this image
            scene = {
                'id': int(time.time() * 1000) + len(user_scenes.get(first_user, [])),
                'prompt': prompt,
                'thumbnail': f"/{image_path}",
                'image_path': f"/{image_path}",
                'resolution': '1080p',
                'type': 'image'
            }
            
            print(f"  Created image scene with prompt: '{prompt}'")  # Debug log
            
            # Add the scene to the user's scenes
            if first_user not in user_scenes:
                user_scenes[first_user] = []
            
            user_scenes[first_user].append(scene)
    
    # UPDATED: Add new video files to user_scenes with improved filename extraction
    for video_file in video_files:
        video_path = os.path.join(OUTPUT_DIR, video_file)
        
        # Check if this video is already in user scenes
        if video_path not in existing_paths and f"/{video_path}" not in existing_paths:
            # Try to extract prompt from filename with improved regex
            prompt = ""
            print(f"Processing video file: {video_file}")  # Debug log
            
            # Clean the filename first - remove any path components
            clean_filename = os.path.basename(video_file)
            
            # Match pattern: video_prompt_text_12345678.mp4
            match = re.search(r'video_(.+?)_[a-f0-9]{8}\.(mp4|webm|mov|avi)$', clean_filename, re.IGNORECASE)
            if match:
                prompt_part = match.group(1)
                # Replace underscores with spaces and capitalize
                prompt = prompt_part.replace('_', ' ').title()
                print(f"  Extracted prompt from pattern 1: {prompt}")
            else:
                # Fallback: try to get everything between video_ and the extension, then remove UUID
                fallback_match = re.search(r'video_(.+)\.(mp4|webm|mov|avi)$', clean_filename, re.IGNORECASE)
                if fallback_match:
                    prompt_part = fallback_match.group(1)
                    # Remove potential UUID at the end
                    prompt_part = re.sub(r'_[a-f0-9]{8}$', '', prompt_part)
                    prompt = prompt_part.replace('_', ' ').title()
                    print(f"  Extracted prompt from pattern 2: {prompt}")
                else:
                    # Last resort: try to extract anything meaningful from the filename
                    no_prefix = clean_filename.replace('video_', '', 1)
                    no_extension = re.sub(r'\.(mp4|webm|mov|avi)$', '', no_prefix, flags=re.IGNORECASE)
                    no_uuid = re.sub(r'_[a-f0-9]{8}$', '', no_extension)
                    if no_uuid and len(no_uuid.strip()) > 0:
                        prompt = no_uuid.replace('_', ' ').title()
                        print(f"  Extracted prompt from last resort: {prompt}")
                    else:
                        prompt = "Generated Video"
                        print(f"  Using default prompt: {prompt}")
            
            # Look for a matching thumbnail (image file with similar name)
            thumbnail_path = None
            potential_thumbnail = video_file.replace('video_', 'image_', 1)
            
            if potential_thumbnail in image_files:
                thumbnail_path = os.path.join(OUTPUT_DIR, potential_thumbnail)
                print(f"  Found matching thumbnail: {potential_thumbnail}")
            else:
                # If no exact match, try to find a similar image file
                base_name_parts = clean_filename.split('_')[1:-1]  # Get the middle parts of the filename
                if base_name_parts:
                    base_pattern = '_'.join(base_name_parts)
                    matching_images = [img for img in image_files if base_pattern in img]
                    if matching_images:
                        thumbnail_path = os.path.join(OUTPUT_DIR, matching_images[0])
                        print(f"  Found similar thumbnail: {matching_images[0]}")
                    else:
                        print(f"  No thumbnail found for: {video_file}")
                else:
                    print(f"  Could not extract base pattern from: {video_file}")
            
            # Create a new scene for this video
            scene = {
                'id': int(time.time() * 1000) + len(user_scenes.get(first_user, [])) + 1000,  # Add offset to avoid ID collisions
                'prompt': prompt,  # This will now contain the formatted filename
                'thumbnail': f"/{thumbnail_path}" if thumbnail_path else None,
                'video_path': f"/{video_path}",
                'resolution': '1080p',
                'duration': 3,  # Default duration
                'quality': 'standard',  # Default quality
                'transition': 'none'  # Default transition
            }
            
            print(f"  Created video scene with prompt: '{prompt}'")  # Debug log
            
            # Add the scene to the user's scenes
            if first_user not in user_scenes:
                user_scenes[first_user] = []
            
            user_scenes[first_user].append(scene)
            
    return user_scenes

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_token' not in session or 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def format_prompt_for_filename(prompt, max_words=10):
    """
    Format a prompt to be used in a filename.
    Takes up to max_words words from the prompt and removes special characters.
    """
    # Remove special characters and replace spaces with underscores
    import re
    
    # First ensure we have a string
    if not prompt or not isinstance(prompt, str):
        return "unnamed"
        
    # Remove special characters that are problematic for filenames
    clean_text = re.sub(r'[^\w\s-]', '', prompt).lower().strip()
    
    # Split into words and take up to max_words
    words = clean_text.split()[:max_words]
    
    # Join with underscores
    filename_text = '_'.join(words)
    
    # Ensure the filename isn't too long and is valid
    if len(filename_text) > 100:
        filename_text = filename_text[:100]
    
    # Return at least something if the prompt was empty or only had special chars
    if not filename_text:
        return "unnamed"
        
    return filename_text


def generate_image(prompt, resolution='1920:1080'):
    try:
        ratio = {
            '1080p': '1920:1080',
            'square': '1080:1080',
            'vertical': '1080:1920',
            'custom': '1920:1080'
        }.get(resolution, '1920:1080')
        
        task = client.text_to_image.create(
            model='gen4_image',
            ratio=ratio,
            prompt_text=prompt,
        )
        task_id = task.id
        print(f"Image task created: {task_id}")
        time.sleep(1)
        task = client.tasks.retrieve(task_id)
        while task.status not in ['SUCCEEDED', 'FAILED']:
            time.sleep(1)
            task = client.tasks.retrieve(task_id)
            print(f"Image task status: {task.status}")
        
        if task.status == 'SUCCEEDED':
            image_url = task.output[0]
            print(f"Image URL: {image_url}")
            
            # Create a prompt-based filename using our helper function
            prompt_part = format_prompt_for_filename(prompt, max_words=10)
            
            # Add unique ID to prevent conflicts
            image_filename = f"image_{prompt_part}_{uuid4().hex[:8]}.jpg"
            image_path = os.path.join(OUTPUT_DIR, image_filename)
            
            response = http_session.get(image_url, timeout=30)
            if response.status_code == 200:
                with open(image_path, "wb") as f:
                    f.write(response.content)
                return image_path, None
            return None, f"Failed to download image: {response.status_code}"
        return None, f"Image generation failed: {task.error or 'Unknown error'}"
    except Exception as e:
        print(f"Error in generate_image: {str(e)}")
        return None, f"Image generation error: {str(e)}"

def generate_video(prompt, image_path=None, duration=5, resolution='1280:720', quality='standard'):
    try:
        ratio = {
            '1080p': '1280:720',
            'square': '720:720',
            'vertical': '720:1280',
            'custom': '1280:720'
        }.get(resolution, '1280:720')
        
        model = 'gen4_turbo' if quality == 'standard' else 'gen4_pro'
        task_params = {
            'model': model,
            'prompt_text': prompt,
            'ratio': ratio,
            'duration': 10  
        }
        
        if image_path:
            with open(image_path, "rb") as img_file:
                base64_str = base64.b64encode(img_file.read()).decode('utf-8')
                task_params['prompt_image'] = f"data:image/jpeg;base64,{base64_str}"
        
        task = client.image_to_video.create(**task_params) if image_path else client.text_to_video.create(**task_params)
        task_id = task.id
        print(f"Video task created: {task_id}")
        time.sleep(10)
        task = client.tasks.retrieve(task_id)
        while task.status not in ['SUCCEEDED', 'FAILED']:
            time.sleep(10)
            task = client.tasks.retrieve(task_id)
            print(f"Video task status: {task.status}")
        
        if task.status == 'SUCCEEDED':
            video_url = task.output[0]
            print(f"Video URL: {video_url}")
            
            # Create a prompt-based filename using our helper function
            prompt_part = format_prompt_for_filename(prompt, max_words=10)
            
            # Add unique ID to prevent conflicts
            video_filename = f"video_{prompt_part}_{uuid4().hex[:8]}.mp4"
            video_path = os.path.join(OUTPUT_DIR, video_filename)
            
            response = http_session.get(video_url, timeout=30)
            if response.status_code == 200:
                with open(video_path, "wb") as f:
                    f.write(response.content)
                return video_path, None
            return None, f"Failed to download video: {response.status_code}"
        return None, f"Video generation failed: {task.error or 'Unknown error'}"
    except Exception as e:
        print(f"Error in generate_video: {str(e)}")
        return None, f"Video generation error: {str(e)}"

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            return render_template('login.html', error='Email and password are required')
        
        # Call authentication service
        response = requests.post(f"{AUTH_URL}/login", json={
            "email": email,
            "password": password
        })
        
        if response.status_code == 200:
            data = response.json()
            if data.get('authenticated'):
                # Store user info in session
                session['user_email'] = email
                session['user_token'] = data.get('token')
                
                # Initialize user's scenes if not exists
                if email not in user_scenes:
                    user_scenes[email] = []
                    
                # Scan for images and add them to the user's scenes
                scan_generated_directory()
                
                return redirect(url_for('index'))
            
        return render_template('login.html', error='Invalid email or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not email or not password:
            return render_template('register.html', error='Email and password are required')
        
        if password != confirm_password:
            return render_template('register.html', error='Passwords do not match')
        
        # Call authentication service
        response = requests.post(f"{AUTH_URL}/register", json={
            "email": email,
            "password": password
        })
        
        data = response.json()
        if response.status_code == 201 and data.get('authenticated'):
            # Store user info in session
            session['user_email'] = email
            session['user_token'] = data.get('token')
            
            # Initialize user's scenes
            user_scenes[email] = []
            
            # Scan for images and add them to the user's scenes
            scan_generated_directory()
            
            return redirect(url_for('index'))
        else:
            error_message = data.get('message', 'Registration failed')
            return render_template('register.html', error=error_message)
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    # Clear user session
    session.pop('user_email', None)
    session.pop('user_token', None)
    return redirect(url_for('login'))

# Application Routes
@app.route('/')
@login_required
def index():
    # Scan the generated directory before rendering the page
    scan_generated_directory()
    return render_template('index.html', user_email=session.get('user_email'))

@app.route('/video')
@login_required
def video():
    # Scan the generated directory before rendering the page
    scan_generated_directory()
    return render_template('video_gen.html', user_email=session.get('user_email'))

@app.route('/image')
@login_required
def image():
    # Scan the generated directory before rendering the page
    scan_generated_directory()
    return render_template('image_gen.html', user_email=session.get('user_email'))

# API Routes
@app.route('/api/scenes', methods=['GET'])
@login_required
def get_scenes():
    """Get all scenes for the current user."""
    # First scan the generated directory to ensure we have all media files
    scan_generated_directory()
    
    user_email = session.get('user_email')
    scenes = user_scenes.get(user_email, [])
    
    # If there are no scenes for the user but scenes exist for default_user
    # Copy the default_user scenes to the current user
    if not scenes and 'default_user' in user_scenes and user_scenes['default_user']:
        user_scenes[user_email] = user_scenes['default_user'].copy()
        scenes = user_scenes[user_email]
        
    # If requesting video scenes only
    if request.args.get('type') == 'video':
        scenes = [s for s in scenes if s.get('video_path') and s.get('type') != 'image']
    # If requesting image scenes only
    elif request.args.get('type') == 'image':
        scenes = [s for s in scenes if s.get('image_path') or s.get('type') == 'image']
    
    # Ensure all file paths are properly formatted
    for scene in scenes:
        if 'thumbnail' in scene and scene['thumbnail'] and not scene['thumbnail'].startswith('/'):
            scene['thumbnail'] = f"/{scene['thumbnail']}"
        if 'image_path' in scene and scene['image_path'] and not scene['image_path'].startswith('/'):
            scene['image_path'] = f"/{scene['image_path']}"
        if 'video_path' in scene and scene['video_path'] and not scene['video_path'].startswith('/'):
            scene['video_path'] = f"/{scene['video_path']}"
    
    return jsonify(scenes)

@app.route('/static/generated/<path:filename>')
def serve_generated_file(filename):
    """Serve a file from the generated directory."""
    return send_file(os.path.join(OUTPUT_DIR, filename))

@app.route('/api/scenes', methods=['POST'])
@login_required
def add_scene():
    user_email = session.get('user_email')
    data = request.form
    prompt = data.get('prompt')
    resolution = data.get('resolution', '1080p')
    quality = data.get('quality', 'standard')
    duration = data.get('duration', '3')
    transition = data.get('transition', 'none')
    generation_method = data.get('generation_method', 'text')
    scene_type = data.get('type', 'video')  # Default to video if not specified
    image = request.files.get('image')
    
    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400
    
    try:
        duration = int(duration)
    except ValueError:
        return jsonify({'error': 'Invalid duration format'}), 400
    
    # Generate thumbnail (image)
    image_path, image_error = generate_image(prompt, resolution)
    if image_error:
        return jsonify({'error': image_error}), 500
    
    # Create the scene object
    scene = {
        'id': int(time.time() * 1000),
        'prompt': prompt,
        'thumbnail': f"/{image_path}",
        'image_path': f"/{image_path}",
        'resolution': resolution
    }
    
    # If this is an image-only scene, we're done
    if scene_type == 'image':
        scene['type'] = 'image'
    else:
        # Generate video
        video_path, video_error = None, None
        if generation_method == 'image' and image:
            image_path = os.path.join(OUTPUT_DIR, f"uploaded_{uuid4()}.jpg")
            image.save(image_path)
            video_path, video_error = generate_video(prompt, image_path, duration, resolution, quality)
        else:
            video_path, video_error = generate_video(prompt, image_path, duration, resolution, quality)
        
        if video_error:
            return jsonify({'error': video_error}), 500
        
        # Add video-specific fields
        scene['duration'] = duration
        scene['quality'] = quality
        scene['transition'] = transition
        scene['generation_method'] = generation_method
        scene['video_path'] = f"/{video_path}"
    
    if user_email not in user_scenes:
        user_scenes[user_email] = []
    
    user_scenes[user_email].append(scene)
    
    return jsonify(scene)

@app.route('/api/scenes/<int:scene_id>', methods=['PUT'])
@login_required
def update_scene(scene_id):
    user_email = session.get('user_email')
    data = request.form
    prompt = data.get('prompt')
    resolution = data.get('resolution', '1080p')
    quality = data.get('quality', 'standard')
    duration = data.get('duration', '3')
    transition = data.get('transition', 'none')
    generation_method = data.get('generation_method', 'text')
    scene_type = data.get('type', None)  # Check if type is specified
    image = request.files.get('image')
    
    try:
        if duration:
            duration = int(duration)
    except ValueError:
        return jsonify({'error': 'Invalid duration format'}), 400
    
    user_scene_list = user_scenes.get(user_email, [])
    scene = next((s for s in user_scene_list if s['id'] == scene_id), None)
    if not scene:
        return jsonify({'error': 'Scene not found'}), 404
    
    if prompt:
        scene['prompt'] = prompt
        scene['resolution'] = resolution
        
        # Regenerate thumbnail and content based on type
        image_path, image_error = generate_image(prompt, resolution)
        if image_error:
            return jsonify({'error': image_error}), 500
        
        scene['thumbnail'] = f"/{image_path}"
        
        # If it's an image type or specified to be an image
        if scene.get('type') == 'image' or scene_type == 'image':
            scene['type'] = 'image'
            scene['image_path'] = f"/{image_path}"
        else:
            # It's a video scene
            scene['quality'] = quality
            scene['duration'] = duration
            scene['transition'] = transition
            scene['generation_method'] = generation_method
            
            video_path, video_error = None, None
            if generation_method == 'image' and image:
                image_path = os.path.join(OUTPUT_DIR, f"uploaded_{uuid4()}.jpg")
                image.save(image_path)
                video_path, video_error = generate_video(prompt, image_path, duration, resolution, quality)
            else:
                video_path, video_error = generate_video(prompt, image_path, duration, resolution, quality)
            
            if video_error:
                return jsonify({'error': video_error}), 500
            
            scene['video_path'] = f"/{video_path}"
    
    return jsonify(scene)

@app.route('/api/scenes/<int:scene_id>', methods=['DELETE'])
@login_required
def delete_scene(scene_id):
    user_email = session.get('user_email')
    if user_email in user_scenes:
        user_scenes[user_email] = [s for s in user_scenes[user_email] if s['id'] != scene_id]
    return jsonify({'message': 'Scene deleted'})

@app.route('/api/scenes/reorder', methods=['POST'])
@login_required
def reorder_scenes():
    user_email = session.get('user_email')
    new_order = request.json.get('order', [])
    
    if user_email not in user_scenes:
        return jsonify([])
    
    user_scene_list = user_scenes[user_email]
    new_scenes = []
    for scene_id in new_order:
        scene = next((s for s in user_scene_list if s['id'] == scene_id), None)
        if scene:
            new_scenes.append(scene)
    
    user_scenes[user_email] = new_scenes
    return jsonify(new_scenes)

@app.route('/api/generate-video', methods=['POST'])
@login_required
def generate_final_video():
    user_email = session.get('user_email')
    video_paths = [s['video_path'] for s in user_scenes.get(user_email, []) if s.get('video_path')]
    return jsonify({
        'videos': video_paths,
        'message': 'Video generation queued (simulated)'
    })

@app.route('/api/generate-image-scene', methods=['POST'])
@login_required
def generate_image_scene():
    user_email = session.get('user_email')
    data = request.form
    prompt = data.get('prompt')
    resolution = data.get('resolution', '1080p')
    
    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400
    
    # Generate image
    image_path, image_error = generate_image(prompt, resolution)
    if image_error:
        return jsonify({'error': image_error}), 500
    
    # Create scene with image only (no video)
    scene = {
        'id': int(time.time() * 1000),
        'prompt': prompt,
        'thumbnail': f"/{image_path}",
        'image_path': f"/{image_path}",
        'resolution': resolution,
        'type': 'image'  # Add a type to distinguish from video scenes
    }
    
    if user_email not in user_scenes:
        user_scenes[user_email] = []
    
    user_scenes[user_email].append(scene)
    
    return jsonify(scene)

@app.route('/api/regenerate-image/<int:scene_id>', methods=['POST'])
@login_required
def regenerate_image(scene_id):
    user_email = session.get('user_email')
    data = request.form
    prompt = data.get('prompt')
    resolution = data.get('resolution', '1080p')
    
    user_scene_list = user_scenes.get(user_email, [])
    scene = next((s for s in user_scene_list if s['id'] == scene_id), None)
    if not scene:
        return jsonify({'error': 'Scene not found'}), 404
    
    # Generate new image
    image_path, image_error = generate_image(prompt, resolution)
    if image_error:
        return jsonify({'error': image_error}), 500
    
    # Update scene with new image
    scene['thumbnail'] = f"/{image_path}"
    scene['image_path'] = f"/{image_path}"
    
    return jsonify(scene)

@app.route('/api/export-images', methods=['GET'])
@login_required
def export_images():
    user_email = session.get('user_email')
    image_paths = []
    
    # First get images from user's scenes
    user_image_paths = [s['image_path'] for s in user_scenes.get(user_email, []) if s.get('image_path')]
    image_paths.extend(user_image_paths)
    
    # Also scan the directory to make sure we get all images
    files = os.listdir(OUTPUT_DIR)
    for file in files:
        if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')) and file.startswith('image_'):
            file_path = f"/static/generated/{file}"
            if file_path not in image_paths and f"/{OUTPUT_DIR}/{file}" not in image_paths:
                image_paths.append(file_path)
    
    return jsonify({
        'images': image_paths,
        'message': 'Images ready for export'
    })

@app.route('/api/export-videos', methods=['GET'])
@login_required
def export_videos():
    user_email = session.get('user_email')
    video_paths = []
    
    # First get videos from user's scenes
    user_video_paths = [s['video_path'] for s in user_scenes.get(user_email, []) if s.get('video_path')]
    video_paths.extend(user_video_paths)
    
    # Also scan the directory to make sure we get all videos
    files = os.listdir(OUTPUT_DIR)
    for file in files:
        if file.lower().endswith(('.mp4', '.mov', '.webm')) and file.startswith('video_'):
            file_path = f"/static/generated/{file}"
            if file_path not in video_paths and f"/{OUTPUT_DIR}/{file}" not in video_paths:
                video_paths.append(file_path)
    
    return jsonify({
        'videos': video_paths,
        'message': 'Videos ready for export'
    })

@app.route('/download/<path:filename>')
@login_required
def download(filename):
    """Download a file from the generated directory."""
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        # If file doesn't exist with the provided path, try stripping any parent directories
        file_path = os.path.join(OUTPUT_DIR, os.path.basename(filename))
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    # Use the original filename with prompt for the download
    # This ensures users get the descriptive filename when they save the file
    download_name = os.path.basename(file_path)
        
    return send_file(file_path, as_attachment=True, download_name=download_name)

# API endpoint to check authentication status
@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    if 'user_email' in session and 'user_token' in session:
        return jsonify({
            'authenticated': True,
            'email': session['user_email']
        })
    return jsonify({
        'authenticated': False
    })

# Initialize the application by scanning the generated directory
scan_generated_directory()

if __name__ == '__main__':
    app.run(debug=True)