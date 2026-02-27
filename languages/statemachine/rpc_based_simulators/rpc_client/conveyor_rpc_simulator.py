from __future__ import annotations

import argparse
import json
import os
from typing import Any

from jsonrpclib import Server

from languages.statemachine.rpc_based_simulators.utility.env_utils import load_env_file


class ConveyorJsonRpcClient:
    """Simple JSON-RPC client for the conveyor simulator server."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5001) -> None:
        self._server = Server(f"http://{host}:{port}")

    def clear_boxes(self) -> dict[str, Any]:
        return self._server.clear_boxes()

    def advance_boxes(self, base_speed: float | None = None) -> dict[str, Any]:
        if base_speed is None:
            return self._server.advance_boxes()
        return self._server.advance_boxes(base_speed)

    def has_any_collision(self) -> bool:
        return self._server.has_any_collision()

    def set_current_state_name(self, new_state_name: str) -> dict[str, Any]:
        return self._server.set_current_state_name(new_state_name)

    def spawn_box(self, weight: float, width: float = 0.9) -> dict[str, Any]:
        return self._server.spawn_box(float(weight), float(width))

    def get_state(self) -> dict[str, Any]:
        return self._server.get_state()

    def invoke(self, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return getattr(self._server, "sim.invoke")(action, params or {})

    def get_state_namespaced(self) -> dict[str, Any]:
        return getattr(self._server, "sim.get_state")()


def _pretty_print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _default_port_from_env() -> int:
    port_raw = os.environ.get("CONVEYOR_RPC_PORT", "5001")
    try:
        return int(port_raw)
    except ValueError as exc:
        raise SystemExit("CONVEYOR_RPC_PORT must be an integer") from exc


def _parse_args() -> argparse.Namespace:
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--env-file", default=".env")
    pre_args, _ = pre_parser.parse_known_args()
    load_env_file(pre_args.env_file)

    parser = argparse.ArgumentParser(description="Simple JSON-RPC client for conveyor simulator")
    parser.add_argument(
        "--env-file",
        default=pre_args.env_file,
        help="Environment file path to load before parsing other defaults (default: .env)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("CONVEYOR_RPC_HOST", "127.0.0.1"),
        help="JSON-RPC host (default: CONVEYOR_RPC_HOST or 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_default_port_from_env(),
        help="JSON-RPC port (default: CONVEYOR_RPC_PORT or 5001)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("state", help="Call get_state")
    subparsers.add_parser("state-ns", help="Call sim.get_state")
    subparsers.add_parser("clear", help="Call clear_boxes")
    subparsers.add_parser("collision", help="Call has_any_collision")

    advance_parser = subparsers.add_parser("advance", help="Call advance_boxes")
    advance_parser.add_argument("--base-speed", type=float, default=None, help="Optional speed override")

    spawn_parser = subparsers.add_parser("spawn", help="Call spawn_box")
    spawn_parser.add_argument("--weight", type=float, required=True, help="Box weight")
    spawn_parser.add_argument("--width", type=float, default=0.9, help="Box width")

    set_state_parser = subparsers.add_parser("set-state", help="Call set_current_state_name")
    set_state_parser.add_argument("--name", required=True, help="New state name")

    invoke_parser = subparsers.add_parser("invoke", help="Call sim.invoke")
    invoke_parser.add_argument("--action", required=True, help="Action name, e.g. spawn_box")
    invoke_parser.add_argument(
        "--params",
        default="{}",
        help='Action params as JSON object string, e.g. \'{"weight": 5, "width": 1.0}\'',
    )

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    client = ConveyorJsonRpcClient(host=args.host, port=args.port)

    if args.command == "state":
        _pretty_print(client.get_state())
        return
    if args.command == "state-ns":
        _pretty_print(client.get_state_namespaced())
        return
    if args.command == "clear":
        _pretty_print(client.clear_boxes())
        return
    if args.command == "collision":
        _pretty_print({"has_any_collision": client.has_any_collision()})
        return
    if args.command == "advance":
        _pretty_print(client.advance_boxes(args.base_speed))
        return
    if args.command == "spawn":
        _pretty_print(client.spawn_box(args.weight, args.width))
        return
    if args.command == "set-state":
        _pretty_print(client.set_current_state_name(args.name))
        return
    if args.command == "invoke":
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--params must be valid JSON: {exc}") from exc
        if not isinstance(params, dict):
            raise SystemExit("--params JSON must be an object")
        _pretty_print(client.invoke(args.action, params))
        return

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
