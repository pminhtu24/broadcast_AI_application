/** @type {import('tailwindcss').Config} */
export default {
    content: ["./index.html", "./src/**/*.{ts,tsx}"],
    theme: {
        extend: {
            fontFamily: {
                sans: ["'Be Vietnam Pro'", "sans-serif"],
                mono: ["'JetBrains Mono'", "monospace"],
            },
            colors: {
                surface: {
                    DEFAULT: "#0f1117",
                    1: "#161b27",
                    2: "#1e2535",
                    3: "#252d3d",
                },
                accent: {
                    DEFAULT: "#3b82f6",
                    hover: "#2563eb",
                    muted: "rgba(59,130,246,0.12)",
                },
                border: {
                    DEFAULT: "rgba(255,255,255,0.08)",
                    strong: "rgba(255,255,255,0.14)",
                },
            },
            animation: {
                "fade-in": "fadeIn 0.2s ease",
                "slide-up": "slideUp 0.25s ease",
                blink: "blink 1s step-end infinite",
                "spin-slow": "spin 2s linear infinite",
            },
            keyframes: {
                fadeIn: { from: { opacity: 0 }, to: { opacity: 1 } },
                slideUp: {
                    from: { opacity: 0, transform: "translateY(8px)" },
                    to: { opacity: 1, transform: "translateY(0)" },
                },
                blink: {
                    "0%,100%": { opacity: 1 },
                    "50%": { opacity: 0 },
                },
            },
        },
    },
    plugins: [],
};