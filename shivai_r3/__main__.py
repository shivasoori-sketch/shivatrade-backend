"""Print the three closed-session snapshots as JSON. No network."""
import json

from shivai_r3.snapshot import build_closed_snapshots, to_plain


def main() -> None:
    payload = [to_plain(snapshot) for snapshot in build_closed_snapshots()]
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
