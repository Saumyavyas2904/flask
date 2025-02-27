from flask import Flask, request, send_file, send_from_directory, render_template_string
import os
import shutil
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":    
        if "file" not in request.files:
            return "No file part"

        file = request.files["file"]
        if file.filename == "":
            return "No selected file"

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)
            return render_template_string(HTML_TEMPLATE, image_url=f"/static/uploads/{filename}")

    return render_template_string(HTML_TEMPLATE, image_url="")

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/viewer/<path:filepath>')
def viewer(filepath):
    """ Serve an image from any directory """
    return send_file(filepath, mimetype='image/jpeg')

@app.route('/process_stitched_image', methods=["POST"])
def process_stitched_image():
    """ API endpoint to process and move stitched image """
    if "filepath" not in request.json:
        return {"error": "Filepath is required"}, 400

    input_path = request.json["filepath"]
    if not os.path.exists(input_path):
        return {"error": "File does not exist"}, 404

    # Move image to static/uploads
    output_filename = "stitched_latest.jpg"
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
    shutil.copy(input_path, output_path)

    return {"message": "Image processed successfully", "url": f"/static/uploads/{output_filename}"}

HTML_TEMPLATE = """
<!DOCTYPE html> 
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>360° Scrollable Panorama</title>
    <style>
        body { margin: 0; overflow: hidden; }
        canvas { display: block; }
        .upload-form { position: absolute; z-index: 10; padding: 10px; background: rgba(0,0,0,0.5); }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>
    {% if not image_url %}
    <form action="/" method="post" enctype="multipart/form-data" class="upload-form">
        <input type="file" name="file">
        <button type="submit">Upload</button>
    </form>
    {% endif %}

    <script>
        let scene, camera, renderer, sphere;
        let moveSpeed = 0.5;  
        let zoomSpeed = 1.0;  
        let rotationSpeed = 0.005;  
        let velocity = new THREE.Vector3(0, 0, 0);
        let forwardAcceleration = 0.08;  
        let backwardAcceleration = 0.05;  
        let maxSpeed = 2.0;  
        let friction = 0.85;  
        let keys = {};
        let isMovingForward = false;
        let stepCounter = 0;  

        function init() {
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0xFFFFFF);  // White background

            camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            camera.position.set(0, 0, 0);

            renderer = new THREE.WebGLRenderer();
            renderer.setSize(window.innerWidth, window.innerHeight);
            document.body.appendChild(renderer.domElement);

            const textureLoader = new THREE.TextureLoader();
            textureLoader.load("{{ image_url }}", function(texture) {
                texture.wrapS = THREE.RepeatWrapping;
                texture.repeat.x = -1;

                const geometry = new THREE.SphereGeometry(500, 60, 40);
                const material = new THREE.MeshBasicMaterial({ map: texture, side: THREE.BackSide });
                sphere = new THREE.Mesh(geometry, material);
                scene.add(sphere);

                animate();
            });

            window.addEventListener('keydown', (event) => {
                keys[event.key.toLowerCase()] = true;
                if (event.key.toLowerCase() === "w") isMovingForward = true;
            });

            window.addEventListener('keyup', (event) => {
                keys[event.key.toLowerCase()] = false;
                if (event.key.toLowerCase() === "w") isMovingForward = false;
            });

            let isDragging = false;
            let previousMouseX = 0, previousMouseY = 0;

            window.addEventListener('mousedown', (event) => {
                isDragging = true;
                previousMouseX = event.clientX;
                previousMouseY = event.clientY;
            });

            window.addEventListener('mouseup', () => { isDragging = false; });

            window.addEventListener('mousemove', (event) => {
                if (isDragging) {
                    let deltaX = event.clientX - previousMouseX;
                    let deltaY = event.clientY - previousMouseY;

                    sphere.rotation.y += deltaX * 0.008; 
                    sphere.rotation.x += deltaY * 0.008;

                    previousMouseX = event.clientX;
                    previousMouseY = event.clientY;
                }
            });

            window.addEventListener('resize', () => {
                camera.aspect = window.innerWidth / window.innerHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(window.innerWidth, window.innerHeight);
            });
        }

        function updateMovement() {
            let direction = new THREE.Vector3();
            camera.getWorldDirection(direction);

            let right = new THREE.Vector3();
            right.crossVectors(camera.up, direction).normalize();

            if (keys['w']) {
                velocity.addScaledVector(direction, forwardAcceleration); 
                stepCounter += 0.05;
                camera.position.y += Math.sin(stepCounter) * 0.02;  
            }
            if (keys['s']) {
                velocity.addScaledVector(direction, -backwardAcceleration); 
            }

            if (keys['a'] || keys['arrowleft']) {
                sphere.rotation.y += rotationSpeed;
            }
            if (keys['d'] || keys['arrowright']) {
                sphere.rotation.y -= rotationSpeed;
            }

            if (keys['arrowup']) camera.position.y += moveSpeed; 
            if (keys['arrowdown']) camera.position.y -= moveSpeed; 

            if (keys['q']) camera.fov = Math.min(camera.fov + zoomSpeed, 90); 
            if (keys['e']) camera.fov = Math.max(camera.fov - zoomSpeed, 30); 

            camera.updateProjectionMatrix();

            velocity.clampLength(0, maxSpeed);
            camera.position.add(velocity);
            velocity.multiplyScalar(friction);  

            if (!isMovingForward && velocity.length() > 0.01) {
                velocity.multiplyScalar(0.95);
            }
        }

        function animate() {
            requestAnimationFrame(animate);
            updateMovement();
            renderer.render(scene, camera);        
        }

        init();
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True)
