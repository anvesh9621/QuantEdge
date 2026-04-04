import React, { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';

export default function Chart({ data }) {
  const chartContainerRef = useRef();
  
  useEffect(() => {
    if (!data || data.length === 0 || !chartContainerRef.current) return;
    
    // Clear previous chart
    chartContainerRef.current.innerHTML = '';
    
    try {
        // Initialize standard TradingView chart
        const chart = createChart(chartContainerRef.current, {
          layout: {
            background: { type: 'solid', color: 'transparent' },
            textColor: '#94a3b8',
          },
      grid: {
        vertLines: { color: 'rgba(51, 65, 85, 0.3)' },
        horzLines: { color: 'rgba(51, 65, 85, 0.3)' },
      },
      crosshair: {
        mode: 1, // Magnet crosshair
      },
      rightPriceScale: {
        borderColor: 'rgba(51, 65, 85, 0.5)',
      },
      timeScale: {
        borderColor: 'rgba(51, 65, 85, 0.5)',
        timeVisible: true,
      },
      height: 400,
    });
    
    // Vibrant Colors
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });
    
    // Deduplicate, filter missing values, and sort chronologically
    const uniqueMap = new Map();
    data.forEach(d => {
        if (d.time && d.open != null && !isNaN(d.open) && !isNaN(d.high) && !isNaN(d.low) && !isNaN(d.close)) {
            uniqueMap.set(d.time, {
                time: d.time,
                open: Number(d.open),
                high: Number(d.high),
                low: Number(d.low),
                close: Number(d.close)
            });
        }
    });
    const cleanData = Array.from(uniqueMap.values()).sort((a, b) => new Date(a.time) - new Date(b.time));
    
    try {
        candlestickSeries.setData(cleanData);
        chart.timeScale().fitContent();
    } catch (err) {
        console.error("Lightweight Charts Data Error:", err);
    }
    
    const handleResize = () => {
        if(chartContainerRef.current) {
            chart.applyOptions({ width: chartContainerRef.current.clientWidth });
        }
    };
    
        window.addEventListener('resize', handleResize);
        
        return () => {
          window.removeEventListener('resize', handleResize);
          chart.remove();
        };
    } catch(err) {
        console.error("Lightweight charts initialization failed:", err);
    }
  }, [data]);
  
  return <div ref={chartContainerRef} className="w-full h-full" />;
}
