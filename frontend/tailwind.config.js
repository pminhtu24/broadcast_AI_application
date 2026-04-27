/** @type {import('tailwindcss').Config} */
export default {
    content: ["./index.html", "./src/**/*.{ts,tsx}"],
    theme: {
        extend: {
            fontFamily: {
                sans: ["Georgia", "Cambria", "Times New Roman", "serif"],
                mono: ["'JetBrains Mono'", "monospace"],
                serif: ["Georgia", "Cambria", "Times New Roman", "serif"],
                display: ["Georgia", "Cambria", "Times New Roman", "serif"],
            },
            colors: {
                // Base surfaces
                surface: {
                    DEFAULT: "#F0F5F4",   // page bg — cool off-white
                    1: "#FFFFFF",         // sidebar, cards
                    2: "#E8EFEE",         // input bg, secondary panels
                    3: "#DAE6E4",         // hover states
                },
                // Teal palette
                teal: {
                    DEFAULT: "#0D3D38",   // primary — deep teal
                    mid:     "#145C54",   // mid shade
                    light:   "#1DB085",   // accent — mint green
                    muted:   "rgba(29,176,133,0.12)",
                    hover:   "#18956F",
                },
                // Text
                ink: {
                    DEFAULT: "#0D3D38",   // primary text
                    2:       "#4A7A72",   // secondary
                    3:       "#8AADA8",   // placeholder/hint
                },
                // Borders
                border: {
                    DEFAULT: "rgba(13,61,56,0.1)",
                    strong:  "rgba(13,61,56,0.18)",
                    accent:  "rgba(29,176,133,0.3)",
                },
                // Status
                amber:  { DEFAULT: "#D97706", muted: "rgba(217,119,6,0.1)" },
                blue:   { DEFAULT: "#2563EB", muted: "rgba(37,99,235,0.1)" },
            },
            animation: {
                "fade-in":   "fadeIn 0.2s ease",
                "slide-up":  "slideUp 0.22s ease",
                blink:       "blink 1.1s step-end infinite",
                "spin-slow": "spin 2s linear infinite",
                "pulse-dot": "pulseDot 1.4s ease-in-out infinite",
            },
            keyframes: {
                fadeIn:   { from: { opacity: 0 }, to: { opacity: 1 } },
                slideUp:  { from: { opacity: 0, transform: "translateY(6px)" }, to: { opacity: 1, transform: "translateY(0)" } },
                blink:    { "0%,100%": { opacity: 1 }, "50%": { opacity: 0 } },
                pulseDot: { "0%,100%": { transform: "scale(0.7)", opacity: 0.4 }, "50%": { transform: "scale(1)", opacity: 1 } },
            },
            boxShadow: {
                card:    "0 1px 4px rgba(13,61,56,0.08), 0 0 0 0.5px rgba(13,61,56,0.08)",
                input:   "0 0 0 3px rgba(29,176,133,0.15)",
                sidebar: "1px 0 0 rgba(13,61,56,0.07)",
            },
        },
    },
    plugins: [],
};