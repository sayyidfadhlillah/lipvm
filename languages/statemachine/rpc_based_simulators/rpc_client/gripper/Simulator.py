from __future__ import annotations

import argparse
import json
import os
from typing import Any

from jsonrpclib import Server

from languages.statemachine.rpc_based_simulators.utility.env_utils import load_env_file


class SimulationJsonRpcClient:
    """Simple JSON-RPC client for the gripper simulator server."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5002) -> None:
        self._server = Server(f"http://{host}:{port}")

    def clear_boxes(self) -> dict[str, Any]:
        return self._server.clear_boxes()

    def has_pickup_boxes(self) -> bool:
        return self._server.has_pickup_boxes()

    def set_current_state_name(self, new_state_name: str) -> dict[str, Any]:
        return self._server.set_current_state_name(new_state_name)

    def spawn_box(self, weight: float, width: float = 0.9) -> dict[str, Any]:
        return self._server.spawn_box(float(weight), float(width))

    def grip_box(self) -> dict[str, Any]:
        return self._server.grip_box()

    def drop_box(self) -> dict[str, Any]:
        return self._server.drop_box()

    def release_box(self) -> dict[str, Any]:
        return self._server.release_box()

    def extend_arm(self) -> dict[str, Any]:
        return self._server.extend_arm()

    def retract_arm(self) -> dict[str, Any]:
        return self._server.retract_arm()

    def move_to_end(self) -> dict[str, Any]:
        return self._server.move_to_end()

    def move_to_start(self) -> dict[str, Any]:
        return self._server.move_to_start()

    def get_state(self) -> dict[str, Any]:
        return self._server.get_state()

    def invoke(self, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return getattr(self._server, "sim.invoke")(action, params or {})

    def get_state_namespaced(self) -> dict[str, Any]:
        return getattr(self._server, "sim.get_state")()


def _pretty_print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _default_port_from_env() -> int:
    port_raw = os.environ.get("GRIPPER_RPC_PORT", "5002")
    try:
        return int(port_raw)
    except ValueError as exc:
        raise SystemExit("GRIPPER_RPC_PORT must be an integer") from exc


def _parse_args() -> argparse.Namespace:
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--env-file", default=".env")
    pre_args, _ = pre_parser.parse_known_args()
    load_env_file(pre_args.env_file)

    parser = argparse.ArgumentParser(description="Simple JSON-RPC client for gripper simulator")
    parser.add_argument(
        "--env-file",
        default=pre_args.env_file,
        help="Environment file path to load before parsing other defaults (default: .env)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("GRIPPER_RPC_HOST", "127.0.0.1"),
        help="JSON-RPC host (default: GRIPPER_RPC_HOST or 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_default_port_from_env(),
        help="JSON-RPC port (default: GRIPPER_RPC_PORT or 5002)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("state", help="Call get_state")
    subparsers.add_parser("state-ns", help="Call sim.get_state")
    subparsers.add_parser("clear", help="Call clear_boxes")
    subparsers.add_parser("has-pickup", help="Call has_pickup_boxes")
    subparsers.add_parser("grip", help="Call grip_box")
    subparsers.add_parser("drop", help="Call drop_box")
    subparsers.add_parser("release", help="Call release_box")
    subparsers.add_parser("extend", help="Call extend_arm")
    subparsers.add_parser("retract", help="Call retract_arm")
    subparsers.add_parser("move-end", help="Call move_to_end")
    subparsers.add_parser("move-start", help="Call move_to_start")

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
    client = GripperJsonRpcClient(host=args.host, port=args.port)

    if args.command == "state":
        _pretty_print(client.get_state())
        return
    if args.command == "state-ns":
        _pretty_print(client.get_state_namespaced())
        return
    if args.command == "clear":
        _pretty_print(client.clear_boxes())
        return
    if args.command == "has-pickup":
        _pretty_print({"has_pickup_boxes": client.has_pickup_boxes()})
        return
    if args.command == "grip":
        _pretty_print(client.grip_box())
        return
    if args.command == "drop":
        _pretty_print(client.drop_box())
        return
    if args.command == "release":
        _pretty_print(client.release_box())
        return
    if args.command == "extend":
        _pretty_print(client.extend_arm())
        return
    if args.command == "retract":
        _pretty_print(client.retract_arm())
        return
    if args.command == "move-end":
        _pretty_print(client.move_to_end())
        return
    if args.command == "move-start":
        _pretty_print(client.move_to_start())
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
