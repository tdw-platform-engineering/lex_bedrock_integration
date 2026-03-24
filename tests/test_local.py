import json
from pathlib import Path
import sys
# load .env for testing
from dotenv import load_dotenv
dotenv_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import lambda_function


def main():
    event_path = ROOT / "test_event.json"
    event = json.loads(event_path.read_text(encoding="utf-8"))

    class Context:
        aws_request_id = "test-request-id"

    response = lambda_function.lambda_handler(event, Context())
    # print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
