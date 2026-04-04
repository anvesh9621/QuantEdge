import React from 'react';
import { Search, ChevronDown } from 'lucide-react';

export default function StockSelector({ stocks, selected, onChange }) {
  return (
    <div className="relative group">
      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
        <Search className="text-slate-400 group-hover:text-primary transition-colors" size={18} />
      </div>
      <select
        value={selected}
        onChange={(e) => onChange(e.target.value)}
        className="w-full pl-10 pr-10 py-3 bg-surface border border-slate-700/50 rounded-xl text-white appearance-none focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all cursor-pointer shadow-lg font-medium"
      >
        {stocks.length === 0 && <option value={selected}>{selected}</option>}
        {stocks.map(stock => (
          <option key={stock} value={stock} className="bg-surface text-white py-2">
            {stock}
          </option>
        ))}
      </select>
      <div className="absolute inset-y-0 right-0 flex items-center px-4 pointer-events-none">
        <ChevronDown size={16} className="text-slate-400" />
      </div>
    </div>
  );
}
