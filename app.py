from flask import Flask, render_template, request, jsonify, send_file
import time
import base64
import requests
import os
from runwayml import RunwayML
from uuid import uuid4
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

# Initialize RunwayML client
client = RunwayML(api_key='###')  # Replace with your actual API key

# Directory to store generated files
OUTPUT_DIR = "static/generated"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# HTTP session with retries
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
session.mount('http://', HTTPAdapter(max_retries=retries))
session.mount('https://', HTTPAdapter(max_retries=retries))

# In-memory storage for user-generated scenes
scenes = []

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
            image_path = os.path.join(OUTPUT_DIR, f"image_{uuid4()}.jpg")
            response = session.get(image_url, timeout=30)
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
            video_path = os.path.join(OUTPUT_DIR, f"video_{uuid4()}.mp4")
            response = session.get(video_url, timeout=30)
            if response.status_code == 200:
                with open(video_path, "wb") as f:
                    f.write(response.content)
                return video_path, None
            return None, f"Failed to download video: {response.status_code}"
        return None, f"Video generation failed: {task.error or 'Unknown error'}"
    except Exception as e:
        print(f"Error in generate_video: {str(e)}")
        return None, f"Video generation error: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scenes', methods=['GET'])
def get_scenes():
    return jsonify(scenes)

@app.route('/api/scenes', methods=['POST'])
def add_scene():
    data = request.form
    prompt = data.get('prompt')
    resolution = data.get('resolution', '1080p')
    quality = data.get('quality', 'standard')
    duration = data.get('duration', '3')
    transition = data.get('transition', 'none')
    generation_method = data.get('generation_method', 'text')
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
    
    scene = {
        'id': int(time.time() * 1000),
        'prompt': prompt,
        'thumbnail': f"/{image_path}",
        'duration': duration,
        'resolution': resolution,
        'quality': quality,
        'transition': transition,
        'generation_method': generation_method,
        'video_path': f"/{video_path}"
    }
    scenes.append(scene)
    
    return jsonify(scene)

@app.route('/api/scenes/<int:scene_id>', methods=['PUT'])
def update_scene(scene_id):
    data = request.form
    prompt = data.get('prompt')
    resolution = data.get('resolution', '1080p')
    quality = data.get('quality', 'standard')
    duration = data.get('duration', '3')
    transition = data.get('transition', 'none')
    generation_method = data.get('generation_method', 'text')
    image = request.files.get('image')
    
    try:
        duration = int(duration)
    except ValueError:
        return jsonify({'error': 'Invalid duration format'}), 400
    
    scene = next((s for s in scenes if s['id'] == scene_id), None)
    if not scene:
        return jsonify({'error': 'Scene not found'}), 404
    
    if prompt:
        scene['prompt'] = prompt
        scene['resolution'] = resolution
        scene['quality'] = quality
        scene['duration'] = duration
        scene['transition'] = transition
        scene['generation_method'] = generation_method
        
        # Regenerate thumbnail and video
        image_path, image_error = generate_image(prompt, resolution)
        if image_error:
            return jsonify({'error': image_error}), 500
        
        video_path, video_error = None, None
        if generation_method == 'image' and image:
            image_path = os.path.join(OUTPUT_DIR, f"uploaded_{uuid4()}.jpg")
            image.save(image_path)
            video_path, video_error = generate_video(prompt, image_path, duration, resolution, quality)
        else:
            video_path, video_error = generate_video(prompt, image_path, duration, resolution, quality)
        
        if video_error:
            return jsonify({'error': video_error}), 500
        
        scene['thumbnail'] = f"/{image_path}"
        scene['video_path'] = f"/{video_path}"
    
    return jsonify(scene)

@app.route('/api/scenes/<int:scene_id>', methods=['DELETE'])
def delete_scene(scene_id):
    global scenes
    scenes = [s for s in scenes if s['id'] != scene_id]
    return jsonify({'message': 'Scene deleted'})

@app.route('/api/scenes/reorder', methods=['POST'])
def reorder_scenes():
    new_order = request.json.get('order', [])
    global scenes
    new_scenes = []
    for scene_id in new_order:
        scene = next((s for s in scenes if s['id'] == scene_id), None)
        if scene:
            new_scenes.append(scene)
    scenes = new_scenes
    return jsonify(scenes)

@app.route('/api/generate-video', methods=['POST'])
def generate_final_video():
    video_paths = [s['video_path'] for s in scenes if s['video_path']]
    return jsonify({
        'videos': video_paths,
        'message': 'Video generation queued (simulated)'
    })

@app.route('/download/<path:filename>')
def download(filename):
    file_path = os.path.join(OUTPUT_DIR, os.path.basename(filename))
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
