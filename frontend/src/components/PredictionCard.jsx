import React from 'react';
import { TrendingUp, TrendingDown, Minus, Info } from 'lucide-react';

export default function PredictionCard({ prediction, loading, stock }) {
  if (loading || !prediction) {
    return (
      <div className="p-6 rounded-2xl bg-surface border border-slate-700/50 flex flex-col items-center justify-center min-h-[400px] shadow-xl relative overflow-hidden">
        <div className="animate-pulse flex flex-col items-center gap-4 relative z-10">
          <div className="w-12 h-12 rounded-full border-4 border-primary/30 border-t-primary animate-spin"></div>
          <p className="text-slate-400 font-medium">Analyzing market algorithms...</p>
        </div>
      </div>
    );
  }
  
  const isBuy = prediction.prediction === "BUY";
  const isSell = prediction.prediction === "SELL";
  
  const colorClass = isBuy ? 'text-success hover:shadow-success/20' : 
                     isSell ? 'text-danger hover:shadow-danger/20' : 
                     'text-primary hover:shadow-primary/20';
                     
  const bgClass = isBuy ? 'bg-success/5 border-success/30' : 
                  isSell ? 'bg-danger/5 border-danger/30' : 
                  'bg-primary/5 border-primary/30';
                  
  const Icon = isBuy ? TrendingUp : isSell ? TrendingDown : Minus;
  
  return (
    <div className={`p-6 rounded-2xl bg-surface border shadow-xl relative overflow-hidden transition-all duration-500 hover:-translate-y-1 ${bgClass}`}>
      
      <div className="flex items-center justify-between mb-8 relative z-10">
        <h2 className="text-xl font-bold text-white">AI Decision Engine</h2>
        <span className={`px-3 py-1 text-xs font-bold rounded-full border shadow-sm ${bgClass} ${colorClass} uppercase tracking-wider`}>
          {prediction.risk || "UNKNOWN"} RISK
        </span>
      </div>
      
      <div className="flex flex-col items-center justify-center gap-5 mb-8">
        <div className={`w-24 h-24 rounded-full flex items-center justify-center shadow-[0_0_30px_rgba(0,0,0,0.3)] border-2 ${bgClass} ${colorClass} transition-transform hover:scale-110 duration-300`}>
          <Icon size={48} className="animate-pulse" />
        </div>
        
        <div className="text-center">
          <h3 className={`text-4xl font-extrabold tracking-tight ${colorClass} mb-2 drop-shadow-sm`}>
            {prediction.prediction}
          </h3>
          <p className="text-slate-400 text-sm font-medium tracking-wide">
            ALGORITHMIC CONFIDENCE: <span className="text-white text-base">{(prediction.confidence * 100).toFixed(1)}%</span>
          </p>
        </div>
      </div>
      
      <div className="w-full bg-background/60 rounded-xl p-5 border border-slate-700/50 backdrop-blur-sm relative z-10 shadow-inner">
        <div className="flex items-center gap-2 mb-3">
          <Info size={16} className={colorClass} />
          <h4 className="text-xs font-bold text-white uppercase tracking-widest">Analysis Reasoning</h4>
        </div>
        <ul className="flex flex-col gap-3">
          {prediction.reason && prediction.reason.length > 0 ? prediction.reason.map((res, i) => (
            <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
              <span className={`mt-0.5 shrink-0 ${colorClass}`}>•</span>
              <span className="leading-snug">{res}</span>
            </li>
          )) : (
            <li className="text-sm text-slate-400">No reasoning details provided by the model.</li>
          )}
        </ul>
      </div>
      
    </div>
  );
}
