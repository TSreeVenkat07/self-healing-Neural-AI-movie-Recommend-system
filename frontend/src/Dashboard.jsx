import { useState, useEffect, useRef, useMemo } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function api(path) {
    const res = await fetch(`${API}${path}`);
    if (!res.ok) throw new Error(`${res.status}`);
    return res.json();
}

/* ═══════════════════════ TMDB Poster Service ══════════════════════════ */
const posterCache = new Map();
const TMDB_API_KEY = "15d2ea6d0dc1d476efbca3eba2b9bbfb"; // Public read-only TMDB key

async function fetchPoster(title, year) {
    if (!title) return null;
    const cacheKey = `${title}-${year || ""}`;
    if (posterCache.has(cacheKey)) return posterCache.get(cacheKey);

    try {
        const cleanTitle = title.replace(/\s*\(\d{4}\)\s*/g, '').trim();
        let queryUrl = `https://api.themoviedb.org/3/search/movie?api_key=${TMDB_API_KEY}&query=${encodeURIComponent(cleanTitle)}`;

        if (year) {
            queryUrl += `&year=${year}`;
        }

        const res = await fetch(queryUrl);
        const data = await res.json();

        if (data.results && data.results.length > 0 && data.results[0].poster_path) {
            const url = `https://image.tmdb.org/t/p/w500${data.results[0].poster_path}`;
            posterCache.set(cacheKey, url);
            return url;
        }

        return null; // Let the MoviePoster component handle the gradient fallback
    } catch (e) {
        return null;
    }
}

async function fetchMovieDetails(title, year) {
    if (!title) return null;
    try {
        const cleanTitle = title.replace(/\s*\(\d{4}\)\s*/g, '').trim();
        let queryUrl = `https://api.themoviedb.org/3/search/movie?api_key=${TMDB_API_KEY}&query=${encodeURIComponent(cleanTitle)}`;
        if (year) queryUrl += `&year=${year}`;

        const res = await fetch(queryUrl);
        const data = await res.json();
        if (data.results && data.results.length > 0) {
            return data.results[0]; // contains overview, backdrop_path, etc.
        }
    } catch (e) { }
    return null;
}

/* ═══════════════════════ Genre Color Map ═══════════════════════════════ */
const GENRE_COLORS = {
    Action: ["#ef4444", "#f97316"], Comedy: ["#f59e0b", "#eab308"],
    Drama: ["#8b5cf6", "#6366f1"], "Sci-Fi": ["#06b6d4", "#3b82f6"],
    Horror: ["#1e1b4b", "#581c87"], Romance: ["#ec4899", "#f43f5e"],
    Thriller: ["#374151", "#1f2937"], Animation: ["#10b981", "#34d399"],
    Documentary: ["#78716c", "#a8a29e"], Children: ["#fb923c", "#fbbf24"],
    Adventure: ["#059669", "#0d9488"], Fantasy: ["#a855f7", "#7c3aed"],
    War: ["#64748b", "#475569"], Crime: ["#dc2626", "#991b1b"],
    Mystery: ["#1e3a5f", "#0f172a"],
};

function getGradient(genres) {
    const g = genres?.[0] || "Drama";
    const [c1, c2] = GENRE_COLORS[g] || ["#7c3aed", "#06b6d4"];
    return `linear-gradient(145deg, ${c1}, ${c2})`;
}

/* ═══════════════════════ Movie Poster ═════════════════════════════════ */
function MoviePoster({ title, genres, year }) {
    const [posterUrl, setPosterUrl] = useState(null);

    useEffect(() => {
        let active = true;
        fetchPoster(title, year).then(url => {
            if (active && url) setPosterUrl(url);
        });
        return () => { active = false; };
    }, [title, year]);

    const initials = title?.split(/\s+/).slice(0, 2).map(w => w[0]).join("") || "VX";

    return (
        <div className="movie-poster" style={{ background: posterUrl ? "#12121a" : getGradient(genres) }}>
            {posterUrl ? (
                <img src={posterUrl} alt={title} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            ) : (
                <div style={{ textAlign: "center", padding: "20px" }}>
                    <div style={{ fontSize: 42, fontWeight: 900, opacity: 0.25, fontFamily: "'Space Grotesk'" }}>
                        {initials}
                    </div>
                    <div style={{ fontSize: 11, opacity: 0.3, marginTop: 4, fontWeight: 600 }}>
                        {year || ""}
                    </div>
                </div>
            )}
            <div className="movie-poster-overlay" />
        </div>
    );
}

