import { useState, useEffect, useRef } from 'react'
import { createChart } from 'lightweight-charts'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
// Convert HTTP API URL to WebSocket URL
const WS_API = API.replace('http://', 'ws://').replace('https://', 'wss://')

// ── ODOMETER (LIVE PRICE SCROLLER) ─────────────────────────────────────────
function LivePriceScroller({ value, decimals = 2, prefix = "₹", suffix = "" }) {
  if (value === null || value === undefined || isNaN(value)) return <span>—</span>

  const valStr = Number(value).toFixed(decimals)
  
  return (
    <div className="odometer-wrapper">
      {prefix && <span style={{ marginRight: 4 }}>{prefix}</span>}
      {valStr.split('').map((char, i) => {
        if (char === '.' || char === ',' || char === '-') {
          return <span key={i} style={{ display: 'inline-block', width: '0.4em', textAlign: 'center' }}>{char}</span>
        }
        
        const num = parseInt(char, 10)
        return (
          <div key={i} style={{ display: 'inline-block', overflow: 'hidden', height: '1em', width: '0.6em', position: 'relative' }}>
            <div className="odometer-digit-col" style={{ transform: `translateY(-${num}em)` }}>
              {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map(d => (
                <div key={d} className="odometer-digit">{d}</div>
              ))}
            </div>
          </div>
        )
      })}
      {suffix && <span>{suffix}</span>}
    </div>
  )
}

