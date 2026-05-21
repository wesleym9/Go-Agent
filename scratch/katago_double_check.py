import sys
import os
import argparse
import time
import json
import queue

# Ensure go-agent root is in sys.path so we can import backend.engine_manager
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.engine_manager import KataGoAnalysis

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

def main():
    parser = argparse.ArgumentParser(description="KataGo Preemptive Double-Check & Move Selection Enhancer")
    parser.add_argument("--moves", type=str, default="", help="Space-separated moves so far (e.g. 'Q4 D4 Q16 R6')")
    parser.add_argument("--proposed", type=str, default="", help="The move you are considering playing (e.g. 'R17')")
    parser.add_argument("--style", type=str, default="normal", choices=["normal", "aggressive", "defensive"], help="Playing style")
    parser.add_argument("--side", type=str, default="none", choices=["none", "B", "W"], help="Your side color")
    parser.add_argument("--visits", type=int, default=5000, help="Number of search visits for deep double-check")
    parser.add_argument("--engine-mode", type=str, default="superhuman", choices=["human", "superhuman"], help="Engine model profile")
    
    args = parser.parse_args()

    # Resolve paths
    katago_path = os.path.abspath("engine/katago.exe")
    model_path = os.path.abspath("models/superhuman_model.bin.gz" if args.engine_mode == "superhuman" else "models/default_model.bin.gz")
    config_path = os.path.abspath("engine/superhuman.cfg" if args.engine_mode == "superhuman" else "engine/human.cfg")

    if not os.path.exists(katago_path):
        print(f"Error: KataGo binary not found at {katago_path}")
        sys.exit(1)
    if not os.path.exists(model_path):
        print(f"Error: Model not found at {model_path}")
        sys.exit(1)
    if not os.path.exists(config_path):
        print(f"Error: Config not found at {config_path}")
        sys.exit(1)

    # Format moves list
    moves_history = []
    raw_moves = args.moves.strip().split()
    for idx, mv in enumerate(raw_moves):
        color = "B" if idx % 2 == 0 else "W"
        moves_history.append([color, mv])

    # Next color to play
    next_color = "B" if len(moves_history) % 2 == 0 else "W"
    color_name = "Black" if next_color == "B" else "White"
    
    # Calculate komi based on style and side
    komi = calculate_custom_komi(args.style, args.side, moves_history)

    print("=" * 70)
    print("                      KATAGO PREEMPTIVE DOUBLE CHECK                  ")
    print("=" * 70)
    print(f"Engine Mode    : {args.engine_mode.upper()} (Playout Visits: {args.visits})")
    print(f"Moves Played   : {len(moves_history)} ({' '.join(raw_moves) if raw_moves else 'None'})")
    print(f"Next to Play   : {color_name} ({next_color})")
    print(f"Playstyle / Komi: {args.style.upper()} (Komi: {komi})")
    if args.proposed:
        print(f"Proposed Play  : {args.proposed.upper()} ({get_board_region(args.proposed)})")
    print("=" * 70)
    print("Starting KataGo Analysis subprocess...")

    # Initialize analysis engine
    analysis_engine = KataGoAnalysis(katago_path, model_path, config_path)
    analysis_engine.start()

    try:
        # Step 1: Query current board state to find AI suggestions
        print("\n[Step 1] Querying current position details...")
        analysis_engine.send_query("base_position", moves_history, komi=komi, max_visits=args.visits)
        
        base_result = None
        start_time = time.time()
        # Wait up to 15 seconds for deep results
        while time.time() - start_time < 15.0:
            res = analysis_engine.get_latest_analysis(timeout=0.1)
            if res and res.get("id") == "base_position" and res.get("rootInfo"):
                base_result = res
                break
        
        if not base_result:
            print("Error: Failed to obtain base position analysis from KataGo.")
            sys.exit(1)

        root = base_result["rootInfo"]
        base_winrate = root["winrate"]
        base_score = root["scoreLead"]
        
        move_infos = base_result.get("moveInfos", [])
        sorted_sugs = sorted(move_infos, key=lambda x: x["winrate"], reverse=True)

        print(f"Base Winrate (Black): {base_winrate * 100:.1f}% | Score Lead: {base_score:+.1f} pts")
        print("\nTop AI Move Recommendations:")
        for idx, sug in enumerate(sorted_sugs[:4]):
            pv_str = " ".join(sug.get("pv", [])[:4])
            print(f"  {idx+1}. Move {sug['move']:<4} | Winrate: {sug['winrate']*100:5.1f}% | Lead: {sug['scoreMean']:+5.1f} pts | PV: {pv_str}...")

        best_sug = sorted_sugs[0] if sorted_sugs else None

        # Step 2: Query the proposed move to verify it precisely
        if args.proposed:
            proposed_move = args.proposed.upper().strip()
            print(f"\n[Step 2] Querying proposed play at {proposed_move}...")
            
            # Form moves list with the proposed move appended
            proposed_moves_history = list(moves_history)
            proposed_moves_history.append([next_color, proposed_move])
            
            analysis_engine.send_query("proposed_position", proposed_moves_history, komi=komi, max_visits=args.visits)
            
            prop_result = None
            start_time = time.time()
            while time.time() - start_time < 15.0:
                res = analysis_engine.get_latest_analysis(timeout=0.1)
                if res and res.get("id") == "proposed_position" and res.get("rootInfo"):
                    prop_result = res
                    break
                    
            if not prop_result:
                print(f"Error: Failed to analyze proposed move {proposed_move}.")
                sys.exit(1)
                
            prop_root = prop_result["rootInfo"]
            prop_winrate = prop_root["winrate"]
            prop_score = prop_root["scoreLead"]
            
            # Delta calculation
            # Note: winrate and score changes are from base state to proposed state
            wr_change = prop_winrate - base_winrate
            score_change = prop_score - base_score
            
            # Perspective adjust for changes: active player perspective
            if next_color == "W":
                wr_change = -wr_change
                score_change = -score_change
                
            print(f"Proposed Play {proposed_move} Stats:")
            print(f"  Winrate: {prop_winrate * 100:.1f}% (Change: {wr_change*100:+.1f}%)")
            print(f"  Score Lead (B): {prop_score:+.1f} (Change: {score_change:+.1f} pts)")
            
            # Deep blunder check and tactical decision compilation
            print("\n" + "="*70)
            print("                          TACTICAL VERDICT REPORT                     ")
            print("="*70)
            
            if best_sug:
                # Calculate differences against the absolute best suggested move
                best_move = best_sug["move"]
                best_winrate = best_sug["winrate"]
                best_score = best_sug["scoreMean"]
                
                wr_gap = best_winrate - prop_winrate
                score_gap = best_score - prop_score
                
                if next_color == "W":
                    # For White, score lead is negative Black lead. Gap = White lead - proposed lead.
                    # Actually, standardizing gaps: Gap = Best Move WR/Score - Proposed Move WR/Score from next_color's perspective
                    # In base result, sug.scoreMean is from the base state perspective (Black lead).
                    # Winrate gap is absolute difference
                    wr_gap = best_winrate - prop_winrate
                    score_gap = -(best_score - prop_score) if next_color == "W" else (best_score - prop_score)

                # Output decision
                if proposed_move == best_move:
                    print("[EXCELLENT INTUITION]")
                    print(f"The proposed play at **{proposed_move}** is the AI's absolute top choice.")
                    print("It perfectly balances spatial shape thickness, local connection stability, and territorial efficiency.")
                elif wr_gap <= 0.02 and score_gap <= 0.5:
                    print("[VIABLE ALTERNATIVE]")
                    print(f"The proposed play at **{proposed_move}** is a highly competitive and playable option.")
                    print(f"It trails the AI's top suggestion (**{best_move}**) by only {wr_gap*100:.1f}% winrate and {score_gap:.1f} points.")
                    print("It represents a solid strategic choice based on personal preference.")
                elif wr_gap <= 0.05 and score_gap <= 1.0:
                    print("[SLIGHT INEFFICIENCY]")
                    print(f"The proposed play at **{proposed_move}** is slightly passive or sub-optimal.")
                    print(f"The AI preferred move is **{best_move}**, which yields {wr_gap*100:.1f}% more winrate and {score_gap:.1f} points of advantage.")
                    print(f"Playing at **{best_move}** is recommended to seize the initiative (sente) or optimize shape spacing.")
                else:
                    print("[TACTICAL BLUNDER WARNING]")
                    print(f"Playing **{proposed_move}** is a significant blunder, conceding a massive {wr_gap*100:.1f}% in winrate and {score_gap:.1f} points!")
                    print(f"The AI strongly recommends playing **{best_move}** instead.")
                    print(f"Reasoning: Playing **{proposed_move}** results in poor shape or leaves critical cutting points, letting your opponent seize control.")
                    
                print("\nAI Recommended Next Sequence:")
                best_pv = best_sug.get("pv", [])
                print(f"  {best_move} -> " + " -> ".join(best_pv[1:5]) + "...")
                
            else:
                print("Analysis completed successfully. Proposed move is stable.")
                
            print("="*70)

    except KeyboardInterrupt:
        print("\nStopping evaluation...")
    finally:
        analysis_engine.stop()

if __name__ == "__main__":
    main()
