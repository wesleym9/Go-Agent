import asyncio
import websockets
import json
import time

async def test():
    uri = "ws://127.0.0.1:8000/ws/analysis"
    print(f"Connecting to {uri}...")
    async with websockets.connect(uri) as websocket:
        print("Connected! Waiting for initial message...")
        init_msg = await websocket.recv()
        print("Initial message received:", init_msg)
        
        # Test 1: Balanced style, auto side
        query_bal = {
            "type": "request_analysis",
            "id": "test_balanced",
            "moves": [["B", "Q4"], ["W", "D4"], ["B", "C16"]],
            "play_style": "normal",
            "player_color": "none"
        }
        print("\n--- Sending Balanced query ---")
        await websocket.send(json.dumps(query_bal))
        
        # Wait for result
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            if data.get("type") == "analysis_result":
                inner_data = data.get("data", {})
                if inner_data.get("id") == "test_balanced" and inner_data.get("rootInfo"):
                    print("Balanced rootInfo:", inner_data["rootInfo"])
                    break
        
        # Test 2: Aggressive style, Black side (since it's White's turn, B is behind, but let's select side 'B' to force B behind)
        query_atk_b = {
            "type": "request_analysis",
            "id": "test_atk_black",
            "moves": [["B", "Q4"], ["W", "D4"], ["B", "C16"]],
            "play_style": "aggressive",
            "player_color": "B"
        }
        print("\n--- Sending Aggressive Black query ---")
        await websocket.send(json.dumps(query_atk_b))
        
        # Wait for result
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            if data.get("type") == "analysis_result":
                inner_data = data.get("data", {})
                if inner_data.get("id") == "test_atk_black" and inner_data.get("rootInfo"):
                    print("Aggressive Black rootInfo:", inner_data["rootInfo"])
                    break

        # Test 3: Defensive style, Black side (since it's White's turn, B is ahead)
        query_def_b = {
            "type": "request_analysis",
            "id": "test_def_black",
            "moves": [["B", "Q4"], ["W", "D4"], ["B", "C16"]],
            "play_style": "defensive",
            "player_color": "B"
        }
        print("\n--- Sending Defensive Black query ---")
        await websocket.send(json.dumps(query_def_b))
        
        # Wait for result
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            if data.get("type") == "analysis_result":
                inner_data = data.get("data", {})
                if inner_data.get("id") == "test_def_black" and inner_data.get("rootInfo"):
                    print("Defensive Black rootInfo:", inner_data["rootInfo"])
                    break

asyncio.run(test())