/* ═══════════════════════ Movie Modal ══════════════════════════════════ */
function MovieModal({ movie, onClose, onToggleSeen, hasSeen }) {
    const [tmdbData, setTmdbData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        fetchMovieDetails(movie.title, movie.year).then(d => {
            setTmdbData(d);
            setLoading(false);
        });
    }, [movie]);

    return (
        <div style={{
            position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
            background: "rgba(0,0,0,0.8)", backdropFilter: "blur(10px)",
            zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center"
        }} onClick={onClose} className="animate-fade-in-up">
            <div style={{
                background: "#12121a", borderRadius: 24, overflow: "hidden",
                width: "90%", maxWidth: 800, border: "1px solid rgba(255,255,255,0.1)",
                display: "flex", flexDirection: "column"
            }} onClick={e => e.stopPropagation()}>
                {/* 1/4 screen landscape ~ height: 25vh */}
                <div style={{
                    width: "100%", height: "30vh", minHeight: 200,
                    background: tmdbData?.backdrop_path ? `url(https://image.tmdb.org/t/p/w1280${tmdbData.backdrop_path}) center/cover no-repeat` : getGradient(movie.genres),
                    position: "relative"
                }}>
                    <div style={{ background: "linear-gradient(to top, #12121a, transparent)", position: "absolute", bottom: 0, left: 0, right: 0, height: "80%" }} />
                    <button onClick={onClose} style={{ position: "absolute", top: 16, right: 16, background: "rgba(0,0,0,0.5)", color: "white", border: "1px solid rgba(255,255,255,0.2)", width: 36, height: 36, borderRadius: "50%", cursor: "pointer", fontSize: 18, zIndex: 10, display: "flex", alignItems: "center", justifyContent: "center" }}>×</button>
                </div>
                <div style={{ padding: "0 32px 32px", marginTop: -60, position: "relative", zIndex: 2 }}>
                    <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
                        {movie.genres?.map(g => (
                            <span key={g} style={{ fontSize: 11, padding: "4px 12px", borderRadius: 100, background: "rgba(124,58,237,0.3)", color: "#c4b5fd", fontWeight: 700 }}>{g}</span>
                        ))}
                    </div>
                    <h2 style={{ fontSize: 32, fontWeight: 900, fontFamily: "'Space Grotesk'", letterSpacing: "-0.02em", marginBottom: 8, color: "white" }}>
                        {movie.title} <span style={{ fontSize: 20, color: "#94a3b8", fontWeight: 500 }}>({movie.year})</span>
                    </h2>

                    <p style={{ fontSize: 15, color: "#cbd5e1", lineHeight: 1.6, marginTop: 16, marginBottom: 32, maxWidth: 650 }}>
                        {loading ? "Loading details..." : (tmdbData?.overview || "No description available for this title.")}
                    </p>

                    <div style={{ display: "flex", gap: 12 }}>
                        <button style={{ padding: "12px 32px", borderRadius: 12, border: "none", background: "linear-gradient(135deg, #7c3aed, #6366f1)", color: "white", fontWeight: 700, fontSize: 14, cursor: "pointer" }}>▶ Play Now</button>
                        <button
                            onClick={(e) => { e.stopPropagation(); onToggleSeen(movie); }}
                            style={{ padding: "12px 24px", borderRadius: 12, border: "1px solid rgba(255,255,255,0.2)", background: hasSeen ? "rgba(16,185,129,0.2)" : "rgba(255,255,255,0.05)", color: hasSeen ? "#10b981" : "#f1f5f9", fontWeight: 600, fontSize: 14, cursor: "pointer", transition: "all 0.2s" }}
                        >
                            {hasSeen ? "✓ In Seen" : "+ Add to Seen"}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

/* ═══════════════════════ Movie Card ═══════════════════════════════════ */
function MovieCard({ movie, index, onToggleSeen, hasSeen, onToggleWish, hasWished, onSelectMovie, showRemove, onRemove }) {
    return (
        <div
            className="movie-card animate-fade-in-up"
            style={{ animationDelay: `${index * 50}ms`, cursor: onSelectMovie ? "pointer" : "default" }}
            onClick={() => onSelectMovie && onSelectMovie(movie)}
        >
            <MoviePoster title={movie.title} genres={movie.genres} year={movie.year} />

            {/* Floating Action Button (Seen) */}
            <button
                onClick={(e) => { e.stopPropagation(); onToggleSeen(movie); }}
                style={{
                    position: "absolute", top: 12, right: 12, zIndex: 20,
                    width: 32, height: 32, borderRadius: "50%", border: "1px solid rgba(255,255,255,0.2)",
                    background: hasSeen ? "rgba(16,185,129,0.9)" : "rgba(10,10,15,0.7)",
                    color: "white", display: "flex", alignItems: "center", justifyContent: "center",
                    cursor: "pointer", fontSize: 16, backdropFilter: "blur(4px)",
                    transition: "all 0.2s"
                }}
            >
                {hasSeen ? "✓" : "+"}
            </button>

            {/* Remove from List Button */}
            {showRemove && (
                <button
                    onClick={(e) => { e.stopPropagation(); onRemove(movie); }}
                    style={{
                        position: "absolute", top: 12, left: 12, zIndex: 20,
                        width: 32, height: 32, borderRadius: "50%", border: "1px solid rgba(255,255,255,0.2)",
                        background: "rgba(244,63,94,0.9)",
                        color: "white", display: "flex", alignItems: "center", justifyContent: "center",
                        cursor: "pointer", fontSize: 16, backdropFilter: "blur(4px)",
                        transition: "all 0.2s"
                    }}
                >
                    —
                </button>
            )}

            <div className="movie-info">
                <h3 style={{
                    fontSize: 13, fontWeight: 700, lineHeight: 1.3, marginBottom: 6,
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap"
                }}>
                    {movie.title}
                </h3>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                    {movie.year && <span style={{ fontSize: 11, color: "#94a3b8" }}>{movie.year}</span>}
                    {movie.score > 0 && (
                        <span style={{ fontSize: 11, color: "#a78bfa", fontWeight: 600 }}>
                            {Math.round(movie.score * 100)}% match
                        </span>
                    )}
                </div>
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap", maxHeight: 20, overflow: "hidden" }}>
                    {movie.genres?.slice(0, 2).map(g => (
                        <span key={g} style={{
                            fontSize: 10, padding: "2px 8px", borderRadius: 100,
                            background: "rgba(124,58,237,0.15)", color: "#a78bfa", fontWeight: 500,
                        }}>{g}</span>
                    ))}
                </div>
            </div>
        </div>
    );
}

/* ═══════════════════════ Skeleton Card ════════════════════════════════ */
function SkeletonCard() {
    return <div className="shimmer" style={{ width: 190, height: 320, flexShrink: 0 }} />;
}

/* ═══════════════════════ Genre Row ════════════════════════════════════ */
function GenreRow({ genre, title, userId, onToggleSeen, seenList, onToggleWish, wishList, onSelectMovie }) {
    const [movies, setMovies] = useState([]);
    const [loading, setLoading] = useState(true);
    const scrollRef = useRef(null);

    useEffect(() => {
        const likedIds = seenList.map(m => m.movie_id).join(',');
        api(`/recommend/genre?genre=${encodeURIComponent(genre)}&user_id=${userId}&limit=25&liked=${likedIds}`)
            .then(d => setMovies(d.movies || []))
            .catch(() => { })
            .finally(() => setLoading(false));
    }, [genre, userId, seenList]);

    const scroll = (dir) => {
        scrollRef.current?.scrollBy({ left: dir * 600, behavior: "smooth" });
    };

    if (!loading && movies.length === 0) return null;

    return (
        <div style={{ marginBottom: 40 }} className="animate-fade-in-up">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, paddingRight: 8 }}>
                <h2 style={{ fontSize: 20, fontWeight: 800, fontFamily: "'Space Grotesk'", letterSpacing: "-0.02em" }}>
                    {title || genre}
                </h2>
                <div style={{ display: "flex", gap: 6 }}>
                    <button onClick={() => scroll(-1)} style={{
                        width: 32, height: 32, borderRadius: 8, border: "1px solid #1e1e2e",
                        background: "#12121a", color: "#94a3b8", cursor: "pointer", fontSize: 14,
                        display: "flex", alignItems: "center", justifyContent: "center",
                    }}>←</button>
                    <button onClick={() => scroll(1)} style={{
                        width: 32, height: 32, borderRadius: 8, border: "1px solid #1e1e2e",
                        background: "#12121a", color: "#94a3b8", cursor: "pointer", fontSize: 14,
                        display: "flex", alignItems: "center", justifyContent: "center",
                    }}>→</button>
                </div>
            </div>
            <div className="genre-scroll" ref={scrollRef}>
                {loading
                    ? Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)
                    : movies.map((m, i) => (
                        <MovieCard
                            key={m.movie_id}
                            movie={m}
                            index={i}
                            onToggleSeen={onToggleSeen}
                            hasSeen={seenList.some(item => item.movie_id === m.movie_id)}
                            onToggleWish={onToggleWish}
                            hasWished={wishList.some(item => item.movie_id === m.movie_id)}
                            onSelectMovie={onSelectMovie}
                        />
                    ))
                }
            </div>
        </div>
    );
}

