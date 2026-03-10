import React, { useState, useRef, useCallback } from 'react';
import { apiRequest } from '../services/api';

const icons = {
    search: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>,
    globe: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>,
    link: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
};

export default function SearchWidget() {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [activeTab, setActiveTab] = useState('All');

    // Abort controller ref — cancels any in-flight request before starting a new one
    const abortRef = useRef(null);

    const handleSearch = useCallback(async (e) => {
        e.preventDefault();
        if (!query.trim()) return;

        // ✅ FIX 1: Use the correct token key — same as the rest of the app
        const token = localStorage.getItem('cn_access_token');
        if (!token) {
            setError('Not logged in. Please sign in first.');
            return;
        }

        // ✅ FIX 2: Cancel any previous in-flight request to prevent duplicate 401s
        if (abortRef.current) {
            abortRef.current.abort();
        }
        abortRef.current = new AbortController();

        setLoading(true);
        setError('');
        setResults([]);

        try {
            const data = await apiRequest(`/search/?query=${encodeURIComponent(query)}`, {
                method: 'POST',
                signal: abortRef.current.signal,
            });
            setResults(Array.isArray(data) ? data : []);
        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error(err);
                setError(err.message || 'Could not reach the backend.');
            }
        } finally {
            setLoading(false);
        }
    }, [query]);

    return (
        <div className="lovart-widget">
            <div className="search-hero">
                <div className="upgrade-pill">
                    <span className="pill-badge">NEW</span>
                    <span>Upgrade now for Kling 3.0 &amp; Nano Banana Pro for up to 50...</span>
                    <span className="pill-link">Upgrade →</span>
                </div>
                <h2 className="hero-title">Design is easier with <span className="brand-highlight">Catalyst</span></h2>
                <p className="hero-subtitle">The design agent that gets you and gets the job done</p>
            </div>

            <div className="search-container">
                <form onSubmit={handleSearch} className="search-bar">
                    <span className="search-icon">{icons.search}</span>
                    <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Ask Catalyst to design a beautiful wedding poster..."
                    />
                    <div className="search-actions">
                        <button type="button" className="action-icon" title="Web Search">{icons.globe}</button>
                        <div className="divider"></div>
                        <button type="submit" className="submit-arrow" disabled={loading || !query.trim()}>
                            {loading ? (
                                <span className="spinner"></span>
                            ) : (
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>
                            )}
                        </button>
                    </div>
                </form>
            </div>

            <div className="chips-row">
                <button className="chip special-chip">Nano Banana Pro</button>
                {['Design', 'Branding', 'Illustration', 'E-Commerce', 'Video'].map(chip => (
                    <button
                        key={chip}
                        className={`chip ${activeTab === chip ? 'active' : ''}`}
                        onClick={() => setActiveTab(chip)}
                    >
                        {chip}
                    </button>
                ))}
            </div>

            {error && (
                <div style={{ padding: '8px 12px', marginTop: 8, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, color: '#fca5a5', fontSize: 13 }}>
                    {error}
                </div>
            )}

            {results.length > 0 && (
                <div className="results-grid animate-fade-in">
                    {results.map((res, i) => (
                        <div key={i} className="result-card">
                            <a href={res.link} target="_blank" rel="noopener noreferrer" className="card-title">{res.title}</a>
                            <div className="card-meta">
                                <span className="link-icon">{icons.link}</span>
                                <span className="link-text">
                                    {(() => { try { return new URL(res.link).hostname; } catch { return res.link; } })()}
                                </span>
                            </div>
                            <p className="card-snippet">{res.snippet}</p>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
