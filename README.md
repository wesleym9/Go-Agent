# 🌌 Go Teaching Companion AI Agent

A state-of-the-art, mathematically precise, and aesthetically premium Go (Weiqi/Baduk) teaching companion. The application integrates a high-performance **FastAPI WebSocket backend**, a zero-downtime hot-swappable **KataGo neural network analysis engine**, and an interactive, responsive **indigo-glassmorphism frontend dashboard** to deliver real-time strategic commentary and interactive path exploration.

---

## 🚀 Key Features

### 1. Zero-Downtime Dual-Engine Architecture
*   **Human 9D Mode**: Uses the `default_model` (imitative 9D supervised model) to evaluate and explain plays with diverse, professional human-style logic.
*   **Superhuman AI Mode**: Uses the celebrated **optimistic 18-block model** (`superhuman_model`) to compute mathematically optimal, flawless Joseki starting corner plays.
*   **Hot-Swapping**: Toggle between models instantly in the header without disrupting WebSocket connections or requiring browser reloads.

### 2. Real-Time Playstyle Tuning (Komi Shifting)
*   Avoid slow subprocess restarts (~10s) by shifting expected score compensation (**Komi**) on the fly:
    *   **Aggressive (Atk)**: Forces the engine to explore high-risk, high-reward invasions and cutting fights by simulating that the active player is behind by 10 points.
    *   **Defensive (Def)**: Compels the engine to prioritize solid connections, thick shapes, and group security by simulating a 10-point lead.
    *   **Balanced (Bal)**: Standard mathematically optimal evaluations.
*   **Auto-Side Tracking**: Automatically tracks the active side to play and aligns playstyle komi offsets accordingly.

### 3. Dynamic Playout Search Depth
*   **Standard (Std)**: Processes **1,000 playout visits** in $<0.2$ seconds for fast, real-time feedback during openings and routine shapes.
*   **Deep Search**: Computes **3,000 playout visits** in $<0.8$ seconds for high-fidelity calculations during capturing races (*Semeai*), corner life & death (*Tsumego*), and joseki derailments.

### 4. CORS-Free OGS Live Sync
*   Directly mirror active Online-Go.com (OGS) matches in real-time.
*   A custom FastAPI proxy route bypasses browser CORS locks, polling the OGS API every 3 seconds to update the board state seamlessly as moves play out.

### 5. Interactive Gold-Stone Proposed Moves
*   Propose alternative moves directly on the board not in the AI's top suggestions.
*   Projects a **pulsing gold ghost stone** during hover, captures coordinates, runs safety checks (blocking suicide moves), and computes perspective-aware winrate and score deltas.

### 6. Interactive Path Explorer (PV Timeline)
*   Hover over any recommendation to overlay the principal variation as numbered ghost stones on the board.
*   Click **Play Variation Path** to enter a dedicated exploration mode. Freeze the primary game, lock interaction, and step through response variations step-by-step using a media slider timeline.

### 7. Premium AI Commentary (BLUF Formatting)
*   Integrates the Gemini API with standard Go battle terms bypassed (`BLOCK_NONE` safety overrides).
*   Enforces a strict, high-impact **BLUF (Bottom Line Up Front)** response formatting: a 2-sentence bold verdict summary, a 1-sentence recommended coordinate, exactly 2 to 3 one-sentence bullet points comparing options, and a follow-up continuation outline.
*   Includes a token-free, sub-millisecond local rule-based heuristic comparator fallback.

---

## 🛠️ Technology Stack

*   **Backend**: Python 3.10+, FastAPI, WebSockets, Uvicorn, Python `subprocess`.
*   **Frontend**: HTML5, Vanilla CSS, Tailwind CSS (Glassmorphism layout), Alpine.js, FontAwesome.
*   **Go Engine**: KataGo C++ Analysis Engine, OpenCL GPGPU acceleration (NVIDIA RTX 3060 autotuned).
*   **LLM Service**: Google Gemini API (Flash 2.5) with safety bypass rules.

---

## 📦 Prerequisites

1.  **Python 3.8+** installed on your system.
2.  An **OpenCL/GPGPU-compatible GPU** (e.g., NVIDIA GeForce RTX 3060) is highly recommended for sub-second evaluations.
3.  A **Gemini API Key** (optional, for detailed premium 9-dan commentary).

---

## 📥 Installation & Setup

