const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';


class APIClient {
  private _sessionId: string | null = null;

  get sessionId(): string {
    if (!this._sessionId) {
      this._sessionId = this.getOrCreateSessionId();
    }
    return this._sessionId;
  }

  private getOrCreateSessionId(): string {
    if (typeof window === 'undefined') {
      return 'server-session';
    }
    let sessionId = localStorage.getItem('session_id');
    if (!sessionId) {
      sessionId = this.generateUUID();
      localStorage.setItem('session_id', sessionId);
    }
    return sessionId;
  }

  private generateUUID(): string {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  private async request(endpoint: string, options: RequestInit = {}): Promise<any> {
    const headers = {
      'X-Session-ID': this.sessionId,
      ...(options.headers || {}),
    };

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      const errorMessage = errorData?.detail || `API Error: ${response.statusText}`;

      // Auto-heal session if the backend returns a 404 session not found error
      if (response.status === 404 && (errorMessage.includes("Session not found") || errorMessage.includes("SessionExpired"))) {
        console.warn("Stale or expired session detected. Resetting session ID:", this.sessionId);
        if (typeof window !== 'undefined') {
          localStorage.removeItem('session_id');
          this._sessionId = null;
          // Force redirect to landing page to trigger fresh initialization cleanly
          window.location.href = '/';
        }
      }

      throw new Error(errorMessage);
    }

    return response.json();
  }

  // Upload MATLAB files
  async uploadMatlabFiles(files: { ecgSignal: File; filteredSignal: File; rpeaks: File; beatSegments: File }) {
    const formData = new FormData();
    formData.append('ecg_signal', files.ecgSignal);
    formData.append('filtered_signal', files.filteredSignal);
    formData.append('rpeaks', files.rpeaks);
    formData.append('beat_segments', files.beatSegments);

    return this.request('/upload/matlab', {
      method: 'POST',
      body: formData, // fetch automatically sets correct multipart/form-data boundary
    });
  }

  // Start inference
  async startInference() {
    return this.request('/inference/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_version: 'v1.0.0', options: { batch_size: 64, confidence_threshold: 0.7 } }),
    });
  }

  // Get inference results
  async getInferenceResults() {
    return this.request('/inference/results');
  }

  // Start quantization
  async startQuantization() {
    return this.request('/quantization/start', { method: 'POST' });
  }

  // Get quantization results
  async getQuantizationResults() {
    return this.request('/quantization/results');
  }

  // Generate HEX files
  async generateHexFiles() {
    return this.request('/hex/generate', { method: 'POST' });
  }

  // Download secure HEX ZIP
  async downloadHexZip() {
    if (typeof window === 'undefined') return;
    const response = await fetch(`${API_BASE_URL}/hex/download`, {
      method: 'GET',
      headers: {
        'X-Session-ID': this.sessionId,
      },
    });
    if (!response.ok) {
      throw new Error(`Download failed: ${response.statusText}`);
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'fpga_weights.zip';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  }

  // Upload Vivado reports
  async uploadVivadoReports(files: { power: File; timing: File; utilization: File }) {
    const formData = new FormData();
    formData.append('power_report', files.power);
    formData.append('timing_report', files.timing);
    formData.append('utilization_report', files.utilization);

    return this.request('/fpga/upload', {
      method: 'POST',
      body: formData,
    });
  }

  // Get parsed FPGA results
  async getFpgaResults() {
    return this.request('/fpga/results');
  }

  // Get complete dashboard data
  async getDashboardData() {
    return this.request('/analytics/dashboard');
  }

  // Load demo patient data
  async loadDemoData() {
    return this.request('/upload/demo', { method: 'POST' });
  }

  // Reset the current analysis session
  async resetSession() {
    return this.request('/session/reset', { method: 'POST' });
  }
}

export const apiClient = new APIClient();

