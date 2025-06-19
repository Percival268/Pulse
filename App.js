import React, { useEffect, useState } from "react";
import axios from "axios";
import { Loader2, Sun, Moon } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

// Icons
import { FaTwitter, FaRedditAlien, FaHackerNews } from "react-icons/fa";
import { SiGooglenews, SiYcombinator } from "react-icons/si";

const sourceIcons = {
  "Twitter": <FaTwitter className="text-sky-400" />,
  "Reddit": <FaRedditAlien className="text-orange-500" />,
  "Hacker News": <FaHackerNews className="text-orange-400" />,
  "YC Blog": <SiYcombinator className="text-orange-300" />,
  "Google News": <SiGooglenews className="text-blue-500" />,
  "Default": <span className="text-gray-400">🌐</span>,
};

const App = () => {
  const [headlines, setHeadlines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [darkMode, setDarkMode] = useState(() =>
    localStorage.getItem("theme") === "dark"
  );
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [weather, setWeather] = useState(null);
  const [localTime, setLocalTime] = useState(null);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode);
    localStorage.setItem("theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  useEffect(() => {
    const fetchHeadlines = async () => {
      try {
        const res = await axios.get(
          `${process.env.REACT_APP_API_URL || "http://localhost:8000"}/trending`
        );
        setHeadlines(res.data);
      } catch (err) {
        console.error("Error fetching headlines:", err);
        setError("Failed to load trending news.");
      } finally {
        setLoading(false);
      }
    };

    fetchHeadlines();
  }, []);
  useEffect(() => {
    if (!navigator.geolocation) return;

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const { latitude, longitude } = position.coords;

        try {
          const res = await axios.get(
            `${process.env.REACT_APP_API_URL || "http://localhost:8000"}/weather?lat=${latitude}&lon=${longitude}`
          );

          if (!res.data.error) {
            const { location, temperature, condition } = res.data;
            setWeather({ location, temperature, condition });
            setLocalTime(new Date().toLocaleTimeString());
          }
        } catch (e) {
          console.error("Weather fetch failed", e);
        }
      },
      (err) => {
        console.warn("Geolocation denied or failed", err);
        setWeather(null); // explicitly prevent showing anything
      },
      { enableHighAccuracy: true, timeout: 5000 }
    );
  }, []);


  const categories = ["All", ...Array.from(new Set(headlines.map(h => h.category || "General")))];
  const visibleHeadlines =
    selectedCategory === "All"
      ? headlines
      : headlines.filter((item) => item.category === selectedCategory);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-white px-6 py-10 font-sans transition-colors duration-300">
      <div className="flex justify-center items-center mb-8 relative">
        {weather && (
          <div className="absolute left-0 text-sm text-zinc-600 dark:text-zinc-300">
            📍 {weather.location} • {weather.temperature}°C, {weather.condition} • {localTime}
          </div>
        )}
        <h1 className="text-4xl font-extrabold text-center">
          <span className="text-blue-600 dark:text-blue-400">📰 Pulse</span> – Trending
        </h1>
        <button
          onClick={() => setDarkMode(!darkMode)}
          className="absolute right-0 p-2 rounded-full border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition"
        >
          {darkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </button>
      </div>

      <div className="flex flex-wrap gap-3 justify-center mb-8">
        {categories.map((category) => (
          <button
            key={category}
            onClick={() => setSelectedCategory(category)}
            className={`px-4 py-1 rounded-full text-sm font-medium border transition
              ${selectedCategory === category
                ? "bg-blue-600 text-white border-blue-600"
                : "bg-zinc-200 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border-zinc-300 dark:border-zinc-700 hover:bg-zinc-300 dark:hover:bg-zinc-700"}`}
          >
            {category}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center items-center h-64">
          <Loader2 className="animate-spin h-8 w-8 text-gray-400" />
        </div>
      ) : error ? (
        <div className="text-center text-red-500 text-lg">{error}</div>
      ) : headlines.length === 0 ? (
        <div className="text-center text-gray-500 text-lg">No headlines available.</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {visibleHeadlines.map((item, index) => {
            const icon = sourceIcons[item.source] || sourceIcons["Default"];
            const timestamp = item.timestamp
              ? formatDistanceToNow(new Date(item.timestamp), { addSuffix: true })
              : "just now";

            const isFeatured = index < 0;

            return (
              <a
                key={index}
                href={item.link}
                target="_blank"
                rel="noopener noreferrer"
                className={`group block p-6 rounded-2xl border transition-all duration-200
                  ${isFeatured
                    ? "bg-white dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700 col-span-1 sm:col-span-2"
                    : "bg-zinc-100 dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800"}
                  hover:border-blue-500 hover:bg-zinc-50 dark:hover:bg-zinc-800 hover:shadow-lg hover:scale-[1.015] hover:ring-1 hover:ring-blue-400 dark:hover:ring-blue-500
                 `}
              >
                <div className="flex items-start gap-3">
                  <div className="pt-1">{icon}</div>
                  <div className="flex-1">
                    <h2 className={`font-semibold group-hover:underline ${isFeatured ? "text-xl" : "text-base"}`}>
                      {item.title}
                    </h2>
                    {item.category && (
                      <span className="inline-block text-xs font-medium text-blue-600 dark:text-blue-300 bg-blue-100 dark:bg-blue-900 px-2 py-0.5 rounded-full mt-2">
                        {item.category}
                      </span>
                    )}
                    <div className="mt-3 flex justify-between text-xs text-zinc-500 dark:text-zinc-400">
                      <span>{item.source || "Unknown"}</span>
                      <span>{timestamp}</span>
                    </div>
                  </div>
                </div>
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default App;