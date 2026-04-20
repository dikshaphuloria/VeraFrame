const API_BASE = "http://localhost:8000";

export interface FrameAnalysis{
    is_ai_generated: boolean;
    confidence: number;
    artifacts_found: string[];
    reasoning: string;
    watermark_detected: boolean; 
}

export interface Frame{
    filename: string;
    image: string;
    analysis: FrameAnalysis;
}

export interface TransitionResult {
  is_suspicious_transition: boolean;
  confidence: number;
  transition_type: string;
  description: string;
  frame_pair: string;
}

export interface AnalysisResult {
  verdict: "AI Generated" | "Possibly AI Generated" | "Likely Real" | "Possibly Edited";
  overall_confidence: number;
  ai_frames: number;
  total_frames: number;
  artifacts_found: string[];
  proof_frames: Frame[];
  all_frames: Frame[];
  transitions: {
    total_analyzed: number;
    suspicious_count: number;
    results: TransitionResult[];
  };
}

export async function analyzeVideo(file: File): Promise<AnalysisResult> {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        body: formData,
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Analysis failed");
      }
    
    return response.json();
}

export async function analyzeVideoStream(
    file: File,
    onProgress: (step: string, message: string, progress: number) => void
  ): Promise<AnalysisResult> {
    const formData = new FormData();
    formData.append("file", file);
  
    const response = await fetch(`${API_BASE}/analyze-stream`, {
      method: "POST",
      body: formData,
    });
  
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Analysis failed");
    }
  
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let result: AnalysisResult | null = null;
  
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
  
      const chunk = decoder.decode(value);
      const lines = chunk.split("\n").filter(l => l.startsWith("data: "));
  
      for (const line of lines) {
        try {
          const data = JSON.parse(line.slice(6));
          onProgress(data.step, data.message, data.progress);
          if (data.step === "complete") {
            result = data.result;
          }
          if (data.step === "error") {
            throw new Error(data.message);
          }
        } catch (e) {
          // skip malformed chunks
        }
      }
    }
  
    if (!result) throw new Error("No result received");
    return result;
  }


  export async function analyzeUrlStream(
    url: string,
    onProgress: (step: string, message: string, progress: number) => void
  ): Promise<AnalysisResult> {
    const response = await fetch(`${API_BASE}/analyze-url-stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
  
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Analysis failed");
    }
  
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let result: AnalysisResult | null = null;
  
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
  
      const chunk = decoder.decode(value);
      const lines = chunk.split("\n").filter(l => l.startsWith("data: "));
  
      for (const line of lines) {
        try {
          const data = JSON.parse(line.slice(6));
          onProgress(data.step, data.message, data.progress);
          if (data.step === "complete") result = data.result;
          if (data.step === "error") throw new Error(data.message);
        } catch (e: any) {
          if (e.message) throw e;
        }
      }
    }
  
    if (!result) throw new Error("No result received");
    return result;
  }