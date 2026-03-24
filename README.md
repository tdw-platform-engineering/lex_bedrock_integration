# demo-lex-bedrock

Amazon Lex V2 fulfillment Lambda that routes conversations through an AI agent backend. Migrated from the original Node.js `lex-bedrock-agent-integration` project to Python.

## Architecture

```
Amazon Connect → Lex V2 Bot → This Lambda (fulfillment hook)
                                  │
                    ┌──────────────┼──────────────┐
                    ▼              ▼               ▼
              Bedrock Agent   AgentCore       EC2 HTTP Agent
                                  │
                                  ▼
                        Customer Profiles
                        (cotización update)
```

The Lambda supports three interchangeable agent backends, selected via the `AGENT_PROVIDER` environment variable:

| Provider | Class | Description |
|----------|-------|-------------|
| `bedrock` (default) | `BedrockAgentService` | Amazon Bedrock Agent via `invoke_agent` |
| `agentcore` | `AgentCoreService` | Bedrock AgentCore runtime endpoint |
| `ec2` | `Ec2AgentService` | HTTP POST to an agent running on EC2 |

## Agent Response Format

All agent backends return a structured response conforming to the `AgentResponse` model defined in `src/modules/models/agent_response.py`:

```json
{
  "sessionid": "a uuid identifying the conversation session",
  "txt": "the agent's textual reply",
  "end": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `sessionid` | `str` | UUID identifying the conversation session |
| `txt` | `str` | The agent's textual reply |
| `end` | `bool` | `true` if the conversation has ended, `false` otherwise |

## Project Structure

```
demo-lex-bedrock/
├── Dockerfile                          # Multi-stage build (Python 3.14-rc + uv + RIE)
├── requirements.txt                    # Python dependencies
├── .env.example                        # Environment variable template
├── test_event.json                     # Sample Lex V2 event for testing
├── README.md
├── deployment/
│   └── deploy.sh                       # ECR build/push + Lambda update
├── iam/
│   ├── policy.json                     # IAM policy with placeholders
│   └── README.md
├── src/
│   ├── lambda_function.py              # Entry point: lambda_handler(event, context)
│   └── modules/
│       ├── handlers/
│       │   └── lex_handler.py          # Lex event parser + response formatter
│       ├── models/
│       │   └── agent_response.py       # AgentResponse dataclass
│       ├── services/
│       │   ├── base_agent.py           # ABC + factory function
│       │   ├── bedrock_agent.py        # Bedrock Agent Runtime client
│       │   ├── agentcore_agent.py      # Bedrock AgentCore client
│       │   ├── ec2_agent.py            # HTTP agent client
│       │   └── customer_profiles.py    # Connect Customer Profiles client
│       ├── utils/
│       │   └── config.py               # Centralized env var configuration
│       └── logger/
│           └── main.py                 # JSON-formatted logging
└── tests/
    ├── conftest.py
    ├── test_lambda_function.py
    └── test_lex_handler.py
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AGENT_PROVIDER` | No | `bedrock` | Agent backend: `bedrock`, `agentcore`, or `ec2` |
| `AWS_REGION` | No | `us-east-1` | AWS region for Bedrock and Customer Profiles |
| `BEDROCK_AGENT_ID` | If bedrock | — | 10-char alphanumeric Bedrock agent ID |
| `BEDROCK_AGENT_ALIAS_ID` | If bedrock | — | 10-char alias ID or `TSTALIASID` |
| `AGENTCORE_RUNTIME_ARN` | If agentcore | — | AgentCore runtime ARN |
| `AGENTCORE_REGION` | No | `us-west-2` | AgentCore region |
| `AGENTCORE_TIMEOUT_MS` | No | `120000` | AgentCore request timeout (ms) |
| `AGENT_HTTP_URL` | No | `http://3.234.208.1:8081/chat` | EC2 agent endpoint |
| `AGENT_HTTP_TIMEOUT_MS` | No | `20000` | EC2 agent request timeout (ms) |
| `CONNECT_DOMAIN_NAME` | No | — | Customer Profiles domain name |
| `SUMMARY_FIELD` | No | `AdditionalInformation` | Customer Profile field to update |
| `CALL_TRANSCRIPT_LOGGING_TABLE` | No | `connect_outbound_call_transcript` | DynamoDB table used to store USER/BOT turn transcripts |

## Transcript Logging

For each processed turn, the Lambda writes two records into `CALL_TRANSCRIPT_LOGGING_TABLE`:

- `type=USER`, `message=<user_input sent to agent>`
- `type=BOT`, `message=<agent response text>`

Both records share the same partition key and use sort keys in the format `TIMESTAMP#<unix>`.

## Local Development

```bash
cd lambda/demo-lex-bedrock
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real values
```

## Testing

```bash
cd lambda/demo-lex-bedrock
python -m pytest tests/ -v
```

## Deployment

```bash
# Build and push to ECR
./deployment/deploy.sh --tag latest

# Build, push, and update Lambda function
./deployment/deploy.sh --function-name demo-lex-bedrock --tag latest
```

## Migrated From

Original JavaScript project: `lex-bedrock-agent-integration/`

### What changed

- **Language**: Node.js (ES modules) → Python 3.14
- **AWS SDK**: `@aws-sdk/client-*` v3 → `boto3`
- **HTTP client**: `fetch()` → `requests`
- **Agent pattern**: Switch statement → ABC base class + factory function
- **Removed**: `DatabaseService` and `QueryBuilder` (dead code, not used by handler)
- **Dockerfile**: Node.js Lambda base → Python 3.14-rc slim + Lambda RIE (matches `connect_trigger` pattern)