/* ═══════════════════════ Similar Row ════════════════════════════════════ */
function SimilarRow({ sourceMovie, userId, onToggleSeen, seenList, onToggleWish, wishList, onSelectMovie }) {
    const [movies, setMovies] = useState([]);
    const [loading, setLoading] = useState(true);
    const scrollRef = useRef(null);

    useEffect(() => {
        if (!sourceMovie) return;
        setLoading(true);
        api(`/recommend/similar?movie_id=${sourceMovie.movie_id}&limit=25`)
            .then(d => setMovies(d.movies || []))
            .catch(() => { })
            .finally(() => setLoading(false));
    }, [sourceMovie, userId]);

    const scroll = (dir) => {
        scrollRef.current?.scrollBy({ left: dir * 600, behavior: "smooth" });
    };

    if (!loading && movies.length === 0) return null;

    return (
        <div style={{ marginBottom: 40 }} className="animate-fade-in-up">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, paddingRight: 8 }}>
                <h2 style={{ fontSize: 20, fontWeight: 800, fontFamily: "'Space Grotesk'", letterSpacing: "-0.02em" }}>
                    Because you liked <span style={{ color: "#a78bfa" }}>{sourceMovie?.title}</span>
                </h2>
                <div style={{ display: "flex", gap: 6 }}>
                    <button onClick={() => scroll(-1)} style={{
                        width: 32, height: 32, borderRadius: 8, border: "1px solid #1e1e2e",
                        background: "#12121a", color: "#94a3b8", cursor: "pointer", fontSize: 14,
                        display: "flex", alignItems: "center", justifyContent: "center",
                    }}>←</button>
                    <button onClick={() => scroll(1)} style={{
                        width: 32, height: 32, borderRadius: 8, border: "1px solid #1e1e2e",
                        background: "#12121a", color: "#94a3b8", cursor: "pointer", fontSize: 14,
                        display: "flex", alignItems: "center", justifyContent: "center",
                    }}>→</button>
                </div>
            </div>
            <div className="genre-scroll" ref={scrollRef}>
                {loading
                    ? Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)
                    : movies.map((m, i) => (
                        <MovieCard
                            key={m.movie_id}
                            movie={m}
                            index={i}
                            onToggleSeen={onToggleSeen}
                            hasSeen={seenList.some(item => item.movie_id === m.movie_id)}
                            onToggleWish={onToggleWish}
                            hasWished={wishList.some(item => item.movie_id === m.movie_id)}
                            onSelectMovie={onSelectMovie}
                        />
                    ))
                }
            </div>
        </div>
    );
}

