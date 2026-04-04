import { useState, useEffect, useRef } from 'react'
import { createChart } from 'lightweight-charts'

const API = 'http://localhost:8000'

// ── CHART (TradingView lightweight-charts v4) ──────────────────────────────
function AdvancedChart({ data, type, timeframe }) {
  const ref = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef(null)

  // Initialize and update chart
  useEffect(() => {
    if (!data || data.length === 0 || !ref.current) return

    if (!chartRef.current) {
      const chart = createChart(ref.current, {
        width: ref.current.clientWidth,
        height: ref.current.clientHeight || 450,
        layout: { background: { color: 'transparent' }, textColor: '#8b95a5' },
        grid: { vertLines: { color: 'rgba(42,49,66,0.3)' }, horzLines: { color: 'rgba(42,49,66,0.3)' } },
        crosshair: { mode: 1 },
        rightPriceScale: { borderColor: 'rgba(59,69,91,0.5)' },
        timeScale: { borderColor: 'rgba(59,69,91,0.5)', timeVisible: true },
      })
      chartRef.current = chart

      const handleResize = () => {
        if (ref.current && chartRef.current) {
          chartRef.current.resize(ref.current.clientWidth, ref.current.clientHeight || 450)
        }
      }
      window.addEventListener('resize', handleResize)
    }

    // Remove old series if type changed
    if (seriesRef.current) {
      chartRef.current.removeSeries(seriesRef.current)
    }

    const seen = new Set()
    const clean = data
      .filter(d => d.time && !isNaN(+d.open) && !isNaN(+d.high) && !isNaN(+d.low) && !isNaN(+d.close))
      .sort((a, b) => (a.time > b.time ? 1 : -1))
      .filter(d => { if (seen.has(d.time)) return false; seen.add(d.time); return true })
      .map(d => ({ time: d.time, open: +d.open, high: +d.high, low: +d.low, close: +d.close }))
      
    if (clean.length === 0) return

    const lastPrice = clean[clean.length - 1].close
    const firstPrice = clean[0].close
    const isUp = lastPrice >= firstPrice

    let series
    if (type === 'area') {
      series = chartRef.current.addAreaSeries({
        lineColor: isUp ? '#00c805' : '#ff5000',
        topColor: isUp ? 'rgba(0, 200, 5, 0.4)' : 'rgba(255, 80, 0, 0.4)',
        bottomColor: isUp ? 'rgba(0, 200, 5, 0.0)' : 'rgba(255, 80, 0, 0.0)',
        lineWidth: 2,
        crosshairMarkerRadius: 6,
      })
      series.setData(clean.map(d => ({ time: d.time, value: d.close })))
    } else {
      series = chartRef.current.addCandlestickSeries({
        upColor: '#00c805', downColor: '#ff5000',
        borderVisible: false,
        wickUpColor: '#00c805', wickDownColor: '#ff5000',
      })
      series.setData(clean)
    }
    seriesRef.current = series

    // Apply Timeframe
    if (timeframe === 'MAX') {
      chartRef.current.timeScale().fitContent()
    } else {
      const daysStr = timeframe.replace('M', '*30').replace('Y', '*365')
      const days = eval(daysStr)
      
      const toIndex = clean.length - 1
      const fromIndex = Math.max(0, toIndex - days)
      chartRef.current.timeScale().setVisibleLogicalRange({ from: fromIndex, to: toIndex })
    }

  }, [data, type, timeframe])

  return <div ref={ref} style={{ width: '100%', height: '100%' }} />
}

// ── SPINNER ────────────────────────────────────────────────────────────────
function Spinner() {
  return (
    <div style={{
      width: 24, height: 24,
      border: '3px solid rgba(0, 200, 5, 0.2)',
      borderTopColor: '#00c805',
      borderRadius: '50%',
      animation: 'spin 0.8s linear infinite',
      flexShrink: 0,
      margin: '0 auto'
    }} />
  )
}

