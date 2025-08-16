# Share-Shield---Ignition-Hacks-25
## Quick start
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env  # add your GEMINI_API_KEY
# macOS/Linux:
export $(grep -v '^#' .env | xargs)

#install " pip install opencv-python pillow requests numpy" for image detection 
For frontend: install 'npm install lucide-react @types/react @types/react-dom' and 'npm install --save-dev @types/react @types/react-dom'