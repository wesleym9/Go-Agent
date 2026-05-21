from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
from backend.engine_manager import KataGoAnalysis
import asyncio
import json
import os
import requests

app = FastAPI()

# Paths to KataGo, models, and configurations
KATAGO_PATH = os.path.abspath("engine/katago.exe")
CONFIG_PATH = os.path.abspath("engine/analysis_example.cfg")

HUMAN_MODEL_PATH = os.path.abspath("models/default_model.bin.gz")
SUPERHUMAN_MODEL_PATH = os.path.abspath("models/superhuman_model.bin.gz")

HUMAN_CONFIG_PATH = os.path.abspath("engine/human.cfg")
SUPERHUMAN_CONFIG_PATH = os.path.abspath("engine/superhuman.cfg")

engine = None
current_model_path = HUMAN_MODEL_PATH
current_config_path = HUMAN_CONFIG_PATH

# Store connected clients
connected_clients = set()

async def broadcast_analysis():
    global engine
    while True:
        if engine:
            while True:
                result = engine.get_latest_analysis(timeout=0)
                if not result:
                    break
                # Broadcast to all connected clients
                message = json.dumps({"type": "analysis_result", "data": result})
                # Create a list of clients to avoid set size change during iteration
                for client in list(connected_clients):
                    try:
                        await client.send_text(message)
                    except:
                        if client in connected_clients:
                            connected_clients.remove(client)
        await asyncio.sleep(0.05)

@app.on_event("startup")
async def startup_event():
    global engine, current_model_path, current_config_path
    print(f"Checking for KataGo at: {KATAGO_PATH}")
    print(f"Checking for Human Model at: {HUMAN_MODEL_PATH}")
    
    # 1. Automatically generate human.cfg and superhuman.cfg from analysis_example.cfg if they don't exist
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                base_config = f.read()
                
            # Create human.cfg if missing (ensure it ends with the rank_9d profile)
            if not os.path.exists(HUMAN_CONFIG_PATH):
                print(f"Creating human config at: {HUMAN_CONFIG_PATH}")
                cleaned_config = base_config
                if "humanSLProfile" not in cleaned_config:
                    cleaned_config += "\n# Human SL Model Settings\nhumanSLProfile = rank_9d\nhumanSLChosenMoveIgnorePass = true\n"
                elif "humanSLChosenMoveIgnorePass" not in cleaned_config:
                    cleaned_config += "\nhumanSLChosenMoveIgnorePass = true\n"
                with open(HUMAN_CONFIG_PATH, "w", encoding="utf-8") as f:
                    f.write(cleaned_config)
                    
            # Create superhuman.cfg if missing (ensure wideRootNoise = 0.0)
            if not os.path.exists(SUPERHUMAN_CONFIG_PATH):
                print(f"Creating superhuman config at: {SUPERHUMAN_CONFIG_PATH}")
                cleaned_config = ""
                for line in base_config.splitlines():
                    if "humanSLProfile" not in line and "humanSLChosenMove" not in line:
                        cleaned_config += line + "\n"
                cleaned_config += "\n# Superhuman Mode Settings\nwideRootNoise = 0.0\n"
                with open(SUPERHUMAN_CONFIG_PATH, "w", encoding="utf-8") as f:
                    f.write(cleaned_config)
        except Exception as config_err:
            print(f"Error generating config files: {config_err}")
            
    # Default to loading the Superhuman model if it is already present, otherwise load the Human model
    if os.path.exists(SUPERHUMAN_MODEL_PATH):
        current_model_path = SUPERHUMAN_MODEL_PATH
        current_config_path = SUPERHUMAN_CONFIG_PATH
        print("Superhuman model found. Starting with Superhuman mode by default.")
    else:
        current_model_path = HUMAN_MODEL_PATH
        current_config_path = HUMAN_CONFIG_PATH
        print("Superhuman model not found. Starting with Human 9D mode.")

    if os.path.exists(KATAGO_PATH) and os.path.exists(current_model_path):
        print(f"Starting engine with model: {current_model_path}...")
        try:
            engine = KataGoAnalysis(KATAGO_PATH, current_model_path, current_config_path)
            engine.start()
            print("Engine start() called successfully.")
            # Start broadcast loop
            asyncio.create_task(broadcast_analysis())
            print("Broadcast task created.")
        except Exception as e:
            print(f"FAILED to start engine: {e}")
    else:
        print("MISSING KataGo or default model files!")