export default function Dashboard() {
  const [stocks, setStocks] = useState([])
  const [selected, setSelected] = useState('RELIANCE')
  const [history, setHistory] = useState([])
  const [prediction, setPrediction] = useState(null)
  const [fundamentals, setFundamentals] = useState(null)
  
  const [loading, setLoading] = useState(true)
  const [chartType, setChartType] = useState('area')
  const [timeframe, setTimeframe] = useState('1Y')

  useEffect(() => {
    fetch(`${API}/api/stocks`).then(r => r.json()).then(d => setStocks(d.stocks || []))
  }, [])

  useEffect(() => {
    if (!selected) return
    setLoading(true)

    Promise.all([
      fetch(`${API}/api/history/${selected}`).then(r => r.json()),
      fetch(`${API}/api/predict/${selected}`).then(r => r.json()),
      fetch(`${API}/api/fundamentals/${selected}`).then(r => r.json()).catch(() => null)
    ]).then(([hist, pred, fund]) => {
      setHistory(Array.isArray(hist) ? hist : [])
      setPrediction(pred)
      setFundamentals(fund)
      setLoading(false)
    }).catch(err => {
      console.error(err)
      setLoading(false)
    })
  }, [selected])

  if (loading && history.length === 0) {
    return (
      <div className="loading-overlay">
        <Spinner />
        <div>Loading System Interfaces...</div>
      </div>
    )
  }

  let displayPrice = 0
  let dayChange = 0
  let dayChangePct = 0

  if (fundamentals?.current_price && fundamentals?.previous_close) {
    displayPrice = fundamentals.current_price
    dayChange = fundamentals.current_price - fundamentals.previous_close
    dayChangePct = fundamentals.previous_close > 0 ? (dayChange / fundamentals.previous_close) * 100 : 0
  } else if (history.length >= 2) {
    displayPrice = history[history.length - 1].close
    let prevClose = displayPrice
    for (let i = history.length - 2; i >= 0; i--) {
      if (history[i].time !== history[history.length - 1].time) {
         prevClose = history[i].close; break;
      }
    }
    dayChange = displayPrice - prevClose
    dayChangePct = prevClose > 0 ? (dayChange / prevClose) * 100 : 0
  }

  const isUp = dayChange >= 0
  
  const hasModel = prediction && !prediction.detail && !prediction.error
  const pPrice = hasModel ? prediction.predicted_price : null
  const pReturn = hasModel ? prediction.predicted_return_pct : null
  const pUp = pReturn >= 0

  return (
    <div className="app-layout">
      {/* ── LEFT SIDEBAR ── */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>Quant<span style={{color: 'var(--color-up)'}}>Edge</span></h1>
          <div style={{fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: 4, letterSpacing: 1}}>QUANTITATIVE RESEARCH</div>
        </div>
        <div className="stock-list">
          {stocks.map(sym => (
            <div key={sym} className={`stock-item ${sym === selected ? 'active' : ''}`} onClick={() => setSelected(sym)}>
              {sym}
            </div>
          ))}
        </div>
      </aside>

      {/* ── MAIN CONTENT ── */}
      <main className="main-content">
        <header className="hud-header">
          <div>
            <div className="ticker-title">{selected}</div>
            <div style={{color: 'var(--text-secondary)', letterSpacing: 1}}>{fundamentals?.sector || 'Nifty 50'} · {fundamentals?.industry || 'Indian Market'}</div>
          </div>
          {displayPrice > 0 && (
            <div className="live-price-container">
              <div className="live-price">₹{displayPrice.toFixed(2)}</div>
              <div className={`price-change ${isUp ? 'up' : 'down'}`}>
                {isUp ? '▲' : '▼'} {Math.abs(dayChange).toFixed(2)} ({Math.abs(dayChangePct).toFixed(2)}%) <span style={{marginLeft: 4, fontWeight: 500, color: 'var(--text-secondary)'}}>today</span>
              </div>
            </div>
          )}
        </header>

        <div className="panel-grid">
          {/* LEFT: Chart & Stats */}
          <div style={{display: 'flex', flexDirection: 'column', gap: 24}}>
            <div className="panel">
              <div className="chart-toolbar">
                <div className="timeframe-btns">
                  {['1M', '6M', '1Y', '5Y', 'MAX'].map(t => (
                    <button key={t} className={`toolbar-btn ${timeframe === t ? 'active' : ''}`} onClick={() => setTimeframe(t)}>{t}</button>
                  ))}
                </div>
                <div className="type-btns">
                  <button className={`toolbar-btn ${chartType === 'area' ? 'active' : ''}`} onClick={() => setChartType('area')}>Area</button>
                  <button className={`toolbar-btn ${chartType === 'candle' ? 'active' : ''}`} onClick={() => setChartType('candle')}>Candle</button>
                </div>
              </div>
              <div className="chart-wrapper">
                {history.length > 0 && <AdvancedChart data={history} type={chartType} timeframe={timeframe} />}
              </div>
            </div>

            {/* Fundamentals Stats */}
            <div className="panel">
              <div className="panel-title">Key Statistics</div>
              <div className="stats-grid" style={{marginTop: 0}}>
                <div className="stat-card">
                  <div className="stat-label">Market Cap</div>
                  <div className="stat-val">{fundamentals?.market_cap ? `₹${(fundamentals.market_cap / 10000000000).toFixed(2)}T` : '—'}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">P/E Ratio</div>
                  <div className="stat-val">{fundamentals?.pe_ratio ? fundamentals.pe_ratio.toFixed(2) : '—'}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Volume (Today)</div>
                  <div className="stat-val">{fundamentals?.volume_today ? (fundamentals.volume_today / 1000000).toFixed(2) + 'M' : '—'}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Avg Volume</div>
                  <div className="stat-val">{fundamentals?.volume_avg ? (fundamentals.volume_avg / 1000000).toFixed(2) + 'M' : '—'}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">52-W High</div>
                  <div className="stat-val">{hasModel && prediction?.week52?.high ? `₹${prediction.week52.high}` : '—'}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">52-W Low</div>
                  <div className="stat-val">{hasModel && prediction?.week52?.low ? `₹${prediction.week52.low}` : '—'}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">50-Day Avg</div>
                  <div className="stat-val">{fundamentals?.fifty_day_avg ? `₹${fundamentals.fifty_day_avg.toFixed(2)}` : '—'}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Dividend Yld</div>
                  <div className="stat-val">{fundamentals?.dividend_yield ? (fundamentals.dividend_yield * 100).toFixed(2) + '%' : '—'}</div>
                </div>
              </div>
            </div>
          </div>

          {/* RIGHT: HUD Panel */}
          <div className="panel">
            <div className="panel-title">Market Signal</div>
            
            {loading ? (
              <div style={{padding: '40px 0'}}>
                <Spinner />
              </div>
            ) : hasModel ? (
              <>
                <div className="prediction-card">
                  <div className={`decision-badge ${prediction.decision}`}>
                    {prediction.decision}
                  </div>
                  <div style={{color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 8}}>NEXT DAY FORECAST</div>
                  <div className="pred-price-display">
                    <div className="pred-price">₹{pPrice.toFixed(2)}</div>
                    <div className={`price-change ${pUp ? 'up' : 'down'}`}>
                      {pUp ? '▲' : '▼'} {Math.abs(pReturn).toFixed(2)}%
                    </div>
                  </div>
                </div>

                <div className="stats-grid" style={{gridTemplateColumns: '1fr 1fr', marginBottom: 24}}>
                  <div className="stat-card">
                    <div className="stat-label">Confidence Level</div>
                    <div className="stat-val" style={{color: prediction.decision === 'HOLD' ? 'var(--color-hold)' : (prediction.decision === 'BUY' ? 'var(--color-up)' : 'var(--color-down)')}}>
                      {(prediction.confidence * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Trend Strength</div>
                    <div className="stat-val" style={{color: prediction.signal_strength_up >= 0.5 ? 'var(--color-up)' : 'var(--color-down)'}}>
                      {prediction.signal_strength_up >= 0.5 ? '▲ ' : '▼ '} 
                      {prediction.signal_strength_up >= 0.5 ? (prediction.signal_strength_up * 100).toFixed(1) : ((1 - prediction.signal_strength_up) * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Market Sentiment</div>
                    <div className="stat-val" style={{color: 'var(--color-up)'}}>{prediction.market_sentiment}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Risk Level</div>
                    <div className="stat-val" style={{color: prediction.risk === 'HIGH' ? 'var(--color-down)' : 'var(--text-primary)'}}>{prediction.risk}</div>
                  </div>
                </div>

                <div className="panel-title">AI Insights</div>
                <ul className="reason-list">
                  {prediction.reason?.map((r, i) => (
                    <li key={i} className="reason-item">{r}</li>
                  ))}
                </ul>
              </>
            ) : (
              <div style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '40px 20px', lineHeight: 1.6 }}>
                 <div style={{ fontSize: '2rem', marginBottom: '16px' }}>⚙️</div>
                 The predictive algorithms for {selected} are currently initializing. Please wait 1-2 minutes and refresh.
              </div>
            )}
          </div>
        </div>
      </main>

      {loading && history.length > 0 && (
         <div style={{position: 'fixed', top: 20, right: 20, background: 'var(--color-up)', color: '#000', padding: '4px 12px', borderRadius: 20, fontSize: 12, fontWeight: 600}}>
           UPDATING...
         </div>
      )}
    </div>
  )
}
