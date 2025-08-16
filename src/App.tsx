
import React, { useState, useRef, useCallback, useEffect } from 'react';
import { Upload, Monitor, Download, Eye, EyeOff, Shield, AlertTriangle, CheckCircle } from 'lucide-react';

interface Finding {
  id: string;
  label: string;
  confidence: number;
  bbox: [number, number, number, number]; // [x, y, width, height]
  risk: 'high' | 'medium' | 'low';
}

interface AppState {
  mode: 'idle' | 'upload' | 'live';
  findings: Finding[];
  toggles: {
    master: boolean;
    categories: Record<string, boolean>;
  };
  isScanning: boolean;
  isStreaming: boolean;
}

const MOCK_CATEGORIES = [
  { name: 'email', label: 'Email Addresses', risk: 'high' },
  { name: 'phone', label: 'Phone Numbers', risk: 'high' },
  { name: 'address', label: 'Addresses', risk: 'medium' },
  { name: 'ssn', label: 'SSN/Tax ID', risk: 'high' },
  { name: 'credit_card', label: 'Credit Cards', risk: 'high' },
  { name: 'username', label: 'Usernames', risk: 'high' },
  { name: 'password', label: 'Passwords', risk: 'high' },
  { name: 'date', label: 'Dates', risk: 'low' },
  { name: 'sensitive_data', label: 'Sensitive Data', risk: 'high' },
  { name: 'api_key', label: 'API Keys', risk: 'high' },
  { name: 'token', label: 'Tokens', risk: 'high' },
];

// API Configuration
const API_BASE_URL = 'http://localhost:5000/api';

// API functions
const scanImage = async (imageData: string): Promise<Finding[]> => {
  const response = await fetch(`${API_BASE_URL}/scan-image`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ image: imageData }),
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`);
  }

  const data = await response.json();
  return data.findings || [];
};

const scanFrameData = async (frameData: string): Promise<Finding[]> => {
  const response = await fetch(`${API_BASE_URL}/scan-frame`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ frameData }),
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`);
  }

  const data = await response.json();
  return data.findings || [];
};