@app.websocket("/ws/analysis")
async def websocket_analysis(websocket: WebSocket):
    global engine, current_model_path, current_config_path
    await websocket.accept()
    print("New WebSocket connection accepted.")
    connected_clients.add(websocket)
    
    # Send the current engine mode status on connection
    initial_mode = "superhuman" if current_model_path == SUPERHUMAN_MODEL_PATH else "human"
    try:
        await websocket.send_text(json.dumps({
            "type": "engine_mode_changed",
            "mode": initial_mode,
            "superhuman_available": os.path.exists(SUPERHUMAN_MODEL_PATH)
        }))
    except Exception as e:
        print(f"Error sending initial mode status: {e}")

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "change_engine_mode":
                requested_mode = message["mode"]
                print(f"Client requested engine mode change to: {requested_mode}")
                
                if requested_mode == "superhuman":
                    if os.path.exists(SUPERHUMAN_MODEL_PATH):
                        current_model_path = SUPERHUMAN_MODEL_PATH
                        current_config_path = SUPERHUMAN_CONFIG_PATH
                        if engine:
                            engine.switch_model(SUPERHUMAN_MODEL_PATH, SUPERHUMAN_CONFIG_PATH)
                        await websocket.send_text(json.dumps({
                            "type": "engine_mode_changed",
                            "mode": "superhuman"
                        }))
                    else:
                        print("Error: Superhuman model not found.")
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "Superhuman model not found! Please run the download script 'python download_superhuman_model.py' in the terminal first."
                        }))
                else: # Default back to human
                    current_model_path = HUMAN_MODEL_PATH
                    current_config_path = HUMAN_CONFIG_PATH
                    if engine:
                        engine.switch_model(HUMAN_MODEL_PATH, HUMAN_CONFIG_PATH)
                    await websocket.send_text(json.dumps({
                        "type": "engine_mode_changed",
                        "mode": "human"
                    }))
                    
            elif message["type"] == "request_analysis":
                if engine:
                    query_id = message.get("id", "web_query")
                    play_style = message.get("play_style", "normal")
                    player_color = message.get("player_color", "none")
                    moves = message.get("moves", [])
                    max_visits = message.get("max_visits", 1000)
                    komi = calculate_custom_komi(play_style, player_color, moves)
                    print(f"Requesting analysis for {len(moves)} moves with id: {query_id}, style: {play_style}, side: {player_color}, calculated komi: {komi}, visits: {max_visits}")
                    try:
                        engine.send_query(query_id, moves, komi=komi, max_visits=max_visits)
                    except Exception as query_err:
                        print(f"Error handling analysis request: {query_err}")
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": f"KataGo analysis engine error: {str(query_err)}"
                        }))
                else:
                    print("ERROR: Engine not initialized!")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "KataGo analysis engine not initialized!"
                    }))

    except Exception as e:
        print(f"WebSocket session ended: {e}")
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


@app.get("/")
async def get():
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/ogs/{game_id}")
async def proxy_ogs_game(game_id: str):
    try:
        url = f"https://online-go.com/api/v1/games/{game_id}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

class SuggestionInfo(BaseModel):
    move: str
    winrate: float
    score: float

class ExplanationRequest(BaseModel):
    move: str
    color: str
    winrate_before: float
    winrate_after: float
    score_before: float
    score_after: float
    pv: List[str]
    board_state: Optional[str] = None
    api_key: Optional[str] = None
    top_suggestions: Optional[List[SuggestionInfo]] = None

def calculate_custom_komi(play_style: str, player_color: str, moves: list) -> float:
    base_komi = 7.5
    
    # Determine the next player color to move based on moves history
    if not moves:
        next_color = "B"
    else:
        last_move_color = moves[-1][0]
        next_color = "W" if last_move_color == "B" else "B"
        
    # If player_color is "none", align style to the active side
    if not player_color or player_color == "none":
        effective_color = next_color
    else:
        effective_color = player_color

    if play_style == "aggressive":
        if effective_color == "B":
            return 17.5  # Black feels 10 points behind -> play aggressively
        elif effective_color == "W":
            return -2.5  # White feels 10 points behind -> play aggressively
    elif play_style == "defensive":
        if effective_color == "B":
            return -2.5  # Black feels 10 points ahead -> play defensively
        elif effective_color == "W":
            return 17.5  # White feels 10 points ahead -> play defensively
            
    return base_komi