/* ═══════════════════════ Hero Section ═════════════════════════════════ */
function HeroSection({ featuredMovie, neuralHealth, onToggleSeen, hasSeen, onToggleWish, hasWished, selectedMovie, onDeselect }) {
    const [tmdbData, setTmdbData] = useState(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!selectedMovie) {
            setTmdbData(null);
            return;
        }
        setLoading(true);
        fetchMovieDetails(selectedMovie.title, selectedMovie.year).then(d => {
            setTmdbData(d);
            setLoading(false);
        });
    }, [selectedMovie]);

    if (selectedMovie) {
        return (
            <div className="hero-gradient animate-fade-in-up"
                style={{
                    position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
                    zIndex: 100, display: "flex", alignItems: "flex-end",
                    background: tmdbData?.backdrop_path ? `url(https://image.tmdb.org/t/p/w1280${tmdbData.backdrop_path}) top/cover no-repeat` : getGradient(selectedMovie.genres),
                }}
            >
                <button onClick={onDeselect} style={{ position: "absolute", top: 32, right: 32, background: "rgba(0,0,0,0.5)", color: "white", border: "1px solid rgba(255,255,255,0.2)", width: 48, height: 48, borderRadius: "50%", cursor: "pointer", fontSize: 24, zIndex: 102, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(4px)" }}>×</button>
                <div style={{ position: "absolute", top: 0, bottom: 0, left: 0, right: 0, background: "linear-gradient(to top, rgba(10,10,15,1) 0%, rgba(10,10,15,0.9) 25%, rgba(10,10,15,0.4) 60%, transparent 100%)", zIndex: 101 }} />

                <div style={{ position: "relative", zIndex: 102, padding: "0 60px 80px", width: "100%", maxWidth: 1200 }}>
                    <div style={{ display: "flex", gap: 12, marginBottom: 20 }}>
                        {selectedMovie.genres?.map(g => (
                            <span key={g} style={{ fontSize: 11, padding: "4px 12px", borderRadius: 100, background: "rgba(124,58,237,0.4)", color: "#e2e8f0", fontWeight: 700 }}>{g}</span>
                        ))}
                    </div>
                    <h1 style={{ fontSize: 64, fontWeight: 900, fontFamily: "'Space Grotesk'", lineHeight: 1.1, letterSpacing: "-0.03em", marginBottom: 16 }}>
                        {selectedMovie.title} <span style={{ fontSize: 32, color: "#94a3b8", fontWeight: 500 }}>({selectedMovie.year})</span>
                    </h1>
                    <p style={{ fontSize: 18, color: "#cbd5e1", lineHeight: 1.6, marginBottom: 32, maxWidth: "800px" }}>
                        {loading ? "Loading details..." : (tmdbData?.overview || "No description available for this title.")}
                    </p>
                    <div style={{ display: "flex", gap: 12 }}>
                        <button
                            onClick={(e) => { e.stopPropagation(); onToggleWish(selectedMovie); }}
                            style={{
                                padding: "12px 32px", borderRadius: 12, border: "none",
                                background: hasWished ? "rgba(124,58,237,0.4)" : "white",
                                color: hasWished ? "#e2e8f0" : "black",
                                fontWeight: 800, fontSize: 15, cursor: "pointer", transition: "all 0.2s"
                            }}>
                            {hasWished ? "★ In Wishlist" : "★ Add to Wishlist"}
                        </button>
                        <button
                            onClick={(e) => { e.stopPropagation(); onToggleSeen(selectedMovie); }}
                            style={{
                                padding: "12px 24px", borderRadius: 12, border: "1px solid rgba(255,255,255,0.2)",
                                background: hasSeen ? "rgba(16,185,129,0.2)" : "rgba(255,255,255,0.1)",
                                color: hasSeen ? "#10b981" : "#f1f5f9",
                                fontWeight: 600, fontSize: 14, cursor: "pointer", transition: "all 0.2s"
                            }}
                        >
                            {hasSeen ? "✓ In Seen" : "+ Add to Seen"}
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="hero-gradient animate-fade-in-up" style={{
            padding: "100px 60px 60px", minHeight: 420, display: "flex", alignItems: "center",
            position: "relative", overflow: "hidden",
            background: "#0a0a0f"
        }}>
            <div className="bg-orb" style={{ width: 300, height: 300, top: -50, left: -50, background: "rgba(124,58,237,0.12)" }} />
            <div className="bg-orb" style={{ width: 400, height: 400, top: -100, right: -50, background: "rgba(6,182,212,0.08)", opacity: 0.12, animationDelay: "4s" }} />
            <div style={{ position: "relative", zIndex: 2 }}>
                <h1 style={{ fontSize: 52, fontWeight: 900, fontFamily: "'Space Grotesk'", lineHeight: 1.1, letterSpacing: "-0.03em", marginBottom: 16 }}>
                    Discover Your Next<br />
                    <span style={{ background: "linear-gradient(135deg, #7c3aed, #06b6d4)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                        Favorite Movie
                    </span>
                </h1>

                <p style={{ fontSize: 16, color: "#94a3b8", marginBottom: 28, maxWidth: "550px", lineHeight: 1.6 }}>
                    <span style={{ fontWeight: 800, color: "#fff", letterSpacing: "1px", background: "linear-gradient(90deg, #c084fc, #818cf8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>V X</span> — The next-generation neural engine that learns what you love. <br />As you build your Seen and Wishlist, VX creates a perfectly tailored streaming universe just for you.
                </p>

                <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                    <div className="neural-pulse" style={{
                        display: "flex", alignItems: "center", gap: 8, padding: "8px 16px",
                        borderRadius: 100, background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)",
                    }}>
                        <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#10b981" }} />
                        <span style={{ fontSize: 12, color: "#10b981", fontWeight: 600 }}>
                            Neural Engine {neuralHealth != null ? `${Math.round(neuralHealth * 100)}%` : "Online"}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
}

/* ═══════════════════════ Main Dashboard ═══════════════════════════════ */
export default function Dashboard() {
    const [genres, setGenres] = useState([]);
    const [activeGenre, setActiveGenre] = useState(null);
    const [neuralHealth, setNeuralHealth] = useState(null);
    const [featuredMovie, setFeaturedMovie] = useState(null);
    const [userId] = useState(() => Math.floor(Math.random() * 500));

    // Modal State for user click details
    const [selectedMovie, setSelectedMovie] = useState(null);

    // Navigation State
    const [activeTab, setActiveTab] = useState("Discover"); // Discover, Trending, Seen, Wishlist

    // Seen State
    const [seenList, setseenList] = useState(() => {
        try {
            return JSON.parse(localStorage.getItem("vx_seenList")) || [];
        } catch { return []; }
    });

    // Wishlist State
    const [wishList, setwishList] = useState(() => {
        try {
            return JSON.parse(localStorage.getItem("vx_wishList")) || [];
        } catch { return []; }
    });

    const topGenre = useMemo(() => {
        if (seenList.length === 0) return null;
        const genreCounts = {};
        seenList.forEach(m => {
            (m.genres || []).forEach(g => {
                genreCounts[g] = (genreCounts[g] || 0) + 1;
            });
        });
        let max = 0;
        let maxGenre = null;
        for (const [g, count] of Object.entries(genreCounts)) {
            if (count > max) {
                max = count;
                maxGenre = g;
            }
        }
        return maxGenre;
    }, [seenList]);

    const lastAddedMovie = useMemo(() => {
        return seenList.length > 0 ? seenList[0] : null; // Reacts to newest at the top
    }, [seenList]);

    // Trending State
    // Trending State
    const [trendingMovies, setTrendingMovies] = useState([]);

    // Search State
    const [searchQuery, setSearchQuery] = useState("");
    const [searchResults, setSearchResults] = useState([]);
    const [isSearching, setIsSearching] = useState(false);

    useEffect(() => {
        localStorage.setItem("vx_seenList", JSON.stringify(seenList));
    }, [seenList]);

    useEffect(() => {
        localStorage.setItem("vx_wishList", JSON.stringify(wishList));
    }, [wishList]);

    /* ── Load initialization data ── */
    useEffect(() => {
        api("/movies/genres")
            .then(g => setGenres(Array.isArray(g) ? g : []))
            .catch(() => setGenres(["Action", "Comedy", "Drama", "Sci-Fi", "Thriller", "Romance"]));

        api("/monitor/status")
            .then(s => setNeuralHealth(s.health_score))
            .catch(() => { });

        // Fetch some raw movies for "Trending"
        api(`/movies?limit=24&offset=300`)
            .then(d => setTrendingMovies(d.movies || []))
            .catch(() => { });
    }, [userId]);

    useEffect(() => {
        const likedIds = seenList.map(m => m.movie_id).join(',');
        api(`/recommend/genre?genre=Sci-Fi&user_id=${userId}&limit=5&liked=${likedIds}`)
            .then(d => {
                if (d.movies?.length > 0) setFeaturedMovie(d.movies[0]);
            })
            .catch(() => { });
    }, [userId, seenList]);

    // Handle Search
    useEffect(() => {
        if (!searchQuery.trim() || searchQuery.length < 2) {
            setSearchResults([]);
            return;
        }

        setIsSearching(true);
        const timeoutId = setTimeout(() => {
            api(`/search?q=${encodeURIComponent(searchQuery)}`)
                .then(data => {
                    setSearchResults(data.movies || []);
                    setIsSearching(false);
                })
                .catch(() => setIsSearching(false));
        }, 300); // 300ms debounce

        return () => clearTimeout(timeoutId);
    }, [searchQuery]);

    const toggleseenList = (movie) => {
        setseenList(prev => {
            if (prev.find(m => m.movie_id === movie.movie_id)) {
                return prev.filter(m => m.movie_id !== movie.movie_id);
            } else {
                return [movie, ...prev];
            }
        });
    };

    const togglewishList = (movie) => {
        setwishList(prev => {
            if (prev.find(m => m.movie_id === movie.movie_id)) {
                return prev.filter(m => m.movie_id !== movie.movie_id);
            } else {
                return [movie, ...prev];
            }
        });
    };

    const displayGenres = activeGenre ? [activeGenre] : genres.slice(0, 10);

    return (
        <div style={{ minHeight: "100vh", background: "#0a0a0f" }}>

            {/* ── Header ─────────────────────────────────────────────────── */}
            <header style={{
                position: "fixed", top: 0, left: 0, right: 0, zIndex: 50,
                padding: "16px 40px",
                background: "linear-gradient(to bottom, rgba(10,10,15,0.95), rgba(10,10,15,0.7))",
                backdropFilter: "blur(20px)", borderBottom: "1px solid rgba(30,30,46,0.5)",
                display: "flex", alignItems: "center", justifyContent: "space-between",
            }}>
                <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
                    {/* VX Logo */}
                    <div style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }} onClick={() => setActiveTab("Discover")}>
                        <div style={{
                            width: 36, height: 36, borderRadius: 10,
                            background: "linear-gradient(135deg, #7c3aed, #06b6d4)",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            fontFamily: "'Space Grotesk'", fontWeight: 900, fontSize: 16,
                            boxShadow: "0 0 20px rgba(124,58,237,0.3)",
                        }}>VX</div>
                        <span style={{ fontFamily: "'Space Grotesk'", fontWeight: 700, fontSize: 18, letterSpacing: "-0.02em" }}>VX</span>
                    </div>
                    {/* Nav */}
                    <nav style={{ display: "flex", gap: 24 }}>
                        {["Discover", "Trending", "Seen", "Wishlist"].map(item => (
                            <button
                                key={item}
                                onClick={() => { setActiveTab(item); setSearchQuery(""); }}
                                style={{
                                    fontSize: 14, fontWeight: 600, background: "none", border: "none",
                                    color: activeTab === item && !searchQuery ? "#f1f5f9" : "#64748b",
                                    cursor: "pointer", transition: "color 0.2s",
                                    borderBottom: activeTab === item && !searchQuery ? "2px solid #7c3aed" : "2px solid transparent",
                                    paddingBottom: 4
                                }}
                            >{item}</button>
                        ))}
                    </nav>
                    {/* Search Input */}
                    <div style={{ position: "relative", marginLeft: 16 }}>
                        <input
                            type="text"
                            placeholder="Search movies..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            style={{
                                background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
                                borderRadius: 100, padding: "8px 16px 8px 36px", color: "white", fontSize: 13,
                                width: 200, outline: "none", transition: "all 0.2s"
                            }}
                        />
                        <span style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", fontSize: 14, opacity: 0.5 }}>⌕</span>
                    </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                    {/* Neural Status */}
                    <div className="neural-pulse" style={{
                        display: "flex", alignItems: "center", gap: 6, padding: "6px 14px",
                        borderRadius: 100, background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.15)",
                    }}>
                        <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#10b981" }} />
                        <span style={{ fontSize: 11, color: "#10b981", fontWeight: 600 }}>
                            AI Engine {neuralHealth != null ? `${Math.round(neuralHealth * 100)}%` : "Online"}
                        </span>
                    </div>
                    {/* User Avatar */}
                    <div style={{
                        width: 34, height: 34, borderRadius: 10,
                        background: "linear-gradient(135deg, #f43f5e, #f59e0b)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 13, fontWeight: 700, cursor: "pointer",
                    }}>U{userId % 10}</div>
                </div>
            </header>

            {/* ── Content View Router ────────────────────────────────────── */}
            {selectedMovie && (
                <HeroSection
                    selectedMovie={selectedMovie}
                    onToggleSeen={toggleseenList}
                    hasSeen={seenList.some(m => m.movie_id === selectedMovie.movie_id)}
                    onToggleWish={togglewishList}
                    hasWished={wishList.some(m => m.movie_id === selectedMovie.movie_id)}
                    onDeselect={() => setSelectedMovie(null)}
                />
            )}

            {/* ── Search Results ─────────────────────────────────────────── */}
            {!selectedMovie && searchQuery.length >= 2 && (
                <main style={{ padding: "120px 40px 80px" }}>
                    <h2 style={{ fontSize: 32, fontWeight: 800, fontFamily: "'Space Grotesk'", letterSpacing: "-0.02em", marginBottom: 32 }}>
                        {isSearching ? "Searching..." : `Search Results for "${searchQuery}"`}
                    </h2>

                    {searchResults.length === 0 && !isSearching && (
                        <p style={{ color: "#94a3b8" }}>No movies found matching your search.</p>
                    )}

                    <div style={{ display: "flex", flexWrap: "wrap", gap: 24 }}>
                        {searchResults.map((m, i) => (
                            <MovieCard
                                key={m.movie_id}
                                movie={m}
                                index={i}
                                onToggleSeen={toggleseenList}
                                hasSeen={seenList.some(item => item.movie_id === m.movie_id)}
                                onToggleWish={togglewishList}
                                hasWished={wishList.some(item => item.movie_id === m.movie_id)}
                                onSelectMovie={setSelectedMovie}
                            />
                        ))}
                    </div>
                </main>
            )}

            {!selectedMovie && !searchQuery && activeTab === "Discover" && (
                <>
                    <HeroSection
                        featuredMovie={featuredMovie}
                        neuralHealth={neuralHealth}
                        onToggleSeen={toggleseenList}
                        hasSeen={featuredMovie && seenList.some(m => m.movie_id === featuredMovie.movie_id)}
                        onToggleWish={togglewishList}
                        hasWished={featuredMovie && wishList.some(m => m.movie_id === featuredMovie.movie_id)}
                    />

                    {lastAddedMovie && (
                        <div style={{ padding: "0 40px", marginTop: 48, marginBottom: 16 }}>
                            <SimilarRow
                                key={`similar-${lastAddedMovie.movie_id}`}
                                sourceMovie={lastAddedMovie}
                                userId={userId}
                                seenList={seenList}
                                onToggleSeen={toggleseenList}
                                wishList={wishList}
                                onToggleWish={togglewishList}
                                onSelectMovie={setSelectedMovie}
                            />
                        </div>
                    )}

                    {topGenre && (
                        <div style={{ padding: "0 40px", marginTop: 48, marginBottom: 16 }}>
                            {/* Removed 'Because you liked [Genre]' section per user request */}
                        </div>
                    )}

                    <div style={{ padding: "0 40px", marginTop: 32, marginBottom: 32 }}>
                        <div style={{ display: "flex", gap: 8, overflowX: "auto", paddingBottom: 8 }} className="genre-scroll">
                            <button className={`genre-pill ${activeGenre === null ? "active" : ""}`} onClick={() => setActiveGenre(null)}>All</button>
                            {genres.map(g => (
                                <button key={g} className={`genre-pill ${activeGenre === g ? "active" : ""}`} onClick={() => setActiveGenre(activeGenre === g ? null : g)}>{g}</button>
                            ))}
                        </div>
                    </div>

                    <main style={{ padding: "0 40px", paddingBottom: 80 }}>
                        {displayGenres.map(g => (
                            <GenreRow key={g} genre={g} userId={userId} seenList={seenList} onToggleSeen={toggleseenList} wishList={wishList} onToggleWish={togglewishList} onSelectMovie={setSelectedMovie} />
                        ))}
                    </main>
                </>
            )}

            {!selectedMovie && !searchQuery && activeTab === "Trending" && (
                <main style={{ padding: "120px 40px 80px" }}>
                    <h2 style={{ fontSize: 32, fontWeight: 800, fontFamily: "'Space Grotesk'", letterSpacing: "-0.02em", marginBottom: 32 }}>
                        Trending Now
                    </h2>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 24 }}>
                        {trendingMovies.map((m, i) => (
                            <MovieCard
                                key={m.movie_id}
                                movie={m}
                                index={i}
                                onToggleSeen={toggleseenList}
                                hasSeen={seenList.some(item => item.movie_id === m.movie_id)}
                                onToggleWish={togglewishList}
                                hasWished={wishList.some(item => item.movie_id === m.movie_id)}
                                onSelectMovie={setSelectedMovie}
                            />
                        ))}
                    </div>
                </main>
            )}

            {!selectedMovie && !searchQuery && activeTab === "Seen" && (
                <main style={{ padding: "120px 40px 80px", minHeight: "80vh" }}>
                    <h2 style={{ fontSize: 32, fontWeight: 800, fontFamily: "'Space Grotesk'", letterSpacing: "-0.02em", marginBottom: 32 }}>
                        Seen
                    </h2>
                    {seenList.length === 0 ? (
                        <div style={{ color: "#64748b", fontSize: 16 }}>
                            Your list is empty. Explore discovering and adding movies!
                        </div>
                    ) : (
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 24 }}>
                            {seenList.map((m, i) => (
                                <MovieCard
                                    key={m.movie_id}
                                    movie={m}
                                    index={i}
                                    onToggleSeen={toggleseenList}
                                    hasSeen={true}
                                    onToggleWish={togglewishList}
                                    hasWished={wishList.some(item => item.movie_id === m.movie_id)}
                                    onSelectMovie={setSelectedMovie}
                                    showRemove={true}
                                    onRemove={(movie) => toggleseenList(movie)}
                                />
                            ))}
                        </div>
                    )}
                </main>
            )}

            {!selectedMovie && !searchQuery && activeTab === "Wishlist" && (
                <main style={{ padding: "120px 40px 80px", minHeight: "80vh" }}>
                    <h2 style={{ fontSize: 32, fontWeight: 800, fontFamily: "'Space Grotesk'", letterSpacing: "-0.02em", marginBottom: 32 }}>
                        Wishlist
                    </h2>
                    {wishList.length === 0 ? (
                        <div style={{ color: "#64748b", fontSize: 16 }}>
                            Your wishlist is empty! Find movies you want to watch and click "★ Add to Wishlist".
                        </div>
                    ) : (
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 24 }}>
                            {wishList.map((m, i) => (
                                <MovieCard
                                    key={m.movie_id}
                                    movie={m}
                                    index={i}
                                    onToggleSeen={toggleseenList}
                                    hasSeen={seenList.some(item => item.movie_id === m.movie_id)}
                                    onToggleWish={togglewishList}
                                    hasWished={true}
                                    onSelectMovie={setSelectedMovie}
                                    showRemove={true}
                                    onRemove={(movie) => togglewishList(movie)}
                                />
                            ))}
                        </div>
                    )}
                </main>
            )}



            {/* ── Footer ─────────────────────────────────────────────────── */}
            <footer style={{
                borderTop: "1px solid #1e1e2e", padding: "24px 40px",
                display: "flex", alignItems: "center", justifyContent: "space-between",
            }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{
                        width: 24, height: 24, borderRadius: 6,
                        background: "linear-gradient(135deg, #7c3aed, #06b6d4)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 9, fontWeight: 900, fontFamily: "'Space Grotesk'",
                    }}>VX</div>
                    <span style={{ fontSize: 12, color: "#475569" }}>Self-Healing Neural Recommendation Engine</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <span style={{ fontSize: 11, color: "#374151" }}>Powered by Neural Collaborative Filtering</span>
                </div>
            </footer>
        </div>
    );
}