// ── CHART (TradingView lightweight-charts v4) ──────────────────────────────
function AdvancedChart({ data, type, timeframe }) {
  const ref = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef(null)

  useEffect(() => {
    if (!data || data.length === 0 || !ref.current) return

    if (!chartRef.current) {
      const chart = createChart(ref.current, {
        autoSize: true,
        layout: { background: { color: 'transparent' }, textColor: '#8b95a5' },
        grid: { vertLines: { color: 'rgba(42,49,66,0.3)' }, horzLines: { color: 'rgba(42,49,66,0.3)' } },
        crosshair: { mode: 1 },
        rightPriceScale: { borderColor: 'rgba(59,69,91,0.5)' },
        timeScale: { borderColor: 'rgba(59,69,91,0.5)', timeVisible: true },
      })
      chartRef.current = chart
    }

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

function formatVal(val) {
  if (val === null || val === undefined || val === 0) return null
  return val
}

export default function Dashboard() {
  const [stocks, setStocks] = useState([])
  const [selected, setSelected] = useState('RELIANCE')
  const [history, setHistory] = useState([])
  const [prediction, setPrediction] = useState(null)
  const [fundamentals, setFundamentals] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)

  // Live WebSocket State
  const [livePrice, setLivePrice] = useState(null)
  const [liveChange, setLiveChange] = useState(null)
  const [liveChangePct, setLiveChangePct] = useState(null)
  
  // Connection Status ('connecting', 'live', 'stale')
  const [wsStatus, setWsStatus] = useState('connecting')

  const [loading, setLoading] = useState(true)
  const [chartType, setChartType] = useState('area')
  const [timeframe, setTimeframe] = useState('1Y')
  
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    fetch(`${API}/api/stocks`).then(r => r.json()).then(d => setStocks(d.stocks || []))
  }, [])

  // ── 1. Fetch backend API data (History/Predict/Fundamentals) ──
  useEffect(() => {
    if (!selected) return
    setFundamentals(null)
    setPrediction(null)
    setLivePrice(null)
    setLiveChange(null)
    setLiveChangePct(null)
    setLoading(true)
    setSidebarOpen(false)

    const historyPromise = fetch(`${API}/api/history/${selected}`)
      .then(r => r.json()).catch(() => [])
    
    const predictPromise = fetch(`${API}/api/predict/${selected}`)
      .then(r => r.ok ? r.json() : null).catch(() => null)

    const fundamentalsPromise = fetch(`${API}/api/fundamentals/${selected}`)
      .then(r => r.ok ? r.json() : null).catch(() => null)

    Promise.all([historyPromise, predictPromise]).then(([hist, pred]) => {
      setHistory(Array.isArray(hist) ? hist : [])
      if (pred && !pred.error && !pred.detail) {
        setPrediction(pred)
      }
      setLoading(false)
    }).catch(err => {
      console.error(err)
      setLoading(false)
    })

    fundamentalsPromise.then(fund => {
      if (fund && Object.keys(fund).length > 0 && !fund.detail) {
        setFundamentals(fund)
      }
    })
  }, [selected])

  // ── 2. Handle Live WebSocket for Real-Time Pricing (Via Backend Proxy) ──
  useEffect(() => {
    if (!selected) return
    
    let ws = null
    let reconnectAttempts = 0
    let isCancelled = false // Prevent state updates on unmounted component
    
    const connectWs = () => {
      setWsStatus('connecting')
      
      // Connect to our own FastAPI backend
      ws = new WebSocket(`${WS_API}/ws/prices/${selected}`)

      ws.onopen = () => {
        if (isCancelled) {
          ws.close()
          return
        }
        reconnectAttempts = 0
        setWsStatus('live')
        
        // Optional: Keep-alive ping to our backend
        // (Usually handled automatically by FastAPI, but safe to have)
      }

      ws.onmessage = (event) => {
        if (isCancelled) return
        try {
          const data = JSON.parse(event.data)
          
          if (data.price) {
            setLivePrice(data.price)
            if (data.change !== undefined) setLiveChange(data.change)
            if (data.changePercent !== undefined) setLiveChangePct(data.changePercent)
            setLastUpdated(new Date())
            
            // If the backend signals that the upstream Yahoo connection dropped, 
            // it will send is_stale = true.
            if (data.is_stale !== undefined) {
              setWsStatus(data.is_stale ? 'stale' : 'live')
            } else {
               setWsStatus('live')
            }
          }
        } catch (e) {
          console.error("Error parsing backend WS message:", e)
        }
      }

      ws.onclose = (event) => {
        if (isCancelled) return
        
        setWsStatus('stale')
        
        // Task 4 (frontend): Distinguish clean server shutdown (code 1001 = "going away")
        // from an unexpected network drop.
        // - Clean close (redeploy): reconnect immediately, no backoff increment.
        // - Abrupt drop: use exponential backoff to avoid hammering the server.
        const isCleanClose = event.code === 1001 || event.code === 1000
        if (!isCleanClose) {
          reconnectAttempts++
        }
        
        const delay = isCleanClose ? 500 : Math.min(1000 * Math.pow(2, reconnectAttempts - 1), 15000)
        console.log(`Frontend WS closed (code ${event.code}). Reconnecting in ${delay}ms...`)
        
        setTimeout(connectWs, delay)
      }
    }

    connectWs()

    return () => {
      isCancelled = true
      if (ws) ws.close()
    }
  }, [selected])

  if (loading && history.length === 0) {
    return (
      <div className="loading-overlay">
        <Spinner />
        <div>Loading System Interfaces...</div>
      </div>
    )
  }

  // ── Compute Fallback display price ─────────────────────
  let displayPrice = 0
  let dayChange = 0
  let dayChangePct = 0

  // Determine if Indian stock market is currently open (Mon-Fri, 09:15 to 15:30 IST)
  const now = new Date();
  const istTime = new Date(now.toLocaleString("en-US", {timeZone: "Asia/Kolkata"}));
  const day = istTime.getDay();
  const hour = istTime.getHours();
  const min = istTime.getMinutes();
  const isMarketOpen = day >= 1 && day <= 5 && 
                       (hour > 9 || (hour === 9 && min >= 15)) && 
                       (hour < 15 || (hour === 15 && min < 30));

  if (isMarketOpen && livePrice > 0) {
    displayPrice = livePrice
    dayChange = liveChange || 0
    dayChangePct = liveChangePct || 0
  } else if (!isMarketOpen && history.length >= 2) {
    // When market is closed (weekend/night), NEVER use the unofficial post-market ticks 
    // from Yahoo WebSocket or fast_info. Use the rock-solid official EOD close from history.
    displayPrice = history[history.length - 1].close
    let prevClose = displayPrice
    for (let i = history.length - 2; i >= 0; i--) {
      if (history[i].time !== history[history.length - 1].time) {
        prevClose = history[i].close; break;
      }
    }
    dayChange = displayPrice - prevClose
    dayChangePct = prevClose > 0 ? (dayChange / prevClose) * 100 : 0
  } else if (isMarketOpen && fundamentals && fundamentals.current_price > 0 && fundamentals.previous_close > 0) {
    displayPrice = fundamentals.current_price
    dayChange = fundamentals.current_price - fundamentals.previous_close
    dayChangePct = (dayChange / fundamentals.previous_close) * 100
  } else if (prediction && prediction.current_price > 0) {
    displayPrice = prediction.current_price
    if (history.length >= 2) {
      let prevClose = displayPrice
      for (let i = history.length - 2; i >= 0; i--) {
        if (history[i].time !== history[history.length - 1].time) {
          prevClose = history[i].close; break;
        }
      }
      dayChange = displayPrice - prevClose
      dayChangePct = prevClose > 0 ? (dayChange / prevClose) * 100 : 0
    }
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

  const w52High = hasModel && prediction.week52 ? prediction.week52.high : null
  const w52Low = hasModel && prediction.week52 ? prediction.week52.low : null
  const marketCap = formatVal(fundamentals?.market_cap)
  const peRatio = formatVal(fundamentals?.pe_ratio)
  const volToday = formatVal(fundamentals?.volume_today)
  const volAvg = formatVal(fundamentals?.volume_avg)
  const fiftyDayAvg = formatVal(fundamentals?.fifty_day_avg)
  const divYield = formatVal(fundamentals?.dividend_yield)

  return (
    <div className="app-layout">
      {/* ── MOBILE HEADER ── */}
      <div className="mobile-header">
        <button className="menu-btn" onClick={() => setSidebarOpen(true)}>☰</button>
        <h1>Quant<span style={{ color: 'var(--color-up)' }}>Edge</span></h1>
      </div>

      {/* ── MOBILE OVERLAY ── */}
      {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />}

      {/* ── LEFT SIDEBAR ── */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <h1>Quant<span style={{ color: 'var(--color-up)' }}>Edge</span></h1>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: 4, letterSpacing: 1 }}>QUANTITATIVE RESEARCH</div>
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
            <div style={{ color: 'var(--text-secondary)', letterSpacing: 1 }}>{fundamentals?.sector || 'Nifty 50'} · {fundamentals?.industry || 'Indian Market'}</div>
          </div>
          {displayPrice > 0 && (
            <div className="live-price-container">
              <div className="live-price">
                <LivePriceScroller key={`price-${selected}`} value={displayPrice} />
              </div>
              <div className={`price-change ${isUp ? 'up' : 'down'}`} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                {isUp ? '▲' : '▼'} 
                <LivePriceScroller key={`change-${selected}`} value={Math.abs(dayChange)} prefix="" suffix="" />
                <span>(</span><LivePriceScroller key={`pct-${selected}`} value={Math.abs(dayChangePct)} prefix="" suffix="%" /><span>)</span>
                <span style={{ marginLeft: 4, fontWeight: 500, color: 'var(--text-secondary)' }}>today</span>
              </div>
              
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4, justifyContent: 'flex-end' }}>
                <span className="live-dot" style={{ 
                  background: wsStatus === 'live' ? 'var(--color-up)' : (wsStatus === 'connecting' ? 'var(--color-hold)' : 'var(--color-down)'),
                  animation: wsStatus === 'live' ? 'pulse-dot 2s ease-in-out infinite' : 'none',
                  opacity: wsStatus === 'live' ? 1 : 0.6
                }} />
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {wsStatus === 'live' ? 'LIVE STREAM' : (wsStatus === 'connecting' ? 'CONNECTING...' : 'DELAYED / STALE')}
                  {lastUpdated && ` · ${lastUpdated.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`}
                </span>
              </div>
            </div>
          )}
        </header>

        <div className="panel-grid">
          {/* LEFT: Chart & Stats */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
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
              <div className="stats-grid" style={{ marginTop: 0 }}>
                <div className="stat-card">
                  <div className="stat-label">Market Cap</div>
                  <div className="stat-val">{marketCap ? `₹${(marketCap / 10000000000).toFixed(2)}T` : '—'}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">P/E Ratio</div>
                  <div className="stat-val">{peRatio ? peRatio.toFixed(2) : '—'}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Volume (Today)</div>
                  <div className="stat-val">{volToday ? (volToday / 1000000).toFixed(2) + 'M' : '—'}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Avg Volume</div>
                  <div className="stat-val">{volAvg ? (volAvg / 1000000).toFixed(2) + 'M' : '—'}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">52-W High</div>
                  <div className="stat-val">{w52High ? `₹${w52High}` : '—'}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">52-W Low</div>
                  <div className="stat-val">{w52Low ? `₹${w52Low}` : '—'}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">50-Day Avg</div>
                  <div className="stat-val">{fiftyDayAvg ? `₹${fiftyDayAvg.toFixed(2)}` : '—'}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Dividend Yld</div>
                  <div className="stat-val">{divYield ? (divYield * 100).toFixed(2) + '%' : '—'}</div>
                </div>
              </div>
            </div>
          </div>

          {/* RIGHT: HUD Panel */}
          <div className="panel">
            <div className="panel-title">Market Signal</div>

            {loading ? (
              <div style={{ padding: '40px 0' }}>
                <Spinner />
              </div>
            ) : hasModel ? (
              <>
                <div className="prediction-card">
                  <div className={`decision-badge ${prediction.decision}`}>
                    {prediction.decision}
                  </div>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 8 }}>NEXT DAY FORECAST</div>
                  <div className="pred-price-display">
                    <div className="pred-price">₹{pPrice.toFixed(2)}</div>
                    <div className={`price-change ${pUp ? 'up' : 'down'}`}>
                      {pUp ? '▲' : '▼'} {Math.abs(pReturn).toFixed(2)}%
                    </div>
                  </div>
                </div>

                <div className="stats-grid prediction-stats" style={{ gridTemplateColumns: '1fr 1fr', marginBottom: 24 }}>
                  <div className="stat-card">
                    <div className="stat-label">Confidence Level</div>
                    <div className="stat-val" style={{ color: prediction.decision === 'HOLD' ? 'var(--color-hold)' : (prediction.decision === 'BUY' ? 'var(--color-up)' : 'var(--color-down)') }}>
                      {(prediction.confidence * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Trend Strength</div>
                    <div className="stat-val" style={{ color: prediction.signal_strength_up >= 0.5 ? 'var(--color-up)' : 'var(--color-down)' }}>
                      {prediction.signal_strength_up >= 0.5 ? '▲ ' : '▼ '}
                      {prediction.signal_strength_up >= 0.5 ? (prediction.signal_strength_up * 100).toFixed(1) : ((1 - prediction.signal_strength_up) * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Market Sentiment</div>
                    <div className="stat-val" style={{ color: 'var(--color-up)' }}>{prediction.market_sentiment}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Risk Level</div>
                    <div className="stat-val" style={{ color: prediction.risk === 'HIGH' ? 'var(--color-down)' : 'var(--text-primary)' }}>{prediction.risk}</div>
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
        <div style={{ position: 'fixed', top: 20, right: 20, background: 'var(--color-up)', color: '#000', padding: '4px 12px', borderRadius: 20, fontSize: 12, fontWeight: 600, zIndex: 100 }}>
          UPDATING...
        </div>
      )}
    </div>
  )
}
