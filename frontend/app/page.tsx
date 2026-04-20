"use client";

import { useState } from "react";
import DropZone from "./components/DropZone";
import Results from "./components/Results";
import ProgressBar from "./components/ProgressBar";
import { analyzeVideoStream, analyzeUrlStream, AnalysisResult } from "./lib/api";

export default function Home() {
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState({ step: "", message: "", value: 0 });

  const handleAnalyze = async (file: File) => {
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const isImage = file.type.startsWith("image/");

      if (isImage) {
        setProgress({ step: "analyzing_frame", message: "Analyzing image...", value: 40 });
        const formData = new FormData();
        formData.append("file", file);
        const response = await fetch("http://localhost:8000/analyze-image", {
          method: "POST",
          body: formData,
        });
        if (!response.ok) {
          const err = await response.json();
          throw new Error(err.detail);
        }
        setProgress({ step: "verdict", message: "Building verdict...", value: 90 });
        const data = await response.json();
        setProgress({ step: "complete", message: "Done!", value: 100 });
        setResult(data);
      } else {
        const data = await analyzeVideoStream(file, (step, message, value) => {
          setProgress({ step, message, value });
        });
        setResult(data);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUrl = async (url: string) => {
    setIsLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await analyzeUrlStream(url, (step, message, value) => {
        setProgress({ step, message, value });
      });
      setResult(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setResult(null);
    setError(null);
  };

  return (
    <main style={{ maxWidth: "760px", margin: "0 auto", padding: "64px 24px 120px" }}>

      {/* Header */}
      <div className="animate-fade-up" style={{ marginBottom: "52px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "16px", marginBottom: "20px" }}>
          <img
            src="/favicon.ico"
            alt="TrueFrame"
            style={{ width: "48px", height: "48px", borderRadius: "12px" }}
          />
          <div style={{
            fontSize: "11px",
            letterSpacing: "0.15em",
            color: "var(--text-muted)",
            textTransform: "uppercase",
            fontWeight: 700,
            fontFamily: "'Instrument Sans', sans-serif",
          }}>
            VeraFrame · AI Detection
          </div>
        </div>

        <h1 style={{
          fontFamily: "'Cabinet Grotesk', sans-serif",
          fontSize: "clamp(36px, 6vw, 56px)",
          fontWeight: 900,
          letterSpacing: "-0.03em",
          lineHeight: 1.0,
          marginBottom: "16px",
          background: "linear-gradient(135deg, #ffffff 0%, rgba(255,255,255,0.6) 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
        }}>
          Is this content real?
        </h1>

        <p style={{
          fontSize: "15px",
          color: "var(--text-secondary)",
          lineHeight: 1.7,
          maxWidth: "480px",
          fontFamily: "'Instrument Sans', sans-serif",
        }}>
          Upload a video, image, or paste a YouTube URL. VeraFrame analyze frames and transitions to detect AI generation.
        </p>
      </div>

      {/* Drop zone */}
      {!result && (
        <div className="animate-fade-up" style={{ animationDelay: "0.1s" }}>
          <DropZone
            onFileSelect={handleAnalyze}
            onUrlSubmit={handleUrl}
            isLoading={isLoading}
          />
        </div>
      )}

      {/* Progress */}
      {isLoading && (
        <ProgressBar
          step={progress.step}
          message={progress.message}
          progress={progress.value}
        />
      )}

      {/* Error */}
      {error && (
        <div
          className="animate-fade-up"
          style={{
            marginTop: "16px",
            padding: "16px 20px",
            background: "rgba(255,59,59,0.06)",
            border: "1px solid rgba(255,59,59,0.2)",
            borderRadius: "14px",
            color: "#ff6b6b",
            fontSize: "14px",
            fontFamily: "'Instrument Sans', sans-serif",
          }}
        >
          ⚠️ {error}
        </div>
      )}

      {/* Results */}
      {result && <Results result={result} onReset={handleReset} />}

      {/* Footer */}
      {!result && !isLoading && (
        <div style={{
          marginTop: "48px",
          display: "flex",
          gap: "24px",
          justifyContent: "center",
          flexWrap: "wrap",
        }}>
          {[
            { icon: "🎬", label: "Frame analysis" },
            { icon: "⚡", label: "Transition detection" },
            { icon: "🔍", label: "Physics reasoning" },
          ].map(({ icon, label }) => (
            <div key={label} style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              fontSize: "12px",
              color: "var(--text-muted)",
              fontFamily: "'Instrument Sans', sans-serif",
              letterSpacing: "0.04em",
            }}>
              <span style={{ fontSize: "14px" }}>{icon}</span>
              {label}
            </div>
          ))}
        </div>
      )}
    </main>
  );
}