def parse_coordinate(move: str):
    if not move or move.upper() in ["PASS", "NONE"]:
        return None
    move = move.upper().strip()
    col_char = move[0]
    row_str = move[1:]
    cols = "ABCDEFGHJKLMNOPQRST"
    if col_char not in cols:
        return None
    try:
        col_val = cols.index(col_char) + 1
        row_val = int(row_str)
        return (col_val, row_val)
    except ValueError:
        return None

def get_move_distance(move1: str, move2: str):
    p1 = parse_coordinate(move1)
    p2 = parse_coordinate(move2)
    if not p1 or not p2:
        return 99.0
    return ((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)**0.5

def get_board_region(move: str) -> str:
    p = parse_coordinate(move)
    if not p:
        return "Unknown"
    col, row = p
    is_col_corner = col <= 4 or col >= 16
    is_row_corner = row <= 4 or row >= 16
    if is_col_corner and is_row_corner:
        return "Corner"
    if 7 <= col <= 13 and 7 <= row <= 13:
        return "Center"
    return "Side"

def get_strategic_comparison(proposed: str, sug_move: str, sug_winrate: float, sug_score: float, prop_winrate: float, prop_score: float, req_color: str):
    dist = get_move_distance(proposed, sug_move)
    sug_region = get_board_region(sug_move)
    
    if dist == 0:
        return f"• **{sug_move}** ({sug_region}, {sug_winrate*100:.0f}% WR): Exact match with your proposed play, representing the ideal local shape."
        
    relation = ""
    if dist <= 1.5:
        relation = "tight tactical alternative in the same fight"
    elif dist <= 4.0:
        relation = "local option with superior spacing"
    else:
        relation = "tenuki (playing elsewhere) for a larger open point"
        
    winrate_gap = sug_winrate - prop_winrate
    score_gap = sug_score - prop_score
    
    if winrate_gap > 0.05:
        advantage = f"stronger by {winrate_gap*100:.1f}% WR (+{score_gap:.1f} pts)"
    elif winrate_gap > 0.01:
        advantage = f"slightly stronger (+{winrate_gap*100:.1f}% WR, +{score_gap:.1f} pts)"
    else:
        advantage = "strategically equal"
        
    return f"• **{sug_move}** ({sug_region}, {sug_winrate*100:.0f}% WR): A {relation}, rated as {advantage}."

def get_tactical_relationships(proposed: str, board_state: str, current_color: str) -> str:
    if not board_state:
        return "Opening move on an empty board."
        
    moves = board_state.strip().split()
    if not moves:
        return "Opening move on an empty board."
        
    last_move = moves[-1]
    
    black_stones = []
    white_stones = []
    for idx, mv in enumerate(moves):
        if not mv or mv.upper() in ["PASS", "NONE"]:
            continue
        if idx % 2 == 0:
            black_stones.append(mv)
        else:
            white_stones.append(mv)
            
    friendly_stones = black_stones if current_color == "B" else white_stones
    enemy_stones = white_stones if current_color == "B" else black_stones
    
    relations = []
    
    dist_to_last = get_move_distance(proposed, last_move)
    if dist_to_last <= 1.05:
        relations.append(f"direct response to opponent's last play at {last_move}")
    elif dist_to_last > 4.5:
        relations.append(f"tenuki (playing away) from the last fight at {last_move}")
        
    valid_friendly = [s for s in friendly_stones if parse_coordinate(s) is not None]
    if valid_friendly:
        nearest_friendly = min(valid_friendly, key=lambda s: get_move_distance(proposed, s))
        f_dist = get_move_distance(proposed, nearest_friendly)
        if abs(f_dist - 1.0) < 0.05:
            relations.append(f"nobi (solid extension) from friendly stone at {nearest_friendly}")
        elif abs(f_dist - 1.414) < 0.05:
            relations.append(f"kosumi (diagonal connection) with friendly stone at {nearest_friendly}")
        elif abs(f_dist - 2.0) < 0.05:
            relations.append(f"ikken-tobi (one-space jump) from {nearest_friendly}")
            
    valid_enemy = [s for s in enemy_stones if parse_coordinate(s) is not None]
    if valid_enemy:
        nearest_enemy = min(valid_enemy, key=lambda s: get_move_distance(proposed, s))
        e_dist = get_move_distance(proposed, nearest_enemy)
        if abs(e_dist - 1.0) < 0.05:
            relations.append(f"tsuke (contact attachment) to enemy stone at {nearest_enemy}")
        elif abs(e_dist - 1.414) < 0.05:
            relations.append(f"hane (bending around) enemy stone at {nearest_enemy}")
            
    if not relations:
        region = get_board_region(proposed)
        return f"independent strategic play in the {region}"
        
    return " and ".join(relations)

@app.post("/api/explain_move")
async def explain_move(req: ExplanationRequest):
    api_key = req.api_key or os.environ.get("GEMINI_API_KEY")
    
    # Point and winrate differences
    wr_diff = req.winrate_after - req.winrate_before
    score_diff = req.score_after - req.score_before
    
    # Standard rule-based fallback explanation
    color_name = "Black" if req.color == "B" else "White"
    
    # Reconstruct shape and connection context from board state
    tactical_desc = get_tactical_relationships(req.move, req.board_state, req.color)
    
    # 1. BLUF Summary
    if abs(wr_diff) < 0.02 and abs(score_diff) < 0.5:
        fallback_msg = f"**BLUF Summary:** Playing **{req.move}** is the AI's top choice, maintaining a solid position and preserving {color_name}'s strategic territorial balance."
    elif wr_diff > -0.04:
        fallback_msg = f"**BLUF Summary:** Playing **{req.move}** is a highly competitive alternative for {color_name}, yielding a tiny change of only {wr_diff*100:+.1f}% win rate."
    elif wr_diff > -0.15:
        fallback_msg = f"**BLUF Summary:** **{req.move}** is somewhat sub-optimal, conceding {abs(score_diff):.1f} points and giving the opponent an opportunity to seize the initiative (sente)."
    else:
        fallback_msg = f"**BLUF Summary:** Playing **{req.move}** is a major strategic blunder, losing {abs(wr_diff)*100:.0f}% win rate and conceding {abs(score_diff):.1f} points due to poor shape."
        
    # 2. Heuristic comparative fallback details & Preemptive AI Recommendations
    comparison_context = ""
    better_move_context = ""
    
    if req.top_suggestions and len(req.top_suggestions) > 0:
        sorted_sugs = sorted(req.top_suggestions, key=lambda s: s.winrate, reverse=True)
        best_sug = sorted_sugs[0]
        
        wr_gap = best_sug.winrate - req.winrate_after
        score_gap = best_sug.score - req.score_after
        
        # Preemptive AI improvement check (if gap is significant)
        if best_sug.move != req.move and (wr_gap > 0.04 or score_gap > 1.0):
            better_move_context = f"\n\n**AI Tactical Recommendation:** The AI recommends playing at **{best_sug.move}** ({best_sug.winrate*100:.0f}% WR, {best_sug.score:+.1f} pts) instead of **{req.move}**. Playing **{best_sug.move}** would capture sente and prevent conceding {score_gap:.1f} points."
        
        comparison_context = "\n\n**Comparative Analysis:**"
        for sug in sorted_sugs[:3]:  # Compare against top 3 recommended moves to keep it compact
            comparison_context += "\n" + get_strategic_comparison(req.move, sug.move, sug.winrate, sug.score, req.winrate_after, req.score_after, req.color)
            
    if better_move_context:
        fallback_msg += better_move_context
    if comparison_context:
        fallback_msg += comparison_context

    # 3. Continuation PV info
    if req.pv and len(req.pv) > 0:
        fallback_msg += f"\n\n**Follow-up Continuation:**\nAnticipated response sequence: {', '.join(req.pv[:4])}."

    if not api_key:
        return {"explanation": fallback_msg, "source": "local_heuristics"}
        
    try:
        system_prompt = "You are a professional Go (Weiqi/Baduk) 9-dan teacher. You explain moves to your student in an elegant, extremely concise, educational, and encouraging tone."
        
        prompt = f"""
        A student has proposed playing the move {req.move} for {color_name} in the current position.
        
        Proposed Move Stats:
        - Win rate: {req.winrate_after*100:.1f}% (Change: {wr_diff*100:+.1f}%)
        - Point lead: {req.score_after:+.1f} points (Change: {score_diff:+.1f} points)
        - Anticipated continuation (PV): {", ".join(req.pv)}
        
        Tactical Context (Board Reconstructor):
        The proposed move at {req.move} is a {tactical_desc}.
        """
        
        if req.top_suggestions and len(req.top_suggestions) > 0:
            sugs_list = [f"{s.move} (Winrate: {s.winrate*100:.1f}%, Score Lead: {s.score:+.1f} pts)" for s in req.top_suggestions]
            prompt += f"\nThe AI's top recommended moves for this position are: {'; '.join(sugs_list)}"
            
            best_sug = sorted(req.top_suggestions, key=lambda s: s.winrate, reverse=True)[0]
            wr_gap = best_sug.winrate - req.winrate_after
            score_gap = best_sug.score - req.score_after
            
            if best_sug.move != req.move and (wr_gap > 0.04 or score_gap > 1.0):
                prompt += f"\nPreemptive Check: The AI top recommendation **{best_sug.move}** is strategically superior to the proposed move **{req.move}** by {wr_gap*100:.1f}% WR and {score_gap:.1f} pts."
                
            prompt += f"""
            
            Please provide an extremely concise, high-impact strategic comparison. You must format your response exactly as follows, with no other text, headers, or conversational intros/outros:
            
            **BLUF Summary:** A single clear paragraph of exactly 2 sentences summarizing the strategic verdict on the proposed move {req.move} based on the Tactical Context and compared to the recommendations. BOLD the move coordinate as **{req.move}** in this summary.
            
            **AI Tactical Recommendation:** If any AI recommended move (like {best_sug.move}) is strategically superior to the proposed move by over 4% winrate or 1 point, write exactly 1 sentence here explicitly recommending that move, explaining why it is tactically urgent (e.g. shape, sente, connection). Otherwise, write: "None (Proposed move is excellent)."
            
            **Comparative Analysis:**
            Use a brief list of exactly 2 to 3 bullet points to compare the proposed play with the AI's recommendations. Keep each bullet point extremely short (exactly 1 sentence), focusing on:
            - Sente (initiative) vs. Gote
            - Shape safety/influence vs. local urgency
            
            **Follow-up Continuation:**
            A single sentence explaining the immediate tactical outcome of the continuation sequence ({", ".join(req.pv[:4])}).
            
            CRITICAL WORD BOUNDS: Keep your entire response under 150 words. Every sentence must end with a period. No conversational filler or greetings.
            """
        else:
            prompt += f"""
            
            Please provide an extremely concise, high-impact strategic explanation. You must format your response exactly as follows, with no other text, headers, or conversational intros/outros:
            
            **BLUF Summary:** A single clear paragraph of exactly 2 sentences summarizing the tactical evaluation of the proposed move {req.move} based on the Tactical Context (what it achieves, preserves, or concedes). BOLD the move coordinate as **{req.move}** in this summary.
            
            **Tactical & Shape Insights:**
            Use exactly 2 brief bullet points (exactly 1 sentence each) giving practical advice on shape stability, thickness, and sente for playing in this local area.
            
            **Follow-up Continuation:**
            A single sentence detailing the immediate responses in the continuation sequence ({", ".join(req.pv[:4])}).
            
            CRITICAL WORD BOUNDS: Keep your entire response under 100 words. Every sentence must end with a period. No conversational filler or greetings.
            """
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "maxOutputTokens": 2500,
                "temperature": 0.4
            },
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                }
            ]
        }
        
        loop = asyncio.get_event_loop()
        def call_gemini():
            return requests.post(url, json=payload, headers=headers, timeout=20)
            
        response = await loop.run_in_executor(None, call_gemini)
        print(f"Gemini API Response Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print("Gemini API Response JSON:")
            print(json.dumps(result, indent=2))
            try:
                candidate = result['candidates'][0]
                text = candidate['content']['parts'][0]['text'].strip()
                finish_reason = candidate.get('finishReason')
                print(f"Parsed Gemini Text (finishReason={finish_reason}): {text}")
                return {"explanation": text, "source": "gemini"}
            except Exception as parse_err:
                print(f"Error parsing Gemini response: {parse_err}")
                return {"explanation": f"{fallback_msg} (Gemini Parse Error: {str(parse_err)})", "source": "local_heuristics_fallback"}
        else:
            print(f"Gemini API Error details: {response.text}")
            return {"explanation": f"{fallback_msg} (Gemini API Error: {response.text})", "source": "local_heuristics_fallback"}
    except Exception as e:
        print(f"Exception querying Gemini: {e}")
        return {"explanation": f"{fallback_msg} (Error querying Gemini: {str(e)})", "source": "local_heuristics_fallback"}


