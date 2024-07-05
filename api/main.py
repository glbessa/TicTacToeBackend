from typing import List, Dict, Optional, Set
from dataclasses import dataclass
import queue

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.websockets import WebSocketDisconnect

from settings import HOST, PORT

class InvalidMoveException(Exception):
    pass

@dataclass
class Player:
    websocket: WebSocket
    nickname: str
    symbol: str = ""
    is_my_turn: bool = False
    opponent: Optional['Player'] = None
    game_board: Optional['GameBoard'] = None

class GameBoard:
    def __init__(self):
        self.board = [" " for _ in range(9)]
        self.winning_combinations = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],
            [0, 3, 6], [1, 4, 7], [2, 5, 8],
            [0, 4, 8], [2, 4, 6]
        ]
    
    def make_move(self, position: int, symbol: str):
        if self.board[position] != " ":
            raise InvalidMoveException("Invalid move")
        self.board[position] = symbol

    def get_winner(self) -> Optional[str]:
        for combination in self.winning_combinations:
            if self.board[combination[0]] == self.board[combination[1]] == self.board[combination[2]] != " ":
                return self.board[combination[0]]
            
        if self.is_draw():
            return "draw"
        
        return None
    
    def is_draw(self) -> bool:
        return all([cell != " " for cell in self.board])
    
    def is_game_over(self):
        return self._check_winner() is not None or self._is_full()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """connect event"""
        await websocket.accept()
        self.active_connections.add(websocket)

    async def send_message(self, websocket: WebSocket, message: str):
        """Direct Message"""
        await websocket.send_text(message)

    async def send_error(self, websocket: WebSocket, message: str):
        """Error Message"""
        await websocket.send_json({
            "type": "error",
            "message": message
        })
    
    async def send_start(self, websocket: WebSocket, symbol: str, opponent_nickname: str):
        """Start Message"""
        await websocket.send_json({
            "type": "start",
            "symbol": symbol,
            "opponent_nickname": opponent_nickname
        })

    async def send_turn(self, websocket: WebSocket, value: bool):
        """Turn Message"""
        await websocket.send_json({
            "type": "turn",
            "value": value
        })

    async def send_move(self, websocket: WebSocket, move: str, symbol: str):
        """Move Message"""
        await websocket.send_json({
            "type": "move",
            "cell": move,
            "symbol": symbol
        })

    async def send_gameover(self, websocket: WebSocket, result: str):
        """Game Over Message"""
        await websocket.send_json({
            "type": "gameover",
            "result": result
        })

    def disconnect(self, websocket: WebSocket):
        """disconnect event"""
        self.active_connections.remove(websocket)

app = FastAPI()
manager = ConnectionManager()
waiting_players: queue.Queue[Player] = queue.Queue()
players: Dict[WebSocket, Player] = {}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data["type"] == "join":
                new_player: Player = Player(websocket, data["nickname"])
                #print(f"Player {new_player.nickname} joined")
                if not waiting_players.empty():
                    opponent: Player = waiting_players.get()
                    opponent.opponent = new_player
                    new_player.opponent = opponent

                    new_player.symbol = "X"
                    opponent.symbol = "O"

                    new_game_board = GameBoard()
                    new_player.game_board = new_game_board
                    opponent.game_board = new_game_board
                    
                    players[websocket] = new_player
                    players[opponent.websocket] = opponent

                    await manager.send_start(new_player.websocket, new_player.symbol, opponent.nickname)
                    await manager.send_start(opponent.websocket, opponent.symbol, new_player.nickname)
                    new_player.is_my_turn = True
                    await manager.send_turn(websocket, True)
                else:
                    waiting_players.put(new_player)
            elif data["type"] == "move":
                player: Optional[Player] = players.get(websocket)
                opponent: Optional[Player] = player.opponent
                game_board = player.game_board
                if player.is_my_turn is False:
                    await manager.send_error(websocket, "Not your turn")
                    continue
                try:
                    player.game_board.make_move(data["cell"], player.symbol)
                except InvalidMoveException:
                    await manager.send_error(websocket, "Invalid move")
                    continue

                await manager.send_move(player.websocket, data["cell"], player.symbol)
                await manager.send_move(opponent.websocket, data["cell"], player.symbol)

                winner = game_board.get_winner()
                #print(winner)
                if winner:
                    await manager.send_gameover(player.websocket, winner)
                    await manager.send_gameover(opponent.websocket, winner)
                    continue


                player.is_my_turn = False
                opponent.is_my_turn = True
                await manager.send_turn(player.websocket, player.is_my_turn)
                await manager.send_turn(opponent.websocket, opponent.is_my_turn)
            else:
                await manager.send_message(websocket, f"Unknown message type:{data['type']}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(e)
        manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)