const redactImage = async (imageData: string, method: 'blackout' | 'blur' = 'blackout'): Promise<string> => {
  const response = await fetch(`${API_BASE_URL}/redact-image`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ image: imageData, method }),
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`);
  }

  const data = await response.json();
  return data.redactedImage;
};

function App() {
  const [state, setState] = useState<AppState>({
    mode: 'idle',
    findings: [],
    toggles: {
      master: true,
      categories: Object.fromEntries(MOCK_CATEGORIES.map(cat => [cat.name, true])),
    },
    isScanning: false,
    isStreaming: false,
  });

  const [apiError, setApiError] = useState<string | null>(null);
  const [originalImageData, setOriginalImageData] = useState<string | null>(null);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const scanIntervalRef = useRef<number | null>(null);

  const updateState = (updates: Partial<AppState>) => {
    setState(prev => ({ ...prev, ...updates }));
  };

  const handleFileUpload = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setApiError(null);
    updateState({ mode: 'upload', isScanning: true });

    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const img = new Image();
    img.onload = async () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);

      // Convert canvas to base64 for API
      const imageData = canvas.toDataURL('image/png');
      setOriginalImageData(imageData);

      try {
        const findings = await scanImage(imageData);
        updateState({ findings, isScanning: false });
        renderOverlay();
      } catch (error) {
        console.error('Scan failed:', error);
        setApiError(error instanceof Error ? error.message : 'Scan failed');
        updateState({ isScanning: false });
      }
    };

    img.src = URL.createObjectURL(file);
  }, []);

  const startScreenShare = useCallback(async () => {
    try {
      setApiError(null);
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { width: 1920, height: 1080 }
      });

      streamRef.current = stream;
      updateState({ mode: 'live', isStreaming: true });

      const video = videoRef.current;
      if (!video) return;

      video.srcObject = stream;
      video.play();

      const scanFrame = async () => {
        const canvas = canvasRef.current;
        if (!canvas || !video) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        canvas.width = video.videoWidth || 1920;
        canvas.height = video.videoHeight || 1080;
        ctx.drawImage(video, 0, 0);

        const frameData = canvas.toDataURL('image/png');
        setOriginalImageData(frameData);
        
        try {
          const findings = await scanFrameData(frameData);
          setState(prev => ({ ...prev, findings }));
          renderOverlay();
        } catch (error) {
          console.error('Frame scan failed:', error);
          setApiError(error instanceof Error ? error.message : 'Frame scan failed');
        }
      };

      video.onloadedmetadata = () => {
        // Start scanning frames every 2 seconds
        scanIntervalRef.current = window.setInterval(scanFrame, 2000);
      };

      stream.getVideoTracks()[0].onended = () => {
        stopScreenShare();
      };

    } catch (error) {
      console.error('Screen share failed:', error);
      setApiError(error instanceof Error ? error.message : 'Screen share failed');
      updateState({ mode: 'idle', isStreaming: false });
    }
  }, []);

  const stopScreenShare = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    if (scanIntervalRef.current) {
      window.clearInterval(scanIntervalRef.current);
      scanIntervalRef.current = null;
    }

    updateState({ mode: 'idle', isStreaming: false, findings: [] });
    setOriginalImageData(null);

    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext('2d');
      ctx?.clearRect(0, 0, canvas.width, canvas.height);
    }
  }, []);

  const renderOverlay = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear existing overlays and redraw base image
    if (state.mode === 'upload' && originalImageData) {
      const img = new Image();
      img.onload = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);
        drawRedactionOverlays(ctx);
      };
      img.src = originalImageData;
    } else if (state.mode === 'live') {
      drawRedactionOverlays(ctx);
    }
  }, [state.findings, state.toggles, originalImageData, state.mode]);

  const drawRedactionOverlays = (ctx: CanvasRenderingContext2D) => {
    if (!state.toggles.master) return;

    state.findings.forEach(finding => {
      if (!state.toggles.categories[finding.label]) return;

      const [x, y, width, height] = finding.bbox;
      
      // Draw black redaction box
      ctx.fillStyle = 'rgba(0, 0, 0, 0.9)';
      ctx.fillRect(x, y, width, height);
      
      // Add subtle border
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 2;
      ctx.strokeRect(x, y, width, height);
    });
  };

  const toggleCategory = (category: string) => {
    setState(prev => ({
      ...prev,
      toggles: {
        ...prev.toggles,
        categories: {
          ...prev.toggles.categories,
          [category]: !prev.toggles.categories[category],
        },
      },
    }));
  };

  const toggleMaster = () => {
    setState(prev => ({
      ...prev,
      toggles: {
        ...prev.toggles,
        master: !prev.toggles.master,
      },
    }));
  };

  const exportRedacted = async () => {
    if (!originalImageData) return;

    try {
      // Get redacted image from backend
      const redactedImageData = await redactImage(originalImageData, 'blackout');
      
      // Create download link
      const link = document.createElement('a');
      link.download = 'redacted-content.png';
      link.href = redactedImageData;
      link.click();
    } catch (error) {
      console.error('Export failed:', error);
      setApiError(error instanceof Error ? error.message : 'Export failed');
    }
  };

  useEffect(() => {
    renderOverlay();
  }, [renderOverlay]);

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'high': return 'text-red-400';
      case 'medium': return 'text-yellow-400';
      case 'low': return 'text-green-400';
      default: return 'text-gray-400';
    }
  };

  const getRiskIcon = (risk: string) => {
    switch (risk) {
      case 'high': return <AlertTriangle className="w-4 h-4" />;
      case 'medium': return <Shield className="w-4 h-4" />;
      case 'low': return <CheckCircle className="w-4 h-4" />;
      default: return <Shield className="w-4 h-4" />;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 text-white">
      <div className="container mx-auto px-6 py-8">
        <header className="text-center mb-12">
          <div className="flex items-center justify-center gap-3 mb-4">
            <Shield className="w-10 h-10 text-blue-400" />
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
              Cypher
            </h1>
          </div>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto">
            Advanced privacy protection with real-time redaction for sensitive information
          </p>
          {apiError && (
            <div className="mt-4 p-3 bg-red-900/50 border border-red-700 rounded-lg max-w-md mx-auto">
              <p className="text-red-300 text-sm">API Error: {apiError}</p>
              <p className="text-red-400 text-xs mt-1">Make sure the backend server is running on http://localhost:5000</p>
            </div>
          )}
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Controls Panel */}
          <div className="lg:col-span-1 space-y-6">
            {/* Upload & Screen Share */}
            <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl p-6 border border-gray-700">
              <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                <Upload className="w-5 h-5" />
                Input Source
              </h2>
              
              <div className="space-y-4">
                <div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*,application/pdf"
                    onChange={handleFileUpload}
                    className="hidden"
                    id="file-input"
                  />
                  <label
                    htmlFor="file-input"
                    className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white py-3 px-4 rounded-lg cursor-pointer transition-all duration-200 hover:scale-105"
                  >
                    <Upload className="w-4 h-4" />
                    Upload Image
                  </label>
                </div>

                <div className="text-center text-gray-400">or</div>

                <button
                  onClick={state.isStreaming ? stopScreenShare : startScreenShare}
                  className={`w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg transition-all duration-200 hover:scale-105 ${
                    state.isStreaming
                      ? 'bg-red-600 hover:bg-red-700 text-white'
                      : 'bg-purple-600 hover:bg-purple-700 text-white'
                  }`}
                >
                  <Monitor className="w-4 h-4" />
                  {state.isStreaming ? 'Stop Sharing' : 'Share Screen'}
                </button>
              </div>

              {/* Status */}
              <div className="mt-4 p-3 bg-gray-700/50 rounded-lg">
                <div className="flex items-center gap-2 text-sm">
                  <div className={`w-2 h-2 rounded-full ${
                    state.mode === 'idle' ? 'bg-gray-400' :
                    state.mode === 'upload' ? 'bg-blue-400' :
                    'bg-green-400 animate-pulse'
                  }`} />
                  <span className="text-gray-300">
                    {state.mode === 'idle' && 'Ready'}
                    {state.mode === 'upload' && 'File Mode'}
                    {state.mode === 'live' && 'Live Scanning'}
                  </span>
                </div>
                {state.isScanning && (
                  <div className="text-xs text-gray-400 mt-1">
                    Analyzing content...
                  </div>
                )}
              </div>
            </div>

            {/* Master Toggle */}
            <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl p-6 border border-gray-700">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {state.toggles.master ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  <span className="font-semibold">Privacy Mode</span>
                </div>
                <button
                  onClick={toggleMaster}
                  className={`relative w-12 h-6 rounded-full transition-all duration-200 ${
                    state.toggles.master ? 'bg-red-500' : 'bg-gray-600'
                  }`}
                >
                  <div className={`absolute top-0.5 w-5 h-5 bg-white rounded-full transition-all duration-200 ${
                    state.toggles.master ? 'left-6' : 'left-0.5'
                  }`} />
                </button>
              </div>
              <p className="text-sm text-gray-400 mt-2">
                {state.toggles.master ? 'Redaction enabled' : 'Content visible'}
              </p>
            </div>

            {/* Category Toggles */}
            <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl p-6 border border-gray-700">
              <h3 className="font-semibold mb-4">Redaction Categories</h3>
              <div className="space-y-3 max-h-80 overflow-y-auto">
                {MOCK_CATEGORIES.map(category => {
                  const isEnabled = state.toggles.categories[category.name];
                  return (
                    <div
                      key={category.name}
                      className="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg hover:bg-gray-700/70 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div className={getRiskColor(category.risk)}>
                          {getRiskIcon(category.risk)}
                        </div>
                        <span className="text-sm font-medium">{category.label}</span>
                      </div>
                      <button
                        onClick={() => toggleCategory(category.name)}
                        className={`relative w-10 h-5 rounded-full transition-all duration-200 ${
                          isEnabled ? 'bg-blue-500' : 'bg-gray-600'
                        }`}
                      >
                        <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full transition-all duration-200 ${
                          isEnabled ? 'left-5' : 'left-0.5'
                        }`} />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Preview Area */}
          <div className="lg:col-span-2">
            <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl p-6 border border-gray-700 h-full">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold">Preview</h2>
                {state.findings.length > 0 && (
                  <div className="text-sm text-gray-400">
                    {state.findings.length} sensitive item{state.findings.length !== 1 ? 's' : ''} detected
                  </div>
                )}
              </div>

              <div className="relative bg-gray-900 rounded-lg overflow-hidden min-h-96">
                <canvas
                  ref={canvasRef}
                  className="max-w-full max-h-full mx-auto block"
                  style={{ objectFit: 'contain' }}
                />
                <video
                  ref={videoRef}
                  className="hidden"
                  autoPlay
                  playsInline
                />
                
                {state.mode === 'idle' && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="text-center">
                      <Shield className="w-16 h-16 text-gray-600 mx-auto mb-4" />
                      <p className="text-gray-400 text-lg">Upload a file or start screen sharing</p>
                      <p className="text-gray-500 text-sm mt-2">
                        Supported formats: PNG, JPG, PDF
                      </p>
                    </div>
                  </div>
                )}

                {state.isScanning && (
                  <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                    <div className="text-center">
                      <div className="animate-spin w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full mx-auto mb-2" />
                      <p className="text-white">Scanning for sensitive content...</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Export Button */}
              {state.mode !== 'idle' && (
                <div className="mt-4 flex justify-end">
                  <button
                    onClick={exportRedacted}
                    className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white py-2 px-4 rounded-lg transition-all duration-200 hover:scale-105"
                  >
                    <Download className="w-4 h-4" />
                    Export Redacted
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