You can set up the application in two ways: either via the fully automated unified installer script (recommended) or through step-by-step manual configuration.

### Method A: Automated One-Click Installer (Recommended)
This script automatically installs all python dependencies, downloads and extracts the optimized Windows KataGo OpenCL engine binary, and fetches both the human and superhuman neural network models.

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/wesleym9/Go-Agent.git
    cd go-agent
    ```
2.  **Run the Installer**:
    ```bash
    python setup.py
    ```

---

### Method B: Manual Step-by-Step Installation

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/wesleym9/Go-Agent.git
    cd go-agent
    ```

2.  **Install Python Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Engine & Models Setup**:
    *   Place your KataGo C++ binary inside the `engine/` folder as `engine/katago.exe`.
    *   Download the default human SL model and save it to `models/default_model.bin.gz`.
    *   To automatically download the superhuman 18-block mirror, run:
        ```bash
        python download_superhuman_model.py
        ```
    *   *On startup, the FastAPI server will automatically generate matching `human.cfg` and `superhuman.cfg` configuration profiles derived from `engine/analysis_example.cfg`.*

---

## 🚀 Running the Application

1.  **Launch the Backend Server**:
    ```bash
    python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000 --reload
    ```
2.  **Open the Web Dashboard**:
    Navigate to `http://127.0.0.1:8000` in your web browser.
3.  **Insert Gemini API Key**:
    Input your Gemini API key inside the header input box to enable detailed 9-dan educational commentaries. Toggle `Detailed AI` to control API usage.

---

## 🔍 Preemptive Double-Check CLI Tool

For offline background calculations and terminal-based move validations, run the preemptive command-line checking script:

```bash
python scratch/katago_double_check.py --moves "Q4 D4 Q16 R6" --proposed "R17" --style "normal" --side "B" --visits 500
```

### Example Output
```text
======================================================================
                      KATAGO PREEMPTIVE DOUBLE CHECK                  
======================================================================
Engine Mode    : SUPERHUMAN (Playout Visits: 500)
Moves Played   : 4 (Q4 D4 Q16 R6)
Next to Play   : Black (B)
Playstyle / Komi: NORMAL (Komi: 7.5)
Proposed Play  : R17 (Corner)
======================================================================
Starting KataGo Analysis subprocess...
KataGo Analysis Engine started.

[Step 1] Querying current position details...
Base Winrate (Black): 44.5% | Score Lead: -0.3 pts

Top AI Move Recommendations:
  1. Move D16  | Winrate:  44.6% | Lead:  -0.3 pts | PV: D16 C17 C16 D17...
  2. Move C16  | Winrate:  44.3% | Lead:  -0.4 pts | PV: C16 E17 D15 O3...

[Step 2] Querying proposed play at R17...
Proposed Play R17 Stats:
  Winrate: 32.8% (Change: -11.7%)
  Score Lead (B): -1.6 (Change: -1.3 pts)

======================================================================
                          TACTICAL VERDICT REPORT                     
======================================================================
[TACTICAL BLUNDER WARNING]
Playing **R17** is a significant blunder, conceding a massive 11.8% in winrate and 1.3 points!
The AI strongly recommends playing **D16** instead.
Reasoning: Playing **R17** results in poor shape or leaves critical cutting points, letting your opponent seize control.

AI Recommended Next Sequence:
  D16 -> C17 -> C16 -> D17 -> F17...
======================================================================
```

---

## 🌟 Custom Agentic Skills Folder

To equip your agentic coding environment (e.g. Gemini Antigravity) with these custom rules, copy the `.md` files inside the project's `skills` configuration folders to:
`C:\Users\Wesley\.gemini\config\skills\`

*   **`go-tactical-shape-recognition.md`**: Custom spatial shapes interpreter.
*   **`go-engine-preemptive-check.md`**: Perspective-aware winrate delta checker.
*   **`go-search-visit-scaling.md`**: Playout visits scaling mapping guidelines.
*   **`go-joseki-fuseki-lookup.md`**: Early game opening verification rules.
*   **`gemini-agent-websockets-resilience.md`**: Self-healing WebSocket control.
*   **`gemini-agent-komi-tuning.md`**: Dynamic komi offsets for playstyle shifts.
*   **`gemini-agent-llm-safety-bypass.md`**: Overrides safety filters to secure Go terminology generations.

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.
